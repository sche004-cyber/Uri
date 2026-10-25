"""FB11 fallback review of 2641b828 (OFFICE-DAILY-USE-r12): regression tests for R2-01..R2-03 (the reviewer's cases)
and the previous rounds' reference cases, which must still hold. Tests named fb11_* fail on 2641b828 and pass after
the repair; *_guard_* tests pass on both."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"
INS = "Prepare a reminder regarding O.M. No. 22011/5/2026-Admn to Shri Prakash Rao, Under Secretary."
T = ["To", "Shri Prakash Rao", "Under Secretary", "Subject: Reminder"]


def miss(instruction, blocks):
    return [w["text"] for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: trailing words and ordinary brackets are not another file ------------------------------------------------
@pytest.mark.parametrize("body", [
    "Kindly refer to this office O.M. No. 22011/5/2026-Admn-dtd. 4.9.2026.",
    "Kindly refer to O.M. No. 22011/5/2026-Admn-wef 1.10.2026.",
    "Subject: O.M. No. 22011/5/2026-Admn-reminder.",
    "Kindly refer to O.M.No.22011/5/2026-Admn.-dated 4.9.2026.",
    "Kindly refer to O.M. No. 22011/5/2026-Admn./dated 4.9.2026.",
    "Kindly refer to O.M. No. 22011/5/2026-Admn(copy) enclosed.",
    "Kindly refer to O.M. No. 22011/5/2026-Admn(PDF).",
    "Kindly refer to Letter-22011/5/2026-Admn.",
])
def test_fb11_r2_01_faithful_reference_forms_give_no_warning(body):
    assert miss(INS, T + [body]) == []


@pytest.mark.parametrize("body", [
    "Kindly refer to O.M. No. 22011/5/2026-Admn-1.", "Kindly refer to O.M. No. 22011/5/2026-Admn-II.",
    "Kindly refer to O.M. No. 22011/5/2026-Admn-Estt.", "Kindly refer to O.M. No. 22011/5/2026-Admn(1).",
    "Kindly refer to O.M. No. 22011/5/2026-Admn(Pt.).", "Kindly refer to O.M. No. A-22011/5/2026-Admn.",
])
def test_guard_code_suffixes_and_prefixes_still_warn(body):
    assert "22011/5/2026-Admn" in miss(INS, T + [body])


@pytest.mark.parametrize("body", [
    "Ref No-22011/5/2026-Admn", "F.No-22011/5/2026-Admn", "Your letter No.22011/5/2026-Admn-dated 3.10.2026.",
    "Subject: Letter No. 22011/5/2026-Admn-reg.", "No. 22011/5/2026-Admn(2 pages)",
])
def test_guard_fb10_faithful_forms_still_give_no_warning(body):
    assert miss(INS, T + [body]) == []


# ---- R2-03: part-file markers longer than four characters ---------------------------------------------------------------
@pytest.mark.parametrize("body", [
    "Ref: No. 22011/5/2026-Admn(Pt.II)", "Ref: No. 22011/5/2026-Admn(Part-I)",
    "Ref: No. 22011/5/2026-Admn(Part II)", "Ref: No. 22011/5/2026-Admn(Vol.2)",
])
def test_fb11_r2_03_part_file_brackets_warn(body):
    assert "22011/5/2026-Admn" in miss(INS, T + [body])


# ---- R2-02: a lowercase titled name at a block end, with a surname ending in -ed / -ing ---------------------------------
@pytest.mark.parametrize("instruction,blocks,name", [
    ("Put up a note on Shri mohammad.", ["To", "Shri mohammad ahmed", "Subject: Leave"], "Shri mohammad"),
    ("Put up a note on Shri ramesh kumar.", ["To", "Shri ramesh kumar harding", "Subject: Leave"],
     "Shri ramesh kumar"),
])
def test_fb11_r2_02_ed_ing_surname_at_a_block_end_warns(instruction, blocks, name):
    assert name in miss(instruction, blocks)


def test_guard_fb10_verb_after_a_lowercase_titled_name_gives_no_warning():
    assert miss("Draft a note on Shri ramesh kumar.", ["Note", "Shri ramesh kumar reported for duty on Monday."]) == []


def test_fb11_plan_records_fb11():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB11" in text
