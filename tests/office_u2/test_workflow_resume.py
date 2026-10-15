"""AC-O2-9 and review round 1 (findings 1, 3, 4): restart, resume, cancel and retention of workflows, with a fake
engine so the lifecycle is tested without LibreOffice. Also the plan §5.1 concurrency check and the validator rules
(AC-O2-8) with fake workers."""
import hashlib
import json
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import pytest

from conftest import pdf_with_text
from uri_office import validate as V
from uri_office.approvals import Approvals
from uri_office.errors import OfficeError
from uri_office.grants import Grants
from uri_office.workflows import RETENTION_SECONDS, Workflows


class FakeLO:
    """Writes a tiny PDF for every conversion; `hold` blocks conversions until released."""
    def __init__(self, work_root):
        self.work_root = work_root
        self.hold = threading.Event()
        self.hold.set()
        self.cancelled = []
        self.integrity = type("I", (), {"pin": {"version": "fake", "manifest_root_sha256": "0" * 64}})()

    def submit(self, src, dst, *, owner, priority=1):
        f = Future()

        def run():
            self.hold.wait(30)
            if owner in self.cancelled:
                f.set_exception(OfficeError("CANCELLED", "", 409))
                return
            pdf_with_text(Path(dst), ["Converted page one", "Converted page two"])
            f.set_result({"seconds": 0.01})
        threading.Thread(target=run, daemon=True).start()
        return f

    def cancel_owner(self, owner):
        self.cancelled.append(owner)
        return 1


class FakeHub:
    def __init__(self, root):
        self.work_root = root
        self.lo = FakeLO(root)

    def text_request(self, op, **kw):
        if op == "info":
            return {"ok": True, "pages": 2, "fonts": [{"name": "Helvetica", "embedded": True}],
                    "page_boxes": [[612, 792], [612, 792]], "encrypted": False}
        if op == "risk":
            return {"ok": True}
        if op == "placeholders":
            return {"ok": True, "pages": []}
        if op == "spans":
            return {"ok": True, "box": [0, 0, 612, 792], "spans": [{"x": 72, "y": 700, "size": 12, "chars": 5}]}
        raise AssertionError(op)

    def raster_request(self, op, **kw):
        from PIL import Image, ImageDraw
        out = []
        for n in kw["pages"]:
            im = Image.new("RGB", (kw["width"], int(kw["width"] * 1.29)), "white")
            ImageDraw.Draw(im).rectangle([40, 40, 200, 60], fill="black")
            name = f"p{n}_w{kw['width']}.png"
            im.save(Path(kw["out_dir"]) / name)
            out.append({"page": n, "file": name})
        return {"ok": True, "rendered": out}


class FakeDocs:
    def __init__(self):
        self.s = {}

    def get(self, did):
        return self.s[did]


def make(tmp_path):
    root = tmp_path / "files"
    root.mkdir(exist_ok=True)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    grants = Grants([tmp_path])
    approvals = Approvals(state, "owner")
    docs = FakeDocs()
    hub = FakeHub(root)
    wf = Workflows(state, hub, grants, approvals, docs, lambda wid: (_ for _ in ()).throw(OfficeError("X")))
    return wf, hub, grants, approvals, docs


def add_doc(tmp_path, docs, grants, name="letter.docx"):
    import docx
    p = tmp_path / name
    d = docx.Document()
    d.add_paragraph("Body text")
    d.save(p)
    g = grants.grant_open(str(p), kind="docx")
    sess = type("S", (), {"kind": "docx", "name": p.name, "path": p, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                          "size": p.stat().st_size, "render_copy": None, "grant_id": g.grant_id})()
    docs.s["d" * 16] = sess
    return p


def run_plan(wf, approvals, wid):
    row = approvals.db.execute("SELECT body_json FROM surface WHERE workbook_id=? AND state='OPEN'", (wid,)).fetchone()
    body = json.loads(row[0])
    w = wf.get(wid)
    with w.lock:
        return wf.apply(body)


