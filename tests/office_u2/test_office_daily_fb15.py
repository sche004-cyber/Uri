"""FB15 fallback review of df14bba1 (OFFICE-DAILY-USE-r16) and owner decision OD-OD-8 (MM LDEC-017): a name without a
title gets FACT_CHECK only; titled names, dates, amounts, numbers and references keep FACT_MISSING. Regression tests for
R2-01 (an untitled person before "and <courtesy> <title>"), R2-02 (a designation before an untitled name), R2-03 (a
single trailing head word is a surname) and R2-04 (a short code after a dash before a title-case word). Tests named
fb15_* fail on df14bba1 and pass after the repair; *_guard_* tests pass on both."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"
UI = Path(__file__).resolve().parents[2] / "uri_ui/lib/living/office/office_workspace.dart"


def names(instruction):
    return [f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "name"]


def codes(instruction, blocks):
    return [(w.get("code", "FACT_MISSING"), w["text"]) for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- OD-OD-8: the two kinds of names -----------------------------------------------------------------------------------------
def test_fb15_untitled_name_not_found_gives_fact_check():
    ins = "Write a memo to Ramesh Kumar about the leave on 5th December 2026."
    w = DR.missing_facts(ins, "Memo to Suresh Kumar about the leave on 5th December 2026.")
    assert w == [{"code": "FACT_CHECK", "kind": "name", "text": "Ramesh Kumar",
                  "message": "'Ramesh Kumar' (from your instruction) was not found in the draft. Check the name."}]


@pytest.mark.parametrize("instruction,draft,fact", [
    ("Write a letter to Shri Ramesh Kumar about the leave.", "Letter to Shri Suresh Kumar about the leave.",
     "Shri Ramesh Kumar"),
    ("Grant leave from 3rd November 2026.", "Leave from 4th November 2026.", "3rd November 2026"),
    ("Sanction Rs. 25,000 for repairs.", "Rs. 26,000 is sanctioned for repairs.", "25,000"),
    ("Sanction leave for 10 days.", "Leave for 12 days is sanctioned.", "10 days"),
    ("Reply to F.No. 12/3/2026-Estt.", "Reply to F.No. 12/4/2026-Estt.", "12/3/2026-Estt"),
])
def test_guard_titled_names_dates_amounts_numbers_references_stay_firm(instruction, draft, fact):
    assert ("FACT_MISSING", fact) in codes(instruction, [draft])


# ---- R2-01 ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,person,titled", [
    ("Write a letter to Ramesh Kumar and Hon'ble Shri Anil Verma about the visit on 5th December 2026.",
     "Ramesh Kumar", "Shri Anil Verma"),
    ("Settle the family pension of Ramesh Chandra and Late Smt. Kamla Devi from 1st January 2027.",
     "Ramesh Chandra", "Smt. Kamla Devi"),
    ("Write to Kavita Sharma and Hon'ble Minister Shri Anil Verma about the visit.", "Kavita Sharma", "Shri Anil Verma"),
])
def test_fb15_r2_01_untitled_person_before_and_courtesy_title(instruction, person, titled):
    assert names(instruction)[:2] == [person, titled]
    assert ("FACT_CHECK", person) in codes(instruction, [f"To {titled}"])
    assert ("FACT_MISSING", person) not in codes(instruction, [f"To {titled}"])
    assert not [t for _, t in codes(instruction, [f"To {person} and {titled}"]) if t in (person, titled)]


def test_r2_01_guard_designations_before_a_title_stay_claimed():
    assert names("Write to Drawing and Disbursing Officer Shri Prakash Joshi.") == ["Shri Prakash Joshi"]
    assert names("Send a letter to the Hon'ble Minister and Shri Rakesh Tiwari.") == ["Shri Rakesh Tiwari"]


# ---- R2-02 ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("designation", ["Deputy Secretary", "Section Officer", "District Collector", "Executive Engineer",
                                         "Under Secretary", "Additional Chief Secretary"])
def test_fb15_r2_02_designation_before_an_untitled_name(designation):
    ins = f"Write to {designation} Ramesh Kumar about the meeting on 5th December 2026."
    assert names(ins) == ["Ramesh Kumar"]
    assert codes(ins, ["To", f"Ramesh Kumar, {designation}", "The meeting is on 5th December 2026."]) == []
    assert codes(ins, ["To", f"Suresh Kumar, {designation}", "The meeting is on 5th December 2026."]) == [
        ("FACT_CHECK", "Ramesh Kumar")]


def test_fb15_r2_02_two_untitled_people_with_designations():
    ins = "Write to Section Officer Kavita Sharma and Executive Engineer Anil Rao about the audit."
    assert names(ins) == ["Kavita Sharma", "Anil Rao"]


# ---- R2-03 ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,changed", [
    ("Shri Asghar Ali Engineer", "Shri Asghar Ali"), ("Shri Asghar Ali Engineer", "Shri Asghar Ali Khan"),
    ("Dr. Jamshed Rustom Collector", "Dr. Jamshed Rustom Contractor"), ("Shri Ram Prakash Senior", "Shri Ram Prakash"),
    ("Shri Ram Kumar Special", "Shri Ram Kumar"),
])
def test_fb15_r2_03_single_trailing_head_word_is_a_surname(name, changed):
    ins = f"Invite {name} to the meeting on 9th November 2026."
    assert names(ins) == [name]
    assert codes(ins, [f"Invite {name} on 9th November 2026."]) == []
    # FB15 follow-up: the trailing head word is soft (FACT_CHECK); the firm part is the name without it
    assert codes(ins, [f"Invite {changed} on 9th November 2026."]) == [("FACT_CHECK", name)]


def test_r2_03_guard_two_word_designation_still_ends_the_name():
    assert names("Invite Smt. Rekha Rani Joint Director and Shri Mohan Lal Deputy Director.") == [
        "Smt. Rekha Rani", "Shri Mohan Lal"]


# ---- R2-04 ---------------------------------------------------------------------------------------------------------------------
def test_fb15_r2_04_code_before_a_title_case_word():
    ins = "Reply on F.No. 12/3/2026–Estt Shri Ram Lal's case dated 5th November 2026."
    assert {"kind": "reference", "text": "12/3/2026–Estt"} in DR.extract_facts(ins)
    assert codes(ins, ["F.No. 12/3/2026-Estt", "Shri Ram Lal", "5th November 2026"]) == []
    assert ("FACT_MISSING", "12/3/2026–Estt") in codes(ins, ["F.No. 12/3/2026-Admn", "Shri Ram Lal",
                                                                    "5th November 2026"])
    assert {"kind": "reference", "text": "7/2/2026–RTI"} in DR.extract_facts("Forward No. 7/2/2026–RTI Cell.")


@pytest.mark.parametrize("text", ["Send on F.No. 12/3/2026—Late Shri Ram Lal.",
                                  "Send on F.No. 12/3/2026–Deputy Commissioner Shri Ram Lal.",
                                  "Send on F.No. 12/3/2026—MLA Shri Ram Lal."])
def test_r2_04_guard_courtesy_words_are_not_codes(text):
    assert {"kind": "reference", "text": "12/3/2026"} in DR.extract_facts(text)


def test_fb15_plan_and_ui_state_od_od_8():
    plan = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "- OD-OD-8 (decided by the owner 2026-10-24, MM LDEC-017" in plan
    assert "Repairs after fallback review FB15 of df14bba1" in plan
    assert "An absent name without a title (\"Sunita\" for \"Anjali\") gives FACT_CHECK (OD-OD-8)" in plan
    ui = UI.read_text(encoding="utf-8")
    assert "a name without a title was not" in ui
