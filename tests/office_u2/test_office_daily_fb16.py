"""FB16 fallback review of b87d5b69 (OFFICE-DAILY-USE-r17): regression tests for R2-01 (titled names written in
capitals, with a lowercase title, with no space after a dotted title, with the title on the line before, "Sri" /
"Shrimati", "Kumari" after a verb), R2-02 (untitled person before "and" with a designation or an article), R2-03 (a
trailing head word in the draft; ", Joint Secretary." in the instruction) and R2-04 (plan count, UI scope note).
Tests named fb16_* fail on b87d5b69 and pass after the repair; *_guard_* tests pass on both."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"
UI = ROOT / "uri_ui/lib/living/office/office_workspace.dart"
CORPUS = Path(__file__).parent / "data" / "office_fact_corpus.json"


def names(instruction):
    return [f["text"] for f in DR.extract_facts(instruction) if f["kind"] == "name"]


def codes(instruction, blocks):
    return [(w.get("code", "FACT_MISSING"), w["text"]) for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01 ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,fact,faithful,replaced", [
    ("Write a letter to SHRI RAMESH KUMAR about the leave.", "SHRI RAMESH KUMAR",
     ["To", "SHRI RAMESH KUMAR"], ["To", "SHRI SURESH KUMAR"]),
    ("Write a letter to MS. ANJALI VERMA about the leave.", "MS. ANJALI VERMA",
     ["To", "Ms. Anjali Verma"], ["To", "MS. ANJALI SHARMA"]),
    ("Write a letter to SMT KAMLA DEVI about the leave.", "SMT KAMLA DEVI", ["To", "SMT KAMLA DEVI"],
     ["To", "SMT VIMLA DEVI"]),
    ("Write a letter to SHRI R.K. SHARMA, DIRECTOR about the leave.", "SHRI R.K. SHARMA",
     ["To", "SHRI R.K. SHARMA", "DIRECTOR"], ["To", "SHRI R.K. VERMA", "DIRECTOR"]),
    ("Grant leave to SMT. KAMLA DEVI, UDC from 3rd November 2026.", "SMT. KAMLA DEVI",
     ["SMT. KAMLA DEVI, UDC, 3rd November 2026"], ["SMT. VIMLA DEVI, UDC, 3rd November 2026"]),
    ("Write a letter to shri Ramesh Kumar about the leave.", "shri Ramesh Kumar", ["To", "Shri Ramesh Kumar"],
     ["To", "shri Suresh Kumar"]),
    ("Write a letter to Smt.Kamla Devi about the leave.", "Smt. Kamla Devi", ["To", "Smt.Kamla Devi"],
     ["To", "Smt.Vimla Devi"]),
    ("Write a letter to Shri\nRamesh Kumar about the leave.", "Shri Ramesh Kumar", ["To", "Shri", "Ramesh Kumar"],
     ["To", "Shri", "Suresh Kumar"]),
    ("Invite Kumari Priya Nair to the function.", "Kumari Priya Nair", ["Kumari Priya Nair"], ["Kumari Priya Menon"]),
    ("write to mr Anil Verma about the meeting.", "mr Anil Verma", ["To", "Mr Anil Verma"], ["To", "mr Anil Sharma"]),
    ("Write to dr. Anil Verma about the meeting.", "dr. Anil Verma", ["To", "Dr. Anil Verma"], ["To", "dr. Sunil Verma"]),
    ("Send it to DR ANIL VERMA.", "DR ANIL VERMA", ["To", "DR ANIL VERMA"], ["To", "DR ANIL SHARMA"]),
    ("Write to Sri Venkatesh Rao about the meeting.", "Sri Venkatesh Rao", ["To", "Sri Venkatesh Rao"],
     ["To", "Sri Venkatesh Reddy"]),
    ("Write to Shrimati Lakshmi Devi about the meeting.", "Shrimati Lakshmi Devi", ["To", "Shrimati Lakshmi Devi"],
     ["To", "Shrimati Lakshmi Bai"]),
])
def test_fb16_r2_01_titled_name_forms_stay_firm(instruction, fact, faithful, replaced):
    assert names(instruction) == [fact]
    assert DR.is_titled(fact)
    assert codes(instruction, faithful) == []
    assert codes(instruction, replaced) == [("FACT_MISSING", fact)]
    assert ("FACT_MISSING", fact) in codes(instruction, ["To", "The officer"])


@pytest.mark.parametrize("text", ["Travel 5 km to Pune.", "Open the file in MS Word.", "Sunita Kumari Singh will come."])
def test_r2_01_guard_short_forms_and_middle_names(text):
    assert not any(DR.is_titled(n) for n in names(text))


# ---- R2-02 ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("instruction,person,titled", [
    ("Write to Deputy Secretary Ramesh Kumar and Shri Anil Verma about the meeting.", "Ramesh Kumar", "Shri Anil Verma"),
    ("Write to Kavita Sharma and the District Collector Shri Anil Deshmukh about it.", "Kavita Sharma",
     "Shri Anil Deshmukh"),
])
def test_fb16_r2_02_untitled_person_before_and(instruction, person, titled):
    assert names(instruction) == [person, titled]
    assert codes(instruction, [titled]) == [("FACT_CHECK", person)]


# ---- R2-03 ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("draft", ["Shri Anil Verma Collector", "To Shri Anil Verma Deputy", "Shri Anil Verma Section"])
def test_fb16_r2_03_one_trailing_head_word_in_the_draft(draft):
    assert codes("Write to Shri Anil Verma about it.", [draft]) == []


def test_fb16_r2_03_designation_after_a_comma_at_clause_end():
    ins = "Reply to the letter from Shri Arvind Kumar Singh, Joint Secretary."
    assert names(ins) == ["Shri Arvind Kumar Singh"]
    assert codes(ins, ["To", "Shri Arvind Kumar Singh"]) == []


def test_r2_03_guard_another_surname_is_still_a_longer_name():
    assert codes("Write to Shri Anil Verma about it.", ["Shri Anil Verma Sharma"]) == [("FACT_CHECK", "Shri Anil Verma")]


# ---- R2-04 ---------------------------------------------------------------------------------------------------------------------
def test_fb16_r2_04_plan_count_and_scope_note():
    n = len(json.loads(CORPUS.read_text(encoding="utf-8"))["cases"])
    plan = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert f"Corpus ({n} instructions)" in plan
    assert "Repairs after fallback review FB16 of b87d5b69" in plan
    ui = UI.read_text(encoding="utf-8")
    assert "only without its trailing" in ui