def wait_state(wf, wid, not_in=("running",), t=20):
    t0 = time.monotonic()
    while time.monotonic() - t0 < t:
        st = wf.get(wid).record["state"]
        if st not in not_in:
            return st
        time.sleep(0.05)
    raise AssertionError("timeout")


def test_unapproved_plan_is_discarded_on_restart_and_cannot_resume(tmp_path):
    wf, hub, grants, approvals, docs = make(tmp_path)
    p = add_doc(tmp_path, docs, grants)
    wid = wf.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    assert wf.get(wid).record["state"] == "waiting_approval"
    wf2, *_ = make(tmp_path)                                  # restart
    assert wf2.get(wid).record["state"] == "discarded"
    with pytest.raises(OfficeError) as e:
        wf2.resume(wid, {"inputs": [{"path": str(p)}]})
    assert e.value.code == "NOT_CANCELLABLE"
    assert approvals.db.execute("SELECT COUNT(*) FROM surface WHERE state='OPEN'").fetchone()[0] == 0


def test_approved_run_interrupted_resumes_only_with_same_input(tmp_path):
    wf, hub, grants, approvals, docs = make(tmp_path)
    p = add_doc(tmp_path, docs, grants)
    hub.lo.hold.clear()                                       # the conversion hangs: "service killed mid-render"
    wid = wf.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    assert run_plan(wf, approvals, wid)["state"] == "running"
    time.sleep(0.3)
    wf2, hub2, grants2, approvals2, docs2 = make(tmp_path)    # restart: grants are gone
    rec = wf2.get(wid).record
    assert rec["state"] == "interrupted" and rec["interrupted_at_step"] == 2 and rec["plan_approved"]
    # a changed input stops the workflow with a finding
    original = p.read_bytes()
    p.write_bytes(original + b"x")
    with pytest.raises(OfficeError) as e:
        wf2.resume(wid, {"inputs": [{"path": str(p)}]})
    assert e.value.code == "INPUT_CHANGED" and wf2.get(wid).record["state"] == "failed"
    # the same input resumes (a fresh run with a new interrupted record)
    p.write_bytes(original)
    hub.lo.hold.set()
    wid2 = wf.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    run_plan(wf, approvals, wid2)
    assert wait_state(wf, wid2) == "ready_to_save"


def test_resume_of_interrupted_approved_run_completes(tmp_path):
    wf, hub, grants, approvals, docs = make(tmp_path)
    p = add_doc(tmp_path, docs, grants)
    hub.lo.hold.clear()
    wid = wf.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    run_plan(wf, approvals, wid)
    time.sleep(0.3)
    wf2, hub2, grants2, approvals2, docs2 = make(tmp_path)
    v = wf2.resume(wid, {"inputs": [{"path": str(p)}]})
    assert v["state"] == "running"
    assert wait_state(wf2, wid) == "ready_to_save"
    assert wf2.get(wid).record["outputs"][0]["pages"] == 2


def test_cancel_while_queued_ends_cancelled_not_failed(tmp_path):
    wf, hub, grants, approvals, docs = make(tmp_path)
    add_doc(tmp_path, docs, grants)
    hub.lo.hold.clear()
    wid = wf.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    run_plan(wf, approvals, wid)
    time.sleep(0.2)
    wf.cancel(wid)
    hub.lo.hold.set()
    assert wait_state(wf, wid) == "cancelled"
    assert [p.name for p in wf.get(wid).folder.iterdir()] == ["workflow.json"]


def test_old_interrupted_runs_are_removed_after_retention(tmp_path):
    wf, hub, grants, approvals, docs = make(tmp_path)
    add_doc(tmp_path, docs, grants)
    hub.lo.hold.clear()
    wid = wf.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    run_plan(wf, approvals, wid)
    time.sleep(0.2)
    wf2, *_ = make(tmp_path)
    w = wf2.get(wid)
    w.record["updated_at"] -= RETENTION_SECONDS + 10
    (w.folder / "workflow.json").write_text(json.dumps(w.record))
    wf3, *_ = make(tmp_path)
    assert wid not in wf3.items and not w.folder.exists()


