"""Regression tests for the URI-OFFICE-M1 review round 6 finding (each failed before its repair):

R6-01  after an approved Google save with structural ops (rename_sheet, add_sheet, insert_rows, delete_rows) the
       service's workbook snapshot and the draft base kept the old layout: renamed/added sheets could not be edited, the
       panel and the Brain saw stale sheet names and row positions.
"""
import pytest

from uri_office import ops as O
from uri_office.draft import change_sha256
from uri_office.errors import OfficeError
from uri_office.service import Office

LINK = "https://docs.google.com/spreadsheets/d/" + "f" * 30


class FakeGoogle:
    """A Google sheet as {title: {(row, col): value}}; `apply` performs the structural ops like batchUpdate does."""

    def __init__(self):
        self.sheets = {"S": {(1, 1): "a", (2, 1): "b", (3, 1): "c"}}
        self.fail_read = False

    def check_sheet(self, fid):
        return {"id": fid, "name": "g"}

    def writable(self, fid):
        return True

    def read(self, fid):
        if self.fail_read:
            raise OfficeError("GOOGLE_NOT_CONNECTED", "", 409)
        from uri_office import refs
        out = []
        for i, (name, cells) in enumerate(self.sheets.items()):
            out.append({"name": name, "index": i, "sheet_id": i, "max_row": max([r for r, _ in cells] or [0]),
                        "max_col": max([c for _, c in cells] or [0]), "truncated": False,
                        "cells": {refs.cell_ref(c, r): {"v": v} for (r, c), v in cells.items()},
                        "merges": [], "col_widths": {}, "row_heights": {}, "locked": []})
        return {"sheets": out, "styles": {}, "kept_not_shown": {}}

    def apply(self, fid, body):
        from uri_office import refs
        for e in body["edits"]:
            col, row = refs.parse_cell(e["cell"])
            self.sheets[e["sheet"]][(row, col)] = e["after"].get("v")
        for op in body["struct_ops"]:
            if op["op"] == "rename_sheet":
                self.sheets = {(op["name"] if k == op["sheet"] else k): v for k, v in self.sheets.items()}
            elif op["op"] == "add_sheet":
                self.sheets[op["name"]] = {}
            elif op["op"] == "insert_rows":
                self.sheets[op["sheet"]] = {((r + op["count"]) if r >= op["at"] else r, c): v
                                            for (r, c), v in self.sheets[op["sheet"]].items()}
            elif op["op"] == "delete_rows":
                end = op["at"] + op["count"]
                self.sheets[op["sheet"]] = {((r - op["count"]) if r >= end else r, c): v
                                            for (r, c), v in self.sheets[op["sheet"]].items()
                                            if not op["at"] <= r < end}
        return {"cells": len(body["edits"]), "struct_ops": len(body["struct_ops"])}


class Brain:
    def __init__(self):
        self.ops, self.sheets = [], None

    def plan(self, text, *, sheets, active, engine, locked, history_rows, **_):
        self.sheets = sheets
        edits = []
        for op in self.ops:
            edits += O.to_cell_edits(op, engine=engine, sheets=[s["name"] for s in sheets], locked=locked)
        return {"message": "", "edits": edits, "refused": [], "metrics": {}}


def _act(prop):
    m = prop["messages"]
    model = m[2]["updateDataModel"]["value"]
    return {"name": "office.apply_change", "surfaceId": m[0]["createSurface"]["surfaceId"], "sourceComponentId": "apply",
            "context": {"surface_digest": model["bound"]["surface"]["digest"],
                        "change_sha256": model["bound"]["change_sha256"]}}


@pytest.fixture
def office(tmp_path):
    g, b = FakeGoogle(), Brain()
    o = Office(tmp_path / "state", allowed_roots=[tmp_path], google=g, brain=b)
    return o, o.open_google(LINK)["workbook_id"], g, b


def _propose_and_accept(o, wid, b, ops):
    b.ops = ops
    new = o.instruct(wid, {"text": "t", "active_sheet": "S"})["proposed"]
    for ch in o.sessions[wid].draft.changes:
        if ch["cid"] in new:
            o.decide(wid, {"change_id": ch["cid"], "decision": "accept", "change_sha256": change_sha256(ch)})


def _names(wb):
    return [s["name"] for s in wb["sheets"]]


