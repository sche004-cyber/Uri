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

from .errors import OfficeError

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
        return {"workbook_id": self.workbook_id, "engine": self.engine, "version": self.version,
                "can_undo": bool(self._undo), "can_redo": bool(self._redo),
                "changes": [dict(ch, change_sha256=change_sha256(ch)) for ch in self.changes
                            if ch["state"] in LIVE or ch["state"] in ("rejected", "edited_by_user")][-500:]}

    # ---- versioning ----------------------------------------------------------------------------------------------
    def _push(self):
        self._undo.append(copy.deepcopy(self.changes))
        del self._undo[:-MAX_VERSIONS]
        self._redo.clear()
        self.version += 1

    def undo(self):
        if not self._undo:
            raise OfficeError("NOTHING_TO_UNDO")
        self._redo.append(copy.deepcopy(self.changes))
        self.changes = self._undo.pop()
        self.version += 1

    def redo(self):
        if not self._redo:
            raise OfficeError("NOTHING_TO_REDO")
        self._undo.append(copy.deepcopy(self.changes))
        self.changes = self._redo.pop()
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

    def _check_cell(self, sheet, cell):
        if sheet not in self.base:
            raise OfficeError("UNKNOWN_SHEET", str(sheet)[:64])
        if cell in self.locked.get(sheet, ()):
            raise OfficeError("CELL_NOT_EDITABLE", f"{sheet}!{cell}")

    def propose(self, edits: list) -> list:
        """URI's validated edits (from `ops.to_cell_edits`) become proposed, marked changes. Returns the new changes."""
        self._push()
        new = []
        for e in edits:
            if "op" in e:
                ch = self._new("uri", "struct", "proposed", op=e, sheet=e.get("sheet"))
            else:
                self._check_cell(e["sheet"], e["cell"])
                ch = self._new("uri", "cell", "proposed", sheet=e["sheet"], cell=e["cell"],
                               before=self.before(e["sheet"], e["cell"]), after=self._after(e))
            self.changes.append(ch)
            new.append(ch)
        return new

    def user_edit(self, edit: dict) -> list:
        """The owner typed in the panel. Returns correction events (for the consented history)."""
        self._check_cell(edit["sheet"], edit["cell"])
        self._push()
        events = []
        for ch in self.changes:
            if ch["kind"] == "cell" and ch["state"] == "proposed" and ch["sheet"] == edit["sheet"] \
                    and ch["cell"] == edit["cell"]:
                ch["state"] = "edited_by_user"
                events.append({"kind": "uri_change_edited_by_user", "change_id": ch["cid"], "sheet": ch["sheet"],
                               "cell": ch["cell"]})
        self.changes.append(self._new("user", "cell", "user", sheet=edit["sheet"], cell=edit["cell"],
                                      before=self.before(edit["sheet"], edit["cell"]), after=self._after(edit)))
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


def patch_edits(pending: dict) -> list:
    """Draft pending edits -> xlsx_patch edits."""
    out = []
    for e in pending["edits"]:
        a = e["after"]
        out.append({"sheet": e["sheet"], "cell": e["cell"], **({"formula": a["f"]} if a.get("f") else {"value": a.get("v")})})
    return out
