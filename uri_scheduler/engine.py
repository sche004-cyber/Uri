"""The scheduler engine.

Lifecycle of a job:   propose (PROPOSED, interpreted schedule + preview shown to the owner)
                      -> confirm(proposal_sha256) by the owner (ACTIVE)  <-> pause/resume  -> cancel (CANCELLED)
Lifecycle of an occurrence:
  SCHEDULED --due--> RUNNING --artifact ok--> AWAITING_REVIEW --approve--> APPROVED
                        |                         |  refine/regenerate --> REVISION_QUEUED --> RUNNING --> AWAITING_REVIEW
                        |                         '-- reject --> REJECTED
                        |-- harness unavailable --> BLOCKED_HARNESS (re-checked at retry_at; owner may retry/reschedule)
                        |-- quota exhausted ------> QUOTA_DEFERRED  (retry at provider reset; never another provider)
                        |-- failure (budget left) -> SCHEDULED (retry_at, backoff)
                        |-- failure (no budget) --> FAILED
                        |-- outcome uncertain ----> NEEDS_ATTENTION (owner decides; never auto-retried)
                        '-- process died ---------> (restart) INTERRUPTED -> SCHEDULED (context kept) or FAILED
  SCHEDULED past its deadline (festival day started) -> MISSED;  past due by more than the grace -> run late, flagged
  any non-terminal --cancel--> CANCELLED;  calendar withdrew the event -> CANCELLED (CALENDAR_WITHDRAWN)

Invariants
  * one occurrence per (job, occurrence_key): UNIQUE constraint; calendar refreshes MOVE occurrences, never add twins
  * claim is a compare-and-set inside BEGIN IMMEDIATE; one scheduler process per state dir (OS file lock)
  * one harness attempt = one supervisor task with a deterministic id (uuid5 of occurrence + attempt number)
  * every mutation by a principal is checked against the job owner; approval is bound to the artifact's sha256 and
    the bytes on disk are re-hashed at decision time
  * nothing is ever published, posted or sent: there is no such capability in this package
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import DEFAULT_TZ, gif_task, timespec
from .calendar_store import CORRECTION_ACTIONS, Calendar, CalendarError, apply_corrections
from .store import Store, jdump

try:
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None

ACTIVE_STATES = ("SCHEDULED", "RUNNING", "REVISION_QUEUED", "BLOCKED_HARNESS", "QUOTA_DEFERRED", "COLLECT_PENDING")
# Open states an owner can cancel (everything that is not terminal).
OPEN_STATES = ("SCHEDULED", "REVISION_QUEUED", "BLOCKED_HARNESS", "QUOTA_DEFERRED", "RUNNING", "AWAITING_REVIEW",
               "AWAITING_CONFIRMATION", "NEEDS_ATTENTION", "COLLECT_PENDING")
SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TERMINAL_STATES = ("APPROVED", "REJECTED", "FAILED", "MISSED", "CANCELLED", "SKIPPED")
DEFAULT_AUTHORITY = {"harness": "claude_code", "tools": ["Read", "Edit", "Write", "Glob", "Grep"], "network": False,
                     "publish": False, "paid_services": False, "writes": "attempt_workspace_only"}
ALLOWED_TOOLS = {"Read", "Edit", "Write", "Glob", "Grep"}
DEFAULT_POLICY = {"missed": "run_late", "grace_s": 600, "max_attempts": 3, "retry_backoff_s": [300, 1800],
                  "harness_recheck_s": 1800, "quota_default_wait_s": 3600, "execution_time": "09:00"}
TEMPLATES = {gif_task.TEMPLATE_ID: gif_task}


class SchedulerError(Exception):
    def __init__(self, code, detail=None):
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code, self.detail = code, detail


class SchedulerAlreadyRunning(SchedulerError):
    pass


def _iso(us):
    return None if us is None else datetime.fromtimestamp(us / 1e6, tz=timezone.utc).isoformat(timespec="seconds")


def _local(us, tz):
    return None if us is None else datetime.fromtimestamp(us / 1e6, tz=timezone.utc).astimezone(timespec.zone(tz)).isoformat(timespec="minutes")


def _us(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000)


def _dt(us: int) -> datetime:
    return datetime.fromtimestamp(us / 1e6, tz=timezone.utc)


class Scheduler:
    def __init__(self, state_dir, *, harness=None, calendar: Calendar | None = None, now_fn=None, lock=True,
                 notify=None):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.calendar = calendar or Calendar.default()
        # Shipped calendars as loaded; owner corrections are re-applied on top of these, never written into them.
        self._calendar_base = {cid: json.loads(json.dumps(d)) for cid, d in self.calendar._data.items()}
        self.harness = harness
        self.now_fn = now_fn
        self.notify = notify or (lambda kind, payload: None)
        self._lock_fh = None
        self._mutex = threading.RLock()
        if lock:
            self._acquire_lock()
        self.store = Store(self.state_dir / "scheduler.db", now_fn=now_fn)
        self.instance_id = uuid.uuid4().hex
        self.startup = {}

    # ---- process lifecycle ----------------------------------------------------------------------------------------
    def _acquire_lock(self):
        path = self.state_dir / "scheduler.lock"
        fh = open(path, "a+b")
        try:
            fh.seek(0)
            if msvcrt is not None:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise SchedulerAlreadyRunning("SCHEDULER_ALREADY_RUNNING", str(path)) from None
        self._lock_fh = fh

    def start(self):
        if self.harness is not None and getattr(self.harness, "sup", None) is None:
            self.harness.open()
        skipped = self._apply_stored_corrections()
        self.startup = self.recover()
        if skipped:
            self.startup["calendar_corrections_not_applied"] = skipped
        self._snapshot_calendars()
        return self

    def close(self):
        if self.harness is not None:
            self.harness.close()
        self.store.close()
        if self._lock_fh is not None:
            with contextlib.suppress(OSError):
                if msvcrt is not None:
                    self._lock_fh.seek(0)
                    msvcrt.locking(self._lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
            self._lock_fh.close()
            self._lock_fh = None

    def now(self) -> int:
        return self.store.now()

    # ---- helpers --------------------------------------------------------------------------------------------------
    def job(self, job_id) -> dict:
        r = self.store.q1("SELECT * FROM job WHERE job_id=?", (job_id,))
        if r is None:
            raise SchedulerError("UNKNOWN_JOB", job_id)
        d = dict(r)
        for k in ("params", "schedule", "authority", "policy", "proposed_dates", "confirmed_dates"):
            d[k] = json.loads(d.pop(k + "_json"))
        return d

    def occurrence(self, occ_id) -> dict:
        r = self.store.q1("SELECT * FROM occurrence WHERE occ_id=?", (occ_id,))
        if r is None:
            raise SchedulerError("UNKNOWN_OCCURRENCE", occ_id)
        d = dict(r)
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
        d["request"] = json.loads(d.pop("request_json")) if d.get("request_json") else None
        return d

    def _owner_check(self, job, principal):
        if not principal or principal != job["owner"]:
            raise SchedulerError("NOT_OWNER", f"{principal} is not the owner of job {job['job_id']}")

    def _set_occ(self, db, occ_id, state, reason=None, **cols):
        # Single choke point for every occurrence transition (review round 5, F1): once the owner has recorded a
        # cancellation on a running occurrence, any settlement (blocked gate, error, retry, completion) ends CANCELLED
        # in the same transaction, so cancelled work can never be re-queued or offered for review.
        cur = db.execute("SELECT state, reason FROM occurrence WHERE occ_id=?", (occ_id,)).fetchone()
        if (cur is not None and cur["state"] == "RUNNING" and cur["reason"] == "CANCEL_REQUESTED"
                and state not in ("RUNNING", "CANCELLED")):
            state, reason = "CANCELLED", "CANCELLED_BY_OWNER"
            cols = {k: v for k, v in cols.items() if k in ("lease_owner", "lease_until_us")}
            cols["retry_at_us"] = None
        sets = ["state=?", "reason=?", "updated_at_us=?"]
        args = [state, reason, self.now()]
        for k, v in cols.items():
            sets.append(f"{k}=?")
            args.append(v)
        args.append(occ_id)
        db.execute(f"UPDATE occurrence SET {', '.join(sets)} WHERE occ_id=?", args)

    def _snapshot_calendars(self):
        with self.store.tx() as db:
            for cid in list(self.calendar._data):
                dig = self.calendar.digest(cid)
                cur = db.execute("INSERT OR IGNORE INTO calendar_snapshot(calendar_id,version,digest,data_json,recorded_at_us) "
                                 "VALUES (?,?,?,?,?)", (cid, self.calendar.version(cid), dig, jdump(self.calendar.raw(cid)), self.now()))
                if cur.rowcount:
                    self.store.emit(db, "calendar.loaded", payload={"calendar_id": cid, "version": self.calendar.version(cid),
                                                                    "digest": dig})

    # ---- proposal / activation -------------------------------------------------------------------------------------
    def propose(self, *, owner, title, template_id, params, schedule, authority=None, policy=None, preview_days=400) -> dict:
        if template_id not in TEMPLATES:
            raise SchedulerError("UNKNOWN_TEMPLATE", template_id)
        sched = timespec.validate(schedule)
        auth = dict(DEFAULT_AUTHORITY | (authority or {}))
        self._validate_authority(auth)
        pol = self._validate_policy(policy)
        if sched["kind"] == "calendar_relative":
            self._validate_selection(sched)
        self._validate_params(params)
        job_id = "job_" + uuid.uuid4().hex[:12]
        proposal = self._proposal(job_id, owner, title, template_id, params, sched, auth, pol, preview_days)
        now = self.now()
        with self.store.tx() as db:
            shown = {r["key"]: r.get("festival_date") for r in proposal["upcoming"]}
            db.execute("INSERT INTO job(job_id,owner,title,template_id,params_json,schedule_json,timezone,authority_json,"
                       "policy_json,state,proposal_sha256,proposed_dates_json,created_at_us,updated_at_us) "
                       "VALUES (?,?,?,?,?,?,?,?,?,'PROPOSED',?,?,?,?)",
                       (job_id, owner, title, template_id, jdump(params), jdump(sched), sched["tz"], jdump(auth), jdump(pol),
                        proposal["proposal_sha256"], jdump(shown), now, now))
            self.store.emit(db, "job.proposed", job_id=job_id, payload={"owner": owner, "proposal_sha256": proposal["proposal_sha256"],
                                                                        "interpretation": proposal["interpretation"]})
        return proposal

    def _validate_authority(self, auth):
        if auth.get("harness") != "claude_code":
            raise SchedulerError("HARNESS_NOT_AUTHORIZED", auth.get("harness"))
        if not set(auth.get("tools", [])) <= ALLOWED_TOOLS:
            raise SchedulerError("TOOLS_EXCEED_EXECUTOR_PROFILE", sorted(set(auth["tools"]) - ALLOWED_TOOLS))
        for flag in ("publish", "paid_services", "network"):
            if auth.get(flag):
                raise SchedulerError("AUTHORITY_REQUIRES_OWNER_DECISION", flag)

    @staticmethod
    def _validate_policy(policy) -> dict:
        """Every policy value is bounded so retry budgets and backoffs are finite and well-formed (review round 4, F1)."""
        if policy is not None and not isinstance(policy, dict):
            raise SchedulerError("BAD_POLICY", "policy must be an object")
        unknown = set(policy or {}) - set(DEFAULT_POLICY)
        if unknown:
            raise SchedulerError("BAD_POLICY", sorted(unknown))
        pol = dict(DEFAULT_POLICY | (policy or {}))

        def int_in(k, lo, hi):
            v = pol[k]
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                raise SchedulerError("BAD_POLICY", f"{k} must be an integer in [{lo}, {hi}]")
        if pol["missed"] not in ("run_late", "skip"):
            raise SchedulerError("BAD_POLICY", "missed")
        int_in("grace_s", 0, 86400)
        int_in("max_attempts", 1, 10)
        int_in("harness_recheck_s", 60, 86400)
        int_in("quota_default_wait_s", 60, 86400)
        b = pol["retry_backoff_s"]
        if (not isinstance(b, list) or not 1 <= len(b) <= 5
                or any(not isinstance(x, int) or isinstance(x, bool) or not 1 <= x <= 86400 for x in b)):
            raise SchedulerError("BAD_POLICY", "retry_backoff_s must be 1-5 integers in [1, 86400]")
        try:
            timespec._parse_time(pol["execution_time"])
        except timespec.ScheduleError:
            raise SchedulerError("BAD_POLICY", "execution_time") from None
        return pol

    @staticmethod
    def _backoff_s(pol, attempts) -> int:
        """Backoff for the n-th attempt; falls back to 300 s for a malformed stored policy instead of raising."""
        b = pol.get("retry_backoff_s") if isinstance(pol, dict) else None
        if not isinstance(b, list) or not b or not all(isinstance(x, int) and x > 0 for x in b):
            return 300
        return b[min(max(int(attempts), 1) - 1, len(b) - 1)]

    @staticmethod
    def _validate_params(params):
        """Template parameters are data that reach file names and prompts: shape-checked, never trusted."""
        if not isinstance(params, dict):
            raise SchedulerError("BAD_PARAMS", "params must be an object")
        if set(params) - {"festival", "style", "audience"}:
            raise SchedulerError("BAD_PARAMS", sorted(set(params) - {"festival", "style", "audience"}))
        for k in ("style", "audience"):
            if k in params and (not isinstance(params[k], str) or len(params[k]) > 300):
                raise SchedulerError("BAD_PARAMS", k)
        f = params.get("festival")
        if f is not None:
            if not isinstance(f, dict) or not SLUG.match(str(f.get("key", ""))):
                raise SchedulerError("BAD_PARAMS", "festival.key must match [a-z][a-z0-9_]*")
            if not isinstance(f.get("name", ""), str) or len(f.get("name", "")) > 80:
                raise SchedulerError("BAD_PARAMS", "festival.name")
            if f.get("date") is not None:
                try:
                    datetime.fromisoformat(str(f["date"]))
                except ValueError:
                    raise SchedulerError("BAD_PARAMS", "festival.date") from None

    def _validate_selection(self, sched):
        known = {f["festival_key"]: f for f in self.calendar.festivals(sched["calendar"])}
        bad = [k for k in sched["selection"] if k not in known]
        if bad:
            raise SchedulerError("UNKNOWN_FESTIVAL", bad)
        solemn = [k for k in sched["selection"] if not known[k]["greeting_appropriate"]]
        if solemn:
            raise SchedulerError("NOT_A_GREETING_OCCASION", solemn)

    def _proposal(self, job_id, owner, title, template_id, params, sched, auth, pol, preview_days):
        now = _dt(self.now())
        occs = timespec.expand(sched, now, now + timedelta(days=preview_days), self.calendar)
        rows = [{"key": o.key, "due_local": _local(_us(o.due_utc), sched["tz"]), "due_utc": o.due_utc.isoformat(timespec="seconds"),
                 **{k: o.meta.get(k) for k in ("festival", "festival_date", "calendar_record", "calendar_version") if k in o.meta}}
                for o in occs]
        excluded = []
        if sched["kind"] == "calendar_relative":
            for ev in self.calendar.all_events(sched["calendar"], include_unschedulable=True):
                if ev.festival_key in sched["selection"] and ev.status != "published":
                    excluded.append({"festival_key": ev.festival_key, "date": ev.start.isoformat(), "status": ev.status,
                                     "why": "record not confirmed; never scheduled until the owner confirms it"})
            for r in rows:
                rec = r.get("calendar_record", "")
                src = None
                for ev in self.calendar.events(sched["calendar"], sched["selection"]):
                    if ev.record_id == rec:
                        src = self.calendar.source(sched["calendar"], ev.source_id)
                r["source"] = {"id": src["id"], "title": src["title"], "verification": src["verification"]} if src else None
        body = {"job_id": job_id, "owner": owner, "title": title, "template_id": template_id, "params": params,
                "schedule": sched, "interpretation": timespec.describe(sched), "authority": auth, "policy": pol,
                "upcoming": rows, "excluded": excluded,
                "notes": ["No result is ever posted, emailed or published; every result waits for your review.",
                          "Claude runs under the URI client profile; if it is unavailable the task waits and is shown as "
                          "blocked, and no other or paid provider is used."]}
        body["proposal_sha256"] = hashlib.sha256(jdump(body).encode()).hexdigest()
        return body

    def confirm(self, job_id, principal, proposal_sha256) -> dict:
        with self._mutex:
            job = self.job(job_id)
            self._owner_check(job, principal)
            if job["state"] != "PROPOSED":
                raise SchedulerError("NOT_PROPOSED", job["state"])
            if proposal_sha256 != job["proposal_sha256"]:
                raise SchedulerError("PROPOSAL_MISMATCH", "confirmation does not match the proposal that was shown")
            now = self.now()
            with self.store.tx() as db:
                db.execute("UPDATE job SET state='ACTIVE', confirmed_by=?, confirmed_at_us=?, updated_at_us=?, "
                           "confirmed_dates_json=proposed_dates_json WHERE job_id=? AND state='PROPOSED'", (principal, now, now, job_id))
                self.store.emit(db, "job.activated", job_id=job_id, payload={"by": principal, "proposal_sha256": proposal_sha256})
            self.materialize(job_id)
            return self.job(job_id)

    def pause(self, job_id, principal):
        return self._job_state(job_id, principal, ("ACTIVE",), "PAUSED", "job.paused")

    def resume(self, job_id, principal):
        r = self._job_state(job_id, principal, ("PAUSED",), "ACTIVE", "job.resumed")
        self.materialize(job_id)
        return r

    def cancel_job(self, job_id, principal):
        with self._mutex:
            r = self._job_state(job_id, principal, ("PROPOSED", "ACTIVE", "PAUSED"), "CANCELLED", "job.cancelled")
            marks = ",".join("?" * len(OPEN_STATES))
            for occ in self.store.q(f"SELECT occ_id FROM occurrence WHERE job_id=? AND state IN ({marks})", (job_id, *OPEN_STATES)):
                self.cancel_occurrence(occ[0], principal, _job_cancel=True)
            return r

    def _job_state(self, job_id, principal, frm, to, kind):
        with self._mutex:
            job = self.job(job_id)
            self._owner_check(job, principal)
            if job["state"] not in frm:
                raise SchedulerError("BAD_JOB_STATE", job["state"])
            with self.store.tx() as db:
                db.execute("UPDATE job SET state=?, updated_at_us=? WHERE job_id=?", (to, self.now(), job_id))
                self.store.emit(db, kind, job_id=job_id, payload={"by": principal, "from": job["state"]})
            return self.job(job_id)

    # ---- materialization ------------------------------------------------------------------------------------------
    def materialize(self, job_id=None) -> dict:
        report = {"inserted": 0, "moved": 0, "withdrawn": 0, "restored": 0}
        jobs = [self.job(job_id)] if job_id else [self.job(r[0]) for r in self.store.q("SELECT job_id FROM job WHERE state='ACTIVE'")]
        for job in jobs:
            if job["state"] != "ACTIVE":
                continue
            sched = job["schedule"]
            now = _dt(self.now())
            start = max(_dt(job["confirmed_at_us"] or job["created_at_us"]) - timedelta(minutes=1), now - timedelta(days=7))
            horizon = {"hourly": 2, "daily": 60}.get(sched.get("freq"), 400)
            if sched["kind"] == "once":
                start = _dt(job["created_at_us"]) - timedelta(days=3650)
            occs = timespec.expand(sched, start, now + timedelta(days=horizon), self.calendar)
            keys = {o.key for o in occs}
            with self.store.tx() as db:
                for o in occs:
                    row = db.execute("SELECT occ_id,state,reason,due_at_us,meta_json FROM occurrence WHERE job_id=? AND occurrence_key=?",
                                     (job["job_id"], o.key)).fetchone()
                    due, dl = _us(o.due_utc), (_us(o.deadline_utc) if o.deadline_utc else None)
                    confirmed = (sched["kind"] != "calendar_relative"
                                 or job["confirmed_dates"].get(o.key) == o.meta.get("festival_date"))
                    if row is None:
                        st0 = "SCHEDULED" if confirmed else "AWAITING_CONFIRMATION"
                        why = None if confirmed else ("DATE_CHANGED_SINCE_CONFIRMATION" if o.key in job["confirmed_dates"]
                                                      else "NOT_IN_CONFIRMED_PROPOSAL")
                        cur = db.execute("INSERT INTO occurrence(job_id,occurrence_key,due_at_us,deadline_us,state,reason,meta_json,"
                                         "created_at_us,updated_at_us) VALUES (?,?,?,?,?,?,?,?,?)",
                                         (job["job_id"], o.key, due, dl, st0, why, jdump(o.meta), self.now(), self.now()))
                        self.store.emit(db, "occurrence.scheduled" if confirmed else "occurrence.awaiting_confirmation",
                                        job_id=job["job_id"], occ_id=cur.lastrowid,
                                        payload={"key": o.key, "due_utc": _iso(due), "due_local": _local(due, sched["tz"]),
                                                 "festival_date": o.meta.get("festival_date"), "reason": why})
                        report["inserted"] += 1
                    elif row["state"] == "CANCELLED" and row["reason"] == "CALENDAR_WITHDRAWN":
                        # The calendar withdrew this date earlier (e.g. the owner disputed it) and lists it again: it comes
                        # back only as a date for the owner to confirm, never straight to SCHEDULED.
                        db.execute("UPDATE occurrence SET due_at_us=?, deadline_us=?, meta_json=?, state='AWAITING_CONFIRMATION', "
                                   "reason='RESTORED_BY_CALENDAR', retry_at_us=NULL, updated_at_us=? WHERE occ_id=?",
                                   (due, dl, jdump(o.meta), self.now(), row["occ_id"]))
                        self.store.emit(db, "occurrence.restored_by_calendar", job_id=job["job_id"], occ_id=row["occ_id"],
                                        payload={"key": o.key, "due_utc": _iso(due), "festival_date": o.meta.get("festival_date")})
                        report["restored"] += 1
                    elif row["due_at_us"] != due and json.loads(row["meta_json"] or "{}").get("owner_due_local"):
                        pass       # the owner rescheduled this occurrence explicitly: the calendar never overrides that
                    elif row["due_at_us"] != due and row["state"] in ("SCHEDULED", "BLOCKED_HARNESS", "QUOTA_DEFERRED",
                                                                       "AWAITING_CONFIRMATION"):
                        # A moved date is a new date: it runs only after the owner confirms it (or it moved back).
                        st1 = "SCHEDULED" if confirmed else "AWAITING_CONFIRMATION"
                        db.execute("UPDATE occurrence SET due_at_us=?, deadline_us=?, meta_json=?, state=?, reason=?, retry_at_us=NULL, "
                                   "updated_at_us=? WHERE occ_id=?", (due, dl, jdump(o.meta), st1,
                                   None if confirmed else "DATE_CHANGED_SINCE_CONFIRMATION", self.now(), row["occ_id"]))
                        self.store.emit(db, "occurrence.moved_by_calendar", job_id=job["job_id"], occ_id=row["occ_id"],
                                        payload={"key": o.key, "from_utc": _iso(row["due_at_us"]), "to_utc": _iso(due),
                                                 "calendar_version": o.meta.get("calendar_version")})
                        report["moved"] += 1
                if sched["kind"] == "calendar_relative":
                    valid = {f"{e.festival_key}:{e.start.year}" for e in self.calendar.events(sched["calendar"], sched["selection"])}
                    for row in db.execute("SELECT occ_id, occurrence_key FROM occurrence WHERE job_id=? AND state IN "
                                          "('SCHEDULED','BLOCKED_HARNESS','QUOTA_DEFERRED','AWAITING_CONFIRMATION')",
                                          (job["job_id"],)).fetchall():
                        if row["occurrence_key"] not in valid:
                            self._set_occ(db, row["occ_id"], "CANCELLED", "CALENDAR_WITHDRAWN")
                            self.store.emit(db, "occurrence.withdrawn_by_calendar", job_id=job["job_id"], occ_id=row["occ_id"],
                                            payload={"key": row["occurrence_key"]})
                            report["withdrawn"] += 1
            del keys
        return report

    def refresh_calendar(self, data: dict) -> dict:
        """Load a new version of a calendar, record the diff, and reconcile every active job against it."""
        from .calendar_store import diff, validate_calendar
        validate_calendar(data)
        cid = data["calendar_id"]
        old = self.calendar.raw(cid) if cid in self.calendar._data else {"festivals": []}
        d = diff(old, data)
        self.calendar.put(data)
        self._snapshot_calendars()
        with self.store.tx() as db:
            self.store.emit(db, "calendar.refreshed", payload={"calendar_id": cid, "version": data["version"],
                                                               "diff": {k: [list(x) for x in v] for k, v in d.items()}})
        return {"diff": d, "reconcile": self.materialize()}

    # ---- owner calendar corrections -------------------------------------------------------------------------------
    def _corrections(self, calendar_id) -> list:
        return [dict(r) for r in self.store.q("SELECT * FROM calendar_correction WHERE calendar_id=? ORDER BY correction_id",
                                              (calendar_id,))]

    def _applicable(self, calendar_id):
        """Recorded corrections that still apply to the shipped calendar, in order, and the ones that do not. A correction
        that no longer applies (e.g. a later shipped calendar dropped the festival) is skipped and reported; it stays in
        the append-only record and never blocks later corrections (review round 9, C1-02)."""
        base, ok, skipped = self._calendar_base[calendar_id], [], []
        for c in self._corrections(calendar_id):
            try:
                apply_corrections(base, ok + [c])
                ok.append(c)
            except CalendarError as exc:
                skipped.append({"correction_id": c["correction_id"], "error": str(exc)})
        return ok, skipped

    def _apply_stored_corrections(self) -> list:
        skipped = []
        for cid, base in self._calendar_base.items():
            ok, sk = self._applicable(cid)
            skipped += sk
            if ok:
                self.calendar.put(apply_corrections(base, ok))
        return skipped

    def correct_calendar(self, principal, calendar_id, festival_key, year, action, *, start=None, end=None, note="") -> dict:
        """Owner review of the festival calendar: correct a date, mark a record disputed, or accept it.

        The correction is append-only, hash-chain-audited and re-applied on every start. It changes no scheduled work by
        itself: a moved date of an active job waits for the owner's confirmation of that occurrence, a disputed date is
        withdrawn, and an accepted date that was withdrawn comes back as awaiting confirmation."""
        if not principal:
            raise SchedulerError("NOT_OWNER", "a correction needs a principal")
        if action not in CORRECTION_ACTIONS:
            raise SchedulerError("BAD_ACTION", action)
        if calendar_id not in self._calendar_base:
            raise SchedulerError("UNKNOWN_CALENDAR", calendar_id)
        note = str(note or "")[:500]
        with self._mutex:
            row = {"calendar_id": calendar_id, "festival_key": festival_key, "year": int(year), "action": action,
                   "start": start, "end": end, "note": note, "principal": principal}
            corr, _ = self._applicable(calendar_id)
            try:
                data = apply_corrections(self._calendar_base[calendar_id], corr + [row])
            except (CalendarError, ValueError, TypeError) as exc:
                raise SchedulerError("BAD_CORRECTION", str(exc)) from None
            with self.store.tx() as db:
                cur = db.execute('INSERT INTO calendar_correction(calendar_id,festival_key,year,action,start,"end",note,principal,'
                                 "base_version,at_us) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                 (calendar_id, festival_key, int(year), action, start, end, note, principal,
                                  self._calendar_base[calendar_id]["version"], self.now()))
                self.store.emit(db, "calendar.corrected", payload=dict(row, correction_id=cur.lastrowid))
            ok, skipped = self._applicable(calendar_id)
            data = apply_corrections(self._calendar_base[calendar_id], ok)
            return {"version": data["version"], "not_applied": skipped, **self.refresh_calendar(data)}

    # ---- occurrence control ---------------------------------------------------------------------------------------
    def cancel_occurrence(self, occ_id, principal, _job_cancel=False):
        with self._mutex:
            occ = self.occurrence(occ_id)
            self._owner_check(self.job(occ["job_id"]), principal)
            if occ["state"] in TERMINAL_STATES:
                raise SchedulerError("ALREADY_FINAL", occ["state"])
            with self.store.tx() as db:
                if occ["state"] == "RUNNING":
                    self._set_occ(db, occ_id, "RUNNING", "CANCEL_REQUESTED")
                else:
                    self._set_occ(db, occ_id, "CANCELLED", "JOB_CANCELLED" if _job_cancel else "CANCELLED_BY_OWNER")
                self.store.emit(db, "occurrence.cancel", job_id=occ["job_id"], occ_id=occ_id,
                                payload={"by": principal, "was": occ["state"]})
            if occ["state"] == "RUNNING" and self.harness is not None:
                att = self.store.q1("SELECT supervisor_task_id FROM attempt WHERE occ_id=? AND ended_at_us IS NULL ORDER BY "
                                    "attempt_id DESC LIMIT 1", (occ_id,))
                if att and att[0]:
                    self.harness.cancel(att[0])
            return self.occurrence(occ_id)

    def confirm_occurrence(self, occ_id, principal):
        """Owner confirms a calendar date that was not part of the approved proposal (new year, moved date)."""
        with self._mutex:
            occ = self.occurrence(occ_id)
            job = self.job(occ["job_id"])
            self._owner_check(job, principal)
            if occ["state"] != "AWAITING_CONFIRMATION" or job["state"] == "CANCELLED":
                raise SchedulerError("NOT_AWAITING_CONFIRMATION", occ["state"])
            dates = dict(job["confirmed_dates"], **{occ["occurrence_key"]: occ["meta"].get("festival_date")})
            with self.store.tx() as db:
                db.execute("UPDATE job SET confirmed_dates_json=?, updated_at_us=? WHERE job_id=?", (jdump(dates), self.now(), job["job_id"]))
                self._set_occ(db, occ_id, "SCHEDULED", "DATE_CONFIRMED_BY_OWNER")
                self.store.emit(db, "occurrence.date_confirmed", job_id=job["job_id"], occ_id=occ_id,
                                payload={"by": principal, "key": occ["occurrence_key"], "festival_date": occ["meta"].get("festival_date")})
            return self.occurrence(occ_id)

    def reschedule_occurrence(self, occ_id, principal, local_iso):
        with self._mutex:
            occ = self.occurrence(occ_id)
            job = self.job(occ["job_id"])
            self._owner_check(job, principal)
            if occ["state"] not in ("SCHEDULED", "BLOCKED_HARNESS", "QUOTA_DEFERRED", "MISSED", "FAILED", "NEEDS_ATTENTION"):
                raise SchedulerError("CANNOT_RESCHEDULE", occ["state"])
            at = datetime.fromisoformat(local_iso)
            if at.tzinfo is not None:
                raise SchedulerError("LOCAL_TIME_EXPECTED")
            due = _us(timespec.local_to_utc(at.date(), at.time(), timespec.zone(job["timezone"])))
            meta = dict(occ["meta"], owner_due_local=local_iso)
            with self.store.tx() as db:
                # An explicit owner time after the festival day started is honoured: the deadline no longer applies.
                dl = occ["deadline_us"] if occ["deadline_us"] is None or due < occ["deadline_us"] else None
                self._set_occ(db, occ_id, "SCHEDULED", "RESCHEDULED_BY_OWNER", due_at_us=due, retry_at_us=None, late=0,
                              meta_json=jdump(meta), deadline_us=dl)
                self.store.emit(db, "occurrence.rescheduled", job_id=job["job_id"], occ_id=occ_id,
                                payload={"by": principal, "was": occ["state"], "due_local": local_iso, "due_utc": _iso(due)})
            return self.occurrence(occ_id)

    def retry_occurrence(self, occ_id, principal):
        """Owner recovery path for BLOCKED_HARNESS / QUOTA_DEFERRED / FAILED / NEEDS_ATTENTION / MISSED: run now."""
        with self._mutex:
            occ = self.occurrence(occ_id)
            self._owner_check(self.job(occ["job_id"]), principal)
            if occ["state"] not in ("BLOCKED_HARNESS", "QUOTA_DEFERRED", "FAILED", "NEEDS_ATTENTION", "MISSED"):
                raise SchedulerError("CANNOT_RETRY", occ["state"])
            nxt = "REVISION_QUEUED" if occ["request"] and occ["request"].get("kind") in ("refine", "regenerate") else "SCHEDULED"
            with self.store.tx() as db:
                self._set_occ(db, occ_id, nxt, "RETRY_BY_OWNER", retry_at_us=None, due_at_us=min(occ["due_at_us"], self.now()),
                              deadline_us=None if occ["state"] == "MISSED" else occ["deadline_us"])
                self.store.emit(db, "occurrence.retry_requested", job_id=occ["job_id"], occ_id=occ_id,
                                payload={"by": principal, "was": occ["state"]})
            return self.occurrence(occ_id)

    # ---- recovery ---------------------------------------------------------------------------------------------------
    def recover(self) -> dict:
        """At startup (we hold the single-instance lock, so no other scheduler owns RUNNING rows).

        An interrupted occurrence is reconciled against what is durably known before anything is re-run (review round 1,
        F3): an artifact already recorded -> AWAITING_REVIEW; supervisor task COMPLETE -> COLLECT_PENDING (URI collects and
        renders the finished work, the harness is not re-run); the executor never started, or every declared effect was
        proven absent with no tool activity -> requeued with its context; anything else -> NEEDS_ATTENTION (the harness
        may have acted; the owner decides)."""
        out = {"interrupted": [], "harness": getattr(self.harness, "startup_report", [])}
        rows = self.store.q("SELECT occ_id, job_id, attempts, reason, request_json FROM occurrence WHERE state='RUNNING'")
        for row in rows:
            pol = json.loads(self.store.q1("SELECT policy_json FROM job WHERE job_id=?", (row["job_id"],))[0])
            # The latest attempt, whether or not it was ended: a RUNNING occurrence may have died between ending its
            # attempt and moving on, or between claiming a collection and reopening the attempt (review round 2, F1).
            att = self.store.q1("SELECT attempt_id, supervisor_task_id FROM attempt WHERE occ_id=? ORDER BY attempt_id DESC LIMIT 1",
                                (row["occ_id"],))
            art = self.store.q1("SELECT artifact_id FROM artifact WHERE attempt_id=?", (att[0],)) if att else None
            settle = None
            if att and art is None and self.harness is not None and hasattr(self.harness, "settlement"):
                settle = self.harness.settlement(att["supervisor_task_id"])
            revision = bool(row["request_json"]) and json.loads(row["request_json"]).get("kind") in ("refine", "regenerate")
            requeue = "REVISION_QUEUED" if revision else "SCHEDULED"
            outcome = "INTERRUPTED"
            if row["reason"] == "CANCEL_REQUESTED":
                nxt, why = "CANCELLED", "CANCELLED_BY_OWNER"
            elif art is not None:
                nxt, why, outcome = "AWAITING_REVIEW", "RECOVERED_ARTIFACT_ALREADY_RECORDED", "COMPLETED"
            elif settle and settle["state"] == "COMPLETE":
                nxt, why = "COLLECT_PENDING", "RECOVERED_HARNESS_WORK_COMPLETE"
            elif settle is None or not settle["spawned"] or settle["absence_proven"]:
                if row["attempts"] < pol["max_attempts"]:
                    nxt, why = requeue, ("INTERRUPTED_NEVER_STARTED" if not (settle and settle["spawned"])
                                         else "INTERRUPTED_NO_EFFECT_PROVEN")
                else:
                    nxt, why = "FAILED", "INTERRUPTED_NO_ATTEMPTS_LEFT"
            else:
                nxt, why = "NEEDS_ATTENTION", "INTERRUPTED_OUTCOME_UNCERTAIN"
            with self.store.tx() as db:
                if att:
                    db.execute("UPDATE attempt SET ended_at_us=COALESCE(ended_at_us, ?), outcome=?, reason=? WHERE attempt_id=?",
                               (self.now(), outcome if nxt != "COLLECT_PENDING" else "HARNESS_COMPLETE_RECOVERED",
                                "SCHEDULER_PROCESS_ENDED:" + why, att[0]))
                self._set_occ(db, row["occ_id"], nxt, why, lease_owner=None, lease_until_us=None)
                self.store.emit(db, "occurrence.interrupted", job_id=row["job_id"], occ_id=row["occ_id"],
                                payload={"attempts": row["attempts"], "next": nxt, "why": why, "context_preserved": True,
                                         "supervisor": settle})
            out["interrupted"].append({"occ_id": row["occ_id"], "next": nxt, "why": why})
        with self.store.tx() as db:
            self.store.emit(db, "scheduler.started", payload={"instance": self.instance_id, "recovered": out["interrupted"],
                                                               "harness_revoked": len(out["harness"])})
        return out

    def _resume_collection(self, occ_id) -> dict:
        """COLLECT_PENDING: the harness finished before the scheduler died; collect, render and file the review now."""
        occ = self.occurrence(occ_id)
        job = self.job(occ["job_id"])
        prev = self.store.q1("SELECT * FROM attempt WHERE occ_id=? ORDER BY attempt_id DESC LIMIT 1", (occ_id,))
        with self.store.tx() as db:      # claim and attempt reopen in ONE transaction (review round 2, F1)
            cur = db.execute("UPDATE occurrence SET state='RUNNING', attempts=attempts+1, retry_at_us=NULL, lease_owner=?, "
                             "updated_at_us=? WHERE occ_id=? AND state='COLLECT_PENDING' AND EXISTS (SELECT 1 FROM job j "
                             "WHERE j.job_id=occurrence.job_id AND j.state<>'CANCELLED')", (self.instance_id, self.now(), occ_id))
            if cur.rowcount != 1:
                return {"occ_id": occ_id, "result": "NOT_CLAIMED"}
            db.execute("UPDATE attempt SET ended_at_us=NULL WHERE attempt_id=?", (prev["attempt_id"],))
            self.store.emit(db, "occurrence.collection_resumed", job_id=job["job_id"], occ_id=occ_id,
                            payload={"attempt_id": prev["attempt_id"], "harness_rerun": False})
        occ = self.occurrence(occ_id)
        done = self._settle_recorded_artifact(occ, job, prev["attempt_id"], {"recovered": True})
        if done is not None:
            return done
        try:
            return self._complete(occ, job, prev["attempt_id"], prev["workspace"], prev["mode"], prev["kind"],
                                  self._previous_for(occ), {"recovered": True, "stages": {"research_concept_assets_animation":
                                                                                          "completed (before restart)"}})
        except Exception as exc:                                  # noqa: BLE001
            return self._post_harness_failure(occ, job, prev["attempt_id"], f"EXECUTION_ERROR:{type(exc).__name__}",
                                              {"error": str(exc)[:500]})

    # ---- the tick ---------------------------------------------------------------------------------------------------
    def tick(self, *, materialize=True) -> list:
        """One scheduling pass. Runs due work synchronously (one harness slot). Returns per-occurrence results."""
        if materialize:
            self.materialize()
        now = self.now()
        with self.store.tx() as db:
            for row in db.execute("SELECT occ_id, job_id, state FROM occurrence WHERE state IN ('BLOCKED_HARNESS','QUOTA_DEFERRED') "
                                  "AND retry_at_us IS NOT NULL AND retry_at_us<=?", (now,)).fetchall():
                req = db.execute("SELECT request_json FROM occurrence WHERE occ_id=?", (row["occ_id"],)).fetchone()[0]
                nxt = "REVISION_QUEUED" if req and json.loads(req).get("kind") in ("refine", "regenerate") else "SCHEDULED"
                self._set_occ(db, row["occ_id"], nxt, "RECHECK_" + row["state"], retry_at_us=None)
                self.store.emit(db, "occurrence.recheck", job_id=row["job_id"], occ_id=row["occ_id"], payload={"was": row["state"]})
        due = self.store.q("SELECT o.occ_id FROM occurrence o JOIN job j ON j.job_id=o.job_id WHERE "
                           "((o.state='SCHEDULED' AND j.state='ACTIVE' AND o.due_at_us<=?) OR "
                           "(o.state='REVISION_QUEUED' AND j.state IN ('ACTIVE','PAUSED'))) AND (o.retry_at_us IS NULL OR o.retry_at_us<=?) "
                           "ORDER BY o.due_at_us, o.occ_id", (now, now))
        results = []
        for (occ_id,) in self.store.q("SELECT occ_id FROM occurrence WHERE state='COLLECT_PENDING' AND (retry_at_us IS NULL OR "
                                      "retry_at_us<=?) ORDER BY occ_id", (now,)):
            results.append(self._resume_collection(occ_id))
        for (occ_id,) in due:
            results.append(self._dispatch(occ_id))
        return results

    def _dispatch(self, occ_id) -> dict:
        # Everything up to the claim runs under the engine mutex, so an owner correction, calendar refresh or cancel
        # cannot change the occurrence between selection and claim (review round 9, C1-01). The run itself does not.
        with self._mutex:
            pre = self._pre_claim(occ_id)
        if "result" in pre:
            return pre
        return self._execute_settled(self.occurrence(occ_id), pre["job"])

    def _pre_claim(self, occ_id) -> dict:
        occ = self.occurrence(occ_id)
        job = self.job(occ["job_id"])
        pol = job["policy"]
        now = self.now()
        if occ["state"] not in ("SCHEDULED", "REVISION_QUEUED") or (occ["state"] == "SCHEDULED" and occ["due_at_us"] > now):
            return {"occ_id": occ_id, "result": "NOT_CLAIMED"}
        revision = occ["state"] == "REVISION_QUEUED"
        if not revision:
            if occ["deadline_us"] is not None and now >= occ["deadline_us"]:
                with self.store.tx() as db:
                    self._set_occ(db, occ_id, "MISSED", "DEADLINE_PASSED")
                    self.store.emit(db, "occurrence.missed", job_id=job["job_id"], occ_id=occ_id,
                                    payload={"due_utc": _iso(occ["due_at_us"]), "deadline_utc": _iso(occ["deadline_us"])})
                self.notify("missed", {"occ_id": occ_id})
                return {"occ_id": occ_id, "result": "MISSED"}
            if now - occ["due_at_us"] > pol["grace_s"] * 1_000_000 and not occ["late"]:
                with self.store.tx() as db:
                    if pol["missed"] == "skip":
                        self._set_occ(db, occ_id, "MISSED", "LATE_SKIPPED_BY_POLICY")
                    else:
                        self._set_occ(db, occ_id, "SCHEDULED", "LATE_RUN", late=1)
                    self.store.emit(db, "occurrence.missed_execution_detected", job_id=job["job_id"], occ_id=occ_id,
                                    payload={"due_utc": _iso(occ["due_at_us"]), "late_by_s": (now - occ["due_at_us"]) // 1_000_000,
                                             "policy": pol["missed"]})
                if pol["missed"] == "skip":
                    return {"occ_id": occ_id, "result": "MISSED"}
        # authority re-validated at dispatch time, not trusted from proposal time
        try:
            self._validate_authority(job["authority"])
        except SchedulerError as exc:
            with self.store.tx() as db:
                self._set_occ(db, occ_id, "FAILED", "AUTHORITY_INVALID:" + exc.code)
                self.store.emit(db, "occurrence.authority_refused", job_id=job["job_id"], occ_id=occ_id, payload={"code": exc.code})
            return {"occ_id": occ_id, "result": "FAILED", "reason": exc.code}
        # claim (compare-and-set)
        with self.store.tx() as db:
            # The job's state is part of the compare-and-set: a job cancelled (or paused, for scheduled work) after this
            # occurrence was selected can never be claimed (review round 1, F7).
            cur = db.execute("UPDATE occurrence SET state='RUNNING', reason=NULL, attempts=attempts+1, lease_owner=?, updated_at_us=? "
                             "WHERE occ_id=? AND state=? AND state IN ('SCHEDULED','REVISION_QUEUED') AND (?=1 OR due_at_us<=?) "
                             "AND EXISTS (SELECT 1 FROM job j WHERE j.job_id=occurrence.job_id AND "
                             "(j.state='ACTIVE' OR (j.state='PAUSED' AND ?=1)))",
                             (self.instance_id, now, occ_id, occ["state"], 1 if revision else 0, now, 1 if revision else 0))
            if cur.rowcount != 1:
                return {"occ_id": occ_id, "result": "NOT_CLAIMED"}
            self.store.emit(db, "occurrence.claimed", job_id=job["job_id"], occ_id=occ_id,
                            payload={"instance": self.instance_id, "attempt_no": occ["attempts"] + 1, "revision": revision})
        return {"job": job}

    def _execute_settled(self, occ, job) -> dict:
        """Every claimed occurrence leaves RUNNING, whatever raises (review round 1, F5)."""
        try:
            return self._execute(occ, job)
        except Exception as exc:                          # noqa: BLE001 - settle, then surface in the receipt
            reason = f"EXECUTION_ERROR:{type(exc).__name__}"
            att = self.store.q1("SELECT attempt_id FROM attempt WHERE occ_id=? AND ended_at_us IS NULL ORDER BY attempt_id DESC "
                                "LIMIT 1", (occ["occ_id"],))
            receipt = {"error": f"{type(exc).__name__}: {str(exc)[:500]}"}
            if att is not None:
                task = self.store.q1("SELECT supervisor_task_id FROM attempt WHERE attempt_id=?", (att[0],))[0]
                settle = self.harness.settlement(task) if hasattr(self.harness, "settlement") else None
                if settle and settle["state"] == "COMPLETE":          # failure after the harness finished (round 2, F2)
                    return self._post_harness_failure(occ, job, att[0], reason, receipt)
                return self._retry_or_fail(occ, job, att[0], reason, receipt)
            with self.store.tx() as db:
                self._set_occ(db, occ["occ_id"], "NEEDS_ATTENTION", reason, lease_owner=None)
                self.store.emit(db, "occurrence.execution_error", job_id=job["job_id"], occ_id=occ["occ_id"], payload=receipt)
            return {"occ_id": occ["occ_id"], "result": "NEEDS_ATTENTION", "reason": reason}

    # ---- execution ------------------------------------------------------------------------------------------------
    def _previous_for(self, occ):
        req = occ["request"]
        if not req or req.get("kind") not in ("refine", "regenerate"):
            return None
        art = self.store.q1("SELECT * FROM artifact WHERE artifact_id=?", (req["base_artifact_id"],))
        info = json.loads(art["info_json"])
        return {"artifact_id": art["artifact_id"], "scene": info["scene"], "concept": art["concept"]}

    def _execute(self, occ, job) -> dict:
        occ_id = occ["occ_id"]
        pol = job["policy"]
        gate = self.harness.gate() if self.harness is not None else None
        if gate is None or not gate.available:
            code = gate.code if gate else "NO_HARNESS_CONFIGURED"
            with self.store.tx() as db:
                self._set_occ(db, occ_id, "BLOCKED_HARNESS", code, attempts=occ["attempts"] - 1, lease_owner=None,
                              retry_at_us=self.now() + pol["harness_recheck_s"] * 1_000_000)
                self.store.emit(db, "harness.unavailable", job_id=job["job_id"], occ_id=occ_id,
                                payload={"code": code, "gate": gate.to_json() if gate else None,
                                         "recovery": ["sign the URI client profile in to Claude, then Retry",
                                                      "Reschedule to a later time", "Cancel this occurrence"],
                                         "auto_recheck_utc": _iso(self.now() + pol["harness_recheck_s"] * 1_000_000),
                                         "substitution": "none (no other or paid provider is ever used)"})
            self.notify("blocked", {"occ_id": occ_id, "code": code})
            return {"occ_id": occ_id, "result": "BLOCKED_HARNESS", "reason": code}
        # Global per-occurrence sequence (revisions reset the retry budget, never the identity): one key, one task.
        seq = self.store.q1("SELECT COUNT(*) FROM attempt WHERE occ_id=?", (occ_id,))[0] + 1
        attempt_key = f"{job['job_id']}:{occ_id}:{seq}"
        workspace = self.state_dir / "work" / f"occ_{occ_id}" / f"attempt_{seq}"
        if workspace.exists():                     # a crashed earlier process with the same attempt number: keep evidence
            workspace = workspace.with_name(workspace.name + "_" + uuid.uuid4().hex[:6])
        kind = (occ["request"] or {}).get("kind", "generate")
        with self.store.tx() as db:
            # Cancellation recorded while the gate ran (review round 6, F1): settle it here, before any attempt exists or
            # any harness work is submitted. After this transaction, cancel_occurrence finds the attempt and withdraws its
            # supervisor task through harness.cancel (never spawned, or killed).
            if db.execute("SELECT reason FROM occurrence WHERE occ_id=?", (occ_id,)).fetchone()["reason"] == "CANCEL_REQUESTED":
                self._set_occ(db, occ_id, "CANCELLED", "CANCELLED_BY_OWNER", lease_owner=None)
                self.store.emit(db, "occurrence.cancelled_before_start", job_id=job["job_id"], occ_id=occ_id, payload={})
                return {"occ_id": occ_id, "result": "CANCELLED", "reason": "CANCELLED_BY_OWNER"}
            cur = db.execute("INSERT INTO attempt(occ_id,kind,mode,harness,started_at_us,supervisor_task_id,workspace) "
                             "VALUES (?,?,?,?,?,?,?)", (occ_id, kind, gate.mode, gate.executor_id, self.now(),
                                                     self.harness.task_id_for(attempt_key), str(workspace)))
            attempt_id = cur.lastrowid
            self.store.emit(db, "attempt.started", job_id=job["job_id"], occ_id=occ_id,
                            payload={"attempt_id": attempt_id, "mode": gate.mode, "executor": gate.executor_id,
                                     "qualification": gate.qualification, "kind": kind, "workspace": str(workspace)})
        template = TEMPLATES[job["template_id"]]
        previous = self._previous_for(occ)
        instructions = template.build_package(workspace, occurrence=occ, params=job["params"], request=occ["request"],
                                              previous=previous)
        valid_until = occ["deadline_us"] if not occ["request"] else None
        outcome = self.harness.run(attempt_key=attempt_key, principal=job["owner"], workspace=workspace,
                                   instructions=instructions, gate=gate, valid_until_us=valid_until)
        receipt = {"gate": gate.to_json(), "harness": outcome.receipt, "status": outcome.status, "reason": outcome.reason,
                   "stages": {"research_concept_assets_animation": outcome.status}}
        cur_state = self.occurrence(occ_id)
        if cur_state["reason"] == "CANCEL_REQUESTED":
            return self._finish(occ, job, attempt_id, "CANCELLED", "CANCELLED_BY_OWNER", receipt, "CANCELLED")
        if outcome.status == "quota":
            reset = outcome.receipt.get("reset_us") or (self.now() + pol["quota_default_wait_s"] * 1_000_000)
            return self._finish(occ, job, attempt_id, "QUOTA_DEFERRED", outcome.reason, receipt, "QUOTA",
                                retry_at_us=max(reset, self.now() + 60_000_000), attempts=occ["attempts"] - 1)
        if outcome.status == "uncertain":
            return self._finish(occ, job, attempt_id, "NEEDS_ATTENTION", outcome.reason, receipt, "UNCERTAIN")
        if outcome.status != "completed":
            return self._retry_or_fail(occ, job, attempt_id, outcome.reason, receipt)
        return self._complete(occ, job, attempt_id, workspace, gate.mode, kind, previous, receipt)

    def _complete(self, occ, job, attempt_id, workspace, mode, kind, previous, receipt) -> dict:
        """Collect -> render -> validate -> artifact -> review. Also the resume point after a restart that found the
        harness work COMPLETE in the supervisor ledger (the harness is never re-run for finished work)."""
        occ_id = occ["occ_id"]
        workspace = Path(workspace)
        template = TEMPLATES[job["template_id"]]
        # Render -> GIF conversion -> Validation (URI-owned)
        try:
            collected = template.collect(workspace)
        except gif_task.TaskError as exc:
            # The harness finished but its output is unusable (missing/invalid files). Producing new content is a CONTENT
            # retry under the job's retry budget, not a duplicate of finished work: nothing usable exists to collect
            # (review round 3, F1; documented in SCHEDULER_ARCHITECTURE.md "Content retry").
            receipt["stages"]["collect"] = str(exc)
            receipt["content_retry"] = True
            return self._retry_or_fail(occ, job, attempt_id, "OUTPUT_INVALID:" + str(exc), receipt)
        version = (self.store.q1("SELECT COALESCE(MAX(version),0) FROM artifact WHERE occ_id=?", (occ_id,))[0]) + 1
        raw = occ["meta"].get("festival_key") or (job["params"].get("festival") or {}).get("key") or "task"
        slug = re.sub(r"[^a-z0-9_]+", "_", str(raw).lower())[:40] or "task"
        tail = re.sub(r"[^0-9A-Za-z_-]+", "_", occ["occurrence_key"].split(":")[-1])[:24]
        name = f"{slug}_{tail}_v{version}"
        out_dir = (self.state_dir / "outputs" / f"occ_{occ_id}").resolve()
        if (out_dir / f"{name}.gif").resolve().parent != out_dir:          # defence in depth (review round 1, F8)
            raise SchedulerError("OUTPUT_PATH_ESCAPE", name)
        try:
            result = template.render_and_validate(collected, out_dir, name)
        except Exception as exc:                               # noqa: BLE001 - renderer failure is a task failure
            receipt["stages"]["render"] = f"{type(exc).__name__}: {exc}"
            return self._post_harness_failure(occ, job, attempt_id, "RENDER_FAILED", receipt)
        receipt["stages"].update({"render": "ok", "gif_conversion": "ok", "validation": "ok" if result["ok"] else "failed"})
        if not result["ok"]:
            receipt["validation"] = result
            receipt["content_retry"] = True        # rendered output fails the GIF/legibility/size gate: new content needed
            return self._retry_or_fail(occ, job, attempt_id, "VALIDATION_FAILED", receipt)
        shutil.copyfile(workspace / "scene.json", out_dir / f"{name}.scene.json")
        (out_dir / f"{name}.concept.md").write_text(collected["concept"], encoding="utf-8")
        (out_dir / f"{name}.research.md").write_text(collected["research"], encoding="utf-8")
        info = {"scene": collected["scene"], "scene_sha256": collected["scene_sha256"], "render": result["render"],
                "gif_checks": result["gif_checks"], "quality": result["quality"], "research": collected["research"],
                "mode": mode, "poster": result["render"]["poster"]}
        parent = previous["artifact_id"] if previous else None
        with self.store.tx() as db:
            cur = db.execute("INSERT INTO artifact(occ_id,attempt_id,version,parent_artifact_id,kind,path,sha256,bytes,info_json,"
                             "concept,status,created_at_us) VALUES (?,?,?,?,'gif',?,?,?,?,?,'CANDIDATE',?)",
                             (occ_id, attempt_id, version, parent, result["path"], result["sha256"], result["bytes"],
                              jdump(info), collected["concept"], self.now()))
            art_id = cur.lastrowid
            if kind == "refine" and parent:
                db.execute("UPDATE artifact SET status='SUPERSEDED' WHERE artifact_id=? AND status IN ('CANDIDATE','APPROVED')", (parent,))
            self.store.emit(db, "artifact.created", job_id=job["job_id"], occ_id=occ_id,
                            payload={"artifact_id": art_id, "version": version, "sha256": result["sha256"], "bytes": result["bytes"],
                                     "parent": parent, "kind": kind, "mode": mode, "quality": result["quality"]})
        receipt["artifact"] = {"artifact_id": art_id, "version": version, "sha256": result["sha256"], "path": result["path"]}
        r = self._finish(occ, job, attempt_id, "AWAITING_REVIEW", "REVIEW_PENDING", receipt, "COMPLETED", request_json=None)
        self.notify("review_pending", {"occ_id": occ_id, "artifact_id": art_id})
        return r | {"artifact_id": art_id}

    def _settle_recorded_artifact(self, occ, job, attempt_id, receipt):
        """If this attempt already recorded its artifact (a failure happened after the insert, e.g. in `_finish`), file
        that artifact for review instead of collecting again: no second version of the same work (review round 3, F2)."""
        art = self.store.q1("SELECT artifact_id FROM artifact WHERE attempt_id=?", (attempt_id,))
        if art is None:
            return None
        receipt = dict(receipt, settled_existing_artifact=art[0])
        r = self._finish(occ, job, attempt_id, "AWAITING_REVIEW", "REVIEW_PENDING", receipt, "COMPLETED", request_json=None)
        return r | {"artifact_id": art[0]}

    def _post_harness_failure(self, occ, job, attempt_id, reason, receipt):
        """A URI-side failure (render, file I/O, recording) after the harness finished: retry COLLECTION from the existing
        workspace with backoff; never start another harness run for finished work (review round 2, F2)."""
        done = self._settle_recorded_artifact(occ, job, attempt_id, receipt)
        if done is not None:
            return done
        pol = job["policy"]
        if occ["attempts"] < pol["max_attempts"]:
            back = self._backoff_s(pol, occ["attempts"])
            return self._finish(occ, job, attempt_id, "COLLECT_PENDING", "COLLECT_RETRY:" + reason, receipt, "COLLECT_FAILED",
                                retry_at_us=self.now() + back * 1_000_000)
        return self._finish(occ, job, attempt_id, "FAILED", "COLLECT_FAILED:" + reason, receipt, "COLLECT_FAILED")

    def _retry_or_fail(self, occ, job, attempt_id, reason, receipt):
        pol = job["policy"]
        if occ["attempts"] < pol["max_attempts"]:
            back = self._backoff_s(pol, occ["attempts"])
            nxt = "REVISION_QUEUED" if occ["request"] else "SCHEDULED"
            return self._finish(occ, job, attempt_id, nxt, "RETRY:" + reason, receipt, "FAILED",
                                retry_at_us=self.now() + back * 1_000_000)
        return self._finish(occ, job, attempt_id, "FAILED", reason, receipt, "FAILED")

    def _finish(self, occ, job, attempt_id, state, reason, receipt, outcome, **cols):
        with self.store.tx() as db:
            # Cancellation is checked INSIDE the settling transaction (review round 4, F2): if the owner cancelled while
            # this attempt ran, the occurrence ends CANCELLED whatever the attempt produced; any artifact stays recorded
            # but is never offered for review.
            now_row = db.execute("SELECT reason FROM occurrence WHERE occ_id=?", (occ["occ_id"],)).fetchone()
            if now_row is not None and now_row["reason"] == "CANCEL_REQUESTED" and state != "CANCELLED":
                receipt = dict(receipt, cancelled_while_running={"would_have_been": state, "reason": reason})
                state, reason, cols = "CANCELLED", "CANCELLED_BY_OWNER", {}
                db.execute("UPDATE artifact SET status='REJECTED' WHERE attempt_id=? AND status='CANDIDATE'", (attempt_id,))
            db.execute("UPDATE attempt SET ended_at_us=?, outcome=?, reason=?, receipt_json=? WHERE attempt_id=?",
                       (self.now(), outcome, reason, jdump(receipt), attempt_id))
            self._set_occ(db, occ["occ_id"], state, reason, lease_owner=None, **cols)
            self.store.emit(db, "attempt.ended", job_id=job["job_id"], occ_id=occ["occ_id"],
                            payload={"attempt_id": attempt_id, "outcome": outcome, "reason": reason, "next_state": state,
                                     "mode": receipt.get("gate", {}).get("mode")})
        return {"occ_id": occ["occ_id"], "result": state, "reason": reason, "attempt_id": attempt_id}

    # ---- review -----------------------------------------------------------------------------------------------------
    def review(self, artifact_id, principal, action, *, expected_sha256, instruction=None) -> dict:
        with self._mutex:
            art = self.store.q1("SELECT * FROM artifact WHERE artifact_id=?", (artifact_id,))
            if art is None:
                raise SchedulerError("UNKNOWN_ARTIFACT", artifact_id)
            occ = self.occurrence(art["occ_id"])
            job = self.job(occ["job_id"])
            self._owner_check(job, principal)
            if job["state"] == "CANCELLED":
                raise SchedulerError("JOB_CANCELLED", job["job_id"])
            if action not in ("approve", "refine", "regenerate", "reject"):
                raise SchedulerError("BAD_ACTION", action)
            if expected_sha256 != art["sha256"]:
                raise SchedulerError("ARTIFACT_VERSION_MISMATCH", "the decision names a different artifact version")
            on_disk = gif_task.sha256_file(art["path"]) if Path(art["path"]).is_file() else None
            if on_disk != art["sha256"]:
                raise SchedulerError("ARTIFACT_CHANGED_ON_DISK", "the file no longer matches the reviewed version")
            if action == "approve":
                if occ["state"] != "AWAITING_REVIEW" or art["status"] != "CANDIDATE":
                    raise SchedulerError("NOT_REVIEWABLE", f"{occ['state']}/{art['status']}")
            elif occ["state"] not in ("AWAITING_REVIEW", "APPROVED") or art["status"] not in ("CANDIDATE", "APPROVED"):
                raise SchedulerError("NOT_REVIEWABLE", f"{occ['state']}/{art['status']}")
            if action in ("refine",) and not (instruction or "").strip():
                raise SchedulerError("INSTRUCTION_REQUIRED")
            if instruction and len(instruction) > 1000:
                raise SchedulerError("INSTRUCTION_TOO_LONG")
            with self.store.tx() as db:
                db.execute("INSERT INTO review(artifact_id,principal,action,instruction,artifact_sha256,at_us) VALUES (?,?,?,?,?,?)",
                           (artifact_id, principal, action, instruction, art["sha256"], self.now()))
                if action == "approve":
                    db.execute("UPDATE artifact SET status='APPROVED' WHERE artifact_id=?", (artifact_id,))
                    db.execute("UPDATE artifact SET status='SUPERSEDED' WHERE occ_id=? AND artifact_id<>? AND status='CANDIDATE'",
                               (occ["occ_id"], artifact_id))
                    self._set_occ(db, occ["occ_id"], "APPROVED", f"APPROVED_V{art['version']}")
                elif action == "reject":
                    db.execute("UPDATE artifact SET status='REJECTED' WHERE artifact_id=?", (artifact_id,))
                    left = db.execute("SELECT COUNT(*) FROM artifact WHERE occ_id=? AND status='CANDIDATE'", (occ["occ_id"],)).fetchone()[0]
                    if left == 0:
                        self._set_occ(db, occ["occ_id"], "REJECTED", f"REJECTED_V{art['version']}")
                else:
                    if art["status"] == "APPROVED":
                        db.execute("UPDATE artifact SET status='CANDIDATE' WHERE artifact_id=?", (artifact_id,))
                        self.store.emit(db, "approval.invalidated", job_id=job["job_id"], occ_id=occ["occ_id"],
                                        payload={"artifact_id": artifact_id, "sha256": art["sha256"], "why": action})
                    req = {"kind": action, "instruction": instruction, "base_artifact_id": artifact_id,
                           "base_sha256": art["sha256"], "requested_by": principal}
                    self._set_occ(db, occ["occ_id"], "REVISION_QUEUED", action.upper() + "_REQUESTED", request_json=jdump(req),
                                  attempts=0, retry_at_us=None)
                self.store.emit(db, "review." + action, job_id=job["job_id"], occ_id=occ["occ_id"],
                                payload={"artifact_id": artifact_id, "version": art["version"], "sha256": art["sha256"],
                                         "by": principal, "instruction": instruction, "published": False})
            return {"occurrence": self.occurrence(occ["occ_id"]), "artifact": self.artifact(artifact_id)}

    def artifact(self, artifact_id) -> dict:
        r = self.store.q1("SELECT * FROM artifact WHERE artifact_id=?", (artifact_id,))
        if r is None:
            raise SchedulerError("UNKNOWN_ARTIFACT", artifact_id)
        d = dict(r)
        d["info"] = json.loads(d.pop("info_json"))
        d["reviews"] = [dict(x) for x in self.store.q("SELECT * FROM review WHERE artifact_id=? ORDER BY review_id", (artifact_id,))]
        return d

    # ---- views for the UI -------------------------------------------------------------------------------------------
    def overview(self, owner=None, limit=20, include_harness=True) -> dict:
        now = self.now()
        own = " AND j.owner=?" if owner else ""
        a = (owner,) if owner else ()

        def occ_rows(where, args, order="o.due_at_us", lim=limit):
            rows = self.store.q(f"SELECT o.*, j.title, j.timezone, j.state AS job_state FROM occurrence o JOIN job j ON "
                                f"j.job_id=o.job_id WHERE {where}{own} ORDER BY {order} LIMIT ?", (*args, *a, lim))
            out = []
            for r in rows:
                d = dict(r)
                d["meta"] = json.loads(d.pop("meta_json") or "{}")
                d.pop("request_json", None)
                d["due_local"] = _local(d["due_at_us"], d["timezone"])
                d["retry_local"] = _local(d["retry_at_us"], d["timezone"])
                out.append(d)
            return out
        pending = []
        for r in occ_rows("o.state='AWAITING_REVIEW'", ()):
            arts = [self.artifact(x[0]) for x in self.store.q("SELECT artifact_id FROM artifact WHERE occ_id=? AND status='CANDIDATE' "
                                                               "ORDER BY version DESC", (r["occ_id"],))]
            for art in arts:
                art["info"].pop("scene", None)
                art["info"].pop("research", None)
            pending.append(r | {"candidates": arts})
        attempts = self.store.q("SELECT a.*, o.job_id, o.occurrence_key, j.title FROM attempt a JOIN occurrence o ON o.occ_id=a.occ_id "
                                f"JOIN job j ON j.job_id=o.job_id WHERE 1=1{own} ORDER BY a.attempt_id DESC LIMIT ?", (*a, limit))
        jobs = self.store.q(f"SELECT job_id, owner, title, template_id, state, timezone, schedule_json FROM job j WHERE 1=1{own} "
                            "ORDER BY created_at_us DESC", a)
        return {"now_utc": _iso(now),
                "upcoming": occ_rows("o.state IN ('SCHEDULED','REVISION_QUEUED','RUNNING','COLLECT_PENDING')", ()),
                "errors": occ_rows("o.state IN ('BLOCKED_HARNESS','QUOTA_DEFERRED','FAILED','NEEDS_ATTENTION','MISSED',"
                                   "'AWAITING_CONFIRMATION')", (),
                                   "o.updated_at_us DESC"),
                "pending_approvals": pending,
                "approved": occ_rows("o.state='APPROVED'", (), "o.updated_at_us DESC", 10),
                "recent_executions": [{k: r[k] for k in r.keys() if k != "receipt_json"} | {"started_utc": _iso(r["started_at_us"]),
                                      "ended_utc": _iso(r["ended_at_us"])} for r in attempts],
                "jobs": [dict(j) | {"schedule": json.loads(j["schedule_json"]), "interpretation": timespec.describe(json.loads(j["schedule_json"]))}
                         for j in jobs],
                "paused_jobs": [j["job_id"] for j in jobs if j["state"] == "PAUSED"],
                "harness": self.harness.gate().to_json() if (include_harness and self.harness is not None) else None}
