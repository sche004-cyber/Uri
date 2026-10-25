"""FB10 fallback review of 264e3036 (OFFICE-DAILY-USE-r11): regression tests for R2-01..R2-03 (the reviewer's cases),
plus the previous round's (FB9) cases, which must still hold. Tests named fb10_* fail on 264e3036 and pass after the
repair; *_guard_* tests pass on both. R2-04 / R2-05 are documented in plan 16 (OD-OD-5), not caught."""
from __future__ import annotations

from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

PLAN = Path(__file__).resolve().parents[2] / "docs/office/unified/16_OFFICE_DAILY_USE_AND_WRITING_INTELLIGENCE_PLAN.md"
INS = "Write a reminder about No. 14/2/2026-Estt to Shri Anil Verma."


def miss(instruction, blocks):
    return [w["text"] for w in DR.missing_facts(instruction, "\n".join(blocks))]


# ---- R2-01: designators joined by a hyphen, trailing words and long brackets ------------------------------------------
@pytest.mark.parametrize("ref_block", [
    "Ref No-14/2/2026-Estt", "F.No-14/2/2026-Estt", "Ref-14/2/2026-Estt", "O.M.No-14/2/2026-Estt",
    "D.O.No-14/2/2026-Estt", "Your letter No.14/2/2026-Estt-dated 3.10.2026 refers.",
    "Subject: Letter No. 14/2/2026-Estt-reg.", "No. 14/2/2026-Estt(2 pages)",
])
def test_fb10_r2_01_faithful_reference_forms_give_no_warning(ref_block):
    assert miss(INS, [ref_block, "To", "Shri Anil Verma"]) == []


@pytest.mark.parametrize("ref_block", [
    "No. 14/2/2026-Estt-1", "No. 14/2/2026-Estt-II", "No. 14/2/2026-Estt(1)", "No. 14/2/2026-Estt(Pt.)",
    "No. 14/2/2026-Estt-Admn", "No. A-14/2/2026-Estt",
])
def test_guard_fb9_reference_extensions_still_warn(ref_block):
    assert "14/2/2026-Estt" in miss(INS, [ref_block, "To", "Shri Anil Verma"])


# ---- R2-02: "Ji" inside a name ------------------------------------------------------------------------------------------
def test_fb10_r2_02_ram_ji_lal_is_one_name():
    ins = "Draft a letter to Shri Ram Ji Lal about his pension."
    assert [f["text"] for f in DR.extract_facts(ins)] == ["Shri Ram Ji Lal"]
    assert "Shri Ram Ji Lal" in miss(ins, ["To", "Shri Ram Ji Gupta", "Subject: Pension"])
    assert "Shri Ram Ji Lal" in miss(ins, ["To", "Shri Ram", "Subject: Pension"])
    assert miss(ins, ["To", "Shri Ram Ji Lal", "Subject: Pension"]) == []


@pytest.mark.parametrize("instruction,blocks", [
    ("Draft a letter to Shri Ramesh about his leave.", ["Respected Shri Ramesh Ji,", "Your leave is sanctioned."]),
    ("Draft a letter to Shri Ramesh Kumar about the hearing.", ["To", "Shri Ramesh Kumar IAS", "Subject: Hearing"]),
])
def test_guard_ji_and_post_nominals_at_the_end_still_end_the_name(instruction, blocks):
    assert miss(instruction, blocks) == []


# ---- R2-03: a lowercase titled name followed by a verb in a sentence ----------------------------------------------------
@pytest.mark.parametrize("body", [
    "Shri ramesh kumar reported for duty on Monday.",
    "Shri ramesh kumar joined the office today.",
    "Shri ramesh kumar applied for leave.",
])
def test_fb10_r2_03_lowercase_titled_name_followed_by_a_verb_gives_no_warning(body):
    assert miss("Draft a note on Shri ramesh kumar.", ["Note", body]) == []


@pytest.mark.parametrize("blocks", [
    ["To", "Shri ramesh kumar sharma", "Subject: Pension"],
    ["Subject: Pension of Shri ramesh kumar sharma", "Sir,", "Shri suresh kumar is informed."],
    ["Note", "Shri suresh kumar reported for duty on Monday."],
])
def test_guard_fb9_lowercase_extensions_and_changes_still_warn(blocks):
    assert "Shri ramesh kumar" in miss("Draft a note on Shri ramesh kumar.", blocks)


# ---- the FB9 middle-name rule still holds, and a salutation is not a name word ------------------------------------------
def test_guard_fb9_kumari_middle_name_still_warns():
    assert "Smt. Sunita" in miss("Draft a letter to Smt. Sunita about her leave.",
                                 ["To", "Smt. Sunita Kumari Singh", "Subject: Leave"])


def test_fb10_plan_records_fb10():
    text = " ".join(PLAN.read_text(encoding="utf-8").split())
    assert "Repairs after fallback review FB10" in text
    assert "Estt.I" in text and "en dash" in text and "after a post-nominal or a heading word" in text
