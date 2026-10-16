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


# O2 (plan rev 3.1 §5.1): one table and one chain for every approval subject. The bound hash is stored in the
# `change_sha256` column for every kind; each action reads it from its own context key.
SUBJECT_KINDS = ("workbook", "plan", "output_files", "print_job")
HASH_KEY = {"office.apply_change": "change_sha256", "office.reject_change": "change_sha256",
            "office.run_plan": "plan_sha256", "office.discard_plan": "plan_sha256"}
DECLINE_ACTIONS = ("office.reject_change", "office.discard_plan")


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
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(surface)")}
        if "subject_kind" not in cols:                   # existing M1/M2 databases: their rows stay 'workbook'
            self.db.execute("ALTER TABLE surface ADD COLUMN subject_kind TEXT NOT NULL DEFAULT 'workbook'")

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
            self._insert(surface, workbook_id, "workbook", body, sha, now)
            self.audit("office.approval_proposed", {"surface_id": surface.surface_id, "change_sha256": sha,
                                                    "cells": len(body["edits"]), "struct_ops": len(body["struct_ops"])})
        return surface

    def _insert(self, surface, subject_id, subject_kind, body, sha, now):
        self.db.execute("INSERT INTO surface (surface_id, owner, workbook_id, state, record_json, body_json, "
                        "change_sha256, created_at, updated_at, subject_kind) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (surface.surface_id, self.owner, subject_id, "OPEN", jdump(surface.to_record()), jdump(body),
                         sha, now, now, subject_kind))

    def _propose_subject(self, subject_id, subject_kind, body, surface_fn, audit_extra) -> Surface:
        sha = hashlib.sha256(canonical(body)).hexdigest()
        try:
            surface = surface_fn(f"office.{subject_kind}.{subject_id}.{uuid.uuid4().hex[:8]}", sha)
        except A2uiInvalid:
            raise OfficeError("CHANGE_CANNOT_BE_SHOWN", "this card cannot be shown", 422) from None
        with self.lock:
            for r in self.db.execute("SELECT surface_id FROM surface WHERE workbook_id=? AND state='OPEN'",
                                     (subject_id,)):
                self._close(r["surface_id"])
                self.audit("office.approval_superseded", {"surface_id": r["surface_id"]})
            self._insert(surface, subject_id, subject_kind, body, sha, time.time())
            self.audit("office.approval_proposed", {"surface_id": surface.surface_id, "change_sha256": sha,
                                                    "subject_kind": subject_kind, **audit_extra})
        return surface

    def propose_plan(self, workflow_id: str, plan: dict) -> Surface:
        """The plan card (`office.run_plan`). `plan`: capability, title, steps [{id, kind, label}], inputs
        [{name, kind, sha256}], outputs [{name, kind}]. The hash binds all of it plus the originals statement."""
        body = {"subject_kind": "plan", "workflow_id": workflow_id, "target": {"kind": "plan"}, "plan": plan,
                "statement": "Your original files will not change."}

        def card(sid, sha):
            kind_label = {"D": "Rule-based", "E": "Engine", "B": "URI-written"}
            lines = [f"{i}. {s['label']} ({kind_label[s['kind']]})" for i, s in enumerate(plan["steps"], 1)]
            lines.append("Reads: " + ", ".join(_quoted(x["name"]) for x in plan["inputs"]))
            lines.append("Makes: " + ", ".join(_quoted(x["name"]) for x in plan["outputs"]) if plan["outputs"]
                         else "Makes: nothing new")
            lines.append(body["statement"])
            return self._card(sid, plan["title"], "", lines, "Run", "Not now", "office.run_plan",
                              "office.discard_plan", "plan_sha256", sha, "office_plan", "Office plan")
        return self._propose_subject(workflow_id, "plan", body, card, {"steps": len(plan["steps"])})

    def propose_outputs(self, workflow_id: str, outputs: list, destination: str, warnings: list,
                        warnings_accepted: bool) -> Surface:
        """The output card (`office.apply_change` on an `output_files` subject). Binds each output (name, size, pages,
        SHA-256), every warning, the acceptance flag and the full destination."""
        body = {"subject_kind": "output_files", "workflow_id": workflow_id,
                "target": {"kind": "output_files", "destination": destination}, "outputs": outputs,
                "warnings": warnings, "warnings_accepted": warnings_accepted,
                "statement": "Your original files will not change."}

        def card(sid, sha):
            if u16(destination) > C.MAX_STRING:
                raise OfficeError("CHANGE_TOO_LARGE_TO_SHOW", "the destination path is too long to show")
            lines = [f"{_quoted(o['name'])}: {o['pages']} pages, {o['size']} bytes, SHA-256 {o['sha256'][:12]}"
                     for o in outputs]
            lines += [f"Warning: {w['message']}" for w in warnings]
            if warnings:
                lines.append("You accepted these warnings." if warnings_accepted else "Warnings not accepted.")
            lines.append(body["statement"])
            lines.append("An existing file is never replaced.")
            return self._card(sid, "Save this file?", destination, lines, "Save", "Not now", "office.apply_change",
                              "office.reject_change", "change_sha256", sha, "office_change", "Office output")
        return self._propose_subject(workflow_id, "output_files", body, card, {"outputs": len(outputs),
                                                                               "warnings": len(warnings)})

    def propose_authoring_save(self, authoring_id: str, body: dict) -> Surface:
        """Authoring (milestone A): `office.apply_change` on an `authoring_save` subject. The hash binds every change
        in plain words, the working copy's SHA-256, the full destination and whether it replaces the opened file."""
        t = body["target"]

        def card(sid, sha):
            dest = t["destination"]
            if u16(dest) > C.MAX_STRING:
                raise OfficeError("CHANGE_TOO_LARGE_TO_SHOW", "the destination path is too long to show")
            lines = list(body["changes"]) or ["A new file with the content shown."]
            lines.append("This replaces the file you opened (a backup is kept)." if t["replaces"]
                         else "A new file is written. An existing file is never replaced.")
            return self._card(sid, "Save this presentation?", dest, lines, "Save", "Not now", "office.apply_change",
                              "office.reject_change", "change_sha256", sha, "office_change", "Office save")
        return self._propose_subject(authoring_id, "authoring_save", body, card, {"changes": len(body["changes"])})

    def propose_print(self, job: str, p: dict) -> Surface:
        """The print card (O2P, A1 §A4): `office.apply_change` on a `print_job` subject. The hash binds the PDF's
        SHA-256, the page list, the printer name, every setting, the capability snapshot, the printer status and the
        output file (for a printer that writes a file)."""
        body = {"subject_kind": "print_job", "job": job, "target": {"kind": "print_job"}, "print": p}
        sides = {"simplex": "one-sided", "long": "two-sided (long edge)", "short": "two-sided (short edge)"}

        def card(sid, sha):
            s = p["settings"]
            pages = p["pages"]
            if len(pages) > 1 and pages == list(range(pages[0], pages[-1] + 1)):
                span = f"pages {pages[0]}-{pages[-1]}"
            else:
                span = "page " + ", ".join(str(n) for n in pages)
            copies = f"{s['copies']} copy" if s["copies"] == 1 else f"{s['copies']} copies"
            lines = [f"Printer: {_quoted(p['printer'])}",
                     f"What: {_quoted(p['label'])}, {span} ({len(pages)} page(s)), {copies}",
                     f"Paper: {_quoted(str(s['paper']))}, {'landscape' if s['landscape'] else 'portrait'}, "
                     f"{'colour' if s['color'] else 'black and white'}, {sides[s['duplex']]}, "
                     f"{'fit to page' if s['fit'] == 'fit' else 'actual size'}, {s['dpi']} dpi"]
            lines += [f"Warning: {w}" for w in p.get("warnings", [])]
            if p["connection"] == "network":
                where = f" on {_quoted(p['server'])}" if p.get("server") else ""
                lines.append(f"Network printer{where}: the pages leave this PC through Windows.")
            else:
                lines.append(f"Pages are sent to {_quoted(p['printer'])} through Windows.")
            if p.get("output"):
                lines.append("This printer writes a file. It is saved as the file shown above; an existing file is "
                             "never replaced.")
            return self._card(sid, "Print this?", p.get("output") or "", lines, "Print", "Not now",
                              "office.apply_change", "office.reject_change", "change_sha256", sha, "office_change",
                              "Office print")
        return self._propose_subject(job, "print_job", body, card, {"pages": len(p["pages"]),
                                                                     "copies": p["settings"]["copies"]})

    def _card(self, sid, title, caption, lines, yes, no, yes_action, no_action, key, sha, kind, label) -> Surface:
        texts = _chunks(lines, C.MAX_STRING)
        if len(texts) > C.MAX_COMPONENTS - FIXED_COMPONENTS:
            raise OfficeError("CHANGE_TOO_LARGE_TO_SHOW", "this card is too large to show in full", 413)
        comps = [{"id": "title", "component": "Text", "variant": "title", "text": title},
                 {"id": "target", "component": "Text", "variant": "caption", "text": caption}]
        kids = ["title", "target"]
        for i, text in enumerate(texts):
            comps.append({"id": f"lines{i}", "component": "Text", "variant": "body", "text": text})
            kids.append(f"lines{i}")
        bind = {key: {"path": f"/bound/{key}"}}
        comps += [
            {"id": "apply", "component": "Button", "variant": "primary", "label": yes,
             "action": {"event": {"name": yes_action, "context": bind}}},
            {"id": "reject", "component": "Button", "variant": "secondary", "label": no,
             "action": {"event": {"name": no_action, "context": bind}}},
            {"id": "buttons", "component": "Row", "children": ["apply", "reject"], "gap": "small"},
        ]
        kids.append("buttons")
        comps.insert(0, {"id": "root", "component": "Column", "children": kids, "gap": "medium"})
        return Surface(sid, kind, comps, data={}, bound={key: sha}, actions=(yes_action, no_action),
                       placement="workspace", title=label)

    def subject_of(self, surface_id):
        """(subject_kind, subject_id) of an approval, or (None, None). Lets the caller take the subject's own lock
        before `action` takes this one."""
        if not isinstance(surface_id, str):
            return None, None
        with self.lock:
            r = self.db.execute("SELECT subject_kind, workbook_id FROM surface WHERE surface_id=?",
                                (surface_id,)).fetchone()
        return (r["subject_kind"], r["workbook_id"]) if r else (None, None)

    def _surface(self, sid, target, body, sha) -> Surface:
        google = target.get("kind") == "google"
        upload = target.get("kind") == "google_upload"
        new_file = target.get("kind") == "new_file"
        # The card shows the whole change set the hash binds (every edit with its full before/after, every structural
        # op, the full destination). A set too large for one card is refused, never shortened.
        lines = [f"{e['sheet']}!{e['cell']}: {_shown(e['before'])} -> {_shown(e['after'])}" for e in body["edits"]]
        lines += [" ".join(f"{k}={json.dumps(op[k], ensure_ascii=False)}" for k in sorted(op))
                  for op in body["struct_ops"]]
        if new_file:
            # M2-D1: a new file changes no existing data and can hold far more cells than a card can show, so the card
            # summarises it; the hash still binds every cell, and a later draft change makes this approval stale.
            per_sheet: dict = {}
            for e in body["edits"]:
                n = per_sheet.setdefault(e["sheet"], [0, 0])
                if e["after"].get("f") or e["after"].get("v") not in (None, ""):
                    n[0] += 1
                    n[1] += 1 if e["after"].get("f") else 0
            lines = ["A new file will be created. No existing file is changed."]
            lines += [f"Sheet {_quoted(name)}: {per_sheet[name][0]} cells, "
                      f"{per_sheet[name][1]} formulas" for name in target.get("sheets", []) if per_sheet.get(name, [0])[0]]
            if target.get("sources"):
                lines.append("Built from: " + ", ".join(_quoted(x) for x in target["sources"]))
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
                      "Apply these changes to the Google Sheet?" if google else
                      "Create this new file?" if new_file else "Save these changes to the file?")},
            {"id": "target", "component": "Text", "variant": "caption", "text": label},
        ]
        kids = ["title", "target"]
        for i, text in enumerate(texts):
            comps.append({"id": f"lines{i}", "component": "Text", "variant": "body", "text": text})
            kids.append(f"lines{i}")
        bind = {"change_sha256": {"path": "/bound/change_sha256"}}
        comps += [
            {"id": "apply", "component": "Button", "variant": "primary",
             "label": "Upload to Google Drive" if upload else "Apply to Google Sheet" if google else
                      "Create file" if new_file else "Save to file",
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
                kind = r["subject_kind"]
                key = HASH_KEY.get(msg["name"])
                if key is None or (key == "plan_sha256") != (kind == "plan"):
                    raise OfficeError("ACTION_NOT_ALLOWED_ON_SURFACE", msg["name"])
                if hashlib.sha256(canonical(body)).hexdigest() != r["change_sha256"] or \
                        ctx[key] != r["change_sha256"]:
                    raise OfficeError("CHANGE_MISMATCH", "the change differs from what was shown")
                subject = {"workbook_id": r["workbook_id"]} if kind == "workbook" else \
                    {"subject_kind": kind, "subject_id": r["workbook_id"]}
                if msg["name"] in DECLINE_ACTIONS:
                    self._close(sid)
                    self.audit("office.approval_declined", {"surface_id": sid, "change_sha256": r["change_sha256"],
                                                            "subject_kind": kind})
                    return {"status": "declined", **subject}
                try:
                    result = apply_fn(body)
                except OfficeError:
                    raise
                except Exception as exc:  # noqa: BLE001 - an unexpected failure is audited and closes the approval
                    self._close(sid)
                    raise OfficeError("APPLY_FAILED", "the change could not be saved; propose it again", 500) from exc
                self._close(sid)
                if kind == "workbook":
                    counts = {"cells": len(body["edits"]), "struct_ops": len(body["struct_ops"])}
                elif kind == "plan":
                    counts = {"steps": len(body["plan"]["steps"])}
                elif kind == "print_job":
                    counts = {"pages": len(body["print"]["pages"]), "copies": body["print"]["settings"]["copies"]}
                elif kind == "authoring_save":
                    counts = {"changes": len(body["changes"])}
                else:
                    counts = {"outputs": len(body.get("outputs", []))}
                self.audit("office.change_applied", {"surface_id": sid, "change_sha256": r["change_sha256"],
                                                     "subject_kind": kind, **counts})
                return {"status": "applied", **subject, **(result or {})}
            except OfficeError as exc:
                self.audit("office.action_refused", {"surface_id": sid if isinstance(sid, str) else None,
                                                     "code": exc.code})
                if exc.code in ("TARGET_CHANGED", "STALE_CHANGE", "STALE_PLAN", "INPUT_CHANGED") and r is not None:
                    self._close(sid)
                raise
