"""Independent review S2 of the completion candidate (7893aaed, UI V2 session's reviewer) and the LOW findings of review
S1 the owner asked to repair first (2026-10-17, "Repair LOW findings first"): each test failed before its repair."""
import os
import stat
import sys
import threading

import pytest

from uri_office import grants as GR
from uri_office import xlsx_patch as X
from uri_office.ops import describe_op

from tests.office.test_completion_s1_repairs import office  # noqa: F401  (fixture)
from tests.office.test_local_rows_service import act, op


def _accept(o, wid, r):
    o.decide_all(wid, {"decision": "accept", "draft_version": r["draft"]["version"],
                       "set_sha256": o._session(wid).draft.proposed_set_sha256()})


# ---- S2-01: an invalid row op does not take the sheet ---------------------------------------------------------------
def test_an_invalid_row_op_does_not_block_a_valid_one_on_the_same_sheet(office):  # noqa: F811
    o, wid, p = office({"message": "x", "status": "propose", "ops": [
        op(op="delete_rows", sheet="Budget", at=5, count=0), op(op="insert_rows", sheet="Budget", at=4, count=1)]})
    r = o.instruct(wid, {"text": "Fix the rows", "active_sheet": "Budget"})
    assert [x["code"] for x in r["refused"]] == ["BAD_ROWS"]
    assert [c["op"]["op"] for c in r["draft"]["changes"]] == ["insert_rows"]


# ---- S2-02: a pending row change refuses the op, not the whole answer -------------------------------------------------
def test_a_row_op_on_a_sheet_with_a_pending_row_change_is_refused_on_its_own(office):  # noqa: F811
    o, wid, p = office(
        {"message": "Insert.", "status": "propose", "ops": [op(op="insert_rows", sheet="Budget", at=4, count=1)]},
        {"message": "Delete.", "status": "propose", "ops": [op(op="delete_rows", sheet="Budget", at=6, count=1)]})
    r = o.instruct(wid, {"text": "Add a row above row 4", "active_sheet": "Budget"})
    _accept(o, wid, r)
    before = o.view(wid)["draft"]["changes"]
    r = o.instruct(wid, {"text": "Delete row 6", "active_sheet": "Budget"})    # answered, not an error
    assert [x["code"] for x in r["refused"]] == ["ROW_CHANGE_PENDING"]
    assert r["draft"]["changes"] == before


# ---- S1-04: the delete card names every captured row ----------------------------------------------------------------
def test_the_delete_card_shows_every_row_it_deletes():
    shown = [[{"v": f"row{i}"}] for i in range(1, 6)]
    text = describe_op({"op": "delete_rows", "sheet": "S", "at": 2, "count": 5, "shown": shown})
    assert all(f"row{i}" in text for i in range(1, 6)) and "more" not in text
    text = describe_op({"op": "delete_rows", "sheet": "S", "at": 2, "count": 60, "shown": shown * 10})
    assert "row5" in text and "and 10 more rows not shown" in text


def test_the_delete_card_still_matches_the_single_row_wording(office):  # noqa: F811
    o, wid, p = office({"message": "Deletes Travel.", "status": "propose", "ops": [
        op(op="delete_rows", sheet="Budget", at=5, count=1)]})
    r = o.instruct(wid, {"text": "Remove the Travel row", "active_sheet": "Budget"})
    [ch] = r["draft"]["changes"]
    assert ch["text"] == "Delete row 5 on 'Budget' (now: Travel  |  60000  |  22100)"
    _accept(o, wid, r)
    assert "Travel  |  60000" in str(o.propose_save(wid, {})["messages"])
    assert act                                                     # (fixture helper import kept)


# ---- S1-06: grants and folders change under one lock -----------------------------------------------------------------
def test_grant_changes_wait_for_the_lock(tmp_path):
    g = GR.Grants([tmp_path])
    f = tmp_path / "a.xlsx"
    f.write_bytes(b"x")
    done = threading.Event()
    with g._lock:
        t = threading.Thread(target=lambda: (g.grant_open(str(f)), done.set()))
        t.start()
        assert not done.wait(0.3)                                  # blocked while another request holds the lock
    assert done.wait(5)
    t.join()


# ---- S1-07: removing a leftover never changes the published file's mode ------------------------------------------------
@pytest.mark.skipif(sys.platform == "win32", reason="PLATFORM-GATED: POSIX file modes; NOT VERIFIED on Windows")
def test_removing_a_hard_linked_leftover_keeps_the_saved_files_mode(tmp_path):
    saved = tmp_path / "Deck.pptx"
    saved.write_bytes(b"NEW")
    os.chmod(saved, 0o640)
    hold = tmp_path / ".Deck.pptx.0123456789ab-00000000abcdef01.uri-office.hold"
    os.link(saved, hold)
    X._unlink_quietly(hold)
    assert not hold.exists() and stat.S_IMODE(os.stat(saved).st_mode) == 0o640
