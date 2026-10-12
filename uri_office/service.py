"""URI Office service: local HTTP API + CLI (AC6), modelled on `uri_scheduler.service`.

  python -m uri_office.service run --state <dir> [--port 18530] [--google-token <path>] [--brain-url <url>]

Security (AC6):
  * binds 127.0.0.1 only; any other host is refused at start;
  * the state folder and the token file get one full-control ACL entry for the current Windows user (inheritance
    removed; folder entry inherited by its contents), so other principals can neither read nor delete-and-replace them;
  * a random bearer token is made per launch and written to `<state>/api-token`; the panel reads it from there;
  * every request must carry that token, a loopback Host header for this port (DNS-rebinding guard) and no Origin
    header (browser pages cannot call it); no CORS header is ever sent and OPTIONS is refused;
  * GET never changes state (status, workbook view, open approval surfaces only); every change is a POST;
  * the command set is narrow: open a file the owner picked, edit the draft, propose/decide hash-bound approvals,
    Google read/copy/export/upload; writes go only to granted paths after the hash checks.
One service instance acts for one owner.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import draft as D
from . import google as G
from . import refs, xlsx_model, xlsx_new, xlsx_patch
from . import sources as SRC
from .approvals import Approvals
from .errors import OfficeError
from .grants import Grants
from .history import History, workbook_key

DEFAULT_PORT = 18530
MAX_BODY = 256 * 1024
MAX_SESSIONS = 16


@dataclass
class Session:
    workbook_id: str
    engine: str                     # "local" | "google" | "new" (M2: a new workbook built from sources)
    label: str
    workbook: dict
    draft: D.Draft
    key: str                        # history key (hash; no path or id stored in history)
    grant_id: str | None = None     # local
    path: Path | None = None        # local, as opened
    open_sha: str | None = None     # local, file hash at open / last save
    file_id: str | None = None      # google
    stale_ops: list = field(default_factory=list)   # google: applied structural ops not yet re-read
    layout_version: int = 0         # google: bumped by every re-read after a layout change; grids carry it
    sources: list = field(default_factory=list)     # new: read-only source workbooks (sources.Source)
    lock: threading.RLock = field(default_factory=threading.RLock)


def excel_lock_present(path: Path) -> bool:
    """Excel keeps `~$<name>` (long names: first two characters replaced) next to a workbook it has open."""
    names = {"~$" + path.name, "~$" + path.name[2:]}
    return any((path.parent / n).exists() for n in names)


class Office:
    def __init__(self, state: Path, *, owner="owner", google: G.GoogleSheets | None = None, brain=None,
                 allowed_roots=None):
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.owner = owner
        self.grants = Grants(allowed_roots)
        self.approvals = Approvals(self.state, owner)
        self.history = History(self.state)
        self.google = google or G.GoogleSheets(self.state, None)
        self.brain = brain
        self.sessions: dict[str, Session] = {}
        self.lock = threading.RLock()

    # ---- sessions ------------------------------------------------------------------------------------------------
    def _session(self, wid) -> Session:
        s = self.sessions.get(wid) if isinstance(wid, str) else None
        if s is None:
            raise OfficeError("UNKNOWN_WORKBOOK", "", 404)
        return s

    def _add(self, s: Session) -> dict:
        with self.lock:
            if len(self.sessions) >= MAX_SESSIONS:
                raise OfficeError("TOO_MANY_OPEN", "close a workbook first")
            self.sessions[s.workbook_id] = s
        self.approvals.audit("office.opened", {"workbook_id": s.workbook_id, "engine": s.engine})
        return self.view(s.workbook_id)

    def view(self, wid) -> dict:
        s = self._session(wid)
        with s.lock:                                     # read-only (AC6): a pending re-read is done by reload()
            out = {"workbook_id": s.workbook_id, "engine": s.engine, "label": s.label, "workbook": s.workbook,
                   "draft": s.draft.snapshot(), "history_on": self.history.consented(s.key)}
            if s.sources:
                out["sources"] = SRC.listing(s.sources)
                w = SRC.working(s.sources)
                out["working"] = w.sid if w else None
                out["task"] = w.role if w else "build"
            if s.engine == "google":
                out["open_url"] = G.open_url(s.file_id)
                out["writable"] = self.google.writable(s.file_id)
                out["reload_required"] = bool(s.stale_ops)
                out["layout_version"] = s.layout_version
            return out

    def reload(self, wid) -> dict:
        """The panel's reload after a save whose re-read failed: re-read the Google sheet now and return the view, with
        how many proposed changes were dropped because their rows moved. If the re-read fails again the view says
        reload_required and nothing changes."""
        s = self._session(wid)
        with s.lock:
            try:
                refreshed = self._refresh(s)
            except OfficeError:
                refreshed = None                         # reported as reload_required in the view
            return {**self.view(wid), "proposals_dropped": refreshed[0] if refreshed is not None else 0}

    def open_local(self, raw_path) -> dict:
        g = self.grants.grant_open(raw_path)
        wid = uuid.uuid4().hex[:16]
        work = self.state / "work" / wid
        work.mkdir(parents=True)
        copy = work / "opened.xlsx"
        shutil.copy2(g.path, copy)                       # copy-in (OD-3); the original is only read here
        sha = xlsx_model.file_sha256(copy)
        if sha != xlsx_model.file_sha256(g.path):
            raise OfficeError("FILE_CHANGING", "the file changed while it was being opened; try again", 409)
        wb = xlsx_model.read(copy)
        s = Session(wid, "local", g.path.name, wb, D.Draft(wid, "local", wb),
                    workbook_key("local", str(g.path).lower()), grant_id=g.grant_id, path=g.path, open_sha=sha)
        return self._add(s)

    def open_google(self, url) -> dict:
        fid = G.parse_link(url)
        meta = self.google.check_sheet(fid)
        wb = self.google.read(fid)
        wid = uuid.uuid4().hex[:16]
        s = Session(wid, "google", meta["name"] or "Google Sheet", wb, D.Draft(wid, "google", wb),
                    workbook_key("google", fid), file_id=fid)
        return self._add(s)

    @staticmethod
    def _empty_sheet(name: str, index: int) -> dict:
        return {"name": name, "index": index, "max_row": 0, "max_col": 0, "truncated": False, "cells": {},
                "locked": [], "merges": [], "col_widths": {}, "row_heights": {}}

    def open_new(self, raw_paths) -> dict:
        """M2-AC1: a new, empty workbook with read-only source files (copied in; the originals are only read)."""
        wid = uuid.uuid4().hex[:16]
        work = self.state / "work" / wid
        work.mkdir(parents=True)
        try:
            srcs = SRC.add(self.grants, work, [], raw_paths)
            wb = {"sheets": [self._empty_sheet("Sheet1", 0)], "styles": {},
                  "kept_not_shown": {"charts": 0, "images": 0, "pivot_tables": 0}}
            s = Session(wid, "new", "New workbook", wb, D.Draft(wid, "new", wb), workbook_key("new", wid), sources=srcs)
            return self._add(s)
        except Exception:
            if wid not in self.sessions:
                shutil.rmtree(work, ignore_errors=True)
            raise

    def add_sources(self, wid, body) -> dict:
        """M2-AC2: more source files for an open new workbook."""
        s = self._session(wid)
        if not s.sources:
            raise OfficeError("NOT_A_NEW_WORKBOOK", "files can be added only to a workbook opened with \"New from files\"")
        with s.lock:
            s.sources = SRC.add(self.grants, self.state / "work" / wid, s.sources, body.get("paths"))
            self.approvals.audit("office.sources_added", {"workbook_id": wid, "sources": len(s.sources)})
            return self.view(wid)

    def set_roles(self, wid, body) -> dict:
        """M2-D10/D11: the owner says what each added file is for. At most one file is checked or edited (the working
        file, shown in the sheet view and saved in place through the M1 path); with none, URI builds a new workbook.
        Changing the working file is refused while the current one has accepted or typed changes not yet saved."""
        s = self._session(wid)
        roles = body.get("roles")
        if not s.sources:
            raise OfficeError("NO_SOURCES", "this workbook has no added files")
        if not isinstance(roles, dict) or any(k not in {x.sid for x in s.sources} or v not in SRC.ROLES
                                              for k, v in roles.items()):
            raise OfficeError("BAD_ROLES", "each file is reference, check or edit")
        with s.lock:
            merged = {x.sid: roles.get(x.sid, x.role) for x in s.sources}
            work = [k for k, v in merged.items() if v in SRC.WORKING_ROLES]
            if len(work) > 1:
                raise OfficeError("ONE_WORKING_FILE", "check or edit one file at a time")
            old = SRC.working(s.sources)
            new_sid = work[0] if work else None
            if (old.sid if old else None) != new_sid:
                if s.draft.pending()["edits"]:
                    raise OfficeError("SAVE_OR_DISCARD_FIRST", "save or undo the changes to the current file before "
                                                               "working on another one", 409)
                self._switch_target(s, next((x for x in s.sources if x.sid == new_sid), None))
            for x in s.sources:
                x.role = merged[x.sid]
            self.approvals.audit("office.roles_set", {"workbook_id": wid, "roles": merged})
            return self.view(wid)

    def _switch_target(self, s, src):
        """Make `src` the working file (a local workbook on the original, saved through the M1 cell patch), or, with
        None, a new empty workbook."""
        self.approvals.close_workbook(s.workbook_id)       # an open approval was for the previous target
        if src is None:
            wb = {"sheets": [self._empty_sheet("Sheet1", 0)], "styles": {},
                  "kept_not_shown": {"charts": 0, "images": 0, "pivot_tables": 0}}
            s.engine, s.label, s.workbook = "new", "New workbook", wb
            s.draft = D.Draft(s.workbook_id, "new", wb)
            s.key = workbook_key("new", s.workbook_id)
            s.grant_id = s.path = s.open_sha = None
            return
        path = self.grants.get(src.grant_id, "open").path
        if xlsx_model.file_sha256(path) != src.sha256:
            raise OfficeError("TARGET_CHANGED", "the file changed on disk since it was added; add it again", 409)
        s.engine, s.label, s.workbook = "local", src.label, src.workbook
        s.draft = D.Draft(s.workbook_id, "local", src.workbook)
        s.key = workbook_key("local", str(path).lower())
        s.grant_id, s.path, s.open_sha = src.grant_id, path, src.sha256

    def _sync_new_sheets(self, s):
        """New workbook: the session's sheet list follows the draft (sheets added or renamed by URI, M2-D4). The grid
        shows sheets with changes first, so it opens on what URI built rather than on the empty starting sheet; the
        file keeps the draft's order (and leaves empty sheets out)."""
        live = {c["sheet"] for c in s.draft.changes if c["kind"] == "cell" and c["state"] in D.LIVE}
        names = s.draft.sheets()
        order = [n for n in names if n in live] + [n for n in names if n not in live]
        s.workbook = {**s.workbook, "sheets": [self._empty_sheet(n, i) for i, n in enumerate(order)]}

    def close(self, wid):
        s = self._session(wid)
        with self.lock:
            self.sessions.pop(wid, None)
        self.approvals.close_workbook(wid)
        for src in s.sources:
            self.grants.revoke(src.grant_id)
        if s.grant_id:
            self.grants.revoke(s.grant_id)
        shutil.rmtree(self.state / "work" / wid, ignore_errors=True)
        return {"closed": wid}

    # ---- draft ---------------------------------------------------------------------------------------------------
    def _locked(self, s):
        return {sh["name"]: set(sh.get("locked", ())) for sh in s.workbook["sheets"]}

    @staticmethod
    def _overlay(sheets: list, edits) -> list:
        """A copy of `sheets` with each edit's `after` (value or formula) written over the cell."""
        out = []
        by_sheet: dict = {}
        for sheet, cell, after in edits:
            by_sheet.setdefault(sheet, []).append((cell, after))
        for sh in sheets:
            if sh["name"] not in by_sheet:
                out.append(sh)
                continue
            cells = dict(sh["cells"])
            max_row, max_col = sh.get("max_row") or 0, sh.get("max_col") or 0
            for cell, after in by_sheet[sh["name"]]:
                c = {k: v for k, v in cells.get(cell, {}).items() if k not in ("v", "f", "t")}
                c.update({"f": after["f"]} if after.get("f") else {"v": after.get("v")})
                cells[cell] = c
                col, row = refs.parse_cell(cell)
                max_row, max_col = max(max_row, row), max(max_col, col)
            out.append({**sh, "cells": cells, "max_row": max_row, "max_col": max_col})
        return out

    def _current_sheets(self, s) -> list:
        """The workbook as the draft holds it now (saved values plus accepted and user changes): what the Brain plans
        from, so it never works from values the owner already changed."""
        latest = {}
        for ch in s.draft.changes:
            if ch["kind"] == "cell" and ch["state"] in ("accepted", "user"):
                latest[(ch["sheet"], ch["cell"])] = ch["after"]
        return self._overlay(s.workbook["sheets"], [(sh, c, a) for (sh, c), a in latest.items()])

    def _committed(self, s, pending):
        """After a save to the session's own target: the draft and the session's workbook snapshot both take the saved
        values, so the panel reloads what the file now holds. Structural ops (Google: rename/add sheets, insert/delete
        rows) change the layout itself, so the sheet is re-read and the snapshot and draft base rebuilt from it."""
        s.draft.committed(pending)
        s.workbook = {**s.workbook, "sheets": self._overlay(
            s.workbook["sheets"], [(e["sheet"], e["cell"], e["after"]) for e in pending["edits"]])}
        if pending["struct_ops"]:
            s.stale_ops = list(s.stale_ops) + list(pending["struct_ops"])
            try:
                return {"layout_reloaded": True, "proposals_dropped": self._refresh(s)[0]}
            except OfficeError:                          # the save itself succeeded; the next call retries the re-read
                return {"layout_reloaded": False}
        return {}

    def _refresh(self, s):
        """Re-read a Google sheet whose layout an applied save changed. Until that succeeds the session refuses edits,
        Brain turns, decisions and saves: its sheet names and row positions no longer match the sheet. Returns (how many
        proposed changes were dropped because their rows moved, the sheets whose rows moved by their names now), or
        None when there was nothing to re-read."""
        if not s.stale_ops:
            return None
        try:
            wb = self.google.read(s.file_id)
        except Exception:  # noqa: BLE001 - a failed re-read must not be reported as a failed save
            raise OfficeError("RELOAD_REQUIRED", "the sheet's layout changed with the last save and could not be "
                                                 "read again; try again", 503) from None
        renames, moved = D.layout_moves(s.stale_ops)
        dropped = s.draft.rebase(wb, s.stale_ops)
        s.workbook = wb
        s.stale_ops = []
        s.layout_version += 1
        return dropped, {renames.get(m, m) for m in moved}

    @staticmethod
    def _reloaded(s, refreshed) -> dict:
        """Response fields after a call that may have re-read the sheet: the layout version, and the new workbook when
        this call re-read it, so the panel reloads its grid before the owner edits it by row and column."""
        if s.engine != "google":
            return {}
        return {"layout_version": s.layout_version, **({"workbook": s.workbook} if refreshed is not None else {})}

    def edit(self, wid, body) -> dict:
        from . import ops as O
        s = self._session(wid)
        with s.lock:
            refreshed = self._refresh(s)
            # The sheet and cell come from the panel's grid. If that grid predates a layout change (rows moved by a
            # Google save) they name a different cell now: refuse rather than write the owner's value there.
            stale_grid = (body.get("layout_version") is not None and body.get("layout_version") != s.layout_version) \
                or (refreshed is not None and str(body.get("sheet")) in refreshed[1])
            if s.engine == "google" and stale_grid:
                raise OfficeError("RELOAD_REQUIRED", "the sheet's rows moved since this grid was loaded; reload it "
                                                     "and edit again", 409)
            op = ({"op": "set_formula", "sheet": body.get("sheet"), "cell": body.get("cell"), "formula": body["formula"]}
                  if "formula" in body else
                  {"op": "set_values", "sheet": body.get("sheet"), "range": body.get("cell"), "values": [[body.get("value")]]})
            edits = O.to_cell_edits(op, engine=s.engine, sheets=s.draft.sheets(), locked=self._locked(s))
            events = s.draft.user_edit(edits[0])
            for ev in events:
                self.history.record(s.key, s.draft.version, ev)
            return {"draft": s.draft.snapshot(), **self._reloaded(s, refreshed)}

    def decide(self, wid, body) -> dict:
        s = self._session(wid)
        with s.lock:
            refreshed = self._refresh(s)
            events = s.draft.decide(body.get("change_id"), body.get("decision"), body.get("change_sha256"))
            for ev in events:
                self.history.record(s.key, s.draft.version, ev, body.get("reason", ""))
            return {"draft": s.draft.snapshot(), **self._reloaded(s, refreshed)}

    def decide_all(self, wid, body) -> dict:
        """M2-AC7: accept or reject every proposed change, bound to the draft version and the set hash shown."""
        s = self._session(wid)
        with s.lock:
            refreshed = self._refresh(s)
            events = s.draft.decide_all(body.get("decision"), body.get("draft_version"), body.get("set_sha256"))
            for ev in events:
                self.history.record(s.key, s.draft.version, ev, body.get("reason", ""))
            return {"draft": s.draft.snapshot(), **self._reloaded(s, refreshed)}

    def undo(self, wid, redo=False) -> dict:
        s = self._session(wid)
        with s.lock:
            refreshed = self._refresh(s)
            (s.draft.redo if redo else s.draft.undo)()
            return {"draft": s.draft.snapshot(), **self._reloaded(s, refreshed)}

    def instruct(self, wid, body) -> dict:
        if self.brain is None:
            raise OfficeError("BRAIN_UNAVAILABLE", "the Brain is not configured for this service", 503)
        s = self._session(wid)
        with s.lock:                                     # the draft is locked for the whole turn; user edits queue
            refreshed = self._refresh(s)
            extra = {}
            if s.sources:
                missing = SRC.roles_needed(s.sources)
                if missing:
                    raise OfficeError("ROLES_NEEDED", "say what each file is for (reference, check or edit): "
                                                      + ", ".join(missing))
                w = SRC.working(s.sources)
                extra = {"sources": [x for x in s.sources if x is not w], "task": w.role if w else "build"}
            res = self.brain.plan(body.get("text"), sheets=self._current_sheets(s), active=body.get("active_sheet"),
                                  engine=s.engine, locked=self._locked(s), history_rows=self.history.recent(s.key),
                                  **extra)
            new = s.draft.propose(res["edits"]) if res["edits"] else []
            out = {"message": res["message"], "proposed": [c["cid"] for c in new if c["state"] == "proposed"],
                   "refused": res["refused"], "metrics": res["metrics"], "draft": s.draft.snapshot(),
                   **self._reloaded(s, refreshed)}
            if res.get("findings") is not None:
                out["findings"] = res["findings"]
            if s.engine == "new":
                self._sync_new_sheets(s)
                out["workbook"] = s.workbook             # the grid reloads: sheets may have been added or renamed
                out["notes"] = res.get("notes", {})
            return out

    # ---- approvals -----------------------------------------------------------------------------------------------
    def propose_save(self, wid, body) -> dict:
        s = self._session(wid)
        with s.lock:
            self._refresh(s)
            pending = s.draft.pending()
            if s.engine == "local":
                dest = None
                if body.get("save_as_path"):
                    g = self.grants.grant_save_as(body["save_as_path"])
                    if g.path.exists():
                        raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
                    dest = g
                target = {"kind": "local", "label": str(dest.path if dest else s.path),
                          "grant_id": dest.grant_id if dest else s.grant_id, "save_as": bool(dest),
                          "source_sha256": s.open_sha, "draft_version": s.draft.version}
            elif s.engine == "new":
                if not body.get("save_as_path"):
                    raise OfficeError("SAVE_AS_REQUIRED", "choose where to create the new file")
                g = self.grants.grant_save_as(body["save_as_path"])
                if g.path.exists():
                    raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
                if not xlsx_new.content(s.draft.sheets(), pending["edits"]):
                    raise OfficeError("NOTHING_TO_SAVE", "the new workbook has no cells")
                target = {"kind": "new_file", "label": str(g.path), "grant_id": g.grant_id,
                          "draft_version": s.draft.version, "sheets": s.draft.sheets(),
                          "sources": [src.label for src in s.sources]}
            else:
                target = {"kind": "google", "label": s.label, "file_id": s.file_id, "draft_version": s.draft.version}
            surface = self.approvals.propose(wid, target, pending)
            return {"messages": surface.messages(), "surface_id": surface.surface_id}

    def propose_share(self, wid) -> dict:
        """'Share via Google': upload the saved local file (as on disk now) and convert it. Hash-bound approval."""
        s = self._session(wid)
        if s.engine != "local":
            raise OfficeError("NOT_LOCAL")
        with s.lock:
            target = {"kind": "google_upload", "label": str(s.path), "grant_id": s.grant_id, "source_sha256": s.open_sha}
            surface = self.approvals.propose(wid, target, {"edits": [], "struct_ops": []})
            return {"messages": surface.messages(), "surface_id": surface.surface_id}

    def _apply(self, body) -> dict:
        s = self._session(body["workbook_id"])
        with s.lock:
            t = body["target"]
            if t["kind"] == "google_upload":
                src = self.grants.get(t["grant_id"], "open").path
                if xlsx_model.file_sha256(src) != t["source_sha256"]:
                    raise OfficeError("TARGET_CHANGED", "the file changed on disk since this was shown", 409)
                r = self.google.upload_convert(src, src.stem)
                return {"google_file_id": r["id"], "open_url": G.open_url(r["id"])}
            # The approval is bound to the draft version it was made from: any later edit, decision or undo means the
            # card no longer shows what the draft holds, so applying it would silently drop or skip changes.
            if s.draft.version != t.get("draft_version"):
                raise OfficeError("STALE_CHANGE", "the draft changed after this approval was shown; review the save "
                                                  "again", 409)
            pending = {"edits": body["edits"], "struct_ops": body["struct_ops"]}
            if t["kind"] == "new_file":
                return self._create_new_file(s, t, pending)
            if t["kind"] == "google":
                r = self.google.apply(t["file_id"], body)
                return {**r, **self._committed(s, pending)}
            src = s.path
            if xlsx_model.file_sha256(src) != t["source_sha256"] or s.open_sha != t["source_sha256"]:
                raise OfficeError("TARGET_CHANGED", "the file changed on disk since it was opened; reload it or save "
                                                    "as a new file", 409)
            if excel_lock_present(src):
                raise OfficeError("FILE_OPEN_ELSEWHERE", "the file is open in Excel; close it there first", 409)
            if t["save_as"]:
                dest = self.grants.get(t["grant_id"], "save_as").path
                if dest.exists():
                    raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
            else:
                dest = self.grants.get(t["grant_id"], "open").path
            backup = self.state / "backups" / s.workbook_id
            backup.mkdir(parents=True, exist_ok=True)
            if not t["save_as"]:
                shutil.copy2(src, backup / f"{int(time.time())}-{src.name}")
            res = xlsx_patch.patch(src, dest, D.patch_edits(pending))
            # A Save As writes a new file but the session keeps editing the original: the draft stays relative to the
            # original (its edits remain pending for it, and for any later Save As), so nothing is committed here.
            if not t["save_as"]:
                self._committed(s, pending)
                s.open_sha = xlsx_model.file_sha256(dest)
            return {"changed_parts": res["changed_parts"], "saved_to": dest.name}

    def _create_new_file(self, s, t, pending) -> dict:
        """M2-AC9/AC10: write the new file (never over an existing one), then continue as an ordinary local session on
        it, so later saves use the M1 cell patch. The sources are released."""
        dest = self.grants.get(t["grant_id"], "save_as").path
        if dest.exists():
            raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
        res = xlsx_new.write(dest, xlsx_new.content(t["sheets"], pending["edits"]))
        g = self.grants.grant_open(str(dest))
        copy = self.state / "work" / s.workbook_id / "opened.xlsx"
        shutil.copy2(dest, copy)
        wb = xlsx_model.read(copy)
        for src in s.sources:
            self.grants.revoke(src.grant_id)
        s.engine, s.label, s.workbook = "local", dest.name, wb
        s.draft = D.Draft(s.workbook_id, "local", wb)
        s.key = workbook_key("local", str(dest).lower())
        s.grant_id, s.path, s.open_sha, s.sources = g.grant_id, dest, xlsx_model.file_sha256(dest), []
        self.approvals.audit("office.new_file_created", {"workbook_id": s.workbook_id, **res})
        return {"saved_to": dest.name, "created": True, **res}

    def action(self, msg) -> dict:
        # Lock order everywhere: workbook lock, then approvals lock (propose_save/propose_share take them that way).
        # Taking the approvals lock first and the workbook lock inside `_apply` could deadlock against a concurrent
        # propose on the same workbook.
        wid = self.approvals.workbook_of(msg.get("surfaceId") if isinstance(msg, dict) else None)
        s = self.sessions.get(wid) if wid else None
        if s is None:
            r = self.approvals.action(msg, self._apply)
        else:
            with s.lock:
                r = self.approvals.action(msg, self._apply)
        if r.get("workbook_id") in self.sessions:
            s = self.sessions[r["workbook_id"]]
            r["draft"] = s.draft.snapshot()
            r["workbook"] = s.workbook
            if s.engine == "google":
                r["layout_version"] = s.layout_version
                r["reload_required"] = bool(s.stale_ops)
        return r

    # ---- google extras -------------------------------------------------------------------------------------------
    def edit_copy(self, wid) -> dict:
        s = self._session(wid)
        if s.engine != "google":
            raise OfficeError("NOT_GOOGLE")
        c = self.google.copy(s.file_id, f"{s.label} (URI copy)")
        return self.open_google(G.open_url(c["id"]))

    def export(self, wid, body) -> dict:
        s = self._session(wid)
        if s.engine != "google":
            raise OfficeError("NOT_GOOGLE")
        g = self.grants.grant_save_as(body.get("dest_path"))
        if g.path.exists():
            raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
        r = self.google.export_xlsx(s.file_id, g.path)
        self.approvals.audit("office.exported", {"workbook_id": wid})
        return r

    # ---- history -------------------------------------------------------------------------------------------------
    def history_op(self, wid, body) -> dict:
        s = self._session(wid)
        act = body.get("action")
        if act == "consent":
            self.history.set_consent(s.key, bool(body.get("on")))
        elif act == "delete":
            self.history.delete(s.key, body.get("row_id"))
        elif act == "delete_all":
            self.history.delete_all(s.key)
        elif act != "view":
            raise OfficeError("BAD_HISTORY_ACTION")
        self.approvals.audit("office.history_" + act, {"workbook_id": wid})
        return {**self.history.view(s.key), "pointer": History.pointer(s.key), "graphify_wired": False}


