"""FB4 fallback review of ef9ce641 (OFFICE-DAILY-USE-r4): regression tests for R5-01..R5-06. Tests named r5_* fail
on ef9ce641 and pass after the repair. The wider net is test_office_daily_fact_corpus.py."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

from test_office_daily_od import DID, TextHub, docs_with
from uri_office import docs as DOCS
from uri_office import ocr as OCR
from uri_office.authoring import drafting as DR
from uri_office.errors import OfficeError
from uri_office.workerproc import Worker, WorkerFailed

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def names(text):
    return [f["text"] for f in DR.extract_facts(text) if f["kind"] == "name"]


# ---- R5-01: several people after a date or reference; Kum./Km./Sushri ------------------------------------------------
@pytest.mark.parametrize("instruction,draft,name", [
    ("On 3rd November Shri Ram Kumar and Smt. Sita Devi will attend",
     "On 3rd November Shri Ram Kumari and Smt. Sita Devi will attend.", "Shri Ram Kumar"),
    ("Notesheet on F.No. A-12/2026-Estt. Shri Ram Kumar and Smt. Sita Devi applied",
     "F.No. A-12/2026-Estt. Shri Ram Kumari and Smt. Sita Devi applied.", "Shri Ram Kumar"),
    ("Notesheet on F.No. 12/2026-Admin Shri Ram Kumar and Shri Mohan Das applied",
     "F.No. 12/2026-Admin Shri Ram Kumari and Shri Mohan Das applied.", "Shri Ram Kumar"),
    ("Relieve Kum. Priya Nair and Smt. Sita Devi from duty",
     "Relieve Kum. Priya Menon and Smt. Sita Devi from duty.", "Kum. Priya Nair"),
    ("Grant leave to Sushri Kavita Rao and Km. Pooja Rani",
     "Grant leave to Sushri Kavita Rani and Km. Pooja Rani.", "Sushri Kavita Rao"),
])
def test_r5_01_every_person_is_a_name_fact(instruction, draft, name):
    assert name in names(instruction)
    assert name in [w["text"] for w in DR.missing_facts(instruction, draft)]
    assert DR.missing_facts(instruction, instruction) == []


def test_r5_01_three_people_with_commas_and_and():
    assert names("On 5th June Shri Ram Kumar, Kum. Priya Nair and Dr Anil Sharma will attend") == \
        ["Shri Ram Kumar", "Kum. Priya Nair", "Dr Anil Sharma"]


# ---- R5-02: "may" as a month ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("Hold the meeting on May 3.", "Hold the meeting on June 3."),
    ("write a notice for the meeting on 3rd may 2026", "The meeting is on 3rd June 2026."),
    ("Circular: last date 3 MAY 2026", "Last date 3 JUNE 2026."),
    ("Circular: last date 03 MAY", "Last date 03 JUNE."),
    ("hold the meeting on 3 may", "Hold the meeting on 3 June."),
])
def test_r5_02_may_dates_warn_when_the_month_changes(instruction, draft):
    assert any(w["kind"] == "date" for w in DR.missing_facts(instruction, draft))


@pytest.mark.parametrize("instruction", [
    "Write a circular: officers aged 55 may apply",
    "May 3 officers be deputed for training? Write a notesheet.",
    "Circular: you may 3 times apply for the post",
])
def test_guard_may_as_a_verb_is_not_a_date(instruction):
    assert not [f for f in DR.extract_facts(instruction) if f["kind"] == "date"]


# ---- R5-03: an identical draft never warns ---------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Office order: sanction Rs. 5,000 one time grant to Smt. Sunita Devi",
    "Circular: depute 2 officers one from each division",
    "Notesheet: create 4 posts two each in Estt and Admin",
    "Training for 5 days ten officers",
    "Fill 3 (three) posts of LDC",
])
def test_r5_03_identical_draft_never_warns(text):
    assert DR.missing_facts(text, text) == []


def test_r5_03_three_three_posts_matches_three_posts():
    assert DR.missing_facts("Fill 3 posts of LDC", "Fill 3 (three) posts of LDC.") == []


# ---- R5-04: designators are part of the reference, never name words --------------------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("Refer O.M. No. A-11019/5/2026-Admin.I dated 3rd May 2026",
     "This refers to the O.M. No. A-11019/5/2026-Admin.I dated 3rd May 2026."),
    ("Write a letter to Shri Ram Kumar F.No. 12/2026 about pay",
     "Letter regarding pay, F.No. 12/2026, to Shri Ram Kumar."),
])
def test_r5_04_no_designator_in_names(instruction, draft):
    assert not [n for n in names(instruction) if "No" in n or n.startswith("Refer")]
    assert DR.missing_facts(instruction, draft) == []


# ---- R5-05: only a real timeout is a time limit -----------------------------------------------------------------------
class LateHub(TextHub):
    def __init__(self, pages, png, error):
        super().__init__(pages, png)
        self.error = error

    def text_request(self, op, **kw):
        DOCS._clock.now += 140.0
        return super().text_request(op, **kw)

    def page_png(self, *a, **kw):
        raise self.error


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_r5_05_a_late_render_failure_is_raised_not_a_time_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(DOCS, "_clock", Clock())
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    d, _ = docs_with(tmp_path, ["", "", ""], png=tmp_path / "p.png")
    d.hub = LateHub(["", "", ""], tmp_path / "p.png", OfficeError("CLM_ACTIVE", "", 503))
    with pytest.raises(OfficeError) as e:
        d.text(DID, ocr=True)
    assert e.value.code == "CLM_ACTIVE"


def test_guard_a_late_render_timeout_is_a_time_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(DOCS, "_clock", Clock())
    monkeypatch.setattr(OCR, "tesseract_exe", lambda: Path("tess.exe"))
    d, _ = docs_with(tmp_path, ["", "", ""], png=tmp_path / "p.png")
    d.hub = LateHub(["", "", ""], tmp_path / "p.png",
                    OfficeError("PREVIEW_UNAVAILABLE", "raster worker TIMEOUT", 503))
    assert d.text(DID, ocr=True)["ocr_skipped_reasons"]["time_limit"] == [1, 2, 3]


# ---- R5-06: waiting for a busy worker counts against the budget -------------------------------------------------------
def test_r5_06_total_timeout_bounds_the_wait_for_a_busy_worker():
    w = Worker("busy", lambda: [sys.executable, "-c", "pass"], memory_limit=64 * 2**20)
    w._lock.acquire()                              # another request holds the worker
    result = {}

    def call():
        try:
            w.request("render", timeout=0.3, total_timeout=True)
        except WorkerFailed as e:
            result["code"] = e.code
    t = threading.Thread(target=call, daemon=True)
    t0 = time.monotonic()
    t.start()
    t.join(5)
    try:
        assert not t.is_alive() and result.get("code") == "BUSY" and time.monotonic() - t0 < 3
    finally:
        w._lock.release()


def test_r5_plan_records_fb4():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB4" in text and "test_office_daily_fact_corpus.py" in text
