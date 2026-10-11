"""Regression tests for the URI-OFFICE-M1 review round 7 findings (each failed before its repair):

R7-01  after a Google save that moved rows, still-proposed insert_rows/delete_rows ops planned against the old rows were
       kept and, once accepted, inserted/deleted the wrong rows.
R7-02  when the post-save re-read failed, the panel kept the stale grid; the next edit (whose call re-read the sheet)
       was applied to the new layout at the stale grid's coordinates.
"""
import pytest
from test_review_r6_repairs import (  # noqa: F401 - fixture
    _act,
    _propose_and_accept,
    office,
)

from uri_office.draft import change_sha256
from uri_office.errors import OfficeError


def _proposed(o, wid):
    return [c for c in o.sessions[wid].draft.changes if c["state"] == "proposed"]


def test_leftover_row_op_is_dropped_after_rows_moved(office):  # noqa: F811
    o, wid, g, b = office
    b.ops = [{"op": "insert_rows", "sheet": "S", "at": 1, "count": 1},
             {"op": "delete_rows", "sheet": "S", "at": 3, "count": 1}]          # row 3 is 'c' as planned
    new = o.instruct(wid, {"text": "t", "active_sheet": "S"})["proposed"]
    ins = next(c for c in o.sessions[wid].draft.changes if c["cid"] == new[0])
    o.decide(wid, {"change_id": ins["cid"], "decision": "accept", "change_sha256": change_sha256(ins)})
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["status"] == "applied" and r["proposals_dropped"] == 1               # was 0
    assert _proposed(o, wid) == []                                               # the delete of old row 3 is gone
    assert g.sheets["S"] == {(2, 1): "a", (3, 1): "b", (4, 1): "c"}


def test_row_op_on_unmoved_sheet_is_kept(office):  # noqa: F811
    o, wid, g, b = office
    g.sheets["T"] = {(1, 1): "t"}
    o.close(wid)
    wid = o.open_google("https://docs.google.com/spreadsheets/d/" + "f" * 30)["workbook_id"]
    _propose_and_accept(o, wid, b, [{"op": "insert_rows", "sheet": "S", "at": 1, "count": 1}])
    b.ops = [{"op": "delete_rows", "sheet": "T", "at": 1, "count": 1}]
    o.instruct(wid, {"text": "t", "active_sheet": "T"})
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["proposals_dropped"] == 0
    assert [c["op"]["op"] for c in _proposed(o, wid)] == ["delete_rows"]


def _failed_reread_after_insert(o, wid, g, b):
    _propose_and_accept(o, wid, b, [{"op": "insert_rows", "sheet": "S", "at": 1, "count": 1}])
    g.fail_read = True
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["status"] == "applied" and r["layout_reloaded"] is False
    grid = r["workbook"]["sheets"][0]["cells"]
    assert grid["A1"]["v"] == "a" and grid["A2"]["v"] == "b"                     # the stale grid the panel shows
    g.fail_read = False
    return r


def test_edit_from_stale_grid_is_refused_when_its_call_rereads(office):  # noqa: F811
    o, wid, g, b = office
    _failed_reread_after_insert(o, wid, g, b)
    with pytest.raises(OfficeError) as e:
        o.edit(wid, {"sheet": "S", "cell": "A2", "value": "B!"})                 # 'b' in the stale grid
    assert e.value.code == "RELOAD_REQUIRED"                                      # was accepted at the new A2 ('a')
    v = o.view(wid)
    assert v["reload_required"] is False and v["workbook"]["sheets"][0]["cells"]["A3"]["v"] == "b"
    o.edit(wid, {"sheet": "S", "cell": "A3", "value": "B!", "layout_version": v["layout_version"]})
    assert o.action(_act(o.propose_save(wid, {})))["status"] == "applied"
    assert g.sheets["S"] == {(2, 1): "a", (3, 1): "B!", (4, 1): "c"}


def test_edit_from_stale_grid_is_refused_after_another_call_reread(office):  # noqa: F811
    o, wid, g, b = office
    r = _failed_reread_after_insert(o, wid, g, b)
    stale_version = r["layout_version"]
    b.ops = []
    u = o.instruct(wid, {"text": "t", "active_sheet": "S"})                      # this call re-reads the sheet
    assert u["workbook"]["sheets"][0]["cells"]["A3"]["v"] == "b"                  # and hands the panel the new grid
    assert u["layout_version"] != stale_version
    with pytest.raises(OfficeError) as e:
        o.edit(wid, {"sheet": "S", "cell": "A2", "value": "B!", "layout_version": stale_version})
    assert e.value.code == "RELOAD_REQUIRED"
    assert g.sheets["S"] == {(2, 1): "a", (3, 1): "b", (4, 1): "c"}
