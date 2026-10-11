"""Regression tests for the URI-OFFICE-M1 review round 8 finding (each failed before its repair):

R8-01  GET /workbook/<id> changed state (AC6): after a Google save whose re-read failed, view() re-read the sheet,
       rebased the draft (silently dropping still-proposed changes), replaced the workbook and bumped layout_version.
       The re-read is now an explicit POST /workbook/<id>/reload that reports how many proposals it dropped.
"""
import json
import threading

import pytest
from test_review_r6_repairs import (  # noqa: F401 - fixture
    _act,
    _propose_and_accept,
    office,
)
from test_service import call

from uri_office.service import serve


@pytest.fixture
def pending(office):  # noqa: F811
    """A Google session whose post-save re-read failed: an applied insert_rows not yet re-read, plus a still-proposed
    set_values on the same sheet, served over HTTP."""
    o, wid, g, b = office
    _propose_and_accept(o, wid, b, [{"op": "insert_rows", "sheet": "S", "at": 1, "count": 1}])
    b.ops = [{"op": "set_values", "sheet": "S", "range": "C1", "values": [["x"]]}]
    o.instruct(wid, {"text": "t", "active_sheet": "S"})
    g.fail_read = True
    r = o.action(_act(o.propose_save(wid, {})))
    assert r["status"] == "applied" and r["layout_reloaded"] is False
    g.fail_read = False
    srv, token = serve(o, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield o, wid, srv.server_address[1], token
    srv.shutdown()
    srv.server_close()


def _state(o, wid):
    s = o.sessions[wid]
    return (json.dumps(s.draft.snapshot(), sort_keys=True), json.dumps(s.workbook, sort_keys=True),
            list(s.stale_ops), s.layout_version)


def test_get_view_never_rereads_or_rebases(pending):
    o, wid, port, token = pending
    before = _state(o, wid)
    assert before[2]                                                    # a re-read is pending
    st, v, _ = call(port, token, "GET", f"/workbook/{wid}")
    assert st == 200 and v["reload_required"] is True                   # was False: the GET re-read the sheet
    assert _state(o, wid) == before                                     # draft, workbook, stale ops, layout unchanged
    assert [c["state"] for c in v["draft"]["changes"]].count("proposed") == 1


def test_post_reload_rereads_and_reports_dropped(pending):
    o, wid, port, token = pending
    version = o.sessions[wid].layout_version
    st, r, _ = call(port, token, "POST", f"/workbook/{wid}/reload", {})
    assert st == 200                                                    # was 404: no reload route
    assert r["reload_required"] is False and r["layout_version"] == version + 1
    assert r["proposals_dropped"] == 1                                  # the proposal planned on the moved rows
    assert r["workbook"]["sheets"][0]["cells"]["A2"]["v"] == "a"
    assert [c for c in r["draft"]["changes"] if c["state"] == "proposed"] == []


def test_post_reload_that_fails_again_changes_nothing(pending):
    o, wid, port, token = pending
    o.google.fail_read = True
    before = _state(o, wid)
    st, r, _ = call(port, token, "POST", f"/workbook/{wid}/reload", {})
    assert st == 200 and r["reload_required"] is True and r["proposals_dropped"] == 0
    assert _state(o, wid) == before
