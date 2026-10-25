"""FB14 fallback review of 3db6a663 (OFFICE-DAILY-USE-r15): regression tests for R2-01 (Sahab/Saheb/Sahib as given
names), R2-02 (nothing before an honorific is a name; a designation after a titled name ends it), R2-03 (a dash or
"&" used as punctuation after a reference), R2-04 (OD-OD-7 before a unit), R2-05 (designation surnames) and R2-06
(a spaced section bracket). Tests named fb14_* fail on 3db6a663 and pass after the repair; *_guard_* tests pass on
both."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def names(instruction):
    return [f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "name"]


def codes(instruction, blocks):
    return [(w.get("code", "FACT_MISSING"), w["text"]) for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: Sahab, Saheb, Sahib ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,name,replaced", [
    ("Sanction earned leave of 10 days to Shri Sahab Singh Chauhan, UDC, from 3rd November 2026.",
     "Shri Sahab Singh Chauhan", "Shri Karan Singh Chauhan"),
    ("Write a letter to Shri Saheb Rao Patil, Sarpanch, about the road.", "Shri Saheb Rao Patil", "Shri Bapu Rao Patil"),
    ("Issue an order posting Shri Sahib Singh Verma to Ludhiana.", "Shri Sahib Singh Verma", "Shri Gurdeep Singh Verma"),
])
def test_fb14_r2_01_sahab_saheb_sahib_are_given_names(instruction, name, replaced):
    assert name in names(instruction)
    assert codes(instruction, [instruction]) == []
    assert ("FACT_MISSING", name) in codes(instruction, [instruction.replace(name, replaced)])


def test_r2_01_guard_sahab_as_the_last_word():
    ins = "Write a letter to Shri Rajendra Prasad Meena about the review."
    assert codes(ins, ["To", "Shri Rajendra Prasad Meena Sahab"]) == []


# ---- R2-02: a titled name starts at its honorific ---------------------------------------------------------------------------
DESIGNATIONS = ["District Collector", "Divisional Commissioner", "Sub-Divisional Magistrate", "Block Development Officer",
                "Section Officer", "Assistant Director", "Senior Superintendent", "Assistant Section Officer",
                "Drawing and Disbursing Officer", "Hon'ble Union Minister", "Executive Engineer", "Director General",
                "Registrar General", "Vice Chancellor", "Chief Engineer", "Superintendent of Police", "Hon'ble Justice",
                "Hon'ble Minister of State for Finance", "Commissioner (Revenue)"]


@pytest.mark.parametrize("designation", DESIGNATIONS)
def test_fb14_r2_02_designation_before_the_title_is_not_a_name(designation):
    ins = f"Write a letter to {designation} Shri Prakash Chandra Joshi about the inspection on 14th November 2026."
    assert names(ins) == ["Shri Prakash Chandra Joshi"]
    assert codes(ins, ["To", "Shri Prakash Chandra Joshi", "The inspection is on 14th November 2026."]) == []
    assert codes(ins, ["To", "Shri Prakash Chandra Pant", "The inspection is on 14th November 2026."]) == [
        ("FACT_MISSING", "Shri Prakash Chandra Joshi")]


def test_fb14_r2_02_designation_before_a_lowercase_titled_name():
    ins = "Write a letter to Executive Engineer Shri ramesh kumar about the inspection."
    assert names(ins) == ["Shri ramesh kumar"]


def test_fb14_r2_02_designation_after_the_titled_name_ends_it():
    ins = "Invite Smt. Rekha Rani Joint Director and Shri Mohan Lal Deputy Director on 3rd November 2026."
    assert names(ins) == ["Smt. Rekha Rani", "Shri Mohan Lal"]
    assert codes(ins, ["Smt. Rekha Rani", "Joint Director", "Shri Mohan Lal", "3rd November 2026"]) == []


def test_fb14_r2_02_designation_tail_after_another_person():
    ins = "Invite Ms Anjali Verma and Drawing and Disbursing Officer Shri Suresh Mishra on 3rd November."
    assert names(ins) == ["Ms Anjali Verma", "Shri Suresh Mishra"]
    assert names("Send a letter to the Hon'ble Minister and Shri Rakesh Tiwari about the review.") == [
        "Shri Rakesh Tiwari"]
    assert names("Ramesh Kumar and Shri Mohan Lal will attend.") == ["Ramesh Kumar", "Shri Mohan Lal"]


# ---- R2-05: designation surnames ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,name,changed", [
    ("Issue an office order transferring Shri Rustom Collector and Smt. Roshan Engineer to the Mumbai office.",
     "Shri Rustom Collector", "Shri Rustom"),
    ("Issue an order for Shri Ram Collector and Smt. Kavita Minister.", "Shri Ram Collector", "Shri Ram Contractor"),
    ("Issue an order for Shri Ram Prakash Member and Dr. Sushma Singh.", "Shri Ram Prakash Member", "Shri Ram Prakash"),
])
def test_fb14_r2_05_designation_word_as_surname(instruction, name, changed):
    assert name in names(instruction)
    assert ("FACT_MISSING", name) in codes(instruction, [instruction.replace(name, changed)])


# ---- R2-03: a dash or "&" used as punctuation ---------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,name", [
    ("Reply on F.No. 12/3/2026—it concerns the pension case dated 5th November 2026.", None),
    ("Send a reminder on F.No. 12/3/2026–Pension case of Shri Ram Lal, dated 5th November 2026.", "Shri Ram Lal"),
    ("Send a reminder on F.No. 12/3/2026—Shri Ram Lal's pension dated 5th November 2026.", "Shri Ram Lal"),
    ("Send a reminder on F.No. 12/3/2026 & Shri Ram Lal's pension dated 5th November 2026.", "Shri Ram Lal"),
])
def test_fb14_r2_03_dash_as_punctuation(instruction, name):
    facts = DR.extract_facts(instruction)
    assert {"kind": "reference", "text": "12/3/2026"} in facts
    assert names(instruction) == ([name] if name else [])
    draft = ["Reference F.No. 12/3/2026 dated 5th November 2026."] + (["To " + name] if name else [])
    assert codes(instruction, draft) == []


def test_r2_03_guard_section_codes_after_a_dash_or_ampersand():
    assert {"kind": "reference", "text": "17011/1/2026–Estt"} in DR.extract_facts("Refer O.M. No. 17011/1/2026–Estt.")
    assert {"kind": "reference", "text": "2(14)/2026-B&A"} in DR.extract_facts("Refer F.No. 2(14)/2026-B&A today.")
    assert {"kind": "reference", "text": "G-25017/4/2026–PMS"} in DR.extract_facts("Refer No. G-25017/4/2026–PMS.")


# ---- R2-04: OD-OD-7 before a unit ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,draft", [
    ("Release Rs. 2 lakh for repairs.", "Rs. 2.00 lakh is released for repairs."),
    ("Release Rs. 2.00 lakh for repairs.", "Rs. 2 lakh is released for repairs."),
    ("Release Rs. 1 crore for repairs.", "Rs. 1.00 crore is released for repairs."),
    ("Release Rs. 1.0 crore for repairs.", "Rs. 1 crore is released for repairs."),
    ("Release Rs. 5 thousand for repairs.", "Rs. 5.00 thousand is released for repairs."),
])
def test_fb14_r2_04_zero_paise_before_a_unit(instruction, draft):
    assert codes(instruction, [draft]) == []


@pytest.mark.parametrize("draft", ["Rs. 2.50 lakh is released.", "Rs. 2.05 lakh is released.", "Rs. 12.00 lakh is released."])
def test_guard_non_zero_paise_before_a_unit_warns(draft):
    assert [c for c, _ in codes("Release Rs. 2 lakh for repairs.", [draft])] == ["FACT_MISSING"]


# ---- R2-06: a spaced section bracket -------------------------------------------------------------------------------------------
def test_fb14_r2_06_spaced_section_bracket():
    ins = "Send a reminder on No. 1/2/2026-P&PW (A) to Shri Anil Verma."
    assert {"kind": "reference", "text": "1/2/2026-P&PW (A)"} in DR.extract_facts(ins)
    assert codes(ins, ["To", "Shri Anil Verma", "Reference No. 1/2/2026-P&PW(A)."]) == []
    assert codes(ins, ["To", "Shri Anil Verma", "Reference No. 1/2/2026-P&PW (B)."]) == [
        ("FACT_MISSING", "1/2/2026-P&PW (A)")]


def test_fb14_plan_records_the_general_rules():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB14 of 3db6a663" in text
    assert "A titled name fact starts at its honorific" in text
    assert "R2-06 (LOW), chosen: the spaced section bracket is accepted" in text
    assert "Applied since FB14 to the number before a unit as well" in text
