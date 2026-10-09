"""Scheduler-domain A2UI producer and action gate (docs/a2ui/A2UI_ARCHITECTURE.md).

The scheduler is the authority for its own capabilities, so it builds the surfaces for them from its own validated
state, through the generic `uri_a2ui` contract:

  schedule_proposal  an interpreted festival-schedule request shown as an editable proposal; revise / confirm / discard
  schedule_status    what was activated (after an explicit confirm)
  artifact_review    one candidate GIF (bytes re-verified by SHA-256 in the renderer) with approve / refine /
                     regenerate / reject, each bound to the artifact's SHA-256
  calendar_review    festival calendar records with their sources; correct a date, dispute or accept a record

Every action passes `uri_a2ui.surface.check_action` (digest of the version shown, the exact Button, declared literals,
bound values) and then the engine's own checks (owner, proposal hash, artifact hash on disk). Surfaces persist in the
scheduler database; every action is audited in the hash chain (`a2ui.action`). Nothing here can publish or send.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date

from uri_a2ui.surface import ActionRefused, Surface, check_action
from uri_a2ui.validate import A2uiInvalid, lone_surrogate

from . import timespec
from .engine import SchedulerError
from .store import jdump

CAL = "in_festivals"
OFFSETS = ("1", "2", "3", "5", "7")
_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
MAX_ASSUMPTIONS = 6
DEFAULT_SELECTION = ("holi", "ram_navami", "mahavir_jayanti", "buddha_purnima", "eid_ul_fitr", "eid_ul_zuha",
                     "janmashtami", "dussehra", "diwali", "guru_nanak_jayanti", "christmas", "milad_un_nabi")
SCHEMA = """
CREATE TABLE IF NOT EXISTS a2ui_surface(
  surface_id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('OPEN','CLOSED')),
  record_json TEXT NOT NULL, created_at_us INTEGER NOT NULL, updated_at_us INTEGER NOT NULL);
