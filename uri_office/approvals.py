"""Save/apply and decline as A2UI confirmed actions (AC3), on the scheduler's pattern (uri_scheduler/a2ui_host.py).

`propose(...)` freezes the exact change set (target + every edit with its before/after + Google structural ops) into a
body, computes `change_sha256 = sha256(canonical(body))`, binds it into an `office_change` surface and stores it OPEN.
`action(msg, apply_fn)`:
  * loads the OPEN surface (owner check), runs `uri_a2ui.surface.check_action` (digest of the version shown, exact
    Button, bound hash), then re-checks the stored body's hash;
  * `office.apply_change` calls `apply_fn(body)`, which must re-read the target and refuse if its state differs from
    the shown "before" (file hash for local files, cell values for Google);
  * closes the surface in both cases, so the same approval can never be replayed;
  * the card shows the whole change set the hash binds (full values, every line, the full destination); a set too
    large for one card is refused, never shortened. A shown value that A2UI would refuse as a link (https://...,
    data:...) is shown as a JSON string with its colons written as \\u003a, which reads back to the exact value;
    anything the card still cannot show is refused as an OfficeError;
  * audits every outcome, refusals included, in a hash chain (`verify_chain`).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from uri_a2ui import catalog as C
from uri_a2ui.surface import ActionRefused, Surface, canonical, check_action
from uri_a2ui.validate import A2uiInvalid, u16

from .errors import OfficeError

GENESIS = "0" * 64
# What A2UI refuses as a link in text (uri_a2ui.validate._URLISH), without its word-boundary anchors, so it also
# catches a link that a split between card texts would expose.
_LINKISH = re.compile(r"(?i)(?:https?|ftp|file)://|(?:javascript|vbscript|data):\S")
FIXED_COMPONENTS = 6          # root, title, target, apply, reject, buttons; the rest of the catalog limit is for lines
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


def _quoted(s: str) -> str:
    """`s` as a JSON string. If it holds something A2UI refuses as a link, every ':' is written as the JSON escape
    \\u003a: the card cannot carry a link, and the shown text still decodes (json.loads) to exactly `s`."""
    q = json.dumps(s, ensure_ascii=False)
    return q.replace(":", "\\u003a") if _LINKISH.search(q) else q


def _shown(v) -> str:
    """The whole value, never shortened: the card shows everything the hash binds. Text is quoted (JSON), so a value
    with line breaks or ' -> ' in it cannot pass for another line of the card."""
    if not v:
        return "(empty)"
    if v.get("f"):
        f = v["f"]
        return f if f.isprintable() and not _LINKISH.search(f) else _quoted(f)
    x = v.get("v")
    if x is None or x == "":
        return "(empty)"
    return _quoted(x) if isinstance(x, str) else str(x)


CONTINUED = "... (continued) "


def _chunks(lines: list, limit: int) -> list:
    """Pack lines into texts of at most `limit` UTF-16 units (the unit the A2UI catalog counts), splitting a longer
    line between whole code points. Nothing is dropped. A text that continues a split line starts with CONTINUED, so
    the rest of a value can never pass for a line of its own."""
    out, cur, n = [], [], 0
    for line in lines:
        mid = False                                     # some of this line is already in a text
        for ch in line + "\n":
            w = 2 if ord(ch) > 0xFFFF else 1
            if n + w > limit:
                out.append("".join(cur))
                cur, n = ([CONTINUED], len(CONTINUED)) if mid else ([], 0)
            cur.append(ch)
            n += w
            mid = True
    if cur:
        out.append("".join(cur).rstrip("\n"))
    return [t for t in out if t]


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
        try:
            surface = self._surface(f"office.{workbook_id}.{uuid.uuid4().hex[:8]}", target, body, sha)
        except A2uiInvalid:
            raise OfficeError("CHANGE_CANNOT_BE_SHOWN", "this change set cannot be shown on an approval card", 422) \
                from None
        with self.lock:
            # One open approval per workbook: a newer one supersedes (closes) the older.
            for r in self.db.execute("SELECT surface_id FROM surface WHERE workbook_id=? AND state='OPEN'", (workbook_id,)):
                self._close(r["surface_id"])
                self.audit("office.approval_superseded", {"surface_id": r["surface_id"]})
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
        # The card shows the whole change set the hash binds (every edit with its full before/after, every structural
        # op, the full destination). A set too large for one card is refused, never shortened.
        lines = [f"{e['sheet']}!{e['cell']}: {_shown(e['before'])} -> {_shown(e['after'])}" for e in body["edits"]]
        lines += [" ".join(f"{k}={json.dumps(op[k], ensure_ascii=False)}" for k in sorted(op))
                  for op in body["struct_ops"]]
        if upload:
            lines = ["The saved file as it is on disk now (unsaved draft changes are not included) will be copied to "
                     "Google Drive. Only you can see it until you share it in Google."]
        label = str(target.get("label", ""))
        if u16(label) > C.MAX_STRING:
            raise OfficeError("CHANGE_TOO_LARGE_TO_SHOW", "the destination path is too long to show")
        texts = _chunks(lines, C.MAX_STRING)
        if len(texts) > C.MAX_COMPONENTS - FIXED_COMPONENTS:
            raise OfficeError("CHANGE_TOO_LARGE_TO_SHOW", "this change set is too large to show in full on one approval; "
                                                          "save in smaller steps", 413)
        comps = [
            {"id": "title", "component": "Text", "variant": "title",
             "text": ("Upload a copy of this file to your Google Drive as a Google Sheet?" if upload else
                      "Apply these changes to the Google Sheet?" if google else "Save these changes to the file?")},
            {"id": "target", "component": "Text", "variant": "caption", "text": label},
        ]
        kids = ["title", "target"]
        for i, text in enumerate(texts):
            comps.append({"id": f"lines{i}", "component": "Text", "variant": "body", "text": text})
            kids.append(f"lines{i}")
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

    def workbook_of(self, surface_id):
        """The workbook an approval belongs to (None if unknown), so the caller can take that workbook's lock before
        `action` takes this one: the lock order is always workbook lock, then approvals lock."""
        if not isinstance(surface_id, str):
            return None
        with self.lock:                                  # held briefly and released; never while taking another lock
            r = self.db.execute("SELECT workbook_id FROM surface WHERE surface_id=?", (surface_id,)).fetchone()
        return r["workbook_id"] if r else None

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
                if exc.code in ("TARGET_CHANGED", "STALE_CHANGE") and r is not None:
                    self._close(sid)
                raise
