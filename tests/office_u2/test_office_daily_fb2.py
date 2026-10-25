"""FB2 fallback review of d94961c7 (OFFICE-DAILY-USE-r2): regression tests for R3-01..R3-07. Each test named after a
finding fails on d94961c7 and passes after the repair; the `*_still_*` cases guard against new false warnings."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document

from test_authoring_docx import FakeDocs
from test_office_daily_od import DID, FakeClient, TextHub, answer, docs_with, office_with
from uri_office import docs as DOCS
from uri_office import ocr as OCR
from uri_office.authoring import drafting as DR
from uri_office.brain import OfficeBrain
from uri_office.errors import OfficeError

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


# ---- R3-01: dates without a year ------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("Write a notice: meeting on 3rd November at 11 AM.", "Meeting on 3rd December at 11 AM."),
    ("Write a notice: meeting on November 3.", "Meeting on December 3."),
    ("Write a notice: meeting on 3 Nov.", "Meeting on 3 Dec."),
    ("Write a circular for 15th August celebrations.", "Circular for 15th January celebrations."),
    ("Write a notice: meeting on 3 November 2026.", "Meeting on 3 December 2026."),
])
def test_r3_01_year_less_dates_are_facts(instruction, draft):
    assert any(w["kind"] == "date" for w in DR.missing_facts(instruction, draft)), (instruction, draft)


def test_r3_01_still_no_warning_for_the_same_date():
    assert DR.missing_facts("Write a notice: meeting on 3rd November at 11 AM.", "Meeting on 3rd November at 11 AM.") \
        == []


# ---- R3-02: a number extended by a number word, or with another unit or AM/PM ---------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("Sanction twenty five thousand rupees.", "Sanction twenty five thousand five hundred rupees."),
    ("Sanction two lakh rupees.", "Sanction two lakh fifty thousand rupees."),
    ("The meeting is at 10:30 PM.", "The meeting is at 10:30 AM."),
    ("Report within 7 weeks.", "Report within 7 days."),
])
def test_r3_02_changed_unit_or_continued_number_warns(instruction, draft):
    assert DR.missing_facts(instruction, draft), (instruction, draft)


@pytest.mark.parametrize("instruction,draft", [
    ("Sanction twenty five thousand rupees.", "Sanction twenty five thousand rupees."),
    ("The meeting is at 10:30 PM.", "The meeting is at 10:30 PM."),
    ("Report within 7 weeks.", "Report within 7 weeks."),
])
def test_r3_02_still_no_warning_when_the_same(instruction, draft):
    assert DR.missing_facts(instruction, draft) == []


# ---- R3-03: characters the document cannot hold are refused, so the check reads the written text -------------------
@pytest.mark.parametrize("bad", [
    answer(blocks=[{"role": "paragraph", "text": "Sanctioned Rs. 1\x015,000 to Shri Ram Kumar\x01i."}]),
    answer(status="clarify", message="Which\x02 officer?"),
    answer(blocks=[{"role": "title", "text": "x"}], missing=["file\x0bnumber"]),
])
def test_r3_03_control_characters_are_refused(bad):
    with pytest.raises(OfficeError) as e:
        OfficeBrain(FakeClient(bad)).draft_document("Write a letter", layout_title="Letter", layout_paras=[])
    assert e.value.code == "BRAIN_OUTPUT_INVALID"


# ---- R3-04: no false warnings for reference fragments, "/-" and plurals ---------------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("Write a letter about F.No. A-12/2026.", "Letter about F.No. A-12/2026."),
    ("Pay Rs. 25,000 to the vendor.", "Pay Rs. 25,000/- to the vendor."),
    ("Sanction Rs. 5 lakh.", "Sanction Rs. 5 lakhs."),
])
def test_r3_04_no_false_warning(instruction, draft):
    assert DR.missing_facts(instruction, draft) == []


def test_r3_04_still_warns_for_a_changed_amount_or_reference():
    assert DR.missing_facts("Pay Rs. 25,000 to the vendor.", "Pay Rs. 25,000/2 to the vendor.")
    assert DR.missing_facts("Write a letter about F.No. A-12/2026.", "Letter about F.No. A-13/2026.")


# ---- R3-05: To Word names the limit for pages OCR left out ----------------------------------------------------------
def test_r3_05_to_word_writes_not_read_with_the_limit(tmp_path, monkeypatch):
    from uri_office.authoring.session import Authoring
    o = office_with(tmp_path, None)
    o._documents, _ = docs_with(tmp_path, ["Text", "", ""], png=tmp_path / "p.png")
    o._authoring = Authoring(o.state, FakeDocs(o.grants), o.grants, o.approvals)
    now = [0.0]
    monkeypatch.setattr(DOCS, "_clock", lambda: now[0])
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))

    def slow(png, exe, **kw):                     # the first scanned page uses up the time
        now[0] += 500.0
        return ""
    monkeypatch.setattr(OCR, "ocr_png", slow)
    v = o.document_to_word(DID, {"ocr": True})
    paras = [(p.style.name, p.text) for p in Document(io.BytesIO(o.authoring.get(v["authoring_id"]).data)).paragraphs]
    assert ("Normal", "[Not read: time limit]") in paras and paras[-1] == ("Normal", "[Not read: time limit]")
    assert paras[paras.index(("Heading 1", "Page 2")) + 1] == ("Normal", "[No text on this page]")   # read, empty


# ---- R3-06: one deadline from request entry, below the app's 240 s timeout -----------------------------------------
def test_r3_06_text_op_and_ocr_share_one_deadline_from_entry(tmp_path, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(DOCS, "_clock", lambda: now[0])

    class SlowTextHub(TextHub):
        def text_request(self, op, **kw):
            self.timeout = kw.get("timeout")
            now[0] += 150.0                       # the text op used 150 s
            return super().text_request(op, **kw)

    d, _ = docs_with(tmp_path, ["", ""], png=tmp_path / "p.png")
    d.hub = SlowTextHub(["", ""], tmp_path / "p.png")
    budgets = []

    def fake_ocr(png, exe, timeout=None):
        budgets.append(timeout)
        now[0] += timeout
        return "w"
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    monkeypatch.setattr(OCR, "ocr_png", fake_ocr)
    r = d.text(DID, ocr=True)
    assert d.hub.timeout < 240                                       # the text op cannot outlast the app's request
    assert sum(budgets) + 150.0 < 240 and budgets[0] <= DOCS.REQUEST_DEADLINE_S - 150.0
    assert r["ocr_skipped_reasons"]["time_limit"] == [2]


# ---- R3-07: the status note describes the Read scans switch ---------------------------------------------------------
def test_r3_07_plan_status_describes_the_read_scans_switch():
    text = PLAN.read_text(encoding="utf-8")
    assert '"Read scans" switch' in text
    assert "exists in the API (`ocr: true`) but has no button." not in text
