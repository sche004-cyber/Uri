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


@pytest.mark.parametrize("instruction,name,replacement,rephrased", [
    ("Draft a circular appointing officer named asha devi as nodal officer.",
     "asha devi", "priya devi",
     "Draft a circular appointing officer named asha devi to serve as nodal officer."),
    ("Issue an office order appointing staff member ramesh kumar as liaison.",
     "ramesh kumar", "suresh kumar",
     "Issue an office order appointing staff member ramesh kumar to liaise with the team."),
])
def test_r7_01_labelled_name_ends_before_as_role(instruction, name, replacement, rephrased):
    assert [f for f in DR.extract_facts(instruction) if f["kind"] == "name"] == [
        {"kind": "name", "text": name}]
    assert [(w["code"], w["kind"], w["text"]) for w in warns(instruction, name, replacement)] == [
        ("FACT_MISSING", "name", name)]
    assert DR.missing_facts(instruction, rephrased) == []


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


def test_r1_01_uncued_may_to_july_period_warns_outside_corpus():
    instruction = "Prepare a circular for May to July leave applications."
    assert {f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "date"} == {"May to July"}
    assert [(w["code"], w["kind"], w["text"]) for w in warns(instruction, "May", "June")] == [
        ("FACT_MISSING", "date", "May to July")]
    assert DR.missing_facts(instruction, instruction) == []


@pytest.mark.parametrize("instruction,month,replacement", [
    ("Draft a notice about attendance in April.", "April", "March"),
    ("Draft a notice about attendance in May.", "May", "June"),
])
def test_r1_02_standalone_month_time_reference_warns(instruction, month, replacement):
    assert {f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "date"} == {month}
    assert [(w["code"], w["kind"], w["text"]) for w in warns(instruction, month, replacement)] == [
        ("FACT_MISSING", "date", month)]
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


@pytest.mark.parametrize("instruction,draft,name", [
    ("Prepare an office order for Shri Anil Kumar.", "Office Order for Shri Anil Kumar Singh.", "Shri Anil Kumar"),
    ("Draft a notice for staff member ramesh kumar.",
     "Draft a notice for staff member ramesh kumar singh.", "ramesh kumar"),
])
def test_r5_01_added_surname_does_not_satisfy_shorter_name(instruction, draft, name):
    assert DR.missing_facts(instruction, instruction) == []
    assert [(w["code"], w["kind"], w["text"]) for w in DR.missing_facts(instruction, draft)] == [
        ("FACT_MISSING", "name", name)]
    assert DR.missing_facts(instruction, draft + f" {name} will report separately.") == []


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


# ---- OFFICE-DAILY-USE-r6 independent review -------------------------------------------------------------------------
def test_r2_01_may_through_july_period_warns_outside_corpus():
    instruction = "Prepare a circular covering May through July."
    assert DR.extract_facts(instruction) == [{"kind": "date", "text": "May through July"}]
    assert DR.missing_facts(instruction, instruction) == []
    assert [(w["code"], w["kind"], w["text"]) for w in warns(instruction, "May through July", "June through August")] == [
        ("FACT_MISSING", "date", "May through July")]


def test_r2_02_next_month_warns_when_changed():
    instruction = "Draft a notice for next April about attendance."
    assert DR.extract_facts(instruction) == [{"kind": "date", "text": "next April"}]
    assert DR.missing_facts(instruction, instruction) == []
    assert [(w["code"], w["kind"], w["text"]) for w in warns(instruction, "next April", "next March")] == [
        ("FACT_MISSING", "date", "next April")]


def test_r2_03_lowercase_name_in_person_context_warns():
    instruction = "Draft a notice for staff member ramesh kumar."
    assert DR.extract_facts(instruction) == [{"kind": "name", "text": "ramesh kumar"}]
    assert DR.missing_facts(instruction, instruction) == []
    assert [(w["code"], w["kind"], w["text"]) for w in warns(instruction, "ramesh kumar", "suresh kumar")] == [
        ("FACT_MISSING", "name", "ramesh kumar")]


