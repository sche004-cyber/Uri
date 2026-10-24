"""FB15 follow-up on d540c918 (coordinator decision after FB15 R2-03): a titled name whose last word is a single
designation head word after two or more other words ("Shri Asghar Ali Engineer", "Shri Homi Dinshaw Mistry Engineer")
is firm without that word and soft with it. Tests named fb15b_* fail on d540c918 and pass after the repair; *_guard_*
tests pass on both."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"
HOMI = "Write to Shri Homi Dinshaw Mistry Engineer about the camp on 7th November 2026."
ASGHAR = "Invite Shri Asghar Ali Engineer to the meeting on 9th November 2026."


def codes(instruction, blocks):
    return [(w.get("code", "FACT_MISSING"), w["text"]) for w in DR.missing_facts(instruction, "\n".join(blocks))]


@pytest.mark.parametrize("blocks", [
    ["To", "Shri Homi Dinshaw Mistry", "Engineer", "Camp on 7th November 2026"],
    ["To", "Shri Homi Dinshaw Mistry, Engineer", "Camp on 7th November 2026"],
])
def test_fb15b_designation_written_apart_gives_no_warning(blocks):
    assert codes(HOMI, blocks) == []


def test_fb15b_firm_part_only_gives_fact_check_naming_both_forms():
    w = DR.missing_facts(ASGHAR, "Invitation\nShri Asghar Ali\nThe meeting is on 9th November 2026.")
    assert w == [{"code": "FACT_CHECK", "kind": "name", "text": "Shri Asghar Ali Engineer", "found": "Shri Asghar Ali",
                  "message": "'Shri Asghar Ali Engineer' appears only as 'Shri Asghar Ali'. Check the name."}]
    assert codes(HOMI, ["To", "Shri Homi Dinshaw Mistry", "Camp on 7th November 2026"]) == [
        ("FACT_CHECK", "Shri Homi Dinshaw Mistry Engineer")]


def test_fb15b_other_surname_gives_fact_check():
    assert codes(ASGHAR, ["Shri Asghar Ali Khan", "The meeting is on 9th November 2026."]) == [
        ("FACT_CHECK", "Shri Asghar Ali Engineer")]


@pytest.mark.parametrize("instruction,draft,fact", [
    (ASGHAR, ["Shri Asghar Khan Engineer", "The meeting is on 9th November 2026."], "Shri Asghar Ali Engineer"),
    (HOMI, ["To", "Shri Homi Dinshaw", "Camp on 7th November 2026"], "Shri Homi Dinshaw Mistry Engineer"),
    ("Write to Shri Rustom Collector about the camp.", ["To", "Shri Rustom", "Camp"], "Shri Rustom Collector"),
])
def test_guard_replaced_firm_part_gives_fact_missing(instruction, draft, fact):
    assert codes(instruction, draft) == [("FACT_MISSING", fact)]


def test_guard_full_form_gives_no_warning():
    assert codes(ASGHAR, ["Shri Asghar Ali Engineer", "The meeting is on 9th November 2026."]) == []


def test_fb15b_plan_states_the_soft_trailing_head_word():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "the name without that word is the firm fact" in text
