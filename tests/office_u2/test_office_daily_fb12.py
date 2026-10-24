"""FB12 fallback review of 644be9b1 (OFFICE-DAILY-USE-r13) and owner decision OD-OD-6 (MM LDEC-014): the fact check
gives two signals. FACT_MISSING only when a marked fact is not in the draft word for word; FACT_CHECK when it is
there word for word but only inside what the rules read as a longer name or reference. Tests named fb12_* fail on
644be9b1 and pass after the repair; *_guard_* tests pass on both."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_office_daily_od import INSTR, ORDER_BLOCKS, FakeClient, answer, office_with
from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def codes(instruction, blocks):
    return [(w.get("code", "FACT_MISSING"), w["text"]) for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: courtesy and designation words before a title -------------------------------------------------------------
MOHAN = "Write a letter to Shri Mohan Lal about the meeting on 12th November 2026."


@pytest.mark.parametrize("blocks", [
    ["To", "Hon'ble Shri Mohan Lal,", "The meeting is on 12th November 2026."],
    ["The meeting with Hon'ble Minister Shri Mohan Lal is on 12th November 2026."],
    ["The meeting with Minister Shri Mohan Lal is on 12th November 2026."],
    ["In memory of Late Shri Mohan Lal, the meeting is on 12th November 2026."],
    ["To", "MLA Shri Mohan Lal", "The meeting is on 12th November 2026."],
    ["To", "Secretary Shri Mohan Lal", "The meeting is on 12th November 2026."],
    ["To", "Collector Shri Mohan Lal", "The meeting is on 12th November 2026."],
    ["Minister of State Shri Mohan Lal will attend the meeting on 12th November 2026."],
    ["Adarniya Shri Mohan Lal Ji,", "The meeting is on 12th November 2026."],
])
def test_fb12_r2_01_words_before_a_title_give_no_warning(blocks):
    assert codes(MOHAN, blocks) == []


def test_fb12_r2_01_the_instruction_fact_is_the_titled_name():
    assert DR.extract_facts("The Hon'ble Minister Shri Mohan Lal will attend.") == [
        {"kind": "name", "text": "Shri Mohan Lal"}]


def test_r2_01_guard_middle_names_are_unchanged():
    for text in ("Smt. Sunita Kumari Singh", "Sunita Kumari Singh will come", "Shri Ramesh Shri Vastava came"):
        assert len([f for f in DR.extract_facts(text) if f["kind"] == "name"]) == 1, text
    assert codes(MOHAN, ["To", "Shri Sohan Lal", "The meeting is on 12th November 2026."]) == [
        ("FACT_MISSING", "Shri Mohan Lal")]


def test_fb12_two_titled_people_without_a_comma_are_two_facts():
    ins = "Draft a letter to Shri Ram Kumar Smt Sita Devi."
    assert [f["text"] for f in DR.extract_facts(ins)] == ["Shri Ram Kumar", "Smt Sita Devi"]
    assert codes(ins, ["To", "Shri Ram Kumar", "Smt Sita Devi"]) == []
    assert codes(ins, ["To", "Shri Ram Kumar", "Smt Gita Devi"]) == [("FACT_MISSING", "Smt Sita Devi")]


# ---- R2-02: date words after a reference --------------------------------------------------------------------------------
VIG = "Send a reminder on letter No. 14/7/2026-Vig dated 3.10.2026 to Shri Anil Verma."
HEAD = ["To", "Shri Anil Verma", "Subject: Reminder"]


@pytest.mark.parametrize("body", [
    "Please refer to letter No. 14/7/2026-Vig/dated 3.10.2026.",
    "Please refer to letter No. 14/7/2026-Vig/dt. 3.10.2026.",
    "Please refer to letter No. 14/7/2026-Vig/Dt. 3.10.2026.",
    "Please refer to letter No. 14/7/2026-Vig/Dated 3.10.2026.",
    "Please refer to letter No. 14/7/2026-Vig-W.E.F. 3.10.2026.",
    "Please refer to letter No. 14/7/2026-VIG-W.E.F. 3.10.2026.",
    "Please refer to letter No. 14/7/2026-Vig-Date 3.10.2026.",
    "Please refer to letter No. 14/7/2026-Vigdt. 3.10.2026.",
])
def test_fb12_r2_02_date_words_after_a_reference_give_no_warning(body):
    assert codes(VIG, HEAD + [body]) == []


def test_fb12_r2_02_slash_forms_of_other_references():
    ins = "Send a reminder on Lr. No. HR/Trg/2026/145 to Dr. Meenakshi Iyer."
    for body in ("Lr. No. HR/Trg/2026/145/dt. 3.10.2026", "Lr. No. HR/Trg/2026/145/dated 3.10.2026",
                 "Lr. No. HR/Trg/2026/145dt. 3.10.2026"):
        assert codes(ins, ["To", "Dr. Meenakshi Iyer", body]) == [], body


# ---- R2-03: a subject line ending in a participle ------------------------------------------------------------------------
RAMESH = "Put up a note on the leave of Shri ramesh kumar from 5th November 2026."


@pytest.mark.parametrize("blocks", [
    ["Note", "Subject: Leave of Shri ramesh kumar pending", "Leave from 5th November 2026."],
    ["Note", "Subject: Leave application of Shri ramesh kumar received", "Leave from 5th November 2026."],
    ["Note", "Leave of Shri ramesh kumar sanctioned", "w.e.f. 5th November 2026"],
])
def test_fb12_r2_03_participle_ending_a_subject_line_gives_no_warning(blocks):
    assert codes(RAMESH, blocks) == []


def test_fb12_r2_03_an_address_line_is_still_a_longer_name():
    # the name starts its block: "To / Shri ramesh kumar sharma" is another person, FACT_CHECK (FB11 R2-02)
    assert codes(RAMESH, ["Note", "To", "Shri ramesh kumar sharma", "Leave from 5th November 2026."]) == [
        ("FACT_CHECK", "Shri ramesh kumar")]


# ---- R2-04 / R2-05: forms the rules read as another file give FACT_CHECK, never FACT_MISSING -----------------------------
@pytest.mark.parametrize("body", [
    "Kindly refer to No. 14/7/2026-Vig-Copy enclosed.", "Kindly refer to No. 14/7/2026-Vig-Encl.",
    "Kindly refer to No. 14/7/2026-Vig-Urgent.", "Kindly refer to No. 14/7/2026-Vig-Sub: reminder.",
    "Kindly refer to OM-14/7/2026-Vig.", "Kindly refer to DO-14/7/2026-Vig.",
    "Kindly refer to No. 14/7/2026-Vig(A).", "Kindly refer to No. 14/7/2026-Vig.(A).",
])
def test_fb12_r2_04_r2_05_extension_forms_give_fact_check(body):
    assert codes(VIG, HEAD + [body + " dated 3.10.2026"]) == [("FACT_CHECK", "14/7/2026-Vig")]


# ---- OD-OD-6: the two signals ---------------------------------------------------------------------------------------------
def test_fb12_fact_check_messages_name_both_forms():
    w = DR.missing_facts("Draft an office order on the deputation of Anjali for training.",
                         "Office Order\nSubject: Deputation of Anjali Sharma\n"
                         "Sanction is accorded to the deputation of Sunita for training.")
    assert w == [{"code": "FACT_CHECK", "kind": "name", "text": "Anjali", "found": "Anjali Sharma",
                  "message": "'Anjali' appears only as 'Anjali Sharma'. Check it is the same person."}]
    w = DR.missing_facts("Reply to O.M. No. 14/2/2026 today.", "Subject: Reply to O.M. No. 14/2/2026-1")
    assert w == [{"code": "FACT_CHECK", "kind": "reference", "text": "14/2/2026", "found": "14/2/2026-1",
                  "message": "'14/2/2026' appears only as '14/2/2026-1'. Check it is the same file."}]


@pytest.mark.parametrize("instruction,blocks,found", [
    ("Draft a letter to Shri Anil Kumar about the hearing.", ["To", "Shri Anil Kumar Singh", "Subject: Hearing"],
     "Shri Anil Kumar Singh"),
    ("Draft a letter to Shri Anil Kumar about the hearing.", ["To", "Shri Anil Kumar-Singh", "Subject: Hearing"],
     "Shri Anil Kumar-Singh"),
    ("Draft a letter to Shri ramesh kumar about the hearing.", ["To", "Shri ramesh kumar Xavier", "Subject: Hearing"],
     "Shri ramesh kumar Xavier"),
    ("Draft a letter to Smt. Sunita about leave.", ["To", "Smt. Sunita Kumari Singh", "Subject: Leave"],
     "Smt. Sunita Kumari Singh"),
    ("Send a reminder on No. 14/2/2026-Estt to Shri Anil Verma.", ["Shri Anil Verma", "No. 14/2/2026-Estt(Pt.)"],
     "14/2/2026-Estt(Pt.)"),
    ("Send a reminder on No. 14/2/2026-Estt to Shri Anil Verma.", ["Shri Anil Verma", "No. A-14/2/2026-Estt"],
     "A-14/2/2026-Estt"),
])
def test_fb12_extensions_give_fact_check_not_fact_missing(instruction, blocks, found):
    w = DR.missing_facts(instruction, "\n".join(blocks))
    assert [(x["code"], x["found"]) for x in w] == [("FACT_CHECK", found)]


@pytest.mark.parametrize("instruction,blocks,fact", [
    ("Draft a letter to Shri Ram Ji Lal about his pension.", ["To", "Shri Ram Ji Gupta", "Subject: Pension"],
     "Shri Ram Ji Lal"),
    ("Draft an office order sanctioning the deputation of Anjali for training.",
     ["Office Order", "Subject: Deputation for training", "Sanction is accorded to the deputation of Sunita."],
     "Anjali"),
    ("Send a reminder on No. 14/7/2026-Vig dated 3.10.2026 to Shri Anil Verma.",
     HEAD + ["Kindly refer to No. 14/8/2026-Vig dated 3.10.2026."], "14/7/2026-Vig"),
    # FB5 R6-02: two instruction facts with the same start; the longer one does not stand in for the shorter
    ("Draft an order posting Shri Anil Kumar and Shri Anil Kumar Singh to Nagpur.",
     ["Office Order", "Shri Anil Kumar Singh is posted to Nagpur."], "Shri Anil Kumar"),
    # FB1 R2-01: the token boundary stays
    ("Draft a letter to Shri Ramesh Kumar about the hearing.", ["To", "Shri Ramesh Kumari", "Subject: Hearing"],
     "Shri Ramesh Kumar"),
    ("Grant leave from 3 November 2026.", ["Leave from 13 November 2026."], "3 November 2026"),
    ("Sanction Rs. 25,000 for repairs.", ["Rs. 1,25,000 is sanctioned for repairs."], "25,000"),
])
def test_guard_a_replaced_fact_gives_fact_missing(instruction, blocks, fact):
    # OD-OD-8 (FB15): a replaced name without a title ("Anjali") gives FACT_CHECK; everything else keeps FACT_MISSING
    titled = fact.split()[0].rstrip(".") in ("Shri", "Smt", "Dr", "Ms", "Mr") or any(c.isdigit() for c in fact)
    assert ("FACT_MISSING" if titled else "FACT_CHECK", fact) in codes(instruction, blocks)


def test_fb12_service_passes_both_codes(tmp_path):
    blocks = [dict(b, text=b["text"].replace("12/3/2026-Admin", "12/3/2026-Admin-1")) for b in ORDER_BLOCKS
              if "25,000" not in b["text"]]
    v = office_with(tmp_path, FakeClient(answer(blocks=blocks))).draft_document({"instruction": INSTR})
    assert v["status"] == "propose"
    assert [(w["code"], w["text"]) for w in v["warnings"]] == [("FACT_CHECK", "12/3/2026-Admin"),
                                                              ("FACT_MISSING", "25,000")]
    check = v["warnings"][0]
    assert check["found"] == "12/3/2026-Admin-1" and "Check it is the same file." in check["message"]


def test_fb12_plan_states_the_two_signals_and_od_od_6():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Two signals (owner decision 2026-10-24, OD-OD-6, MM LDEC-014" in text
    assert "a faithful draft (one that keeps the fact word for word) never gives FACT_MISSING" in text
    assert "FACT_CHECK coverage" in text
    assert "- OD-OD-6 (decided by the owner 2026-10-24, MM LDEC-014" in text
    assert "Repairs after fallback review FB12 of 644be9b1" in text