def make_handler(office: Office, token: str):
    class H(BaseHTTPRequestHandler):
        server_version = "uri-office/1"

        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _auth(self) -> bool:
            """Every request: Host must be this loopback listener (DNS-rebinding guard); browser-originated requests
            (any Origin header) are refused and no CORS header is ever sent; then the per-launch bearer token."""
            port = self.server.server_address[1]
            if self.headers.get("Host", "") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                self._send(421, {"error": "BAD_HOST"})
                return False
            if self.headers.get("Origin") is not None:
                self._send(403, {"error": "BROWSER_ORIGIN_REFUSED"})
                return False
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self._send(401, {"error": "UNAUTHORIZED"})
                return False
            return True

        def do_OPTIONS(self):
            self._send(405, {"error": "METHOD_NOT_ALLOWED"})

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise OfficeError("BODY_TOO_LARGE")
            b = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(b, dict):
                raise OfficeError("BAD_REQUEST")
            if b.get("principal") not in (None, office.owner):
                raise OfficeError("PRINCIPAL_MISMATCH", "this service acts only for its owner", 403)
            return b

        def _run(self, fn):
            try:
                self._send(200, fn())
            except OfficeError as exc:
                self._send(exc.status, {"error": exc.code, "detail": exc.detail})
            except (KeyError, ValueError, TypeError) as exc:
                self._send(400, {"error": "BAD_REQUEST", "detail": type(exc).__name__})
            except Exception as exc:  # noqa: BLE001 - never leak internals or cell values
                self._send(500, {"error": type(exc).__name__})

        def do_GET(self):
            if not self._auth():
                return
            u = urlparse(self.path)
            parts = [p for p in u.path.split("/") if p]
            qs = parse_qs(u.query)

            def go():
                if parts == ["status"]:
                    return {"open": len(office.sessions), "chain": office.approvals.verify_chain(),
                            "google": office.google.status(), "brain": office.brain is not None}
                if len(parts) == 2 and parts[0] == "workbook":
                    return office.view(parts[1])
                if parts == ["a2ui", "surfaces"]:
                    return {"messages": office.approvals.open_messages(qs.get("workbook", [None])[0])}
                raise OfficeError("NOT_FOUND", "", 404)
            self._run(go)

        def do_POST(self):
            if not self._auth():
                return
            parts = [p for p in urlparse(self.path).path.split("/") if p]

            def go():
                b = self._body()
                if parts == ["open", "local"]:
                    return office.open_local(b.get("path"))
                if parts == ["open", "google"]:
                    return office.open_google(b.get("url"))
                if parts == ["open", "new"]:
                    return office.open_new(b.get("paths"))
                if parts == ["a2ui", "action"]:
                    return office.action(b.get("action"))
                if len(parts) == 3 and parts[0] == "workbook":
                    wid, verb = parts[1], parts[2]
                    table = {"edit": lambda: office.edit(wid, b), "decide": lambda: office.decide(wid, b),
                             "undo": lambda: office.undo(wid), "redo": lambda: office.undo(wid, redo=True),
                             "instruct": lambda: office.instruct(wid, b),
                             "propose_save": lambda: office.propose_save(wid, b),
                             "propose_share": lambda: office.propose_share(wid), "reload": lambda: office.reload(wid),
                             "edit_copy": lambda: office.edit_copy(wid), "export": lambda: office.export(wid, b),
                             "history": lambda: office.history_op(wid, b), "close": lambda: office.close(wid),
                             "sources": lambda: office.add_sources(wid, b),
                             "roles": lambda: office.set_roles(wid, b),
                             "decide_all": lambda: office.decide_all(wid, b)}
                    if verb in table:
                        return table[verb]()
                raise OfficeError("NOT_FOUND", "", 404)
            self._run(go)

    return H


