"""Save/apply and decline as A2UI confirmed actions (AC3), on the scheduler's pattern (uri_scheduler/a2ui_host.py).

`propose(...)` freezes the exact change set (target + every edit with its before/after + Google structural ops) into a
body, computes `change_sha256 = sha256(canonical(body))`, binds it into an `office_change` surface and stores it OPEN.
`action(msg, apply_fn)`:
  * loads the OPEN surface (owner check), runs `uri_a2ui.surface.check_action` (digest of the version shown, exact
    Button, bound hash), then re-checks the stored body's hash;
  * `office.apply_change` calls `apply_fn(body)`, which must re-read the target and refuse if its state differs from
    the shown "before" (file hash for local files, cell values for Google);
  * closes the surface in both cases, so the same approval can never be replayed;
  * audits every outcome, refusals included, in a hash chain (`verify_chain`).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from uri_a2ui.surface import ActionRefused, Surface, canonical, check_action

from .errors import OfficeError

GENESIS = "0" * 64
MAX_LINES = 30
SCHEMA = """
CREATE TABLE IF NOT EXISTS surface(
  surface_id TEXT PRIMARY KEY, owner TEXT NOT NULL, workbook_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('OPEN','CLOSED')), record_json TEXT NOT NULL, body_json TEXT NOT NULL,
  change_sha256 TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS event(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
  prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
"""


def jdump(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _shown(v) -> str:
    if not v:
        return "(empty)"
    if v.get("f"):
        return v["f"]
    x = v.get("v")
    s = "(empty)" if x is None or x == "" else str(x)
    return s if len(s) <= 60 else s[:57] + "..."


class Approvals:
    def __init__(self, state_dir: Path, owner: str):
        self.owner = owner
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(Path(state_dir) / "office.db"), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- audit chain ---------------------------------------------------------------------------------------------
    def audit(self, kind: str, payload: dict):
        with self.lock:
            prev = self.db.execute("SELECT hash FROM event ORDER BY seq DESC LIMIT 1").fetchone()
            prev_hash = prev[0] if prev else GENESIS
            at = time.time()
            body = jdump({"at": at, "kind": kind, "payload": payload, "prev": prev_hash})
            h = hashlib.sha256(body.encode()).hexdigest()
            self.db.execute("INSERT INTO event(at,kind,payload_json,prev_hash,hash) VALUES (?,?,?,?,?)",
                            (at, kind, jdump(payload), prev_hash, h))

    def verify_chain(self) -> dict:
        prev, n = GENESIS, 0
        for r in self.db.execute("SELECT at,kind,payload_json,prev_hash,hash FROM event ORDER BY seq"):
            body = jdump({"at": r["at"], "kind": r["kind"], "payload": json.loads(r["payload_json"]), "prev": prev})
            if r["prev_hash"] != prev or hashlib.sha256(body.encode()).hexdigest() != r["hash"]:
                return {"ok": False, "broken_at": n}
            prev, n = r["hash"], n + 1
        return {"ok": True, "events": n}

    # ---- surfaces ------------------------------------------------------------------------------------------------
    def propose(self, workbook_id: str, target: dict, pending: dict) -> Surface:
        if not pending["edits"] and not pending["struct_ops"] and target.get("kind") != "google_upload":
            raise OfficeError("NOTHING_TO_SAVE", "there are no accepted or typed changes")
        body = {"workbook_id": workbook_id, "target": target, "edits": pending["edits"],
                "struct_ops": pending["struct_ops"]}
        sha = hashlib.sha256(canonical(body)).hexdigest()
        with self.lock:
            # One open approval per workbook: a newer one supersedes (closes) the older.
            for r in self.db.execute("SELECT surface_id FROM surface WHERE workbook_id=? AND state='OPEN'", (workbook_id,)):
                self._close(r["surface_id"])
                self.audit("office.approval_superseded", {"surface_id": r["surface_id"]})
            surface = self._surface(f"office.{workbook_id}.{uuid.uuid4().hex[:8]}", target, body, sha)
            now = time.time()
            self.db.execute("INSERT INTO surface VALUES (?,?,?,?,?,?,?,?,?)",
                            (surface.surface_id, self.owner, workbook_id, "OPEN", jdump(surface.to_record()),
                             jdump(body), sha, now, now))
            self.audit("office.approval_proposed", {"surface_id": surface.surface_id, "change_sha256": sha,
                                                    "cells": len(body["edits"]), "struct_ops": len(body["struct_ops"])})
        return surface

    def _surface(self, sid, target, body, sha) -> Surface:
        google = target.get("kind") == "google"
        upload = target.get("kind") == "google_upload"
        lines = []
        for e in body["edits"][:MAX_LINES]:
            lines.append(f"{e['sheet']}!{e['cell']}: {_shown(e['before'])} -> {_shown(e['after'])}")
        for op in body["struct_ops"][:MAX_LINES]:
            lines.append(" ".join(f"{k}={op[k]}" for k in sorted(op)))
        more = len(body["edits"]) + len(body["struct_ops"]) - len(lines)
        comps = [
            {"id": "title", "component": "Text", "variant": "title",
             "text": ("Upload a copy of this file to your Google Drive as a Google Sheet?" if upload else
                      "Apply these changes to the Google Sheet?" if google else "Save these changes to the file?")},
            {"id": "target", "component": "Text", "variant": "caption", "text": str(target.get("label", ""))[:300]},
            {"id": "lines", "component": "Text", "variant": "body", "text": "\n".join(lines)[:3900]},
        ]
        if upload:
            comps[2]["text"] = ("The saved file as it is on disk now (unsaved draft changes are not included) will be "
                                "copied to Google Drive. Only you can see it until you share it in Google.")
        kids = ["title", "target", "lines"]
        if more > 0:
            comps.append({"id": "more", "component": "Text", "variant": "caption", "text": f"... and {more} more"})
            kids.append("more")
        bind = {"change_sha256": {"path": "/bound/change_sha256"}}
        comps += [
            {"id": "apply", "component": "Button", "variant": "primary",
             "label": "Upload to Google Drive" if upload else "Apply to Google Sheet" if google else "Save to file",
             "action": {"event": {"name": "office.apply_change", "context": bind}}},
            {"id": "reject", "component": "Button", "variant": "secondary", "label": "Not now",
             "action": {"event": {"name": "office.reject_change", "context": bind}}},
            {"id": "buttons", "component": "Row", "children": ["apply", "reject"], "gap": "small"},
        ]
        kids.append("buttons")
        comps.insert(0, {"id": "root", "component": "Column", "children": kids, "gap": "medium"})
        return Surface(sid, "office_change", comps, data={}, bound={"change_sha256": sha},
                       actions=("office.apply_change", "office.reject_change"), placement="workspace",
                       title="Office change")

    def _close(self, sid):
        self.db.execute("UPDATE surface SET state='CLOSED', updated_at=? WHERE surface_id=?", (time.time(), sid))

    def open_messages(self, workbook_id=None) -> list:
        q = "SELECT record_json FROM surface WHERE owner=? AND state='OPEN'"
        args = [self.owner]
        if workbook_id:
            q += " AND workbook_id=?"
            args.append(workbook_id)
        out = []
        for r in self.db.execute(q + " ORDER BY created_at", args):
            out += Surface.from_record(json.loads(r["record_json"])).messages()
        return out

    def close_workbook(self, workbook_id):
        with self.lock:
            self.db.execute("UPDATE surface SET state='CLOSED', updated_at=? WHERE workbook_id=? AND state='OPEN'",
                            (time.time(), workbook_id))

    def action(self, msg: dict, apply_fn) -> dict:
        """Gate one client action message. `apply_fn(body)` performs the write after every check passed."""
        with self.lock:
            sid = msg.get("surfaceId") if isinstance(msg, dict) else None
            r = self.db.execute("SELECT * FROM surface WHERE surface_id=?", (sid,)).fetchone() \
                if isinstance(sid, str) else None
            try:
                if r is None or r["state"] != "OPEN":
                    raise OfficeError("UNKNOWN_SURFACE", "this approval is closed or does not exist")
                if r["owner"] != self.owner:
                    raise OfficeError("NOT_OWNER", "", 403)
                surface = Surface.from_record(json.loads(r["record_json"]))
                try:
                    ctx = check_action(surface, msg)
                except ActionRefused as exc:
                    raise OfficeError(exc.code, exc.detail) from None
                body = json.loads(r["body_json"])
                if hashlib.sha256(canonical(body)).hexdigest() != r["change_sha256"] or \
                        ctx["change_sha256"] != r["change_sha256"]:
                    raise OfficeError("CHANGE_MISMATCH", "the change differs from what was shown")
                if msg["name"] == "office.reject_change":
                    self._close(sid)
                    self.audit("office.approval_declined", {"surface_id": sid, "change_sha256": r["change_sha256"]})
                    return {"status": "declined", "workbook_id": r["workbook_id"]}
                result = apply_fn(body)
                self._close(sid)
                self.audit("office.change_applied", {"surface_id": sid, "change_sha256": r["change_sha256"],
                                                     "cells": len(body["edits"]), "struct_ops": len(body["struct_ops"])})
                return {"status": "applied", "workbook_id": r["workbook_id"], **(result or {})}
            except OfficeError as exc:
                self.audit("office.action_refused", {"surface_id": sid if isinstance(sid, str) else None,
                                                     "code": exc.code})
                if exc.code in ("TARGET_CHANGED",) and r is not None:
                    self._close(sid)
                raise
