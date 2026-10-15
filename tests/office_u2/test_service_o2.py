"""O2 routes through the real HTTP service. Route security for every new route (AC-O2-13); contract (C7);
end to end with the real engine (marked `engine`): open and preview DOCX/PPTX/PDF (AC-O2-1), Save as PDF with the plan
card, validation, output card and no-overwrite write (AC-O2-7, AC-O2-12), Excel unsaved-change refusal (P-6),
cancel, and no document content in records (AC-O2-14)."""
from __future__ import annotations

import hashlib
import http.client
import json
import shutil
import threading
import time
from pathlib import Path

import pytest

import canaries as CN
from conftest import lo_present, needs_windows, pdf_with_text
from uri_office import contracts as K
from uri_office.service import Office, serve

SENTINEL = "SENTINEL-CONTENT-7f3a"


def call(port, token, method, path, body=None, headers=None, raw=False):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    h.update(headers or {})
    c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    if raw:
        return r.status, data, dict(r.getheaders())
    return r.status, json.loads(data or b"{}")


@pytest.fixture
def svc(tmp_path):
    office = Office(tmp_path / "state", allowed_roots=[tmp_path])
    srv, token = serve(office, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield office, srv.server_address[1], token, tmp_path
    srv.shutdown()
    srv.server_close()
    if office._hub is not None:
        office._hub.shutdown()


GET_ROUTES = ["/contract", "/capabilities", "/recent", "/document/0123456789abcdef",
              "/document/0123456789abcdef/page/1", "/workflow/0123456789abcdef"]
POST_ROUTES = ["/open/document", "/request", "/workflow", "/recent/remove", "/recent/clear",
               "/document/0123456789abcdef/search", "/document/0123456789abcdef/close",
               "/workflow/0123456789abcdef/cancel", "/workflow/0123456789abcdef/resume",
               "/workflow/0123456789abcdef/accept_warnings", "/workflow/0123456789abcdef/propose_save"]


@pytest.mark.parametrize("method,path", [("GET", p) for p in GET_ROUTES] + [("POST", p) for p in POST_ROUTES])
def test_every_new_route_refuses_bad_token_host_and_origin(svc, method, path):
    _, port, token, _ = svc
    assert call(port, "wrong", method, path, {} if method == "POST" else None)[0] == 401
    assert call(port, token, method, path, {} if method == "POST" else None, {"Host": "evil.example"})[0] == 421
    assert call(port, token, method, path, {} if method == "POST" else None, {"Origin": "http://x"})[0] == 403


def test_contract_and_capabilities(svc):
    _, port, token, _ = svc
    st, c = call(port, token, "GET", "/contract")
    assert st == 200 and c["contract"] == K.CONTRACT_VERSION
    st, caps = call(port, token, "GET", "/capabilities")
    assert st == 200 and {g["id"] for g in caps["goals"]} >= {"pdfs", "data"}


def test_unknown_ids_and_paths_outside_grants(svc, tmp_path):
    office, port, token, root = svc
    assert call(port, token, "GET", "/document/zz")[0] == 404
    assert call(port, token, "GET", "/workflow/0123456789abcdef")[1]["error"] in ("UNKNOWN_WORKFLOW",)
    outside = Path(root.anchor) / "Windows" / "win.ini"
    st, out = call(port, token, "POST", "/open/document", {"path": str(outside)})
    assert st in (400, 415) and out["error"] in ("PATH_REFUSED", "UNSUPPORTED_KIND")
    st, out = call(port, token, "POST", "/open/document", {"path": str(root / "x.txt")})
    assert out["error"] == "UNSUPPORTED_KIND" and "message" in out and out["recovery"] == ["open_other"]


def test_request_routes_without_brain(svc):
    _, port, token, _ = svc
    assert call(port, token, "POST", "/request", {"text": "convert this to pdf", "target": {"kind": "docx"}})[1][
        "intent"] == "save_as_pdf"
    assert call(port, token, "POST", "/request", {"text": "print this", "target": {"kind": "docx"}})[1][
        "result"] == "planned"
    assert call(port, token, "POST", "/request", {"text": "do the usual"})[1]["result"] == "clarify"


# ---------------------------------------------------------------- engine end to end ----------------------------
def engine(fn):
    for m in (pytest.mark.engine, needs_windows,
              pytest.mark.skipif(not lo_present(), reason="pinned LibreOffice not present on this PC")):
        fn = m(fn)
    return fn


@pytest.fixture(scope="module")
def verified_manifest(tmp_path_factory):
    from uri_office import engines as E
    st = tmp_path_factory.mktemp("manifest")
    ei = E.EngineIntegrity("libreoffice", st)
    ei.verify_full()
    return ei.store


def _seed(office, manifest):
    dst = office.state / "engines"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(manifest, dst / manifest.name)


def _wait(fn, timeout=240):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        v = fn()
        if v:
            return v
        time.sleep(0.3)
    raise AssertionError("timed out")


def _letter(path: Path):
    import docx
    d = docx.Document()
    d.add_heading("Office Order No. 41", 1)
    d.add_paragraph(SENTINEL + " The committee shall meet on the first Monday of every month.")
    d.add_heading("Distribution", 2)
    d.add_paragraph("All section officers.")
    d.save(path)
    return path


def _run_card(port, token, messages, button):
    sid = messages[0]["createSurface"]["surfaceId"]
    bound = messages[2]["updateDataModel"]["value"]["bound"]
    key = "plan_sha256" if "plan_sha256" in bound else "change_sha256"
    name = {("plan_sha256", "apply"): "office.run_plan", ("plan_sha256", "reject"): "office.discard_plan",
            ("change_sha256", "apply"): "office.apply_change", ("change_sha256", "reject"): "office.reject_change"}[
        (key, button)]
    return call(port, token, "POST", "/a2ui/action", {"action": {
        "name": name, "surfaceId": sid, "sourceComponentId": button,
        "context": {"surface_digest": bound["surface"]["digest"], key: bound[key]}}})


@engine
def test_docx_open_preview_and_save_as_pdf_end_to_end(svc, verified_manifest):
    office, port, token, root = svc
    _seed(office, verified_manifest)
    src = _letter(root / "order.docx")
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    st, view = call(port, token, "POST", "/open/document", {"path": str(src)})
    assert st == 200 and view["kind"] == "docx" and view["outline"][0]["title"] == "Office Order No. 41"
    did = view["document_id"]
    view = _wait(lambda: (lambda v: v if v["preview"]["state"] != "rendering" else None)(
        call(port, token, "GET", f"/document/{did}")[1]))
    assert view["preview"]["state"] == "ready" and view["pages"] >= 1
    st, png, hdr = call(port, token, "GET", f"/document/{did}/page/1?w=440", raw=True)
    assert st == 200 and hdr["Content-Type"] == "image/png" and png[:4] == b"\x89PNG"
    # Save as PDF: plan card -> run -> ready
    st, wf = call(port, token, "POST", "/workflow", {"capability": "save_as_pdf",
                                                     "inputs": [{"document_id": did}]})
    assert st == 200 and wf["view"]["state"] == "waiting_approval"
    wid = wf["workflow_id"]
    st, r = _run_card(port, token, wf["messages"], "apply")
    assert st == 200 and r["status"] == "applied" and r["state"] == "running"
    # replaying the same plan approval is refused
    assert _run_card(port, token, wf["messages"], "apply")[0] != 200
    v = _wait(lambda: (lambda x: x if x["state"] not in ("running",) else None)(
        call(port, token, "GET", f"/workflow/{wid}")[1]))
    assert v["state"] in ("ready_to_save", "needs_review"), v
    assert [s["state"] for s in v["steps"]] == ["done"] * 4
    if any(f["severity"] == "warning" for f in v["findings"]):
        assert call(port, token, "POST", f"/workflow/{wid}/propose_save",
                    {"save_as_path": str(root / "order.pdf")})[1]["error"] == "WARNINGS_NOT_ACCEPTED"
        assert call(port, token, "POST", f"/workflow/{wid}/accept_warnings", {})[0] == 200
    # destination that exists is refused at proposal time
    (root / "taken.pdf").write_bytes(b"keep")
    assert call(port, token, "POST", f"/workflow/{wid}/propose_save",
                {"save_as_path": str(root / "taken.pdf")})[1]["error"] == "DESTINATION_EXISTS"
    st, card = call(port, token, "POST", f"/workflow/{wid}/propose_save", {"save_as_path": str(root / "order.pdf")})
    assert st == 200
    # a file created at the name after the card was shown is never replaced
    (root / "order.pdf").write_bytes(b"RACER")
    st, r = _run_card(port, token, card["messages"], "apply")
    assert st == 409 and r["error"] == "DESTINATION_EXISTS" and (root / "order.pdf").read_bytes() == b"RACER"
    (root / "order.pdf").unlink()
    st, card = call(port, token, "POST", f"/workflow/{wid}/propose_save", {"save_as_path": str(root / "order.pdf")})
    st, r = _run_card(port, token, card["messages"], "apply")
    assert st == 200 and r["saved_to"] == "order.pdf"
    assert (root / "order.pdf").read_bytes()[:5] == b"%PDF-"
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert call(port, token, "GET", f"/workflow/{wid}")[1]["state"] == "saved"
    assert (root / "taken.pdf").read_bytes() == b"keep"
    assert not [p for p in root.iterdir() if p.name.startswith(".~uri-")]
    # AC-O2-14: no document text in records, recent list or logs outside the working folders
    for p in office.state.rglob("*"):
        if p.is_file() and not any(part in ("previews", "docs") for part in p.parts) and p.suffix in (
                ".json", ".log", ".txt", ".db", ""):
            assert SENTINEL.encode() not in p.read_bytes(), p
    assert office.approvals.verify_chain()["ok"]


@engine
def test_pdf_open_search_and_hostile_pdf(svc, verified_manifest):
    office, port, token, root = svc
    pdf = pdf_with_text(root / "tender.pdf", [f"Clause {i} tender conditions" for i in range(1, 7)])
    st, v = call(port, token, "POST", "/open/document", {"path": str(pdf)})
    assert st == 200
    did = v["document_id"]
    v = _wait(lambda: (lambda x: x if x["preview"]["state"] != "rendering" else None)(
        call(port, token, "GET", f"/document/{did}")[1]))
    assert v["pages"] == 6 and v["renderer"] == "Windows"
    st, m = call(port, token, "POST", f"/document/{did}/search", {"text": "clause 5"})
    assert [x["page"] for x in m["matches"]] == [5]
    assert call(port, token, "POST", f"/document/{did}/search", {"text": "absent"})[1]["matches"] == []
    bad = root / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4\n" + b"[" * 60000)
    st, v = call(port, token, "POST", "/open/document", {"path": str(bad)})
    bid = v["document_id"]
    v = _wait(lambda: (lambda x: x if x["preview"]["state"] != "rendering" else None)(
        call(port, token, "GET", f"/document/{bid}")[1]))
    assert v["preview"]["state"] == "unavailable"
    assert call(port, token, "GET", "/contract")[0] == 200                # the service survived
    assert call(port, token, "POST", f"/document/{did}/close", {})[0] == 200
    assert call(port, token, "GET", f"/document/{did}")[0] == 404


@engine
def test_excel_save_as_pdf_needs_a_saved_file(svc, verified_manifest):
    office, port, token, root = svc
    _seed(office, verified_manifest)
    from openpyxl import Workbook
    wbp = root / "budget.xlsx"
    wb = Workbook()
    wb.active["A1"] = "Head"
    wb.active["B1"] = 1250
    wb.save(wbp)
    wid = call(port, token, "POST", "/open/local", {"path": str(wbp)})[1]["workbook_id"]
    call(port, token, "POST", f"/workbook/{wid}/edit", {"sheet": "Sheet", "cell": "B1", "value": 99})
    st, r = call(port, token, "POST", "/workflow", {"capability": "save_as_pdf", "inputs": [{"workbook_id": wid}]})
    assert st == 409 and r["error"] == "UNSAVED_CHANGES" and r["recovery"] == ["save", "discard"]
    call(port, token, "POST", f"/workbook/{wid}/undo", {})
    st, wf = call(port, token, "POST", "/workflow", {"capability": "save_as_pdf", "inputs": [{"workbook_id": wid}]})
    assert st == 200, wf
    _run_card(port, token, wf["messages"], "apply")
    v = _wait(lambda: (lambda x: x if x["state"] != "running" else None)(
        call(port, token, "GET", f"/workflow/{wf['workflow_id']}")[1]))
    assert v["state"] in ("ready_to_save", "needs_review"), v
    assert v["outputs"][0]["pages"] >= 1


@engine
def test_plan_can_be_discarded_and_cancel(svc, verified_manifest):
    office, port, token, root = svc
    _seed(office, verified_manifest)
    src = _letter(root / "memo.docx")
    did = call(port, token, "POST", "/open/document", {"path": str(src)})[1]["document_id"]
    wf = call(port, token, "POST", "/workflow", {"capability": "save_as_pdf", "inputs": [{"document_id": did}]})[1]
    st, r = _run_card(port, token, wf["messages"], "reject")
    assert st == 200 and r["status"] == "declined"
    assert call(port, token, "GET", f"/workflow/{wf['workflow_id']}")[1]["state"] == "discarded"
    wf2 = call(port, token, "POST", "/workflow", {"capability": "save_as_pdf", "inputs": [{"document_id": did}]})[1]
    assert call(port, token, "POST", f"/workflow/{wf2['workflow_id']}/cancel", {})[1]["state"] == "cancelled"
    assert _run_card(port, token, wf2["messages"], "apply")[0] != 200          # the plan card closed with it
    st, r = call(port, token, "POST", "/workflow", {"capability": "print_document",
                                                    "inputs": [{"document_id": did}]})
    assert st == 409 and r["error"] == "CAPABILITY_PLANNED"