"""


class A2uiHostError(Exception):
    def __init__(self, code, detail=""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def _t(i, text, variant="body"):
    return {"id": i, "component": "Text", "text": text, "variant": variant}


def _btn(i, label, name, context=None, variant="secondary"):
    return {"id": i, "component": "Button", "label": label, "variant": variant,
            "action": {"event": {"name": name, "context": context or {}}}}


class SchedulerA2ui:
    def __init__(self, sched, owner):
        self.s, self.owner = sched, owner
        with self.s.store._lock:
            self.s.store.db.executescript(SCHEMA)

    # ---- persistence ----------------------------------------------------------------------------------------------
    def _save(self, surface: Surface, state="OPEN"):
        now = self.s.now()
        with self.s.store.tx() as db:
            db.execute("INSERT INTO a2ui_surface(surface_id,owner,kind,state,record_json,created_at_us,updated_at_us) "
                       "VALUES (?,?,?,?,?,?,?) ON CONFLICT(surface_id) DO UPDATE SET state=excluded.state, "
                       "record_json=excluded.record_json, updated_at_us=excluded.updated_at_us",
                       (surface.surface_id, self.owner, surface.kind, state, jdump(surface.to_record()), now, now))

    def _load(self, surface_id) -> Surface:
        r = self.s.store.q1("SELECT owner, state, record_json FROM a2ui_surface WHERE surface_id=?", (surface_id,))
        if r is None or r["state"] != "OPEN":
            raise A2uiHostError("UNKNOWN_SURFACE", surface_id)
        if r["owner"] != self.owner:
            raise A2uiHostError("NOT_OWNER", surface_id)
        surface = self._reconcile(Surface.from_record(json.loads(r["record_json"])))
        if surface is None:
            raise A2uiHostError("UNKNOWN_SURFACE", surface_id)
        return surface

    def _reconcile(self, surface):
        """The authority's state wins over a stored surface (A2UI r5, R5-2): an engine transition whose surface update was
        not stored (e.g. a storage failure between the two transactions) is reflected the next time the surface is used.
        A proposal surface whose job is ACTIVE becomes the status surface; one whose job is CANCELLED is closed. Returns
        the current surface, or None when it was closed."""
        if surface.kind != "schedule_proposal":
            return surface
        try:
            job = self.s.job(surface.bound["job_id"])
        except SchedulerError:
            self._save(surface, state="CLOSED")
            return None
        if job["state"] == "PROPOSED":
            return surface
        if job["state"] in ("ACTIVE", "PAUSED"):
            new = self._status_surface(surface, job)
            self._save(new)
            return new
        self._save(surface, state="CLOSED")
        return None

    def open_messages(self) -> list:
        """Every open surface, re-rendered from the stored record (after a UI or scheduler restart)."""
        self.sync_reviews()
        out = []
        with self.s._mutex:
            for r in self.s.store.q("SELECT record_json FROM a2ui_surface WHERE owner=? AND state='OPEN' ORDER BY "
                                    "created_at_us", (self.owner,)):
                current = self._reconcile(Surface.from_record(json.loads(r["record_json"])))
                if current is not None:
                    out += current.messages()
        return out

    # ---- schedule proposal ----------------------------------------------------------------------------------------
    def _festival_options(self):
        today = date.fromtimestamp(self.s.now() / 1e6).isoformat()
        nxt = {}
        for r in self.s.calendar.records(CAL):
            if r["status"] == "published" and r["greeting_appropriate"] and r["start"] >= today:
                nxt.setdefault(r["festival_key"], r)
        rows = sorted(nxt.values(), key=lambda r: (r["regions"] != ["national"], r["start"]))
        return [{"label": f"{r['name']} · next {r['start']}" + ("" if "national" in r["regions"] else f" · {', '.join(r['regions'])}"),
                 "value": r["festival_key"]} for r in rows][:80]

    def _check_request(self, req) -> dict:
        if not isinstance(req, dict):
            raise A2uiHostError("BAD_REQUEST")
        known = {o["value"] for o in self._festival_options()}
        sel = req.get("festivals")
        if sel is None:
            sel = list(DEFAULT_SELECTION)
        if not isinstance(sel, list) or not sel or len(sel) > 80 or not all(isinstance(k, str) for k in sel):
            raise A2uiHostError("BAD_SELECTION")
        greeting = {f["festival_key"]: f["name"] for f in self.s.calendar.festivals(CAL) if f.get("greeting_appropriate", True)}
        unknown = [k for k in sel if k not in greeting]
        if unknown:
            raise A2uiHostError("UNKNOWN_FESTIVAL", ",".join(unknown[:5]))
        # A known festival without a dated occurrence in the coming year (e.g. a Sikkim festival whose 2026 date has
        # passed and whose 2027 date is not notified) is left out and said so, instead of refusing the whole request.
        undated = [k for k in sel if k not in known]
        sel = [k for k in sel if k in known]
        if not sel:
            raise A2uiHostError("NO_UPCOMING_FESTIVAL", ",".join(undated[:5]))
        tm = req.get("time") or "09:00"
        off = str(req.get("offset_days", 2))
        if not (isinstance(tm, str) and _TIME.match(tm)) or off not in OFFSETS:
            raise A2uiHostError("BAD_TIME_OR_OFFSET")
        assumptions = req.get("assumptions") or []
        if not isinstance(assumptions, list) or len(assumptions) > MAX_ASSUMPTIONS or \
                not all(isinstance(a, str) and len(a) <= 300 and not lone_surrogate(a) for a in assumptions):
            raise A2uiHostError("BAD_ASSUMPTIONS")
        if undated:
            note = "No dated occurrence in the coming year, so not included: " + ", ".join(greeting[k] for k in undated) + "."
            assumptions = (assumptions + [note[:300]])[:MAX_ASSUMPTIONS]
        return {"festivals": sorted(set(sel), key=sel.index), "time": tm, "offset_days": int(off),
                "assumptions": assumptions}

    def _propose_job(self, req):
        sched = {"kind": "calendar_relative", "calendar": CAL, "selection": req["festivals"],
                 "offset_days": -req["offset_days"], "time": req["time"], "tz": "Asia/Kolkata"}
        return self.s.propose(owner=self.owner, title=f"Festival greeting GIF, {req['offset_days']} day(s) before each "
                              "selected festival", template_id="festival_gif.v1", params={}, schedule=sched)

    def _readable(self, interpretation, keys):
        """The engine's interpretation with festival keys replaced by their calendar names (display only)."""
        names = {f["festival_key"]: f["name"] for f in self.s.calendar.festivals(CAL)}
        listed = ", ".join(names.get(k, k) for k in sorted(set(keys), key=lambda k: names.get(k, k)))
        head = interpretation.rsplit(": ", 1)[0] if ": " in interpretation else interpretation
        head = head.replace("each selected event in 'in_festivals'", "each selected festival")
        return f"{head}: {listed}"

    def _proposal_surface(self, surface_id, req, prop, revision=1) -> Surface:
        rows = prop["upcoming"]
        lines = [f"• {r.get('festival', r['key'])} {r.get('festival_date', '')}: GIF {r['due_local'].replace('T', ' ')[:16]} IST"
                 for r in rows[:8]]
        more = len(rows) - len(lines)
        excluded = [f"{x['festival_key']} {x['date']} ({x['status']})" for x in prop.get("excluded", [])]
        kids = ["title", "interp"]
        comps = [_t("title", "Festival greeting GIFs: proposed schedule", "title"),
                 _t("interp", self._readable(prop["interpretation"], req["festivals"]))]
        if req["assumptions"]:
            comps.append(_t("assumptions", "I assumed: " + " ".join(req["assumptions"]), "caption"))
            kids.append("assumptions")
        comps += [_t("upcoming_hdr", f"Next runs ({len(rows)} in the coming year)", "label"),
                  _t("upcoming", "\n".join(lines) + (f"\n… and {more} more" if more > 0 else "") if lines else
                     "No festival in the selection falls in the coming year.")]
        kids += ["upcoming_hdr", "upcoming"]
        if excluded:
            comps.append(_t("excluded", "Not scheduled until confirmed: " + "; ".join(excluded[:10]), "caption"))
            kids.append("excluded")
        comps += [
            {"id": "picker", "component": "ChoicePicker", "label": "Festivals", "multiple": True,
             "value": {"path": "/draft/selection"}, "options": self._festival_options()},
            {"id": "time", "component": "DateTimeInput", "label": "Time (Asia/Kolkata)", "mode": "time",
             "value": {"path": "/draft/time"}},
            {"id": "offset", "component": "ChoicePicker", "label": "Days before the festival", "multiple": False,
             "value": {"path": "/draft/offset"}, "options": [{"label": f"{o} day" + ("s" if o != "1" else ""), "value": o}
                                                             for o in OFFSETS]},
            _t("safety", "Nothing runs until you confirm. Each GIF waits for your approval; nothing is posted or sent.",
               "caption"),
            _btn("revise", "Update proposal", "scheduler.revise_proposal",
                 {"selection": {"path": "/draft/selection"}, "time": {"path": "/draft/time"},
                  "offset_days": {"path": "/draft/offset"}}),
            _btn("confirm", "Confirm schedule", "scheduler.confirm_proposal",
                 {"proposal_sha256": {"path": "/bound/proposal_sha256"}, "selection": {"path": "/draft/selection"},
                  "time": {"path": "/draft/time"}, "offset_days": {"path": "/draft/offset"}}, "primary"),
            _btn("discard", "Discard", "scheduler.discard_proposal"),
            {"id": "buttons", "component": "Row", "children": ["revise", "confirm", "discard"], "gap": "small"},
        ]
        kids += ["picker", "time", "offset", "safety", "buttons"]
        comps.insert(0, {"id": "root", "component": "Column", "children": kids, "gap": "medium"})
        return Surface(surface_id, "schedule_proposal", comps,
                       data={"draft": {"selection": req["festivals"], "time": req["time"], "offset": str(req["offset_days"])}},
                       bound={"proposal_sha256": prop["proposal_sha256"], "job_id": prop["job_id"],
                              "request": {k: req[k] for k in ("festivals", "time", "offset_days")}},
                       actions=("scheduler.revise_proposal", "scheduler.confirm_proposal", "scheduler.discard_proposal"),
                       placement="companion", title="Festival GIF schedule", revision=revision)

    def propose_from_request(self, req) -> dict:
        """An interpreted scheduling request (from intent discovery) becomes a PROPOSED job and its proposal surface."""
        req = self._check_request(req)
        with self.s._mutex:
            prop = self._propose_job(req)
            try:
                surface = self._proposal_surface("sched-" + uuid.uuid4().hex[:12], req, prop)
                self._save(surface)
            except Exception:
                # No orphan: a proposal whose surface cannot be built or stored is withdrawn at once (A2UI r4, R4-1).
                self.s.cancel_job(prop["job_id"], self.owner)
                raise
        return {"surface_id": surface.surface_id, "messages": surface.messages(), "job_id": prop["job_id"]}

    # ---- artifact review ------------------------------------------------------------------------------------------
    def _review_surface(self, row, art) -> Surface:
        info = art.get("info") or {}
        params = (self.s.job(row["job_id"]).get("params") or {}).get("festival") or {}
        fest = (row.get("meta") or {}).get("festival") or params.get("name") or row["occurrence_key"]
        att = self.s.store.q1("SELECT mode FROM attempt WHERE attempt_id=?", (art["attempt_id"],))
        mode = (att["mode"] if att else "").upper()
        comps = [
            {"id": "root", "component": "Column", "children": ["title", "mode", "image", "concept", "instr", "safety",
                                                               "buttons"], "gap": "medium"},
            _t("title", f"Review: {fest} GIF, version {art['version']}", "title"),
            {"id": "mode", "component": "Badge", "text": "Synthetic fixture output" if mode == "FIXTURE" else
             ("Made by Claude" if mode == "LIVE" else "Origin not recorded"), "tone": "warning" if mode != "LIVE" else "accent"},
            {"id": "image", "component": "ArtifactImage", "artifactId": int(art["artifact_id"]), "sha256": art["sha256"],
             "caption": f"{art['bytes']} bytes, SHA-256 {art['sha256'][:12]}…"},
            _t("concept", (art.get("concept") or "")[:1500] or "No concept note."),
            {"id": "instr", "component": "TextField", "label": "What should change? (for Refine)", "maxLength": 1000,
             "multiline": True, "value": {"path": "/draft/instruction"}},
            _t("safety", "Approving keeps the GIF for you; it is never posted or sent.", "caption"),
            _btn("approve", "Approve", "scheduler.review_artifact",
                 {"artifact_sha256": {"path": "/bound/artifact_sha256"}, "decision": "approve"}, "primary"),
            _btn("refine", "Refine", "scheduler.refine_artifact",
                 {"artifact_sha256": {"path": "/bound/artifact_sha256"}, "instruction": {"path": "/draft/instruction"}}),
            _btn("regenerate", "Regenerate", "scheduler.review_artifact",
                 {"artifact_sha256": {"path": "/bound/artifact_sha256"}, "decision": "regenerate"}),
            _btn("reject", "Reject", "scheduler.review_artifact",
                 {"artifact_sha256": {"path": "/bound/artifact_sha256"}, "decision": "reject"}, "danger"),
            {"id": "buttons", "component": "Row", "children": ["approve", "refine", "regenerate", "reject"], "gap": "small"},
        ]
        return Surface(f"review-{int(art['artifact_id'])}", "artifact_review", comps, data={"draft": {"instruction": ""}},
                       bound={"artifact_sha256": art["sha256"], "artifact_id": int(art["artifact_id"]), "occ_id": row["occ_id"]},
                       actions=("scheduler.review_artifact", "scheduler.refine_artifact"), placement="workspace",
                       title=f"{fest} GIF v{art['version']}")

    def sync_reviews(self):
        """One open review surface per candidate artifact awaiting the owner; closed when no longer reviewable."""
        ov = self.s.overview(owner=self.owner, include_harness=False)
        live = set()
        for row in ov["pending_approvals"]:
            for art in row["candidates"]:
                sid = f"review-{int(art['artifact_id'])}"
                live.add(sid)
                r = self.s.store.q1("SELECT state FROM a2ui_surface WHERE surface_id=?", (sid,))
                if r is None:
                    self._save(self._review_surface(row, art))
        for r in self.s.store.q("SELECT surface_id, record_json FROM a2ui_surface WHERE owner=? AND kind='artifact_review' "
                                "AND state='OPEN'", (self.owner,)):
            if r["surface_id"] not in live:
                self._save(Surface.from_record(json.loads(r["record_json"])), state="CLOSED")

    # ---- calendar review ------------------------------------------------------------------------------------------
    def calendar_surface(self) -> dict:
        today = date.fromtimestamp(self.s.now() / 1e6).isoformat()
        recs = [r for r in self.s.calendar.records(CAL) if r["start"] >= today][:80]
        opts = [{"label": f"{r['start']} · {r['name']} · {r['status']} · {r['source']['verification'] or ''}",
                 "value": f"{r['festival_key']}:{r['year']}"} for r in recs]
        comps = [
            {"id": "root", "component": "Column", "children": ["title", "about", "record", "start", "note", "safety", "buttons"],
             "gap": "medium"},
            _t("title", "Festival calendar: review and correct", "title"),
            _t("about", f"Calendar {self.s.calendar.version(CAL)}. Every date was read from a government notification; "
               "the source of each record is shown in the list.", "caption"),
            {"id": "record", "component": "ChoicePicker", "label": "Record", "multiple": False,
             "value": {"path": "/draft/record"}, "options": opts or [{"label": "No upcoming record", "value": "none"}]},
            {"id": "start", "component": "DateTimeInput", "label": "Correct date (for Correct date)", "mode": "date",
             "value": {"path": "/draft/start"}},
            {"id": "note", "component": "TextField", "label": "Note", "maxLength": 300, "value": {"path": "/draft/note"}},
            _t("safety", "A corrected or restored date never runs before you confirm it in the schedule.", "caption"),
            _btn("set_date", "Correct date", "calendar.correct_record",
                 {"record": {"path": "/draft/record"}, "start": {"path": "/draft/start"}, "note": {"path": "/draft/note"},
                  "correction": "set_date"}, "primary"),
            _btn("dispute", "Mark disputed", "calendar.correct_record",
                 {"record": {"path": "/draft/record"}, "note": {"path": "/draft/note"}, "correction": "dispute"}, "danger"),
            _btn("accept", "Accept", "calendar.correct_record",
                 {"record": {"path": "/draft/record"}, "note": {"path": "/draft/note"}, "correction": "accept"}),
            {"id": "buttons", "component": "Row", "children": ["set_date", "dispute", "accept"], "gap": "small"},
        ]
        first = opts[0]["value"] if opts else "none"
        s = Surface("calendar-review", "calendar_review", comps,
                    data={"draft": {"record": first, "start": "", "note": ""}},
                    bound={"calendar_version": self.s.calendar.version(CAL)}, actions=("calendar.correct_record",),
                    placement="workspace", title="Festival calendar", revision=self._next_revision("calendar-review"))
        self._save(s)
        return {"surface_id": s.surface_id, "messages": s.messages()}

    def _next_revision(self, surface_id):
        r = self.s.store.q1("SELECT record_json FROM a2ui_surface WHERE surface_id=?", (surface_id,))
        return (json.loads(r["record_json"])["revision"] + 1) if r else 1

    # ---- actions --------------------------------------------------------------------------------------------------
    def action(self, msg) -> dict:
        """One client `action`. Returns {"result", "messages"}; refusals raise A2uiHostError with a stable code."""
        if not isinstance(msg, dict) or not isinstance(msg.get("surfaceId"), str):
            raise A2uiHostError("BAD_ACTION_MESSAGE")
        # Hostile identifiers are refused before anything is looked up or audited (A2UI r4, R4-2).
        if any(not isinstance(msg.get(k), str) or len(msg[k]) > 128 or lone_surrogate(msg[k])
               for k in ("surfaceId", "name", "sourceComponentId")):
            raise A2uiHostError("BAD_ACTION_MESSAGE")
        # The whole action (surface load, gate, state checks, engine call, surface update) is one critical section
        # under the engine mutex: no concurrent action, tick or reconciliation can interleave (A2UI r1, F2).
        with self.s._mutex:
            return self._action_locked(msg)

    def _action_locked(self, msg) -> dict:
        surface = self._load(msg["surfaceId"])
        try:
            ctx = check_action(surface, msg)
        except ActionRefused as exc:
            self._audit(surface, msg, exc.code)
            raise A2uiHostError(exc.code, exc.detail) from None
        name = msg["name"]
        try:
            out = getattr(self, "_do_" + name.split(".")[1])(surface, ctx)
        except SchedulerError as exc:
            self._audit(surface, msg, exc.code)
            raise A2uiHostError(exc.code, str(exc.detail or "")) from None
        except A2uiHostError as exc:
            self._audit(surface, msg, exc.code)
            raise
        self._audit(surface, msg, "OK")
        return out

    def _audit(self, surface, msg, code):
        with self.s.store.tx() as db:
            self.s.store.emit(db, "a2ui.action", payload={"surface_id": surface.surface_id, "kind": surface.kind,
                                                          "revision": surface.revision, "digest": surface.digest,
                                                          "name": str(msg.get("name"))[:64],
                                                          "component": str(msg.get("sourceComponentId"))[:64],
                                                          "result": code})

    def _do_revise_proposal(self, surface, ctx):
        req = self._check_request({"festivals": ctx["selection"], "time": ctx["time"], "offset_days": ctx["offset_days"],
                                   "assumptions": []})
        old = surface.bound["request"]
        if _norm(req) == _norm(old):
            return {"result": "UNCHANGED", "messages": surface.messages()}
        prop = self._propose_job(req)
        try:
            new = self._proposal_surface(surface.surface_id, req, prop, revision=surface.revision + 1)
            self._save(new)
        except Exception:
            self.s.cancel_job(prop["job_id"], self.owner)       # the shown surface still names the old proposal
            raise
        # Only after the new surface is stored is the superseded proposal withdrawn (A2UI r5, R5-2). If this step fails,
        # the old proposal stays PROPOSED: inert (a PROPOSED job never runs) and closed by reconciliation below.
        if self.s.job(surface.bound["job_id"])["state"] == "PROPOSED":
            self.s.cancel_job(surface.bound["job_id"], self.owner)
        return {"result": "REVISED", "job_id": prop["job_id"], "messages": new.messages()[1:]}

    def _status_surface(self, surface, job) -> Surface:
        """What was activated, built from the engine's job record (also used to reconcile after a failed save)."""
        gate = self.s.harness.gate().to_json() if self.s.harness is not None else {"available": False, "code": "NO_HARNESS"}
        nxt = self.s.store.q("SELECT occurrence_key, due_at_us, state FROM occurrence WHERE job_id=? ORDER BY due_at_us LIMIT 3",
                             (job["job_id"],))
        lines = [f"• {r['occurrence_key']}: {timespec_local(r['due_at_us'])} ({r['state'].lower().replace('_', ' ')})" for r in nxt]
        comps = [
            {"id": "root", "component": "Column", "children": ["title", "state", "interp", "next", "harness", "dismiss"],
             "gap": "medium"},
            _t("title", "Festival GIF schedule is active", "title"),
            {"id": "state", "component": "Badge", "text": "Active", "tone": "success"},
            _t("interp", self._readable(timespec.describe(job["schedule"]), job["schedule"].get("selection", []))),
            _t("next", "\n".join(lines) or "No run in the coming year."),
            {"id": "harness", "component": "Badge", "tone": "success" if gate.get("available") else "warning",
             "text": "Claude is ready" if gate.get("available") else
             f"Claude is not available ({gate.get('code')}): runs wait and are shown as blocked; no other provider is used"},
            _btn("dismiss", "Done", "surface.dismiss"),
        ]
        new = Surface(surface.surface_id, "schedule_status", comps, bound={"job_id": job["job_id"]},
                      actions=("surface.dismiss",), placement="companion", title="Festival GIF schedule",
                      revision=surface.revision + 1)
        return new

    def _do_confirm_proposal(self, surface, ctx):
        old = surface.bound["request"]
        drafted = {"festivals": ctx["selection"], "time": ctx["time"], "offset_days": int(ctx["offset_days"])}
        if _norm(drafted) != _norm(old):
            raise A2uiHostError("DRAFT_CHANGED", "update the proposal before confirming the changed choices")
        job = self.s.confirm(surface.bound["job_id"], self.owner, ctx["proposal_sha256"])
        new = self._status_surface(surface, job)
        self._save(new)
        return {"result": "ACTIVATED", "job_id": job["job_id"], "messages": new.messages()[1:]}

    def _do_discard_proposal(self, surface, ctx):
        if self.s.job(surface.bound["job_id"])["state"] == "PROPOSED":
            self.s.cancel_job(surface.bound["job_id"], self.owner)
        self._save(surface, state="CLOSED")
        return {"result": "DISCARDED", "messages": [surface.delete_message()]}

    def _do_dismiss(self, surface, ctx):
        self._save(surface, state="CLOSED")
        return {"result": "DISMISSED", "messages": [surface.delete_message()]}

    def _review(self, surface, decision, instruction=None):
        r = self.s.review(surface.bound["artifact_id"], self.owner, decision, expected_sha256=surface.bound["artifact_sha256"],
                          instruction=instruction)
        self._save(surface, state="CLOSED")
        return {"result": decision.upper(), "occurrence_state": r["occurrence"]["state"],
                "messages": [surface.delete_message()]}

    def _do_review_artifact(self, surface, ctx):
        return self._review(surface, ctx["decision"])

    def _do_refine_artifact(self, surface, ctx):
        if not (ctx.get("instruction") or "").strip():
            raise A2uiHostError("INSTRUCTION_REQUIRED", "say what should change")
        return self._review(surface, "refine", ctx["instruction"].strip())

    def _do_correct_record(self, surface, ctx):
        rec = ctx["record"]
        m = re.match(r"^([a-z][a-z0-9_]{0,63}):(\d{4})$", rec or "")
        if not m:
            raise A2uiHostError("BAD_RECORD", str(rec)[:80])
        kind = ctx["correction"]
        if kind == "set_date" and not ctx.get("start"):
            raise A2uiHostError("DATE_REQUIRED", "pick the corrected date")
        r = self.s.correct_calendar(self.owner, CAL, m.group(1), int(m.group(2)), kind,
                                    start=ctx.get("start") if kind == "set_date" else None, note=ctx.get("note") or "")
        out = self.calendar_surface()
        return {"result": "CORRECTED", "version": r["version"],
                "reconcile": {k: v for k, v in r["reconcile"].items()}, "messages": out["messages"][1:]}


def _norm(req):
    return (sorted(set(req["festivals"])), req["time"], int(req["offset_days"]))


def timespec_local(us):
    from .engine import _local
    return (_local(us, "Asia/Kolkata") or "").replace("T", " ")[:16] + " IST"


__all__ = ["SchedulerA2ui", "A2uiHostError", "A2uiInvalid"]
