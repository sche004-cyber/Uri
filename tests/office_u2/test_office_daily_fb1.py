"""FB1 fallback review of 03c2fba9 (OFFICE-DAILY-USE-r1): regression tests for R2-01..R2-05. Each one fails on
03c2fba9 and passes after the repair."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_office_daily_od import DID, FakeClient, answer, docs_with
from uri_office import docs as DOCS
from uri_office import ocr as OCR
from uri_office.authoring import drafting as DR
from uri_office.brain import OfficeBrain
from uri_office.errors import OfficeError


# ---- R2-01: a changed fact is never counted as present --------------------------------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("Ask the staff to report within 7 days.", "The staff will report within 17 days."),
    ("Sanction an advance of Rs. 5 lakh.", "An advance of Rs. 50 lakh is sanctioned."),
    ("Hold the meeting on 3 November 2026.", "The meeting is on 13 November 2026."),
    ("The meeting is in room 12.", "The meeting is in room 112."),
    ("Write an office order No. 12/2026 for the move.", "Office Order No. 112/2026 for the move."),
    ("Write an office order transferring Shri Ram Kumar to accounts.", "Shri Ram Kumari is transferred to accounts."),
    ("Pay Rs. 25,000 to the vendor.", "Pay Rs. 1,25,000 to the vendor."),
])
def test_changed_facts_warn(instruction, draft):
    warned = DR.missing_facts(instruction, draft)
    assert warned and all(w["code"] == "FACT_MISSING" for w in warned), (instruction, draft)


@pytest.mark.parametrize("instruction,draft", [
    ("Ask the staff to report within 7 days.", "The staff will report within 7 days."),
    ("Sanction an advance of Rs. 5 lakh.", "An advance of Rs. 5 lakh is sanctioned."),
    ("Hold the meeting on 3 November 2026.", "The meeting is on 3   November 2026."),          # spacing ignored
    ("The meeting is in room 12.", "The meeting is in room 12."),
    ("Write an office order No. 12/2026 for the move.", "Office Order No. 12/2026."),
    ("Write an office order transferring Shri Ram Kumar to accounts.", "SHRI RAM KUMAR is transferred to accounts."),
    ("Pay Rs. 25,000 to the vendor.", "Pay Rs. 25,000 (twenty-five thousand) to the vendor."),
])
def test_exact_facts_do_not_warn(instruction, draft):
    assert DR.missing_facts(instruction, draft) == []


# ---- R2-03: single cue names and numbers in words are extracted and checked -----------------------------------------
def test_single_cue_names_and_number_words_are_checked():
    assert {"kind": "name", "text": "Ramesh"} in DR.extract_facts("Write a memo to Ramesh about leave.")
    assert {"kind": "name", "text": "Dr. Rao"} in DR.extract_facts("Send it from Dr. Rao.")
    facts = DR.extract_facts("Sanction twenty five thousand rupees.")
    assert {"kind": "number", "text": "twenty five thousand"} in facts
    assert DR.extract_facts("send one letter") == []                  # a lone small number word is not a fact
    # FB5 R6-03: unless a unit follows it
    assert DR.extract_facts("send one copy") == [{"kind": "number", "text": "one copy"}]
    w = DR.missing_facts("Write a memo to Ramesh about leave of twenty days.", "Memo to Suresh about leave of "
                                                                             "thirty days.")
    assert {x["text"] for x in w} == {"Ramesh", "twenty days"}             # FB2 R3-02: the unit is part of the fact


# ---- R2-04: over-long message or missing item is refused, never cut ---------------------------------------------------
@pytest.mark.parametrize("bad", [
    answer(status="clarify", message="m" * 601),
    answer(status="propose", blocks=[{"role": "title", "text": "x"}], missing=["n" * 121]),
])
def test_over_long_message_or_missing_item_is_refused(bad):
    with pytest.raises(OfficeError) as e:
        OfficeBrain(FakeClient(bad)).draft_document("Write a letter", layout_title="Letter", layout_paras=[])
    assert e.value.code == "BRAIN_OUTPUT_INVALID"


def test_limits_at_the_cap_are_accepted():
    r = OfficeBrain(FakeClient(answer(status="clarify", message="m" * 600, missing=["n" * 120]))).draft_document(
        "Write a letter", layout_title="Letter", layout_paras=[])
    assert len(r["message"]) == 600 and r["missing"] == ["n" * 120]


# ---- R2-02: OCR text cut by the size cap, and pages left out for it, are said so ---------------------------------------
def test_ocr_text_cut_by_the_cap_sets_truncated(tmp_path, monkeypatch):
    d, _ = docs_with(tmp_path, ["x" * 95, ""], png=tmp_path / "p.png")
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    monkeypatch.setattr(OCR, "ocr_png", lambda png, exe, **kw: "y" * 50)
    r = d.text(DID, ocr=True, max_chars=100)
    assert r["truncated"] is True and r["pages"][1]["text"] == "y" * 5 and r["pages"][1].get("cut") is True


def test_pages_left_out_for_the_size_cap_are_named_for_it(tmp_path, monkeypatch):
    d, _ = docs_with(tmp_path, ["x" * 100, "", ""], png=tmp_path / "p.png")
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    monkeypatch.setattr(OCR, "ocr_png", lambda png, exe, **kw: "y")
    r = d.text(DID, ocr=True, max_chars=100)
    assert r["truncated"] is True
    assert r["ocr_skipped_reasons"] == {"page_limit": [], "size_limit": [2, 3], "time_limit": []}


# ---- R2-05: one deadline for the whole OCR request, below the app's request timeout ------------------------------------
def test_ocr_request_deadline_lists_the_rest_as_skipped_for_time(tmp_path, monkeypatch):
    assert OCR.OCR_DEADLINE_S < 240                                    # the app's POST timeout (office_client.dart)
    now = [0.0]
    monkeypatch.setattr(DOCS, "_clock", lambda: now[0])
    d, _ = docs_with(tmp_path, ["", "", "", ""], png=tmp_path / "p.png")
    budgets = []

    def fake_ocr(png, exe, timeout=None):
        budgets.append(timeout)
        now[0] += 100.0
        return "w"
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    monkeypatch.setattr(OCR, "ocr_png", fake_ocr)
    r = d.text(DID, ocr=True)
    assert budgets == [OCR.OCR_TIMEOUT_S, OCR.OCR_DEADLINE_S - 100.0]
    assert r["ocr_skipped_reasons"]["time_limit"] == [3, 4] and r["ocr_skipped"] == [3, 4]
    assert [p["source"] for p in r["pages"]] == ["ocr", "ocr", "none", "none"]
