import json
import uuid

import pytest

from uri_operational_intelligence import answer as A
from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import harness_choice as H
from uri_operational_intelligence import planner as P
from uri_operational_intelligence.reasoning_policy import FAST, NORMAL
from uri_operational_intelligence.task_ledger import LedgerError, TaskLedger
from tests.oi.fake_llama import FakeLlama


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


# ---- answer channel -------------------------------------------------------------------------------
def test_action_marker_split_across_chunks_is_never_shown(fake):
    fake.scripts.append({"chunks": [("answer", "<<AC"), ("answer", "TION>>")] + [("answer", "x")] * 50,
                         "finish": "stop", "delay": 0.01})
    shown = []
    out = A.answer(BC.BrainClient(fake.url), "jot down Ravi owes me 500", on_delta=lambda k, t: shown.append(t))
    assert out.status == "ACTION_REQUESTED" and shown == []


def test_normal_answer_is_released_and_marker_check_does_not_delay_much(fake):
    fake.scripts.append({"chunks": [("answer", "An office "), ("answer", "order is...")], "finish": "stop"})
    shown = []
    out = A.answer(BC.BrainClient(fake.url), "what is an office order", on_delta=lambda k, t: shown.append(t))
    assert out.status == "COMPLETE" and "".join(shown) == "An office order is..." and out.complete


def test_reply_that_is_a_strict_prefix_of_the_marker_is_still_delivered(fake):
    fake.scripts.append({"chunks": [("answer", "<")], "finish": "stop"})
    shown = []
    out = A.answer(BC.BrainClient(fake.url), "show a less-than sign", on_delta=lambda k, t: shown.append(t))
    assert out.status == "COMPLETE" and "".join(shown) == "<"


def test_unverified_action_claim_is_flagged_and_corrected(fake):
    fake.scripts.append({"chunks": [("answer", "Sure! I've saved your note.")], "finish": "stop"})
    out = A.answer(BC.BrainClient(fake.url), "hmm")
    assert "UNVERIFIED_ACTION_CLAIM" in out.flags and out.text.endswith(A.CLAIM_CORRECTION)
    fake.scripts.append({"chunks": [("answer", "I've saved your note.")], "finish": "stop"})
    out2 = A.answer(BC.BrainClient(fake.url), "hmm", executed_action=True)
    assert out2.flags == []


@pytest.mark.parametrize("chunks", [
    ["I have saved your new fact."],
    ["I ha", "ve sa", "ved your new fact."],
    ["Here is the date. I", " have saved your new fact."],
    ["Done", ". I have saved your new fact."],
])
def test_unverified_action_claim_is_never_streamed_or_retained(fake, chunks):
    """R1-03: no answer delta or final result may assert an action this channel never executed."""
    fake.scripts.append({"chunks": [("answer", chunk) for chunk in chunks], "finish": "stop"})
    deltas = []
    out = A.answer(BC.BrainClient(fake.url), "What day is it?", on_delta=lambda k, t: deltas.append((k, t)))
    shown = "".join(text for kind, text in deltas if kind == "answer")
    assert shown == out.text
    assert "saved your new fact" not in shown
    assert not any("saved your new fact" in text for _, text in deltas)
    assert shown.endswith(A.CLAIM_CORRECTION)
    assert "UNVERIFIED_ACTION_CLAIM" in out.flags


def test_normal_tier_request_parameters_and_length_escalation(fake):
    fake.scripts.append({"chunks": [("reasoning", "r" * 10), ("answer", "partial")], "finish": "length"})
    out = A.answer(BC.BrainClient(fake.url), "plan my week", tier=NORMAL)
    body = fake.requests[-1]
    assert body["thinking_budget_tokens"] == 768 and body["chat_template_kwargs"]["enable_thinking"] is True
    assert out.status == "INCOMPLETE_LENGTH" and out.escalation_candidate and not out.complete


def test_messages_layout_is_stable_system_first_current_turn_last():
    m = A.build_messages("now", history=[{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
                                         {"role": "tool", "content": "ignored"}])
    assert m[0] == {"role": "system", "content": A.URI_SYSTEM} and m[-1] == {"role": "user", "content": "now"}
    assert [x["role"] for x in m] == ["system", "user", "assistant", "user"]


# ---- planner validation -------------------------------------------------------------------------
TEXT = "Remember that the audit is on Monday, then email the checklist to Ravi."


def plan(**over):
    p = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "remember date", "kind": "action", "capability": "remember_fact",
         "source_span": "Remember that the audit is on Monday", "depends_on": []},
        {"id": "s2", "description": "email", "kind": "action", "capability": None,
         "source_span": "email the checklist to Ravi", "depends_on": ["s1"]}]}
    p.update(over)
    return p