def test_rename_and_add_sheet_are_reflected_after_save(office):
    o, wid, g, b = office
    _propose_and_accept(o, wid, b, [{"op": "rename_sheet", "sheet": "S", "name": "Budget"},
                                    {"op": "add_sheet", "name": "New"}])
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["status"] == "applied" and list(g.sheets) == ["Budget", "New"]
    assert _names(r["workbook"]) == ["Budget", "New"]                 # was ['S']
    assert _names(o.view(wid)["workbook"]) == ["Budget", "New"]
    o.edit(wid, {"sheet": "Budget", "cell": "B1", "value": 5})        # was UNKNOWN_SHEET
    o.edit(wid, {"sheet": "New", "cell": "A1", "value": 7})
    b.ops = []
    o.instruct(wid, {"text": "t", "active_sheet": "Budget"})
    assert [s["name"] for s in b.sheets] == ["Budget", "New"]         # the Brain plans against the new names
    r = o.action(_act(o.propose_save(wid, {})))                       # was TARGET_CHANGED (sheet 'S' gone)
    assert r["status"] == "applied"
    assert g.sheets["Budget"][(1, 2)] == 5 and g.sheets["New"][(1, 1)] == 7


def test_insert_rows_moves_snapshot_and_draft_base(office):
    o, wid, g, b = office
    _propose_and_accept(o, wid, b, [{"op": "insert_rows", "sheet": "S", "at": 2, "count": 2}])
    # a still-proposed cell change planned against the old rows must not survive the shift
    b.ops = [{"op": "set_values", "sheet": "S", "range": "B2", "values": [["x"]]}]
    o.instruct(wid, {"text": "t", "active_sheet": "S"})
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["status"] == "applied" and r["proposals_dropped"] == 1
    cells = r["workbook"]["sheets"][0]["cells"]
    assert cells["A1"]["v"] == "a" and cells["A4"]["v"] == "b" and cells["A5"]["v"] == "c"   # was b at A2, c at A3
    assert "A2" not in cells and "A3" not in cells
    d = o.sessions[wid].draft
    assert d.base["S"]["A4"] == {"v": "b"} and "A2" not in d.base["S"]
    assert r["draft"]["changes"] == []
    # the owner types into what is now row 4 ("b"): the save's before-value is the shifted one and lands there
    o.edit(wid, {"sheet": "S", "cell": "A4", "value": "B!"})
    prop = o.propose_save(wid, {})
    assert o.action(_act(prop))["status"] == "applied"
    assert g.sheets["S"][(4, 1)] == "B!" and g.sheets["S"][(1, 1)] == "a"


def test_delete_rows_and_proposals_follow_rename(office):
    o, wid, g, b = office
    _propose_and_accept(o, wid, b, [{"op": "delete_rows", "sheet": "S", "at": 1, "count": 1}])
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["workbook"]["sheets"][0]["cells"]["A1"]["v"] == "b"      # was 'a'
    _propose_and_accept(o, wid, b, [{"op": "rename_sheet", "sheet": "S", "name": "T"}])
    b.ops = [{"op": "set_values", "sheet": "S", "range": "C1", "values": [["kept"]]}]
    o.instruct(wid, {"text": "t", "active_sheet": "S"})
    r = o.action(_act(o.propose_save(wid, {})))
    ch = [c for c in r["draft"]["changes"] if c["state"] == "proposed"]
    assert [(c["sheet"], c["cell"]) for c in ch] == [("T", "C1")]     # follows the rename, still decidable
    o.decide(wid, {"change_id": ch[0]["cid"], "decision": "accept", "change_sha256": ch[0]["change_sha256"]})
    assert o.action(_act(o.propose_save(wid, {})))["status"] == "applied"
    assert g.sheets["T"][(1, 3)] == "kept"


def test_failed_reread_blocks_until_reloaded(office):
    o, wid, g, b = office
    _propose_and_accept(o, wid, b, [{"op": "rename_sheet", "sheet": "S", "name": "Budget"}])
    g.fail_read = True
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["status"] == "applied" and r["layout_reloaded"] is False   # the write itself succeeded
    assert o.view(wid)["reload_required"] is True
    with pytest.raises(OfficeError) as e:
        o.edit(wid, {"sheet": "S", "cell": "B1", "value": 5})           # stale layout: never edit it
    assert e.value.code == "RELOAD_REQUIRED"
    g.fail_read = False
    o.edit(wid, {"sheet": "Budget", "cell": "B1", "value": 5})
    assert _names(o.view(wid)["workbook"]) == ["Budget"] and o.view(wid)["reload_required"] is False
