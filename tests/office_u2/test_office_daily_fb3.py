"""FB3 fallback review of da62f66d (OFFICE-DAILY-USE-r3): regression tests for R4-01..R4-04. Tests named r4_* fail on
da62f66d and pass after the repair; tests named *_guard_* pass on both and keep earlier behaviour."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_office_daily_od import DID, TextHub, docs_with
from uri_office import docs as DOCS
from uri_office import ocr as OCR
from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"

# ---- R4-01: a full name right after a year-less date or a reference with a capitalised suffix --------------------
R4_01 = [
    ("Put up a notesheet on F.No. A-12/2026-Estt. Shri Ram Kumar has applied for leave",
     "F.No. A-12/2026-Estt. Shri Ram Kumari has applied for leave.", "Shri Ram Kumar"),
    ("Write a notice: on 3rd November Dr Anil Sharma will chair the meeting",
     "On 3rd November Dr Anil Verma will chair the meeting.", "Dr Anil Sharma"),
    ("Write a circular: from 1st April Smt. Kavita Rao takes charge",
     "From 1st April Smt. Kavita Rani takes charge.", "Smt. Kavita Rao"),
    ("Write an office order: On 3rd November Shri Ram Kumar, UDC, is relieved",
     "On 3rd November Shri Ram Kumari, UDC, is relieved.", "Shri Ram Kumar"),
]


@pytest.mark.parametrize("instruction,draft,name", R4_01)
def test_r4_01_full_name_after_a_date_or_reference_is_checked(instruction, draft, name):
    assert {"kind": "name", "text": name} in DR.extract_facts(instruction)
    assert name in [w["text"] for w in DR.missing_facts(instruction, draft)]
    assert DR.missing_facts(instruction, instruction) == []


@pytest.mark.parametrize("instruction,draft", [
    ("Write a circular: from 1st April 2027 Smt. Kavita Rao takes charge",
     "From 1st April 2027 Smt. Kavita Rani takes charge."),
    ("Write a circular: from 1st April, Smt. Kavita Rao takes charge",
     "From 1st April, Smt. Kavita Rani takes charge."),
])
def test_guard_name_after_a_date_with_a_year_or_comma_still_warns(instruction, draft):
    assert "Smt. Kavita Rao" in [w["text"] for w in DR.missing_facts(instruction, draft)]


# ---- R4-02: no false warnings or false facts ------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Write an office order sanctioning Rs. 25,000 and one laptop to Shri Ram Kumar.",
    "Write an office order granting 10 days and one half day leave.",
])
def test_r4_02_and_one_noun_is_not_a_continued_number(text):
    assert DR.missing_facts(text, text) == []


def test_r4_02_lowercase_may_is_not_a_month():
    facts = DR.extract_facts("Write a circular: officers aged 55 may apply")
    assert not [f for f in facts if f["kind"] == "date"]
    assert DR.missing_facts("Write a circular: officers aged 55 may apply",
                            "Officers who are 55 years old may apply.") == []
    assert not [f for f in DR.extract_facts("May 3 officers apply for the post?") if f["kind"] == "date"]


def test_guard_capitalised_may_dates_are_dates():
    assert {"kind": "date", "text": "3 May"} in DR.extract_facts("Hold the meeting on 3 May.")
    assert {"kind": "date", "text": "May 3rd"} in DR.extract_facts("Hold the meeting on May 3rd.")
    assert DR.missing_facts("Hold the meeting on 3 May.", "The meeting is on 3 June.")


def test_r4_02_amount_with_slash_dash_is_an_amount():
    assert DR.extract_facts("Sanction Rs 2,50,000/- to the vendor.") == [{"kind": "amount", "text": "2,50,000"}]
    assert DR.missing_facts("Sanction Rs 2,50,000/- to the vendor.", "Sanctioned Rs. 2,50,000 to the vendor.") == []


def test_guard_and_number_word_still_continues_a_number():
    assert DR.missing_facts("Sanction two lakh rupees.", "Sanction two lakh and fifty thousand rupees.")


# ---- R4-03: page rendering is inside the request deadline -----------------------------------------------------------
def test_r4_03_rendering_is_bounded_by_the_request_deadline(tmp_path, monkeypatch):
    """The reviewer's probe_deadline.py: text op 150 s, first render 1 s, OCR 44 s, second render would take the
    raster worker's full 60 s. On da62f66d the request reached 256 s."""
    now = [0.0]
    monkeypatch.setattr(DOCS, "_clock", lambda: now[0])
    renders = []

    class Hub(TextHub):
        def text_request(self, op, **kw):
            now[0] += 150.0
            return super().text_request(op, **kw)

        def page_png(self, pdf, cache, n, width, **kw):
            limit = kw.get("timeout", 60.0)
            renders.append(limit)
            now[0] += min(1.0 if len(renders) == 1 else 60.0, limit)
            return tmp_path / "p.png"

    d, _ = docs_with(tmp_path, ["", "", ""], png=tmp_path / "p.png")
    d.hub = Hub(["", "", ""], tmp_path / "p.png")

    def fake_ocr(png, exe, timeout=None):
        t = max(1.0, min(float(timeout), OCR.OCR_TIMEOUT_S))
        now[0] += min(t, 44.0)
        return "word"
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    monkeypatch.setattr(OCR, "ocr_png", fake_ocr)
    r = d.text(DID, ocr=True)
    assert now[0] <= DOCS.REQUEST_DEADLINE_S < 240                   # the whole request, not only OCR
    assert r["ocr_skipped_reasons"]["time_limit"]                     # what did not fit is listed for time


# ---- R4-04: common office units are part of the fact, and the plan lists them ---------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("The distance is 5 km.", "The distance is 5 miles."),
    ("Fill 3 posts of LDC.", "Fill 3 vacancies of UDC."),
    ("Send 4 copies to the Ministry of Home Affairs.", "Send 4 pages to the Ministry of Home Affairs."),
])
def test_r4_04_office_units_are_part_of_the_fact(instruction, draft):
    assert DR.missing_facts(instruction, draft)
    assert DR.missing_facts(instruction, instruction) == []


def test_r4_04_plan_lists_the_units_that_count():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Units that count as part of a number" in text
    for unit in ("km(s)", "kg(s)", "post(s)", "copy/copies", "vacancy/vacancies"):
        assert unit in text