def test_plan_validation_accepts_verbatim_spans():
    v = P.validate_plan(plan(), TEXT, {"remember_fact"})
    assert v["ok"] and v["downgraded"] == []
    assert v["plan"]["steps"][1]["unusable_reason"] == "NO_MATCHING_CAPABILITY"


def test_plan_validation_downgrades_model_written_spans():
    p = plan()
    p["steps"][0]["source_span"] = "Store the audit date of Monday"
    v = P.validate_plan(p, TEXT, {"remember_fact"})
    s = v["plan"]["steps"][0]
    assert v["downgraded"] == ["s1"] and s["kind"] == "ask_user" and s["source_span"] is None


def test_plan_validation_rejects_unknown_capability_and_forward_dependencies():
    p = plan()
    p["steps"][0]["capability"] = "format_disk"
    p["steps"][0]["depends_on"] = ["s2"]
    v = P.validate_plan(p, TEXT, {"remember_fact"})
    assert "UNKNOWN_CAPABILITY:s1" in v["problems"] and v["plan"]["steps"][0]["capability"] is None
    assert any(x.startswith("FORWARD_OR_UNKNOWN_DEPENDENCY:s1") for x in v["problems"])
    assert v["plan"]["steps"][0]["depends_on"] == []
    dup = plan()
    dup["steps"][1]["id"] = "s1"
    assert not P.validate_plan(dup, TEXT, {"remember_fact"})["ok"]


def test_propose_plan_uses_normal_tier_and_schema(fake):
    fake.scripts.append({"json": json.dumps(plan()), "finish": "stop"})
    v = P.propose_plan(BC.BrainClient(fake.url), TEXT, ["remember_fact"])
    body = fake.requests[-1]
    assert v["ok"] and body["response_format"]["type"] == "json_schema"
    assert body["thinking_budget_tokens"] == 768
    fake.scripts.append({"json": "{bad", "finish": "stop"})
    assert P.propose_plan(BC.BrainClient(fake.url), TEXT, ["remember_fact"])["problems"] == ["PLANNER_OUTPUT_INVALID"]
    fake.scripts.append({"json": "{", "finish": "length"})
    r = P.propose_plan(BC.BrainClient(fake.url), TEXT, ["remember_fact"])
    assert r["problems"] == ["PLANNER_INCOMPLETE_LENGTH"] and r["escalation_candidate"]


# ---- ledger ---------------------------------------------------------------------------------------
def test_ledger_transitions_and_completion(tmp_path):
    L = TaskLedger(tmp_path)
    t = L.create(session_id="s", request_text=TEXT, plan=P.validate_plan(plan(), TEXT, {"remember_fact"})["plan"])
    tid = t["task_id"]
    assert [s["step_id"] for s in L.ready_steps(L.get(tid))] == ["s1"]
    L.set_step(tid, "s1", "IN_CORE")
    L.set_step(tid, "s1", "WAITING_APPROVAL", core={"state": "approval_required"})
    with pytest.raises(LedgerError):
        L.set_step(tid, "s1", "ANSWERED")             # not a legal transition
    with pytest.raises(LedgerError):
        L.set_step(tid, "s1", "VERIFIED")             # outcomes only via EXECUTING (approval made durable first)
    L.set_step(tid, "s1", "EXECUTING")
    with pytest.raises(LedgerError):
        L.set_step(tid, "s1", "EXECUTING")            # a claim cannot be taken twice
    L.set_step(tid, "s1", "VERIFIED")
    with pytest.raises(LedgerError):
        L.set_step(tid, "s1", "PENDING")              # terminal
    assert [s["step_id"] for s in L.ready_steps(L.get(tid))] == ["s2"]
    L.set_step(tid, "s2", "SKIPPED")
    assert L.get(tid)["state"] == "COMPLETED"
    assert L.get(tid)["steps"][0]["attempts"] == 1


