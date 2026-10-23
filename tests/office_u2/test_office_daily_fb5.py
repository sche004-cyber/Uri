"""FB5 fallback review of dbde00f6 (OFFICE-DAILY-USE-r5): regression tests for R6-01..R6-04 (the reviewer's cases).
Tests named r6_* fail on dbde00f6 and pass after the repair; the corpus test covers the same forms by template."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def warns(instruction, old, new):
    assert old in instruction
    return DR.missing_facts(instruction, instruction.replace(old, new, 1))


# ---- R6-01: month and year, "Nth (day) of Month", periods -----------------------------------------------------------
@pytest.mark.parametrize("instruction,old,new", [
    ("Prepare a notesheet on the salary bill for the month of April 2026.", "April 2026", "March 2026"),
    ("Circular: APAR for April, 2026 to March, 2027 must be submitted.", "April, 2026", "May, 2026"),
    ("Office order: in May 2026, 4 drivers will be engaged.", "May 2026", "June 2026"),
    ("Write a letter asking Shri Anand Rao to join duty on the 5th of June, 2026.", "5th of June", "5th of July"),
    ("Office order dated 12th day of March 2026: Smt. Neelam Kapoor is promoted.", "12th day of March",
     "12th day of April"),
    ("Draft a letter to Sh. Balwinder Singh Sandhu, Section Officer, asking him to report on 5th of May 2026.",
     "5th of May 2026", "5th of June 2026"),
    ("Notesheet: hire 3 cars for the period April to June 2026.", "April to June", "April to July"),
])
def test_r6_01_month_year_and_day_of_month_dates_warn(instruction, old, new):
    assert any(w["kind"] == "date" for w in warns(instruction, old, new))
    assert DR.missing_facts(instruction, instruction) == []


# ---- R6-02: a name that is a prefix of another person's name ---------------------------------------------------------
@pytest.mark.parametrize("instruction,old,new", [
    ("Office order: Shri Anil Kumar Singh, UDC and Shri Anil Kumar, LDC are transferred to Cash Section.",
     "Shri Anil Kumar, LDC", "Shri Sunil Kumar, LDC"),
    ("Office order: Shri Anil Kumar, LDC and Shri Anil Kumar Singh, UDC are transferred to Cash Section.",
     "Shri Anil Kumar, LDC", "Shri Sunil Kumar, LDC"),
    ("Notesheet: Smt. Sunita Sharma, ASO and Smt. Sunita, MTS have applied for leave.",
     "Smt. Sunita, MTS", "Smt. Savita, MTS"),
    ("Circular: Dr. Rakesh Gupta (Medical) and Dr. Rakesh (Dental) will examine staff on 3rd June.",
     "Dr. Rakesh (Dental)", "Dr. Mukesh (Dental)"),
])
def test_r6_02_each_person_is_checked(instruction, old, new):
    assert warns(instruction, old, new)
    assert DR.missing_facts(instruction, instruction) == []


# ---- R6-03: one..ten with a unit ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,old,new", [
    ("Notesheet: The file was received from Shri Harish Chandra on 3 May and the reply is due within seven days.",
     "seven days", "five days"),
    ("Circular: two officers each from Shri Gupta's and Smt. Rao's sections will attend.", "two officers",
     "three officers"),
])
def test_r6_03_small_number_words_with_units_warn(instruction, old, new):
    assert warns(instruction, old, new)
    assert DR.missing_facts(instruction, instruction) == []


# ---- R6-04: Mohd./Md., "Dr. (Smt.)", and no name made of an honorific or a designator alone ---------------------------
def test_r6_04_name_abbreviations_and_bracketed_honorifics():
    names = lambda t: [f["text"] for f in DR.extract_facts(t) if f["kind"] == "name"]   # noqa: E731
    assert names("Office order: Shri Mohd. Irfan Ansari, MTS, is transferred.") == ["Shri Mohd. Irfan Ansari"]
    assert names("Write a letter to Dr. (Smt.) Kavita Krishnan, Director.") == ["Dr. (Smt.) Kavita Krishnan"]
    assert "Room" not in names("Meeting in Room No. 115 on 3rd November.")
    assert "Dr" not in names("Write a letter to Dr. (Smt.) Kavita Krishnan, Director.")


def test_r6_plan_records_fb5():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB5" in text
