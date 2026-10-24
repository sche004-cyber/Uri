"""FB9 fallback review of 2831f984 (OFFICE-DAILY-USE-r10): regression tests for R2-01..R2-05 (the reviewer's cases).
Tests named fb9_* fail on 2831f984 and pass after the repair; *_guard_* tests pass on both. OD-OD-5: this is the last
repair round for the extension class; the rest is stated in plan 16's "Fact-check scope"."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def miss(instruction, blocks):
    return [w["text"] for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: "Kumari" as a middle name ---------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,blocks,name", [
    ("Draft a letter to Smt. Sunita about her leave.",
     ["To", "Smt. Sunita Kumari Singh", "Subject: Leave", "Madam,", "Smt. Rekha is granted leave."], "Smt. Sunita"),
    ("Draft an office order on the deputation of Anjali for training.",
     ["Office Order", "Subject: Deputation of Anjali Kumari Singh",
      "Sanction is accorded to the deputation of Sunita for training."], "Anjali"),
    ("Draft a letter to Shri Anil about his leave.", ["To", "Shri Anil Kumari Prasad", "Subject: Leave"], "Shri Anil"),
])
def test_fb9_r2_01_kumari_middle_name_is_an_extension(instruction, blocks, name):
    assert name in miss(instruction, blocks)


def test_guard_two_people_joined_by_and_still_split():
    names = [f["text"] for f in DR.extract_facts("Office order: Shri Ram Kumar and Smt Sita Devi are relieved.")
             if f["kind"] == "name"]
    assert names == ["Shri Ram Kumar", "Smt Sita Devi"]


# ---- R2-02: a titled lowercase name at the end of a block -----------------------------------------------------------
@pytest.mark.parametrize("instruction,blocks,name", [
    ("Draft a letter to Shri ramesh kumar about his pension.", ["To", "Shri ramesh kumar sharma", "Subject: Pension"],
     "Shri ramesh kumar"),
    ("Draft a letter to Shri ramesh kumar about his pension.",
     ["Subject: Pension of Shri ramesh kumar sharma", "Sir,", "Shri suresh kumar is informed."], "Shri ramesh kumar"),
    ("Write a memo to Smt. anita sharma about her leave.", ["To", "Smt. anita sharma devi", "Subject: Leave"],
     "Smt. anita sharma"),
])
def test_fb9_r2_02_lowercase_titled_name_extended_in_a_block_warns(instruction, blocks, name):
    assert name in miss(instruction, blocks)


def test_guard_lowercase_titled_name_faithful_block_gives_no_warning():
    assert miss("Draft a letter to Shri ramesh kumar about his pension.",
                ["To", "Shri ramesh kumar", "Subject: Pension", "Sir,", "Your pension is processed."]) == []


# ---- R2-03: an extended reference is another file -------------------------------------------------------------------
@pytest.mark.parametrize("instruction,draft_ref", [
    ("Draft a reply to O.M. No. 14/2/2026 on leave rules.", "O.M. No. 14/2/2026-1"),
    ("Draft a reply to O.M. No. 14/2/2026 on leave rules.", "O.M. No. 14/2/2026(1)"),
    ("Draft a reply to O.M. No. 14/2/2026 on leave rules.", "O.M. No. 14/2/2026-Admn"),
    ("Draft a reply to O.M. No. 14/2/2026 on leave rules.", "O.M. No. A-14/2/2026"),
    ("Draft a letter under F.No. A-12011/3/2026-Estt. about the meeting.", "F.No. A-12011/3/2026-Estt.-II"),
    ("Draft a letter under F.No. A-12011/3/2026-Estt. about the meeting.", "F.No. A-12011/3/2026-Estt.(Pt.)"),
    ("Draft a letter under F.No. A-12011/3/2026-Estt. about the meeting.", "F.No. A-12011/3/2026-Estt./1"),
])
def test_fb9_r2_03_extended_reference_warns(instruction, draft_ref):
    assert miss(instruction, [draft_ref, "Subject: Meeting"])


@pytest.mark.parametrize("instruction,blocks", [
    ("Draft a letter under F.No. A-12011/3/2026-Estt. about the meeting.",
     ["F.No. A-12011/3/2026-Estt.", "Subject: Meeting"]),
    ("Draft a reply to O.M. No. 14/2/2026 on leave rules.",
     ["Subject: Reply to O.M. No. 14/2/2026, dated today", "This refers to O.M. No. 14/2/2026 on leave rules."]),
    ("Draft a letter under F.No. 12/5/2026-Estt.(A) on leave rules.", ["F.No. 12/5/2026-Estt.(A)", "x"]),
])
def test_guard_faithful_references_still_match(instruction, blocks):
    assert miss(instruction, blocks) == []


# ---- R2-04: post-nominals and heading words end a name ----------------------------------------------------------------
@pytest.mark.parametrize("instruction,blocks", [
    ("Draft a letter to Shri Ramesh Kumar about the hearing.",
     ["To", "Shri Ramesh Kumar IAS", "District Collector", "Subject: Hearing", "The hearing is fixed."]),
    ("Draft a letter to Shri Ramesh Kumar about the hearing.", ["To", "Shri Ramesh Kumar Esq.", "Subject: Hearing"]),
    ("Draft a letter to Dr. Rakesh Gupta about the meeting.", ["To", "Dr. Rakesh Gupta MD", "Subject: Meeting"]),
    ("Draft an office order on the deputation of Anjali for training.",
     ["OFFICE ORDER", "Subject: Deputation of Anjali Under Rule 12", "Sanction is accorded for training."]),
    ("Draft a letter to Ramesh about his leave.",
     ["Subject: Leave of Ramesh Sanctioned", "Sir,", "Your leave is sanctioned."]),
    ("Draft a letter to Shri Ramesh Kumar about pay.",
     ["Subject: Representation of Shri Ramesh Kumar Regarding Pay Fixation", "Sir,", "The representation is examined."]),
])
def test_fb9_r2_04_post_nominals_and_heading_words_give_no_false_warning(instruction, blocks):
    assert miss(instruction, blocks) == []


def test_guard_md_abbreviation_stays_a_name_word():
    assert {"kind": "name", "text": "Shri Md. Salim Khan"} in DR.extract_facts("Letter to Shri Md. Salim Khan today.")


# ---- R2-05: the extension exception is stated inside the scope ---------------------------------------------------------
def test_fb9_r2_05_plan_states_the_exception_and_od_od_5():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Exception inside the scope (owner decision 2026-10-24, OD-OD-5)" in text
    assert "- OD-OD-5 (decided by the owner 2026-10-24" in text
    assert "Repairs after fallback review FB9" in text
