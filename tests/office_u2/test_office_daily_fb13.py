"""FB13 fallback review of 01ac1695 (OFFICE-DAILY-USE-r14) and owner decision OD-OD-7 (MM LDEC-015): regression tests
for R2-01 (courtesy words before a title in the instruction), R2-02 ("&" and en dashes in references), R2-03 ("Sahab")
and R2-04 (".00" after an amount). Tests named fb13_* fail on 01ac1695 and pass after the repair; *_guard_* tests pass
on both."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"


def facts(instruction):
    return [f["text"] for f in DR.extract_facts(instruction)]


def codes(instruction, blocks):
    return [(w.get("code", "FACT_MISSING"), w["text"]) for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: the instruction's own fact is only the titled name ------------------------------------------------------
@pytest.mark.parametrize("instruction,name,blocks", [
    ("Write a letter to Hon'ble Minister Shri Mohan Lal about the meeting on 12th November 2026.", "Shri Mohan Lal",
     ["To", "Shri Mohan Lal,", "Minister of State (Finance),", "Respected Sir,", "The meeting is on 12th November 2026."]),
    ("Draft a reply to the letter received from Hon'ble MP Shri Arvind Sawant.", "Shri Arvind Sawant",
     ["Shri Arvind Sawant", "Sir, the reply is enclosed."]),
    ("Write to Collector Shri Arvind Rao about the floods.", "Shri Arvind Rao",
     ["To", "Shri Arvind Rao", "District Magistrate, Pune"]),
    ("Write a condolence letter to Late Shri Ram Prasad's family.", "Shri Ram Prasad",
     ["To", "The family of Shri Ram Prasad"]),
    ("Write a letter to Minister Smt Kamla Devi.", "Smt Kamla Devi", ["To", "Smt Kamla Devi"]),
    ("Write a letter to Joint Secretary Sushri Rekha Rao.", "Sushri Rekha Rao", ["To", "Sushri Rekha Rao"]),
    ("Write a letter to Joint Secretary Kumari Priya Nair.", "Kumari Priya Nair",
     ["To", "Kumari Priya Nair", "Joint Secretary"]),
    ("Write a letter to Minister of State Shri ramesh kumar.", "Shri ramesh kumar", ["To", "Shri ramesh kumar"]),
])
def test_fb13_r2_01_courtesy_words_in_the_instruction_are_not_facts(instruction, name, blocks):
    assert [f for f in DR.extract_facts(instruction) if f["kind"] == "name"] == [{"kind": "name", "text": name}]
    assert codes(instruction, blocks) == []


def test_fb13_r2_01_courtesy_tail_after_another_person():
    ins = "Invite Ms Anjali Verma and Hon'ble Shri Suresh Mishra on 3rd November."
    assert facts(ins) == ["Ms Anjali Verma", "Shri Suresh Mishra", "3rd November"]


def test_r2_01_guard_a_changed_name_still_warns():
    ins = "Write a letter to Hon'ble Minister Shri Mohan Lal about the meeting on 12th November 2026."
    assert codes(ins, ["To", "Hon'ble Minister Shri Sohan Lal,", "The meeting is on 12th November 2026."]) == [
        ("FACT_MISSING", "Shri Mohan Lal")]


# ---- R2-02: "&" and en dashes inside a reference ------------------------------------------------------------------------
H = ["To", "Shri Anil Verma", "Subject: Reminder"]


@pytest.mark.parametrize("instruction,ref,faithful,changed", [
    ("Send a reminder on F.No. 2(14)/2026-B&A dated 5th September 2026 to Shri Anil Verma.", "2(14)/2026-B&A",
     ["Refer F.No. 2(14)/2026-B&A dated 5th September 2026."],
     ["Refer F.No. 2(14)/2026-B&C dated 5th September 2026.", "Refer F.No. 2(14)/2026-B&AR dated 5th September 2026.",
      "Refer F.No. 2(14)/2026-B dated 5th September 2026."]),
    ("Send a reminder on F.No. 11/3/2026-P&PW to Shri Anil Verma.", "11/3/2026-P&PW",
     ["Refer F.No. 11/3/2026-P&PW."], ["Refer F.No. 11/3/2026-P&AR.", "Refer F.No. 11/3/2026-P."]),
    ("Send a reminder on No. 38/37/2016-P&PW(A) to Shri Anil Verma.", "38/37/2016-P&PW(A)",
     ["Refer No. 38/37/2016-P&PW(A)."], ["Refer No. 38/37/2016-P&PW(B).", "Refer No. 38/37/2016-P&AR(A)."]),
    ("Send a reminder on O.M. No. 17011/1/2026–Estt to Shri Anil Verma.", "17011/1/2026–Estt",
     ["Refer O.M. No. 17011/1/2026–Estt.", "Refer O.M. No. 17011/1/2026-Estt."],
     ["Refer O.M. No. 17011/1/2026–Admn.", "Refer O.M. No. 17011/1/2026–Vig."]),
])
def test_fb13_r2_02_ampersand_and_en_dash_references(instruction, ref, faithful, changed):
    assert ref in facts(instruction)
    for body in faithful:
        assert codes(instruction, H + [body]) == [], body
    for body in changed:
        assert codes(instruction, H + [body]) == [("FACT_MISSING", ref)], body


def test_fb13_r2_02_an_en_dash_suffix_is_another_file():
    ins = "Send a reminder on O.M. No. 17011/1/2026–Estt to Shri Anil Verma."
    w = DR.missing_facts(ins, "\n".join(H + ["Refer O.M. No. 17011/1/2026–Estt–1."]))
    assert [(x["code"], x["found"]) for x in w] == [("FACT_CHECK", "17011/1/2026-Estt-1")]


# ---- R2-03: Sahab ends a name ----------------------------------------------------------------------------------------------
def test_fb13_r2_03_sahab_after_the_name():
    ins = "Write a letter to Shri Rajendra Prasad Meena about the review."
    for blocks in (["To", "Shri Rajendra Prasad Meena Sahab"], ["Shri Rajendra Prasad Meena Saheb is requested."]):
        assert codes(ins, blocks) == [], blocks


# ---- R2-04 / OD-OD-7: ".00" after an amount ---------------------------------------------------------------------------------
INS_AMT = "Sanction the release of Rs. 4,75,000 for 12 vacancies by 30.11.2026."


@pytest.mark.parametrize("amount", ["4,75,000.00", "4,75,000.0", "4,75,000.00/-"])
def test_fb13_r2_04_zero_paise_is_the_same_amount(amount):
    assert codes(INS_AMT, [f"Release of Rs. {amount} for 12 vacancies by 30.11.2026."]) == []


def test_fb13_r2_04_zero_paise_in_the_instruction():
    ins = "Sanction Rs. 4,75,000.00 to Shri Anil Verma."
    assert codes(ins, ["Rs. 4,75,000 is sanctioned to Shri Anil Verma."]) == []


@pytest.mark.parametrize("amount", ["4,75,000.50", "4,75,000.05", "14,75,000.00", "4,75,500.00"])
def test_guard_non_zero_paise_or_another_amount_warns(amount):
    assert codes(INS_AMT, [f"Release of Rs. {amount} for 12 vacancies by 30.11.2026."]) == [
        ("FACT_MISSING", "4,75,000")]


def test_fb13_plan_records_od_od_7_and_the_history():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "- OD-OD-7 (decided by the owner 2026-10-24, MM LDEC-015" in text
    assert "Repairs after fallback review FB13 of 01ac1695" in text
    assert "a designation or another word after the name on the same line without a comma" in text
