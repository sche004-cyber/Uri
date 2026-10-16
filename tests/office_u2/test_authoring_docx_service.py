"""Milestone C through the real HTTP service and engine (marked `engine`): open a Word document, edit it, the preview
renders the working copy, the save card replaces the file only after approval (C-1, C-2, C-5); every built-in layout
renders in LibreOffice (C-6)."""
from __future__ import annotations

import io

from docx import Document

from test_authoring_docx import report_bytes
from test_authoring_service import svc  # noqa: F401 (fixture)
from test_service_o2 import _run_card, _seed, _wait, call, engine, verified_manifest  # noqa: F401 (fixture)


def _ready(port, token, pid):
    return _wait(lambda: (lambda x: x if x["preview"]["state"] != "rendering" else None)(
        call(port, token, "GET", f"/document/{pid}")[1]))


def test_layout_list_route(svc):  # noqa: F811
    _, port, token, _ = svc
    st, out = call(port, token, "GET", "/authoring/layouts")
    assert st == 200 and [x["id"] for x in out["docx"]][:2] == ["blank", "letter"]


@engine
def test_edit_a_word_document_preview_and_save_end_to_end(svc, verified_manifest):  # noqa: F811
    office, port, token, root = svc
    _seed(office, verified_manifest)
    src = root / "Annual Report.docx"
    src.write_bytes(report_bytes())
    before = src.read_bytes()
    st, doc = call(port, token, "POST", "/open/document", {"path": str(src)})
    assert st == 200 and doc["kind"] == "docx"
    st, v = call(port, token, "POST", "/authoring/edit", {"document_id": doc["document_id"]})
    assert st == 200 and v["kind"] == "docx"
    aid, b3 = v["authoring_id"], v["doc"]["blocks"][3]
    st, v = call(port, token, "POST", f"/authoring/{aid}/op",
                 {"op": {"op": "set_paragraph_text", "block": 3, "expect": b3["expect"], "text": "Costs fell."}})
    assert st == 200
    st, v = call(port, token, "POST", f"/authoring/{aid}/op", {"op": {"op": "insert_page_break", "after": 3}})
    st, v = call(port, token, "POST", f"/authoring/{aid}/op", {"op": {"op": "insert_page_number"}})
    assert st == 200 and len(v["changes"]) == 3
    # a stale address is refused through the service too
    st, err = call(port, token, "POST", f"/authoring/{aid}/op",
                   {"op": {"op": "delete_block", "block": 3, "expect": b3["expect"]}})
    assert st == 409 and err["error"] == "STALE_BLOCK"
    pv = _ready(port, token, v["preview_document_id"])
    assert pv["preview"]["state"] == "ready" and pv["pages"] >= 2              # the page break made a second page
    assert src.read_bytes() == before
    st, card = call(port, token, "POST", f"/authoring/{aid}/save", {})
    assert st == 200 and "Save this document?" in str(card["messages"])
    st, r = _run_card(port, token, card["messages"], "apply")
    assert st == 200 and r["status"] == "applied", r
    saved = Document(io.BytesIO(src.read_bytes()))
    assert "Costs fell." in [p.text for p in saved.paragraphs]
    assert call(port, token, "POST", f"/authoring/{aid}/close", {})[0] == 200


@engine
def test_every_built_in_layout_renders(svc, verified_manifest):  # noqa: F811
    office, port, token, root = svc
    _seed(office, verified_manifest)
    st, lays = call(port, token, "GET", "/authoring/layouts")
    for lay in lays["docx"]:
        st, v = call(port, token, "POST", "/authoring/new", {"kind": "docx", "layout": lay["id"]})
        assert st == 200, (lay, v)
        pv = _ready(port, token, v["preview_document_id"])
        assert pv["preview"]["state"] == "ready" and pv["pages"] >= 1, (lay, pv)
        call(port, token, "POST", f"/authoring/{v['authoring_id']}/close", {})