def test_new_save_proposal_revokes_the_previous_destination_grant(tmp_path):
    wf, hub, grants, approvals, docs = make(tmp_path)
    add_doc(tmp_path, docs, grants)
    wid = wf.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    run_plan(wf, approvals, wid)
    assert wait_state(wf, wid) == "ready_to_save"
    if wf.get(wid).findings.warnings:
        wf.accept_warnings(wid)
    wf.propose_save(wid, {"save_as_path": str(tmp_path / "a.pdf")})
    first = wf.get(wid).private["dest_grant"]
    wf.propose_save(wid, {"save_as_path": str(tmp_path / "b.pdf")})
    with pytest.raises(OfficeError):
        grants.get(first, "save_as")


# ---- plan §5.1 concurrency: a workbook save completes while a conversion runs (review N2) -------------------------
def test_workbook_save_completes_while_a_conversion_runs(tmp_path):
    import http.client
    from openpyxl import Workbook, load_workbook
    from uri_office.service import Office, serve

    office = Office(tmp_path / "state", allowed_roots=[tmp_path])
    hub = FakeHub(office.state / "files")
    (office.state / "files").mkdir(parents=True, exist_ok=True)
    office._hub = hub
    from uri_office.workflows import Workflows as W
    docs = FakeDocs()
    office._documents = docs
    office._workflows = W(office.state, hub, office.grants, office.approvals, docs, office._session)
    p = add_doc(tmp_path, docs, office.grants)
    hub.lo.hold.clear()                                        # the conversion is running and blocked
    wid = office.workflows.create("save_as_pdf", [{"document_id": "d" * 16}])["workflow_id"]
    srv, token = serve(office, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def call(method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request(method, path, body=json.dumps(body).encode() if body is not None else None,
                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        r = c.getresponse()
        out = (r.status, json.loads(r.read() or b"{}"))
        c.close()
        return out
    try:
        msgs = office.approvals.open_messages(wid)
        bound = msgs[2]["updateDataModel"]["value"]["bound"]
        st, r = call("POST", "/a2ui/action", {"action": {"name": "office.run_plan", "surfaceId":
                     msgs[0]["createSurface"]["surfaceId"], "sourceComponentId": "apply",
                     "context": {"surface_digest": bound["surface"]["digest"], "plan_sha256": bound["plan_sha256"]}}})
        assert st == 200 and r["state"] == "running"
        book = tmp_path / "book.xlsx"
        wb = Workbook()
        wb.active["A1"] = 1
        wb.save(book)
        wbid = call("POST", "/open/local", {"path": str(book)})[1]["workbook_id"]
        call("POST", f"/workbook/{wbid}/edit", {"sheet": "Sheet", "cell": "A1", "value": 2})
        prop = call("POST", f"/workbook/{wbid}/propose_save", {})[1]
        b2 = prop["messages"][2]["updateDataModel"]["value"]["bound"]
        t0 = time.monotonic()
        st, r = call("POST", "/a2ui/action", {"action": {"name": "office.apply_change", "surfaceId":
                     prop["messages"][0]["createSurface"]["surfaceId"], "sourceComponentId": "apply",
                     "context": {"surface_digest": b2["surface"]["digest"], "change_sha256": b2["change_sha256"]}}})
        assert st == 200 and r["status"] == "applied" and time.monotonic() - t0 < 5
        assert load_workbook(book).active["A1"].value == 2
        assert office.workflows.get(wid).record["state"] == "running"     # the conversion is still running
    finally:
        hub.lo.hold.set()
        srv.shutdown()
        srv.server_close()


# ---- validator rules (AC-O2-8) with fake workers -------------------------------------------------------------
class FakeText(FakeHub):
    def __init__(self, info=None, risk=None, ph=None, spans=None):
        self._info, self._risk, self._ph, self._spans = info, risk, ph, spans

    def request(self, op, **kw):
        if op == "info" and self._info is not None:
            return self._info
        if op == "risk" and self._risk is not None:
            return self._risk
        if op == "placeholders" and self._ph is not None:
            return self._ph
        if op == "spans" and self._spans is not None:
            return self._spans
        return FakeHub.text_request(self, op, **kw)


class FakeRaster(FakeHub):
    def __init__(self, blank=(), edge=()):
        self.blank, self.edge = set(blank), set(edge)

    def request(self, op, **kw):
        from PIL import Image, ImageDraw
        out = []
        for n in kw["pages"]:
            w = kw["width"]
            im = Image.new("RGB", (w, int(w * 1.29)), "white")
            if n not in self.blank:
                ImageDraw.Draw(im).rectangle([40, 40, 200, 60], fill="black")
            if n in self.edge:
                ImageDraw.Draw(im).rectangle([w - 3, 100, w - 1, 140], fill="black")
            im.save(Path(kw["out_dir"]) / f"p{n}_w{w}.png")
            out.append({"page": n, "file": f"p{n}_w{w}.png"})
        return {"ok": True, "rendered": out}


def checks(fs):
    return sorted((f.check, f.severity) for f in fs.items)


def test_validator_flags_blank_edge_size_count_and_risk(tmp_path):
    pdf = tmp_path / "o.pdf"
    pdf.write_bytes(b"%PDF")
    v = V.Validator(FakeText(risk={"ok": True, "javascript": 1},
                             ph={"ok": True, "pages": [{"page": 2, "count": 3}]},
                             spans={"ok": True, "box": [0, 0, 612, 792],
                                    "spans": [{"x": -5, "y": 700, "size": 6.5, "chars": 4}]}),
                    FakeRaster(blank=[2], edge=[1]))
    fs, facts = v.check_output_pdf(pdf, kind="pptx", work_dir=tmp_path / "w", expected_pages=3)
    got = checks(fs)
    assert ("pdf_risky_content", "error") in got and ("placeholders", "error") in got
    assert ("page_count", "error") in got and ("blank_page", "warning") in got
    assert ("text_outside_page", "warning") in got and ("min_font_size", "warning") in got
    assert ("edge_ink_right", "warning") not in got              # slides are not checked for edge ink
    assert len(fs.errors) == 3


def test_validator_font_substitution_and_source_change(tmp_path):
    import docx
    src = tmp_path / "s.docx"
    d = docx.Document()
    r = d.add_paragraph().add_run("x")
    r.font.name = "Nirmala UI"
    d.save(src)
    pdf = tmp_path / "o.pdf"
    pdf.write_bytes(b"%PDF")
    orig = tmp_path / "orig.docx"
    orig.write_bytes(b"one")
    v = V.Validator(FakeText(), FakeRaster(edge=[1]))
    fs, _ = v.check_output_pdf(pdf, kind="docx", work_dir=tmp_path / "w", source=src,
                               sources={str(orig): hashlib.sha256(b"two").hexdigest()})
    got = checks(fs)
    assert ("font_substitution", "warning") in got and ("source_unchanged", "error") in got
    edge = [f for f in fs.items if f.check == "edge_ink_right"]
    assert edge and edge[0].weak                                  # labelled weaker
    assert "Nirmala UI" in " ".join(f.message for f in fs.items)


def test_two_short_lines_are_not_a_blank_page(tmp_path):
    """Live run 2026-10-15 regression: a page holding only a two-line signature block was reported blank."""
    from PIL import Image, ImageDraw
    p = tmp_path / "sig.png"
    im = Image.new("RGB", (440, 568), "white")
    ImageDraw.Draw(im).text((60, 50), "By order,", fill="black")
    ImageDraw.Draw(im).text((60, 62), "Joint Secretary", fill="black")
    im.save(p)
    cov, edge, ink = V.ink_stats(p, 4)
    assert cov < 0.002 and ink >= V.BLANK_MAX_INK_PIXELS          # the old rule would have called it blank
    blank = tmp_path / "blank.png"
    Image.new("RGB", (440, 568), "white").save(blank)
    assert V.ink_stats(blank, 4)[2] == 0


def test_page_with_only_a_page_number_is_blank(tmp_path):
    """Review round 3, m5: ink only in the footer band (a page number) still counts as a blank page."""
    from PIL import Image, ImageDraw
    p = tmp_path / "num.png"
    im = Image.new("RGB", (440, 568), "white")
    ImageDraw.Draw(im).text((210, 545), "12", fill="black")
    im.save(p)
    assert V.ink_stats(p, 4)[2] < V.BLANK_MAX_INK_PIXELS


def test_repair_interface_has_no_rules_in_o2_and_keeps_findings():
    from uri_office.contracts import Findings
    fs = Findings()
    fs.add("blank_page", "visual", "warning", "Page 1 is blank.", page=1)
    changes, remaining = V.repair(fs)
    assert changes == [] and len(remaining) == 1 and V.REPAIR_RULES == {}


def test_hindi_text_in_a_theme_font_resolves_to_the_theme_script_font(tmp_path):
    """Review round 4 m6: a run with w:cstheme="minorBidi" and Hindi marked as its complex-script language uses the
    theme's Devanagari font (empty <a:cs>, <a:font script="Deva">), not the theme's Latin font."""
    import re
    import zipfile
    import docx
    src = tmp_path / "hi.docx"
    d = docx.Document()
    d.add_paragraph().add_run("नमस्ते")
    d.save(src)
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    theme = next(n for n in parts if "/theme/" in n)
    t = parts[theme].decode()
    t = re.sub(r"(<a:minorFont>.*?<a:cs typeface=)\"[^\"]*\"", r'\1""', t, count=1, flags=re.S)
    t = t.replace("<a:minorFont>", '<a:minorFont><a:font script="Deva" typeface="URI Test Devanagari"/>', 1) \
        if 'script="Deva"' not in t.split("<a:minorFont>", 1)[1].split("</a:minorFont>", 1)[0] else \
        re.sub(r'(<a:minorFont>.*?<a:font script="Deva" typeface=)"[^"]*"', r'\1"URI Test Devanagari"', t, count=1,
               flags=re.S)
    parts[theme] = t.encode()
    doc = parts["word/document.xml"].decode()
    doc = doc.replace("<w:r>", '<w:r><w:rPr><w:rFonts w:cstheme="minorBidi"/><w:lang w:bidi="hi-IN"/></w:rPr>', 1)
    parts["word/document.xml"] = doc.encode()
    with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)
    fonts = V.source_fonts(src, "docx")
    assert "URI Test Devanagari" in fonts


def test_language_tags_and_unused_lists_do_not_add_fonts(tmp_path):
    """Real-app run r2 (2026-10-15): a plain English report made with python-docx was warned about Arial, Symbol and
    Times New Roman. Its defaults tag Arabic and Japanese (w:bidi="ar-SA", w:eastAsia="ja-JP") and its numbering part
    names Symbol, but it has no such text and no list."""
    import docx
    plain = tmp_path / "plain.docx"
    d = docx.Document()
    d.add_heading("Report", 1)
    d.add_paragraph("Plain English text only.")
    d.save(plain)
    fonts = V.source_fonts(plain, "docx")
    assert not {"Arial", "Symbol", "Times New Roman"} & fonts, fonts
    listed = tmp_path / "list.docx"
    d = docx.Document()
    d.add_paragraph("first point", style="List Bullet")
    d.save(listed)
    assert "Symbol" in V.source_fonts(listed, "docx")             # a used bullet list still counts its font