def test_ledger_restart_recovery_never_retries_possible_execution(tmp_path):
    L = TaskLedger(tmp_path)
    p = P.validate_plan(plan(), TEXT, {"remember_fact"})["plan"]
    a = L.create(session_id="s", request_text=TEXT, plan=p, state="RUNNING")["task_id"]
    L.set_step(a, "s1", "IN_CORE", core={"state": "executing"})
    b = L.create(session_id="s", request_text=TEXT, plan=p, state="RUNNING")["task_id"]
    L.set_step(b, "s1", "IN_CORE")
    L.set_step(b, "s1", "WAITING_APPROVAL", core={"state": "approval_required"})
    owner = TaskLedger(tmp_path)
    owner.acquire_owner()
    try:
        summary = {r["task_id"]: r["changes"] for r in owner.recover()}
    finally:
        owner.release_owner()
    assert summary[a] == [("s1", "UNCERTAIN")] and L.get(a)["state"] == "NEEDS_ATTENTION"
    assert summary[b] == [("s1", "PENDING")] and L.get(b)["state"] == "WAITING_USER_CHOICE"
    # the dependent of an uncertain step is blocked, never run on top of it
    task = L.get(a)
    assert [s["step_id"] for s in L.blocked_steps(task)] == ["s2"] and L.ready_steps(task) == []


def test_ledger_ids_are_uuids_only(tmp_path):
    L = TaskLedger(tmp_path)
    with pytest.raises(ValueError):
        L.get("../../etc/passwd")
    with pytest.raises(LedgerError):
        L.get(str(uuid.uuid4()))


# ---- harness choice ------------------------------------------------------------------------------
def st(provider, **kw):
    base = dict(qualification="QUALIFIED", auth="OK", quota="OK", offered_by_policy=True, source="test")
    base.update(kw)
    return H.HarnessStatus(provider, provider, **base)


def test_harness_choice_never_selects_without_the_user():
    c = H.choose([st("codex"), st("claude_code")])
    assert c.recommendation == "codex" and c.requires_user_choice and c.selected is None


def test_harness_choice_explicit_and_history():
    assert H.choose([st("codex"), st("claude_code")], explicit="claude_code").selected == "claude_code"
    bad = H.choose([st("codex"), st("claude_code", auth="NOT_LOGGED_IN")], explicit="claude_code")
    assert bad.selected is None and bad.requires_user_choice and bad.recommendation is None
    h = H.choose([st("codex"), st("claude_code")], task_choice_history=["claude_code"])
    assert h.recommendation == "claude_code" and h.requires_user_choice


def test_harness_choice_quota_exclusion_and_reasons():
    c = H.choose([st("codex"), st("claude_code", qualification="BLOCKED"), st("antigravity", offered_by_policy=False)],
                 exclude=("codex",))
    why = {o["provider"]: o["why_not"] for o in c.options}
    assert c.recommendation is None and why == {"codex": "EXCLUDED_QUOTA_EXHAUSTED", "claude_code": "QUALIFICATION_BLOCKED",
                                                "antigravity": "NOT_OFFERED_BY_OWNER_POLICY"}


def test_documented_status_is_labelled_and_never_offered():
    rows = H.documented_status()
    assert {r.provider for r in rows} == {"codex", "claude_code", "antigravity"}
    assert all(r.source in ("documented", "documented_missing") and not r.offered_by_policy for r in rows)
    assert H.choose(rows).recommendation is None


def test_documented_status_without_manifest_is_unknown(tmp_path):
    rows = H.documented_status(tmp_path / "missing.json")
    assert all(r.source == "documented_missing" and r.qualification == "UNKNOWN" and not r.usable() for r in rows)


@pytest.mark.parametrize("text,span,negated", [
    ("Don't email Ravi, just draft the reply.", "email Ravi", True),
    ("Do not delete the old files; archive them.", "delete the old files", True),
    ("Never send it to the principal.", "send it to the principal", True),
    ("Draft the reply instead of emailing Ravi.", "emailing Ravi", True),
    ("Draft the reply, then email Ravi.", "email Ravi", False),
    ("I don't know the date, but remember that the audit is on Monday.", "remember that the audit is on Monday", False),
])
def test_negated_spans_are_never_executable(text, span, negated):
    p = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "x", "kind": "action", "capability": "remember_fact", "source_span": span, "depends_on": []}]}
    v = P.validate_plan(p, text, {"remember_fact"})
    step = v["plan"]["steps"][0]
    assert (step["kind"] == "ask_user" and step.get("unusable_reason") == "SOURCE_SPAN_NEGATED") is negated
