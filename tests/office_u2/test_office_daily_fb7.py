"""FB7 fallback review of db652f38 (OFFICE-DAILY-USE-r8): regression tests for R2-01..R2-03 (the reviewer's cases).
Tests named fb7_* fail on db652f38 and pass after the repair; *_guard_* tests pass on both. The corpus test adds
property (e), facts inside headings, "To" blocks and sentences, for every case."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def miss(instruction, blocks):
    return [w["text"] for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: a title-case phrase around a name does not hide it ---------------------------------------------------------
FAITHFUL = [
    ("Prepare a notesheet on the promotion of Ramesh to the grade of UDC.",
     ["Notesheet", "Subject: Promotion of Ramesh", "The promotion of Ramesh to the grade of UDC is put up for orders.",
      "Section Officer"]),
    ("Draft an office order on the deputation of Anjali for training.",
     ["Office Order", "Subject: Deputation of Anjali", "Sanction is accorded to the deputation of Anjali for training.",
      "Under Secretary", "Guard File"]),
    ("Prepare a notesheet on the suspension of Gurpreet pending inquiry.",
     ["Notesheet", "Subject: Suspension of Gurpreet", "The suspension of Gurpreet pending inquiry is put up.",
      "Section Officer"]),
    ("Write a note on the absence of Venkat from duty.",
     ["Note", "Subject: Absence of Venkat from Duty", "The absence of Venkat from duty is reported.", "Under Secretary"]),
    ("Draft a letter to the tehsildar of Haveli about the 3 posts.",
     ["To", "The Tehsildar of Haveli", "Sir,", "This is regarding the 3 posts.", "Yours faithfully"]),
    ("Prepare a notesheet for the post of Superintendent in the cash section.",
     ["Notesheet", "Subject: Filling Up of the Post of Superintendent", "The post of Superintendent is vacant.",
      "Section Officer"]),
]


@pytest.mark.parametrize("instruction,blocks", FAITHFUL)
def test_fb7_r2_01_faithful_draft_with_a_title_case_heading_gives_no_warning(instruction, blocks):
    assert miss(instruction, blocks) == []


@pytest.mark.parametrize("instruction,blocks", FAITHFUL[:4])
def test_guard_a_changed_name_inside_the_heading_and_body_still_warns(instruction, blocks):
    fact = [f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "name"][0]
    changed = [b.replace(fact, fact + "a") for b in blocks]
    assert fact in miss(instruction, changed)


def test_guard_a_longer_name_of_another_person_still_does_not_count():
    ins = "Office order: Shri Anil Kumar Singh, UDC and Shri Anil Kumar, LDC are transferred to Cash Section."
    assert "Shri Anil Kumar" in miss(ins, [ins.replace("Shri Anil Kumar, LDC", "Shri Sunil Kumar, LDC")])
    assert "Shri Anil Kumar" in miss(ins, ["Shri Anil Kumar Singh, UDC", "Cash Section"])


# ---- R2-03: a title added to a single cued name (choice: accepted as the same name) ----------------------------------------
def test_fb7_r2_03_a_title_added_to_a_cued_name_is_the_same_name():
    ins = "Draft a letter to Ramesh about his leave."
    assert miss(ins, ["To", "Shri Ramesh", "Sir,", "Your leave is sanctioned."]) == []


def test_guard_a_longer_name_with_a_title_is_still_another_person():
    ins = "Draft a letter to Ramesh about his leave."
    assert "Ramesh" in miss(ins, ["To", "Shri Ramesh Kumar", "Sir,", "Your leave is sanctioned."])


def test_fb7_dash_dates_are_dates():
    ins = "Circular: The DPC will meet on 5-May-2026 and 6-Jun-2026."
    assert [f["text"] for f in DR.extract_facts(ins)] == ["5-May-2026", "6-Jun-2026"]
    assert "6-Jun-2026" in miss(ins, [ins.replace("6-Jun-2026", "7-Jun-2026")])


def test_fb7_plan_records_fb7():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB7" in text
