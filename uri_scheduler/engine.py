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
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import DEFAULT_TZ, gif_task, timespec
from .calendar_store import Calendar
from .store import Store, jdump

try:
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None

ACTIVE_STATES = ("SCHEDULED", "RUNNING", "REVISION_QUEUED", "BLOCKED_HARNESS", "QUOTA_DEFERRED")
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
        self.startup = self.recover()
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
        for k in ("params", "schedule", "authority", "policy"):
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
        pol = dict(DEFAULT_POLICY | (policy or {}))
        if pol["missed"] not in ("run_late", "skip"):
            raise SchedulerError("BAD_POLICY", "missed")
        if sched["kind"] == "calendar_relative":
            self._validate_selection(sched)
        job_id = "job_" + uuid.uuid4().hex[:12]
        proposal = self._proposal(job_id, owner, title, template_id, params, sched, auth, pol, preview_days)
        now = self.now()
        with self.store.tx() as db:
            db.execute("INSERT INTO job(job_id,owner,title,template_id,params_json,schedule_json,timezone,authority_json,"
                       "policy_json,state,proposal_sha256,created_at_us,updated_at_us) VALUES (?,?,?,?,?,?,?,?,?,'PROPOSED',?,?,?)",
                       (job_id, owner, title, template_id, jdump(params), jdump(sched), sched["tz"], jdump(auth), jdump(pol),
                        proposal["proposal_sha256"], now, now))
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
                db.execute("UPDATE job SET state='ACTIVE', confirmed_by=?, confirmed_at_us=?, updated_at_us=? WHERE job_id=? "
                           "AND state='PROPOSED'", (principal, now, now, job_id))
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
            for occ in self.store.q("SELECT occ_id FROM occurrence WHERE job_id=? AND state IN ('SCHEDULED','REVISION_QUEUED',"
                                    "'BLOCKED_HARNESS','QUOTA_DEFERRED','RUNNING')", (job_id,)):
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
        report = {"inserted": 0, "moved": 0, "withdrawn": 0}
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
                    row = db.execute("SELECT occ_id,state,due_at_us,meta_json FROM occurrence WHERE job_id=? AND occurrence_key=?",
                                     (job["job_id"], o.key)).fetchone()
                    due, dl = _us(o.due_utc), (_us(o.deadline_utc) if o.deadline_utc else None)
                    if row is None:
                        cur = db.execute("INSERT INTO occurrence(job_id,occurrence_key,due_at_us,deadline_us,state,meta_json,"
                                         "created_at_us,updated_at_us) VALUES (?,?,?,?,'SCHEDULED',?,?,?)",
                                         (job["job_id"], o.key, due, dl, jdump(o.meta), self.now(), self.now()))
                        self.store.emit(db, "occurrence.scheduled", job_id=job["job_id"], occ_id=cur.lastrowid,
                                        payload={"key": o.key, "due_utc": _iso(due), "due_local": _local(due, sched["tz"])})
                        report["inserted"] += 1
                    elif row["due_at_us"] != due and json.loads(row["meta_json"] or "{}").get("owner_due_local"):
                        pass       # the owner rescheduled this occurrence explicitly: the calendar never overrides that
                    elif row["due_at_us"] != due and row["state"] in ("SCHEDULED", "BLOCKED_HARNESS", "QUOTA_DEFERRED"):
                        db.execute("UPDATE occurrence SET due_at_us=?, deadline_us=?, meta_json=?, updated_at_us=? WHERE occ_id=?",
                                   (due, dl, jdump(o.meta), self.now(), row["occ_id"]))
                        self.store.emit(db, "occurrence.moved_by_calendar", job_id=job["job_id"], occ_id=row["occ_id"],
                                        payload={"key": o.key, "from_utc": _iso(row["due_at_us"]), "to_utc": _iso(due),
                                                 "calendar_version": o.meta.get("calendar_version")})
                        report["moved"] += 1
                if sched["kind"] == "calendar_relative":
                    valid = {f"{e.festival_key}:{e.start.year}" for e in self.calendar.events(sched["calendar"], sched["selection"])}
                    for row in db.execute("SELECT occ_id, occurrence_key FROM occurrence WHERE job_id=? AND state IN "
                                          "('SCHEDULED','BLOCKED_HARNESS','QUOTA_DEFERRED')", (job["job_id"],)).fetchall():
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
        """At startup (we hold the single-instance lock, so no other scheduler owns RUNNING rows)."""
        out = {"interrupted": [], "harness": getattr(self.harness, "startup_report", [])}
        with self.store.tx() as db:
            for row in db.execute("SELECT occ_id, job_id, attempts, reason, request_json FROM occurrence WHERE state='RUNNING'").fetchall():
                job = json.loads(db.execute("SELECT policy_json FROM job WHERE job_id=?", (row["job_id"],)).fetchone()[0])
                db.execute("UPDATE attempt SET ended_at_us=?, outcome='INTERRUPTED', reason='SCHEDULER_PROCESS_ENDED' "
                           "WHERE occ_id=? AND ended_at_us IS NULL", (self.now(), row["occ_id"]))
                if row["reason"] == "CANCEL_REQUESTED":
                    nxt, why = "CANCELLED", "CANCELLED_BY_OWNER"
                elif row["attempts"] < job["max_attempts"]:
                    nxt = "REVISION_QUEUED" if row["request_json"] and json.loads(row["request_json"]).get("kind") in ("refine", "regenerate") else "SCHEDULED"
                    why = "INTERRUPTED_REQUEUED"
                else:
                    nxt, why = "FAILED", "INTERRUPTED_NO_ATTEMPTS_LEFT"
                self._set_occ(db, row["occ_id"], nxt, why, lease_owner=None, lease_until_us=None)
                self.store.emit(db, "occurrence.interrupted", job_id=row["job_id"], occ_id=row["occ_id"],
                                payload={"attempts": row["attempts"], "next": nxt, "context_preserved": True})
                out["interrupted"].append({"occ_id": row["occ_id"], "next": nxt})
            self.store.emit(db, "scheduler.started", payload={"instance": self.instance_id, "recovered": out["interrupted"],
                                                               "harness_revoked": len(out["harness"])})
        return out

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
        for (occ_id,) in due:
            results.append(self._dispatch(occ_id))
        return results

    def _dispatch(self, occ_id) -> dict:
        occ = self.occurrence(occ_id)
        job = self.job(occ["job_id"])
        pol = job["policy"]
        now = self.now()
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
            cur = db.execute("UPDATE occurrence SET state='RUNNING', reason=NULL, attempts=attempts+1, lease_owner=?, updated_at_us=? "
                             "WHERE occ_id=? AND state=?", (self.instance_id, now, occ_id, occ["state"]))
            if cur.rowcount != 1:
                return {"occ_id": occ_id, "result": "NOT_CLAIMED"}
            self.store.emit(db, "occurrence.claimed", job_id=job["job_id"], occ_id=occ_id,
                            payload={"instance": self.instance_id, "attempt_no": occ["attempts"] + 1, "revision": revision})
        return self._execute(self.occurrence(occ_id), job)

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
            cur = db.execute("INSERT INTO attempt(occ_id,kind,mode,harness,started_at_us,supervisor_task_id) VALUES (?,?,?,?,?,?)",
                             (occ_id, kind, gate.mode, gate.executor_id, self.now(), self.harness.task_id_for(attempt_key)))
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
        # Render -> GIF conversion -> Validation (URI-owned)
        try:
            collected = template.collect(workspace)
        except gif_task.TaskError as exc:
            receipt["stages"]["collect"] = str(exc)
            return self._retry_or_fail(occ, job, attempt_id, "OUTPUT_INVALID:" + str(exc), receipt)
        version = (self.store.q1("SELECT COALESCE(MAX(version),0) FROM artifact WHERE occ_id=?", (occ_id,))[0]) + 1
        name = f"{(occ['meta'].get('festival_key') or job['params'].get('festival', {}).get('key') or 'task')}_{occ['occurrence_key'].split(':')[-1]}_v{version}"
        out_dir = self.state_dir / "outputs" / f"occ_{occ_id}"
        try:
            result = template.render_and_validate(collected, out_dir, name)
        except Exception as exc:                               # noqa: BLE001 - renderer failure is a task failure
            receipt["stages"]["render"] = f"{type(exc).__name__}: {exc}"
            return self._retry_or_fail(occ, job, attempt_id, "RENDER_FAILED", receipt)
        receipt["stages"].update({"render": "ok", "gif_conversion": "ok", "validation": "ok" if result["ok"] else "failed"})
        if not result["ok"]:
            receipt["validation"] = result
            return self._retry_or_fail(occ, job, attempt_id, "VALIDATION_FAILED", receipt)
        shutil.copyfile(workspace / "scene.json", out_dir / f"{name}.scene.json")
        (out_dir / f"{name}.concept.md").write_text(collected["concept"], encoding="utf-8")
        (out_dir / f"{name}.research.md").write_text(collected["research"], encoding="utf-8")
        info = {"scene": collected["scene"], "scene_sha256": collected["scene_sha256"], "render": result["render"],
                "gif_checks": result["gif_checks"], "quality": result["quality"], "research": collected["research"],
                "mode": gate.mode, "poster": result["render"]["poster"]}
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
                                     "parent": parent, "kind": kind, "mode": gate.mode, "quality": result["quality"]})
        receipt["artifact"] = {"artifact_id": art_id, "version": version, "sha256": result["sha256"], "path": result["path"]}
        r = self._finish(occ, job, attempt_id, "AWAITING_REVIEW", "REVIEW_PENDING", receipt, "COMPLETED", request_json=None)
        self.notify("review_pending", {"occ_id": occ_id, "artifact_id": art_id})
        return r | {"artifact_id": art_id}

    def _retry_or_fail(self, occ, job, attempt_id, reason, receipt):
        pol = job["policy"]
        if occ["attempts"] < pol["max_attempts"]:
            back = pol["retry_backoff_s"][min(occ["attempts"] - 1, len(pol["retry_backoff_s"]) - 1)]
            nxt = "REVISION_QUEUED" if occ["request"] else "SCHEDULED"
            return self._finish(occ, job, attempt_id, nxt, "RETRY:" + reason, receipt, "FAILED",
                                retry_at_us=self.now() + back * 1_000_000)
        return self._finish(occ, job, attempt_id, "FAILED", reason, receipt, "FAILED")

    def _finish(self, occ, job, attempt_id, state, reason, receipt, outcome, **cols):
        with self.store.tx() as db:
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
                "upcoming": occ_rows("o.state IN ('SCHEDULED','REVISION_QUEUED','RUNNING')", ()),
                "errors": occ_rows("o.state IN ('BLOCKED_HARNESS','QUOTA_DEFERRED','FAILED','NEEDS_ATTENTION','MISSED')", (),
                                   "o.updated_at_us DESC"),
                "pending_approvals": pending,
                "approved": occ_rows("o.state='APPROVED'", (), "o.updated_at_us DESC", 10),
                "recent_executions": [{k: r[k] for k in r.keys() if k != "receipt_json"} | {"started_utc": _iso(r["started_at_us"]),
                                      "ended_utc": _iso(r["ended_at_us"])} for r in attempts],
                "jobs": [dict(j) | {"schedule": json.loads(j["schedule_json"]), "interpretation": timespec.describe(json.loads(j["schedule_json"]))}
                         for j in jobs],
                "paused_jobs": [j["job_id"] for j in jobs if j["state"] == "PAUSED"],
                "harness": self.harness.gate().to_json() if (include_harness and self.harness is not None) else None}
