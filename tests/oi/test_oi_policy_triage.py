import pytest

from uri_operational_intelligence import reasoning_policy as RP
from uri_operational_intelligence import triage as T

CASES = [
    ("hi", T.TRIVIAL), ("Thanks URI!", T.TRIVIAL), ("good morning", T.TRIVIAL), ("how are you today?", T.TRIVIAL),
    ("What is an office order?", T.QUESTION), ("Explain the difference between RAM and VRAM.", T.QUESTION),
    ("Draft a short leave application for two days.", T.QUESTION), ("Write a haiku about rain.", T.QUESTION),
    ("How do I remember names better?", T.QUESTION), ("Is it safe to delete temp files on Windows?", T.QUESTION),
    ("Compare SSD and HDD for a school office and recommend one.", T.ANALYSIS),
    ("Why does my laptop slow down after an hour? Diagnose likely causes.", T.ANALYSIS),
    ("What are the pros and cons of moving our timetable to Google Sheets?", T.ANALYSIS),
    ("remember that my favourite colour is teal", T.ACTION), ("Please remember that the VC meeting moved to Thursday.", T.ACTION),
    ("Delete all the files on my desktop", T.ACTION), ("Send an email to Meena about the exam", T.ACTION),
    ("Can you save this note to my documents?", T.ACTION), ("forget my old phone number", T.ACTION),
    ("Draft a leave letter and save it to my desktop as leave.docx", T.ACTION),
    ("Refactor the Flutter settings screens across 14 files and run the tests.", T.HARNESS),
    ("Fix the failing unit tests in the repo", T.HARNESS),
    ("Search my mail for the fee circular, then draft a reply and send it to the principal.", T.MULTI_STEP),
    ("1. remember that the audit is on Monday\n2. create a checklist file\n3. email it to Ravi", T.MULTI_STEP),
    ("Do a deep research literature review of all the papers on MoE routing", T.ESCALATE),
]


@pytest.mark.parametrize("text,kind", CASES)
def test_triage_labels(text, kind):
    assert T.triage(text).kind == kind


def test_policy_rules():
    assert RP.decide(T.TRIVIAL).tier == RP.FAST
    assert RP.decide(T.QUESTION).tier == RP.FAST
    assert RP.decide(T.ANALYSIS).tier == RP.NORMAL
    assert RP.decide(T.MULTI_STEP).tier == RP.NORMAL
    a = RP.decide(T.ACTION, "normal")
    assert a.tier == RP.FAST and a.selected_by == "core_seam"        # rule 1 beats the user depth for Core seams
    assert RP.decide(T.QUESTION, "normal").tier == RP.NORMAL and RP.decide(T.QUESTION, "normal").selected_by == "user"
    assert RP.decide(T.ANALYSIS, "fast").tier == RP.FAST
    d = RP.decide(T.QUESTION, "deep")
    assert d.tier == RP.ESCALATE and d.escalation_offer
    assert RP.decide(T.ESCALATE).escalation_offer
    with pytest.raises(ValueError):
        RP.decide(T.QUESTION, "unbounded")


def test_tier_params_are_server_side_and_bounded():
    f = RP.tier_params(RP.FAST)
    assert f["chat_template_kwargs"] == {"enable_thinking": False} and f["temperature"] == 0.0
    assert RP.tier_params(RP.FAST, use="seam", max_tokens=500)["max_tokens"] == 500
    assert RP.tier_params(RP.FAST, max_tokens=10**6)["max_tokens"] == 4000
    n = RP.tier_params(RP.NORMAL)
    assert n["thinking_budget_tokens"] == 768 and n["max_tokens"] >= 4000
    assert n["chat_template_kwargs"] == {"enable_thinking": True}
    with pytest.raises(ValueError):
        RP.tier_params(RP.ESCALATE)


def test_normal_length_becomes_escalation_candidate_never_local_retry():
    assert RP.after_result(RP.NORMAL, "INCOMPLETE_LENGTH") == {"complete": False, "escalation_candidate": True,
                                                              "reason": "normal_budget_exhausted"}
    assert RP.after_result(RP.FAST, "INCOMPLETE_LENGTH")["escalation_candidate"] is False
    assert RP.after_result(RP.FAST, "COMPLETE")["complete"] is True
    assert RP.after_result(RP.FAST, "CANCELLED")["complete"] is False