def test_r6_01_lowercase_letter_recipient_warns_outside_corpus():
    instruction = "Draft a letter to ramesh kumar about his transfer."
    assert DR.extract_facts(instruction) == [{"kind": "name", "text": "ramesh kumar"}]
    assert DR.missing_facts(instruction, instruction) == []
    assert [(w["code"], w["kind"], w["text"]) for w in DR.missing_facts(
        instruction, "Dear suresh kumar, your transfer is approved."
    )] == [("FACT_MISSING", "name", "ramesh kumar")]
    assert DR.missing_facts(instruction, "Dear ramesh kumar, your transfer is approved.") == []
    assert DR.extract_facts("Draft a letter to request transfer.") == []


# ---- OFFICE-DAILY-USE-r6 R3 review repair ---------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,draft,name", [
    ("Draft a notice to staff member ramesh kumar about training.",
     "Notice: ramesh kumar must attend training.", "ramesh kumar"),
    ("Draft a letter for employee named asha devi regarding pension.",
     "Letter: asha devi requests pension processing.", "asha devi"),
])
def test_r3_01_person_name_stops_before_topic(instruction, draft, name):
    assert [f for f in DR.extract_facts(instruction) if f["kind"] == "name"] == [
        {"kind": "name", "text": name}]
    assert DR.missing_facts(instruction, draft) == []
    assert [(w["kind"], w["text"]) for w in DR.missing_facts(instruction, draft.replace(name, "another person"))] == [
        ("name", name)]


def test_r3_02_digit_amount_grown_by_number_word_warns():
    instruction = "Draft a memo approving Rs. 12 for stationery."
    assert {f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "amount"} == {"12"}
    assert DR.missing_facts(instruction, "The memo approves Rs. 12 for stationery.") == []
    assert [(w["kind"], w["text"]) for w in DR.missing_facts(
        instruction, "The memo approves Rs. 12 thousand for stationery.")] == [("amount", "12")]
    exact = "Draft a memo approving Rs. 12 thousand for stationery."
    assert DR.missing_facts(exact, exact) == []


@pytest.mark.parametrize("instruction,old,new", [
    ("Draft a notice: April salary processing starts soon.", "April", "March"),
    ("Draft a circular: March attendance records are due.", "March", "April"),
])
def test_r3_03_month_modifying_period_topic_warns(instruction, old, new):
    assert {f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "date"} == {old}
    assert DR.missing_facts(instruction, instruction) == []
    assert [(w["kind"], w["text"]) for w in warns(instruction, old, new)] == [("date", old)]


# ---- OFFICE-DAILY-USE-r6 R4 root-cause repair -----------------------------------------------------------
@pytest.mark.parametrize("instruction,month,replacement", [
    ("Draft a notice about the June roster.", "June", "July"),
    ("Prepare a circular: October duty chart changes.", "October", "November"),
    ("Write a memo for the February review cycle.", "February", "March"),
    ("Draft a notice about May roster changes.", "May", "June"),
])
def test_r4_01_bare_month_in_office_period_warns(instruction, month, replacement):
    assert [f for f in DR.extract_facts(instruction) if f["kind"] == "date"] == [
        {"kind": "date", "text": month}]
    assert DR.missing_facts(instruction, instruction) == []
    assert [(w["code"], w["kind"], w["text"]) for w in warns(instruction, month, replacement)] == [
        ("FACT_MISSING", "date", month)]


def test_r4_01_auxiliary_may_is_not_a_date():
    for instruction in ("May 3 officers be deputed?", "May staff apply for leave?", "Staff may apply for leave."):
        assert not [f for f in DR.extract_facts(instruction) if f["kind"] == "date"]


@pytest.mark.parametrize("instruction,draft,name", [
    ("Write a memo to staff member ramesh kumar on leave.",
     "Memo to staff member ramesh kumar regarding leave.", "ramesh kumar"),
    ("Draft a letter for employee named asha devi under review.",
     "Letter concerning asha devi and the review.", "asha devi"),
    ("Prepare a notice for officer named mohammed irfan ansari with a transfer request.",
     "Notice: mohammed irfan ansari requests a transfer.", "mohammed irfan ansari"),
])
def test_r4_02_labelled_name_stops_at_topic_clause(instruction, draft, name):
    assert [f for f in DR.extract_facts(instruction) if f["kind"] == "name"] == [
        {"kind": "name", "text": name}]
    assert DR.missing_facts(instruction, draft) == []
    assert [(w["kind"], w["text"]) for w in DR.missing_facts(
        instruction, draft.replace(name, "another person"))] == [("name", name)]
