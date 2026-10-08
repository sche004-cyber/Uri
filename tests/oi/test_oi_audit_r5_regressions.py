"""Regression tests for the Codex audit round-5 findings (2026-10-08)."""
import pytest

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import planner as P
from uri_operational_intelligence.orchestrator import Orchestrator
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.task_ledger import LedgerError, TaskLedger
from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import SEL, FakeCore

APPROVAL = {"turn_id": "single-1", "state": "approval_required", "code": "APPROVAL_REQUIRED",
            "approval_request": {"capability_id": "remember_fact", "arguments": {"inputs": {"request_text": "a"}},
                                 "approval_digest": "0" * 64}}
CONFIRM = {"turn_id": "single-c", "state": "reply", "code": "INTENT_CONFIRMATION_REQUIRED",
           "confirmation": {"intent_id": "i-single", "revision": 1, "digest": "d"}}


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def orch(fake, tmp_path, replies):
    core = FakeCore(replies)
    return Orchestrator(client=BC.BrainClient(fake.url), core=core, brain_selection=SEL, ledger=TaskLedger(tmp_path),
                        readiness=lambda: Readiness("READY", fake.url)), core


# R5-1 (High): a plan step's payload spliced under a registered single-turn id is refused.
def test_spliced_payload_under_registered_id_refused(fake, tmp_path):
    o, core = orch(fake, tmp_path, [dict(CONFIRM)])
    single = o.handle_turn("remember that the gate code is 1234", "s").core
    spliced = {"turn_id": single["turn_id"], "state": "reply", "code": "INTENT_CONFIRMATION_REQUIRED",
               "confirmation": {"intent_id": "i-PLAN-STEP", "revision": 3, "digest": "other"}}
    with pytest.raises(LedgerError):
        o.confirm("s", spliced)
    assert [c[0] for c in core.calls] == ["begin"]


def test_tampered_approval_envelope_refused_and_single_use(fake, tmp_path):
    o, core = orch(fake, tmp_path, [dict(APPROVAL)])
    env = o.handle_turn("remember that the gate code is 1234", "s").core
    tampered = dict(env, approval_request=dict(env["approval_request"], arguments={"inputs": {"request_text": "b"}}))
    with pytest.raises(LedgerError):
        o.decide("x", "s", tampered, True)
    o.decide("x", "s", env, True)                 # the exact issued envelope works once
    with pytest.raises(LedgerError):
        o.decide("x", "s", env, True)             # and never twice
    assert [c for c in core.calls if c[0] == "decide"] == [("decide", True)]


def test_registry_is_bounded(fake, tmp_path):
    o, _ = orch(fake, tmp_path, [])
    for i in range(o.MAX_SINGLE_TURNS + 50):
        o._register_single(dict(APPROVAL, turn_id="t%d" % i))
    assert len(o._single_turns) == o.MAX_SINGLE_TURNS and "t0" not in o._single_turns


# R5-2 (High): all Unicode dash punctuation and quote marks are folded for negation and boundaries.
@pytest.mark.parametrize("text,span,expect", [
    ("Please don‛t email Ravi.", "email Ravi", "SOURCE_SPAN_NEGATED"),        # U+201B
    ("Please de―activate account 42.", "activate account", "SOURCE_SPAN_NOT_VERBATIM"),  # U+2015
    ("Please re⸺send invoice 7.", "send invoice", "SOURCE_SPAN_NOT_VERBATIM"),  # U+2E3A two-em dash (Pd)
    ("Please donʼt delete the files.", "delete the files", "SOURCE_SPAN_NEGATED"),  # modifier apostrophe
])
def test_unicode_categories_folded(text, span, expect):
    p = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "x", "kind": "action", "capability": "remember_fact", "source_span": span, "depends_on": []}]}
    s = P.validate_plan(p, text, {"remember_fact"})["plan"]["steps"][0]
    assert s["unusable_reason"] == expect
