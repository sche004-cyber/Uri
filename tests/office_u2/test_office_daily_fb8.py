"""FB8 fallback review of 1ad2e97f (OFFICE-DAILY-USE-r9): regression tests for R2-01 (the reviewer's cases and the
same masking class found in the follow-up search). Tests named fb8_* fail on 1ad2e97f and pass after the repair;
*_guard_* tests pass on both. The corpus test adds property (f) for every name."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def miss(instruction, blocks):
    return [w["text"] for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: a longer name in a "<Noun> of <name> <More>" heading is another person ------------------------------------
@pytest.mark.parametrize("instruction,blocks,name", [
    ("Draft an office order on the deputation of Anjali for training.",
     ["Office Order", "Subject: Deputation of Anjali Sharma",
      "Sanction is accorded to the deputation of Sunita for training.", "Under Secretary"], "Anjali"),
    ("Draft an office order on the deputation of Anjali for training.",
     ["Office Order", "Subject: Deputation of Anjali Devi", "Sanction is accorded."], "Anjali"),
    ("Prepare a notesheet on the promotion of Kavitha to the grade of UDC.",
     ["Notesheet", "Subject: Promotion of Kavitha Reddy to the Grade of UDC", "Put up for orders.",
      "Section Officer"], "Kavitha"),
    ("Prepare a notesheet on the deputation of Ramesh Kumar to NIC.",
     ["Notesheet", "Subject: Deputation of Ramesh Kumar Yadav", "The deputation of Suresh Kumar to NIC is put up.",
      "Section Officer"], "Ramesh Kumar"),
    ("Draft a letter to Ramesh about leave.", ["Subject: Leave for Ramesh Kumar", "Your leave is sanctioned."],
     "Ramesh"),
])
def test_fb8_r2_01_an_extended_name_in_a_heading_warns(instruction, blocks, name):
    assert name in miss(instruction, blocks)


# ---- the same class found in the follow-up search ----------------------------------------------------------------------
@pytest.mark.parametrize("instruction,blocks,name", [
    ("Draft an office order on the deputation of Anjali for training.",
     ["Subject: Leave for Anjali Kumari", "Sanction to Sunita."], "Anjali"),          # a surname that is an honorific
    ("Draft an office order on the deputation of Anjali for training.",
     ["Subject: Deputation of Anjali-Sharma", "Sanction to Sunita."], "Anjali"),       # a hyphenated surname
    ("Draft a letter to Shri ramesh kumar about his pension.",
     ["Subject: Deputation of Shri ramesh kumar Xavier", "Letter to Shri ramesh kumari about his pension."],
     "Shri ramesh kumar"),                                                               # a lowercase name extended
])
def test_fb8_masking_variants_warn(instruction, blocks, name):
    assert name in miss(instruction, blocks)


# ---- the FB7 fixes and the R2-03 choice stay -------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,blocks", [
    ("Draft an office order on the deputation of Anjali for training.",
     ["Office Order", "Subject: Deputation of Anjali", "Sanction is accorded to the deputation of Anjali for training.",
      "Under Secretary", "Guard File"]),
    ("Draft a letter to the tehsildar of Haveli about the 3 posts.",
     ["To", "The Tehsildar of Haveli", "Sir,", "This is regarding the 3 posts.", "Yours faithfully"]),
    ("Prepare a notesheet on the promotion of Ramesh to the grade of UDC.",
     ["Notesheet", "Subject: Promotion of Ramesh to the Grade of UDC", "The promotion of Ramesh is put up."]),
    ("Draft a letter to Ramesh about his leave.", ["To", "Shri Ramesh", "Sir,", "Your leave is sanctioned."]),
    ("Draft a letter for employee named asha devi regarding pension.",
     ["Letter", "asha devi requests pension processing."]),
])
def test_guard_faithful_drafts_still_give_no_warning(instruction, blocks):
    assert miss(instruction, blocks) == []


def test_fb8_plan_records_fb8():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB8" in text