def serve(office: Office, host: str, port: int):
    """Start the HTTP server on a loopback address only. Returns (server, token)."""
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise OfficeError("BIND_REFUSED", "the Office service binds to 127.0.0.1 only")
    except ValueError:
        raise OfficeError("BIND_REFUSED", "the Office service binds to 127.0.0.1 only") from None
    token = secrets.token_urlsafe(32)
    restrict_to_user(office.state, folder=True)
    write_token_file(office.state / "api-token", token)
    srv = ThreadingHTTPServer((host, port), make_handler(office, token))
    return srv, token


def restrict_to_user(path: Path, *, folder=False):
    """Replace the inherited ACL with one full-control entry for the current Windows user. For the state folder the entry
    is inherited by everything created inside it, so no other principal can read, delete or replace the token, the
    working copies, backups, history or the audit database."""
    if os.name != "nt":
        os.chmod(path, 0o700 if folder else 0o600)
        return
    user = os.environ.get("USERNAME")
    if not user:
        raise OfficeError("ACL_FAILED", "no current user")
    grant = f"{user}:(OI)(CI)F" if folder else f"{user}:F"
    r = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", grant], capture_output=True, text=True,
                       timeout=30)
    if r.returncode != 0:
        raise OfficeError("ACL_FAILED", "could not restrict access to this user")


