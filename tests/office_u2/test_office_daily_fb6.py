"""FB6 fallback review of 3f445a75 (OFFICE-DAILY-USE-r7): regression tests for R2-01..R2-05 (the reviewer's cases).
Tests named fb6_* fail on 3f445a75 and pass after the repair; *_guard_* tests pass on both. The corpus test adds
property (d), a faithful multi-block draft for every case."""
from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_office_daily_od import DID, docs_with
from uri_office import ocr as OCR
from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def names(text):
    return [f["text"] for f in DR.extract_facts(text) if f["kind"] == "name"]


# ---- R2-01: a block boundary ends a name in the draft -------------------------------------------------------------------
@pytest.mark.parametrize("instruction,blocks", [
    ("Draft a letter to Shri Venkatesh Iyer asking him to join the Pension Cell on 14th January 2027.",
     ["Letter", "To", "Shri Venkatesh Iyer", "Assistant Section Officer", "Pension Cell",
      "Sir, you are requested to join the Pension Cell on 14th January 2027."]),
    ("Write a letter to Smt. Meenakshi Sundaram about the 3 posts.",
     ["To", "Smt. Meenakshi Sundaram", "Deputy Secretary", "Sir,", "The 3 posts are approved."]),
    ("Office order signed by Dr. Harish Chandra Pant on 5th June.",
     ["Office Order", "Issued on 5th June.", "Dr. Harish Chandra Pant", "Joint Secretary"]),
    ("Office order on leave, copy to Shri Ramesh Kumar.",
     ["Office Order", "Leave is granted.", "Copy to: Shri Ramesh Kumar", "Guard File"]),
    ("Letter on the transfer of Shri Arun Kumar.",
     ["Subject: Transfer of Shri Arun Kumar", "Sir,", "The transfer is approved."]),
])
def test_fb6_r2_01_faithful_multi_block_draft_gives_no_warning(instruction, blocks):
    assert DR.missing_facts(instruction, "\n".join(blocks)) == []


def test_fb6_r2_01_a_changed_name_in_a_block_still_warns():
    ins = "Draft a letter to Shri Venkatesh Iyer asking him to join the Pension Cell on 14th January 2027."
    draft = "\n".join(["To", "Shri Venkatesh Ayer", "Assistant Section Officer", "Pension Cell", "14th January 2027"])
    assert "Shri Venkatesh Iyer" in [w["text"] for w in DR.missing_facts(ins, draft)]


# ---- R2-02: an honorific with a lowercase name ---------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,old,new,name", [
    ("Draft a letter to Shri ramesh kumar about his pending pension case.", "ramesh", "suresh", "Shri ramesh kumar"),
    ("Write a memo to Smt. anita sharma about late attendance.", "anita", "sunita", "Smt. anita sharma"),
])
def test_fb6_r2_02_honorific_with_lowercase_name(instruction, old, new, name):
    assert names(instruction) == [name]
    assert name in [w["text"] for w in DR.missing_facts(instruction, instruction.replace(old, new))]
    assert DR.missing_facts(instruction, instruction) == []


def test_fb6_r2_02_an_honorific_alone_is_never_a_name():
    for t in ("Draft a letter to Shri ramesh kumar.", "Memo from Dr about it.", "Letter to Smt."):
        assert not [n for n in names(t) if n.rstrip(".") in DR.HONORIFICS]


# ---- R2-03: "of" as a name cue, and its negatives -------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,old,new", [
    ("Prepare a notesheet on the transfer of Ramesh to the Accounts Section.", "Ramesh", "Suresh"),
    ("Draft an office order on the deputation of Anjali for training.", "Anjali", "Kavya"),
])
def test_fb6_r2_03_of_cue(instruction, old, new):
    assert old in [w["text"] for w in DR.missing_facts(instruction, instruction.replace(old, new))]


@pytest.mark.parametrize("instruction,not_names", [
    ("Write to the district collector of Pune about the 3 posts.", ["Pune"]),
    ("Write to the secretary of the department about the pay.", ["the"]),
    ("Notesheet: the director of Kolkata office has sought 3 posts.", ["Kolkata"]),
])
def test_guard_of_after_a_designation_is_not_a_name_cue(instruction, not_names):
    assert not set(not_names) & set(names(instruction))
    assert DR.missing_facts(instruction, instruction) == []


def test_guard_ministry_and_government_of_stay_whole_names():
    t = "Letter to the Ministry of Finance about the transfer of Ramesh."
    assert names(t) == ["Ministry of Finance", "Ramesh"]


# ---- R2-04: OCR page images go with the document ----------------------------------------------------------------------
def test_fb6_r2_04_ocr_page_images_are_removed_on_close(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    png = cache / "p1_w1240.png"
    png.write_bytes(b"png")
    d, _ = docs_with(tmp_path, [""], png=png)
    d._lock = threading.Lock()
    d.grants = SimpleNamespace(revoke=lambda g: None)
    d.hub.lo = SimpleNamespace(cancel_owner=lambda did: None)
    s = d.sessions[DID]
    s.folder, s.cache = tmp_path / "doc", cache
    s.folder.mkdir()
    s.ready.set()
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    monkeypatch.setattr(OCR, "ocr_png", lambda png, exe, **kw: "scanned")
    assert d.text(DID, ocr=True)["pages"][0]["source"] == "ocr"
    d.close(DID)
    assert not png.exists()


# ---- R2-05: the text cap includes the page labels ---------------------------------------------------------------------
def test_fb6_r2_05_returned_text_never_exceeds_the_cap(tmp_path):
    d, _ = docs_with(tmp_path, ["a" * 40, "b" * 40, "c" * 40])
    r = d.text(DID, max_chars=100)
    assert len(r["text"]) <= 100 and r["chars"] <= 100 and r["truncated"] is True


def test_fb6_plan_records_fb6():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB6" in text
