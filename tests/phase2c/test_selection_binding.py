"""D-C1 (Phase 2C): the executor selection the approval was requested under is bound to the turn.

The frozen Phase 1 ticket binds turn/operation/capability/arguments/confirmed intent, not the reasoning selection
(provider, model). Found while qualifying the real path: a caller could begin a turn (approval shown for provider A)
and decide it under provider B; the bridge would then run B under A's approval. SupervisedTurnRunner now records
the selection digest at `begin` and refuses a different one at `_run_harness`, before any registry or executor
check. Through the REAL paired server, SYNTHETIC executor.
"""
import json

from phase2b.conftest import CLAUDE, CODEX, uid

TEXT = "use the harness to write a greeting into out.txt"


def test_same_selection_at_begin_and_decide_still_verifies(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    final = s.run(reasoning=CODEX)
    assert final["code"] == "SETTLED_VERIFIED", final
    assert s.runner._selection == {}                      # consumed: one binding, one run


def test_provider_swapped_between_begin_and_decide_is_refused_before_any_executor(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = s.runner.begin(TEXT, session, CLAUDE)
    assert turn["state"] == "approval_required"
    final = s.runner.decide(TEXT, session, CODEX, turn, True)          # user approved CLAUDE's run, caller runs CODEX
    assert final["code"] == "SETTLED_FAILED", final
    rec = s.turn_record(final["turn_id"])
    assert rec["execution_outcome"] == "failed" and rec["execution_closed"] is True
    settle = [p for _, p in s.calls if p.endswith("/settle")]
    assert settle, "the turn must be settled"
    assert s.L.q1("SELECT COUNT(*) FROM task")[0] == 0 and s.result_files() == []


def test_model_swapped_between_begin_and_decide_is_refused(bridge_stack, monkeypatch):
    """Same provider, different model: the policy row (codex_cli, None) exists, so only the binding catches it."""
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = s.runner.begin(TEXT, session, CODEX)
    assert turn["state"] == "approval_required"
    final = s.runner.decide(TEXT, session, {**CODEX, "model": "other-model"}, turn, True)
    assert final["code"] == "SETTLED_FAILED", final
    assert s.L.q1("SELECT COUNT(*) FROM task")[0] == 0


def test_refusal_code_names_the_selection_mismatch_and_is_not_started(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = s.runner.begin(TEXT, session, CLAUDE)
    seen = {}
    real = s.runner._run_harness

    def spy(sess, request, reasoning):
        seen["r"] = real(sess, request, reasoning)
        return seen["r"]
    s.runner._run_harness = spy
    s.runner.decide(TEXT, session, CODEX, turn, True)
    assert seen["r"] == ("failed", [], "NOT_STARTED:AUTHORITY_SELECTION_MISMATCH")


def test_a_turn_never_begun_by_this_runner_cannot_be_executed(bridge_stack, monkeypatch):
    """A second runner (same client) that did not show the approval holds no binding for the turn: refused."""
    from uri_supervisor_bridge.runner import SupervisedTurnRunner
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = s.runner.begin(TEXT, session, CLAUDE)
    other = SupervisedTurnRunner(s.cm, s.persistence, s.call, s.runner.server_public_key, s.runner.generation, s.bridge,
                                 harness=s.runner.harness)
    final = other.decide(TEXT, session, CLAUDE, turn, True)
    assert final["code"] == "SETTLED_FAILED" and s.L.q1("SELECT COUNT(*) FROM task")[0] == 0


def test_quota_continuation_binds_the_new_selection(bridge_stack, monkeypatch):
    """continue_waiting starts a fresh turn under the newly chosen provider: that selection is bound and runs."""
    s = bridge_stack
    session = uid()
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    paused = s.run(session=session)
    assert paused["code"] == "WAITING_FOR_MODEL", paused
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    final = s.runner.continue_waiting(session, paused["turn_id"], CODEX, lambda req: True)
    assert final["code"] == "SETTLED_VERIFIED"
    req = json.loads(s.L.q1("SELECT request_json FROM task WHERE state='COMPLETE'")[0])
    assert req["provider"] == "codex_cli"