def write_token_file(path: Path, token: str):
    """`<state>/api-token`, new on every launch, readable by the current Windows user only (scheduler model): the file
    is created empty, its inherited ACL is replaced by one full-control entry for this user, then the token is written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    path.write_bytes(b"")
    try:
        restrict_to_user(path)
    except OfficeError:
        path.unlink()
        raise
    path.write_text(token, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="uri_office")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--state", required=True)
    run.add_argument("--port", type=int, default=DEFAULT_PORT)
    run.add_argument("--owner", default="owner")
    run.add_argument("--google-token", help="absolute path of URI's existing Google token.json")
    run.add_argument("--brain-url", help="Runtime v1 base URL, e.g. http://127.0.0.1:18470")
    run.add_argument("--allow-root", action="append", default=None,
                     help="folder the owner's workbooks may come from (repeatable; default: the user's home folder)")
    a = ap.parse_args(argv)
    state = Path(a.state)
    brain = None
    if a.brain_url:
        from uri_operational_intelligence import brain_client as BC
        from .brain import OfficeBrain
        brain = OfficeBrain(BC.BrainClient(a.brain_url))
    office = Office(state, owner=a.owner, google=G.GoogleSheets(state, a.google_token), brain=brain,
                    allowed_roots=a.allow_root)
    srv, _ = serve(office, "127.0.0.1", a.port)
    (state / "service.json").write_text(json.dumps({"port": srv.server_address[1], "pid": os.getpid(),
                                                     "started": time.time(), "token_file": str(state / "api-token")}),
                                        encoding="utf-8")
    print(json.dumps({"ready": True, "port": srv.server_address[1]}), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
