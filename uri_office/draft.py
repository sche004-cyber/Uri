"""One versioned draft per open workbook (AC2).

The draft never touches the file. It holds the workbook as opened (`base`: values and formulas) and an ordered list of
changes on top of it:

  by "uri"   proposed by URI; shown marked; the owner accepts or rejects each one (bound to the change's SHA-256)
  by "user"  typed by the owner in the panel; applied in the draft at once

A user edit on a cell that still has a proposed URI change supersedes that change (state "edited_by_user"). Undo/redo
restore whole earlier versions (cap 50). `pending()` is what an approval will commit: the latest accepted or user value
per cell that differs from `base`, plus Google structural ops in order.
"""
from __future__ import annotations

import copy
import hashlib
import uuid

from uri_a2ui.surface import canonical

from . import refs
from .errors import OfficeError
from .ops import _XML_INVALID, describe_op

MAX_VERSIONS = 50
MAX_CHANGES = 20_000
LIVE = ("proposed", "accepted", "user")


def change_sha256(ch: dict) -> str:
    body = {k: ch.get(k) for k in ("cid", "by", "kind", "sheet", "cell", "before", "after", "op")}
    return hashlib.sha256(canonical(body)).hexdigest()


class Draft:
    def __init__(self, workbook_id: str, engine: str, workbook: dict):
        self.workbook_id, self.engine = workbook_id, engine
        self.base = {s["name"]: {ref: {k: c.get(k) for k in ("v", "f") if k in c} for ref, c in s["cells"].items()}
                     for s in workbook["sheets"]}
        self.locked = {s["name"]: set(s.get("locked", ())) for s in workbook["sheets"]}
        self.changes: list[dict] = []
        self._undo: list[list] = []
        self._redo: list[list] = []
        self.version = 1

    # ---- reading -------------------------------------------------------------------------------------------------
    def sheets(self):
        return list(self.base)

    def before(self, sheet, cell) -> dict:
        cur = dict(self.base.get(sheet, {}).get(cell, {}))
        for ch in self.changes:
            if ch["kind"] == "cell" and ch["sheet"] == sheet and ch["cell"] == cell and ch["state"] in ("accepted", "user"):
                cur = dict(ch["after"])
        return cur

    def snapshot(self) -> dict:
        """Every live change plus the latest 500 historical changes, in draft order."""
        shown = [ch for ch in self.changes if ch["state"] in LIVE or ch["state"] in ("rejected", "edited_by_user")]
        history = {id(ch) for ch in [c for c in shown if c["state"] in ("rejected", "edited_by_user")][-500:]}
        return {"workbook_id": self.workbook_id, "engine": self.engine, "version": self.version,
                "can_undo": bool(self._undo), "can_redo": bool(self._redo),
                "proposed_count": sum(1 for c in self.changes if c["state"] == "proposed"),
                "proposed_set_sha256": self.proposed_set_sha256(),
                "changes": [dict(ch, change_sha256=change_sha256(ch)) for ch in shown
                            if ch["state"] in LIVE or id(ch) in history]}

    # ---- versioning ----------------------------------------------------------------------------------------------
    def _state(self):
        """What undo and redo restore: the changes and, for a new workbook, its sheets (Codex R2-03). Only a new
        workbook changes its sheets inside the draft, so an opened file's (possibly large) base is not copied."""
        if self.engine == "new":
            return copy.deepcopy((self.changes, self.base, self.locked))
        return (copy.deepcopy(self.changes), None, None)

    def _restore(self, state):
        changes, base, locked = state
        self.changes = changes
        if base is not None:
            self.base, self.locked = base, locked

    def _push(self):
        self._undo.append(self._state())
        del self._undo[:-MAX_VERSIONS]
        self._redo.clear()
        self.version += 1

    def undo(self):
        if not self._undo:
            raise OfficeError("NOTHING_TO_UNDO")
        self._redo.append(self._state())
        self._restore(self._undo.pop())
        self.version += 1

    def redo(self):
        if not self._redo:
            raise OfficeError("NOTHING_TO_REDO")
        self._undo.append(self._state())
        self._restore(self._redo.pop())
        self.version += 1

    # ---- edits ---------------------------------------------------------------------------------------------------
    def _new(self, by, kind, state, **kw) -> dict:
        if len(self.changes) >= MAX_CHANGES:
            raise OfficeError("DRAFT_TOO_LARGE", "save or discard before making more changes")
        return {"cid": uuid.uuid4().hex[:16], "by": by, "kind": kind, "state": state, "sheet": kw.get("sheet"),
                "cell": kw.get("cell"), "before": kw.get("before"), "after": kw.get("after"), "op": kw.get("op")}

    @staticmethod
    def _after(edit) -> dict:
        return {"f": edit["formula"]} if "formula" in edit else {"v": edit.get("value")}

    def _check_cell(self, sheet, cell) -> str:
        """Returns the canonical ref; locks and changes are keyed by it, never by the raw input."""
        if sheet not in self.base:
            raise OfficeError("UNKNOWN_SHEET", str(sheet)[:64])
        cell = refs.canonical_cell(cell)
        if cell in self.locked.get(sheet, ()):
            raise OfficeError("CELL_NOT_EDITABLE", f"{sheet}!{cell}")
        return cell

    def propose(self, edits: list) -> list:
        """URI's validated edits (from `ops.to_cell_edits`) become proposed, marked changes. Returns the new changes.
        In a new workbook (engine "new", M2-D4/D12) add_sheet takes effect at once and is recorded as an
        accepted structural change. All or nothing: a refusal part way (draft cap, unknown sheet, locked cell)
        leaves the draft exactly as it was (Codex C-03)."""
        if len(self.changes) + len(edits) > MAX_CHANGES:
            raise OfficeError("DRAFT_TOO_LARGE", "save or discard before making more changes")
        saved = (copy.deepcopy(self.changes), copy.deepcopy(self.base), copy.deepcopy(self.locked),
                 copy.deepcopy(self._undo), copy.deepcopy(self._redo), self.version)
        try:
            return self._propose(edits)
        except Exception:
            self.changes, self.base, self.locked, self._undo, self._redo, self.version = saved
            raise

    def _propose(self, edits: list) -> list:
        self._push()
        new = []
        for e in edits:
            if "op" in e and self.engine == "new":
                self._sheet_op(e)
                ch = self._new("uri", "struct", "accepted", op=e, sheet=e.get("sheet") or e.get("name"))
            elif "op" in e:
                op = dict(e)
                if op["op"] == "delete_rows":           # the card shows what the rows hold now (OD-R2: before values)
                    op["shown"] = self._rows_now(op["sheet"], op["at"], op["count"])
                ch = self._new("uri", "struct", "proposed", op=op, sheet=e.get("sheet"))
                ch["text"] = describe_op(op)
            else:
                cell = self._check_cell(e["sheet"], e["cell"])
                ch = self._new("uri", "cell", "proposed", sheet=e["sheet"], cell=cell,
                               before=self.before(e["sheet"], cell), after=self._after(e))
            self.changes.append(ch)
            new.append(ch)
        return new

    def _rows_now(self, sheet: str, at: int, count: int) -> list:
        """Values of rows at..at+count-1 as the draft holds them (accepted and own changes included), columns A to the
        last used one, at most 50 rows."""
        cells = dict(self.base.get(sheet, {}))
        for ch in self.changes:
            if ch["kind"] == "cell" and ch["sheet"] == sheet and ch["state"] in ("accepted", "user"):
                cells[ch["cell"]] = ch["after"]
        out = []
        for r in range(at, at + min(count, 50)):
            row = {}
            for ref, c in cells.items():
                col, rr = refs.parse_cell(ref)
                if rr == r and (c.get("f") or c.get("v") not in (None, "")):
                    row[col] = {"f": c["f"]} if c.get("f") else {"v": c.get("v")}
            out.append([row.get(col, {"v": None}) for col in range(1, max(row) + 1)] if row else [])
        return out

    def _sheet_op(self, op: dict):
        """New workbook only: add a sheet now. Undo and redo restore the sheets with the changes."""
        if op["op"] == "add_sheet":
            name = op["name"]
            if not isinstance(name, str) or _XML_INVALID.search(name) or \
                    any(name.casefold() == sheet.casefold() for sheet in self.base):
                raise OfficeError("BAD_SHEET_NAME", str(name)[:40])
            self.base[op["name"]] = {}
            self.locked[op["name"]] = set()
        else:
            raise OfficeError("OP_NOT_SUPPORTED_LOCALLY", op["op"])

    def proposed_set_sha256(self) -> str:
        """M2-D2: the hash of every change still proposed, as (change id, change hash) pairs in id order."""
        pairs = sorted((c["cid"], change_sha256(c)) for c in self.changes if c["state"] == "proposed")
        return hashlib.sha256(canonical(pairs)).hexdigest()

    def decide_all(self, decision: str, version, set_sha: str) -> list:
        """Accept or reject every proposed change at once, only if the draft is still at `version` and the proposed set
        still hashes to `set_sha` (what the owner saw). All or nothing. Returns correction events for rejections."""
        if decision not in ("accept", "reject"):
            raise OfficeError("BAD_DECISION")
        if version != self.version or set_sha != self.proposed_set_sha256():
            raise OfficeError("STALE_CHANGE", "the suggested changes differ from what was shown; review them again")
        todo = [c for c in self.changes if c["state"] == "proposed"]
        if not todo:
            raise OfficeError("NOTHING_PROPOSED")
        for c in todo:
            if c["kind"] == "cell" and c["before"] != self.before(c["sheet"], c["cell"]):
                raise OfficeError("STALE_CHANGE", "a cell changed after URI proposed this; review it again")
        self._push()
        events = []
        for c in self.changes:
            if c["state"] != "proposed":
                continue
            c["state"] = "accepted" if decision == "accept" else "rejected"
            if decision == "reject":
                events.append({"kind": "uri_change_rejected", "change_id": c["cid"], "sheet": c["sheet"],
                               "cell": c["cell"]})
        return events

    def user_edit(self, edit: dict) -> list:
        """The owner typed in the panel. Returns correction events (for the consented history)."""
        cell = self._check_cell(edit["sheet"], edit["cell"])
        self._push()
        events = []
        for ch in self.changes:
            if ch["kind"] == "cell" and ch["state"] == "proposed" and ch["sheet"] == edit["sheet"] \
                    and ch["cell"] == cell:
                ch["state"] = "edited_by_user"
                events.append({"kind": "uri_change_edited_by_user", "change_id": ch["cid"], "sheet": ch["sheet"],
                               "cell": ch["cell"]})
        self.changes.append(self._new("user", "cell", "user", sheet=edit["sheet"], cell=cell,
                                      before=self.before(edit["sheet"], cell), after=self._after(edit)))
        return events

    def decide(self, cid: str, decision: str, sha: str) -> list:
        """Accept or reject one proposed URI change. `sha` must equal the hash of the change the owner saw."""
        if decision not in ("accept", "reject"):
            raise OfficeError("BAD_DECISION")
        ch = next((c for c in self.changes if c["cid"] == cid), None)
        if ch is None or ch["by"] != "uri":
            raise OfficeError("UNKNOWN_CHANGE")
        if ch["state"] != "proposed":
            raise OfficeError("ALREADY_DECIDED", ch["state"])
        if sha != change_sha256(ch):
            raise OfficeError("STALE_CHANGE", "the change differs from what was shown; review it again")
        if ch["kind"] == "cell" and ch["before"] != self.before(ch["sheet"], ch["cell"]):
            raise OfficeError("STALE_CHANGE", "the cell changed after URI proposed this; review it again")
        self._push()
        ch = next(c for c in self.changes if c["cid"] == cid)
        ch["state"] = "accepted" if decision == "accept" else "rejected"
        if decision == "reject":
            return [{"kind": "uri_change_rejected", "change_id": cid, "sheet": ch["sheet"], "cell": ch["cell"]}]
        return []

    # ---- commit --------------------------------------------------------------------------------------------------
    def pending(self) -> dict:
        """What an approval would commit, in a stable order. `before` is the value in the file as opened."""
        latest: dict = {}
        structs = []
        for ch in self.changes:
            if ch["state"] not in ("accepted", "user"):
                continue
            if ch["kind"] == "struct":
                structs.append(ch["op"])
            else:
                latest[(ch["sheet"], ch["cell"])] = ch["after"]
        edits = []
        for (sheet, cell), after in latest.items():
            base = self.base.get(sheet, {}).get(cell, {})
            same = (base.get("f") == after["f"]) if after.get("f") else \
                (base.get("f") is None and base.get("v") == after.get("v"))
            if same:
                continue
            edits.append({"sheet": sheet, "cell": cell, "before": base, "after": after})
        edits.sort(key=lambda e: (list(self.base).index(e["sheet"]) if e["sheet"] in self.base else 0, e["cell"]))
        return {"edits": edits, "struct_ops": structs}

    def committed(self, pending: dict):
        """After a successful save: the saved values become the new base, decided changes are cleared."""
        for e in pending["edits"]:
            self.base.setdefault(e["sheet"], {})[e["cell"]] = dict(e["after"])
        self.changes = [c for c in self.changes if c["state"] == "proposed"]
        for c in self.changes:
            if c["kind"] == "cell":
                c["before"] = self.before(c["sheet"], c["cell"])
        self._undo.clear()
        self._redo.clear()
        self.version += 1

    def rebase(self, workbook: dict, struct_ops: list) -> int:
        """After a committed save that changed the layout (Google structural ops): the re-read workbook becomes the
        base. Still-proposed changes follow sheet renames; proposed cell changes on a sheet whose rows moved are
        dropped (their coordinates no longer name the cell URI planned against), and so are proposed row inserts and
        deletes there (their row numbers name the old rows too). Returns how many were dropped."""
        renames, moved = layout_moves(struct_ops)
        self.base = {s["name"]: {ref: {k: c.get(k) for k in ("v", "f") if k in c} for ref, c in s["cells"].items()}
                     for s in workbook["sheets"]}
        self.locked = {s["name"]: set(s.get("locked", ())) for s in workbook["sheets"]}
        kept, dropped = [], 0
        for c in self.changes:
            if c["sheet"] in moved and (c["kind"] == "cell" or c["op"]["op"] in ROW_OPS):
                dropped += 1
                continue
            if c["sheet"] in renames:
                c["sheet"] = renames[c["sheet"]]
                if c["kind"] == "struct":
                    c["op"] = {**c["op"], "sheet": c["sheet"]}
            if c["kind"] == "cell" and c["sheet"] not in self.base:
                dropped += 1
                continue
            kept.append(c)
        self.changes = kept
        for c in self.changes:
            if c["kind"] == "cell":
                c["before"] = self.before(c["sheet"], c["cell"])
        self.version += 1
        return dropped


ROW_OPS = ("insert_rows", "delete_rows")


def layout_moves(struct_ops: list) -> tuple:
    """What applied structural ops did to the layout: ({name as the draft knew it: name now}, {names as the draft knew
    them whose rows moved})."""
    renames: dict = {}
    moved: set = set()
    for op in struct_ops:
        orig = next((o for o, n in renames.items() if n == op.get("sheet")), op.get("sheet"))
        if op["op"] == "rename_sheet":
            renames[orig] = op["name"]
        elif op["op"] in ROW_OPS:
            moved.add(orig)
    return renames, moved


def patch_edits(pending: dict) -> list:
    """Draft pending edits -> xlsx_patch edits."""
    out = []
    for e in pending["edits"]:
        a = e["after"]
        out.append({"sheet": e["sheet"], "cell": e["cell"], **({"formula": a["f"]} if a.get("f") else {"value": a.get("v")})})
    return out
