"""End to end through the REAL Phase 1 paired server: text -> deterministic proposer -> intent discovery ->
digest-bound confirmation -> approval -> signed ticket -> claim -> SupervisorBridge -> uri_supervisor -> fake
executor -> receipt -> server settle. Only the executor is SYNTHETIC."""
import json
from pathlib import Path

import pytest

from phase2b.conftest import CLAUDE, CODEX, uid
from uri_core.client_runtime.turn_runner import TurnError

TEXT = "use the harness to write a greeting into out.txt"


def ledger_task(stack, turn_id):
    op = stack.turn_record(turn_id)["operation_id"]
    return stack.L.task(op), op


def test_full_chain_verified_once_with_supervisor_evidence(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    final = s.run()
    assert final["code"] == "SETTLED_VERIFIED", final
    t, op = ledger_task(s, final["turn_id"])
    assert t is not None and t["state"] == "COMPLETE" and t["principal"] == s.cm.data["principal_id"]
    req = json.loads(t["request_json"])
    assert req["operation_id"] == op and req["turn_id"] == final["turn_id"] and req["provider"] == "claude_code"
    rec = s.turn_record(final["turn_id"])
    assert rec["state"] == "reply" and rec["execution_outcome"] == "verified" and rec["dispatched"] is True
    assert len(s.result_files()) == 1 and s.result_files()[0].read_text().startswith("hello from fake harness")
    paths = [p for _, p in s.calls]
    assert paths.index(f"/client/v1/turns/{final['turn_id']}/approval") < paths.index(f"/client/v1/turns/{final['turn_id']}/claim") \
        < paths.index(f"/client/v1/turns/{final['turn_id']}/settle")
    # the ledger's authorization is the ticket's authority, not something the supervisor invented
    auth = json.loads(s.L.q1("SELECT scope_json FROM authorization WHERE task_id=?", (op,))[0])
    assert auth["approval_digest"] == req["approval_digest"] and auth["allowed_executors"] == ["claude_code"]


def test_declined_approval_reaches_neither_supervisor_nor_executor(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    final = s.run(approve=lambda req: False)
    assert final["code"] == "APPROVAL_DENIED"
    assert s.L.q1("SELECT COUNT(*) FROM task")[0] == 0 and s.result_files() == []


def test_unconfirmed_text_never_reaches_the_supervisor(bridge_stack, monkeypatch):
    """Plain text while a confirmation is outstanding changes nothing; only the structured, digest-bound decision does."""
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    first = s.runner.begin("use the harness to write a greeting", session, CLAUDE)      # no file name: clarification
    assert first["code"] in ("INTENT_CLARIFICATION", "CLARIFICATION_REQUIRED") or first.get("clarification"), first
    assert s.L.q1("SELECT COUNT(*) FROM task")[0] == 0
    second = s.runner.begin("yes do it", session, CLAUDE)                               # typed text is not confirmation
    assert second["state"] != "approval_required" and s.L.q1("SELECT COUNT(*) FROM task")[0] == 0


def test_false_claim_is_retried_once_under_same_authority_then_uncertain_for_the_user(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "false_claim")
    final = s.run()
    assert final["code"] == "SETTLED_EXECUTION_UNCERTAIN", final      # dispatched + failed => uncertain (Phase 1 rule)
    t, op = ledger_task(s, final["turn_id"])
    assert t["state"] == "FAILED" and s.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (op,))[0] == 2
    assert len({r[0] for r in s.L.q("SELECT auth_id FROM admission WHERE task_id=?", (op,))}) == 1
    assert s.result_files() == []
    rec = s.turn_record(final["turn_id"])
    assert rec["state"] == "execution_uncertain" and not rec.get("execution_closed")


@pytest.mark.parametrize("scenario", ["empty_output", "wrong_file", "partial_then_die", "done_ok_exit3", "success_shaped_string"])
def test_misleading_executor_outcomes_are_never_verified(bridge_stack, monkeypatch, scenario):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
    final = s.run()
    assert final["code"] in ("SETTLED_EXECUTION_UNCERTAIN",), (scenario, final)
    t, op = ledger_task(s, final["turn_id"])
    assert t["state"] != "COMPLETE" and s.result_files() == []


def test_quota_pause_preserves_task_and_only_an_explicit_other_provider_continues(bridge_stack, monkeypatch):
    s = bridge_stack
    session = uid()
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    paused = s.run(session=session)
    assert paused["code"] == "WAITING_FOR_MODEL", paused
    t, op = ledger_task(s, paused["turn_id"])
    assert t["state"] == "FAILED" and s.L.q1("SELECT reason_code FROM recovery_decision WHERE task_id=?", (op,))[0] == "PROVIDER_QUOTA_EXHAUSTED"
    assert len(list((s.client_root / "control/checkpoints").glob("*.json"))) == 1 and s.result_files() == []
    with pytest.raises(TurnError, match="SAME_PROVIDER"):
        s.runner.continue_waiting(session, paused["turn_id"], CLAUDE, lambda req: True)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    approvals = []
    final = s.runner.continue_waiting(session, paused["turn_id"], CODEX, lambda req: approvals.append(1) or True)
    assert final["code"] == "SETTLED_VERIFIED" and approvals == [1]
    assert len(s.result_files()) == 1 and s.L.q1("SELECT COUNT(*) FROM task")[0] == 2    # two tickets, two tasks, one effect


def test_quota_after_activity_is_uncertain_not_a_pause(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota_after_write")
    final = s.run()
    assert final["code"] == "SETTLED_EXECUTION_UNCERTAIN", final
    assert not list((s.client_root / "control/checkpoints").glob("*.json")) and s.result_files() == []


def test_executor_substitution_is_refused_before_any_task_exists(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    s.bridge.executors.pop("codex_cli")                       # user explicitly selects codex; supervisor cannot run it
    final = s.run(reasoning=CODEX)
    assert final["code"] == "SETTLED_FAILED" and s.L.q1("SELECT COUNT(*) FROM task")[0] == 0 and s.result_files() == []
    s.runner.harness.qualified.pop("claude_code")             # Phase 1 says claude is not usable: no fallback to codex
    final = s.run(reasoning=CLAUDE)
    assert final["code"] == "SETTLED_FAILED" and s.L.q1("SELECT COUNT(*) FROM task")[0] == 0


def test_verified_intent_cannot_be_replayed_into_a_second_execution(bridge_stack, monkeypatch):
    """Phase 1 guard reused: an older client state replaying the verified intent is refused by the server; the
    supervisor sees nothing."""
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    first = s.runner.begin(TEXT, session, CLAUDE)
    assert first["state"] == "approval_required"
    stale = s.persistence.snapshot(session, [__import__("uri_core.client_contracts", fromlist=["ReadQuery"]).ReadQuery(
        store="sessions", method="get_session", args=[session])])
    final = s.runner.decide(TEXT, session, CLAUDE, first, True)
    assert final["code"] == "SETTLED_VERIFIED"
    tasks_before = s.L.q1("SELECT COUNT(*) FROM task")[0]
    # replay: a confirm decision carrying the old intent digest after the intent already executed
    conf = first.get("intent") or {}
    if conf.get("digest"):
        replay = s.runner.begin("Confirm", session, CLAUDE, {"intent_id": conf["intent_id"], "revision": conf["revision"],
                                                             "decision": "confirm", "digest": conf["digest"]})
        assert replay["state"] != "approval_required", replay
    assert s.L.q1("SELECT COUNT(*) FROM task")[0] == tasks_before and len(s.result_files()) == 1


def test_bridge_does_not_touch_core_intent_or_session_state(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    first = s.runner.begin(TEXT, session, CLAUDE)
    assert first["state"] == "approval_required"
    intent_before = json.dumps(first.get("intent"), sort_keys=True)
    update_before = json.dumps(first.get("session_update"), sort_keys=True)
    final = s.runner.decide(TEXT, session, CLAUDE, first, True)
    assert final["code"] == "SETTLED_VERIFIED"
    assert json.dumps(first.get("intent"), sort_keys=True) == intent_before
    assert json.dumps(first.get("session_update"), sort_keys=True) == update_before
    # the server's settle supplied the post-execution session; the bridge wrote no session or intent anywhere
    hist = s.persistence.snapshot(session, [__import__("uri_core.client_contracts", fromlist=["ReadQuery"]).ReadQuery(
        store="history", method="get_session", args=[session])]).reads[0].result
    assert hist and hist[-1]["status"] == "reply"


def test_server_restart_generation_change_refuses_old_ticket_at_the_bridge(bridge_stack, monkeypatch):
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    first = s.runner.begin(TEXT, session, CLAUDE)
    assert first["state"] == "approval_required"
    s.runner.generation = uid()           # the client learned a new server generation (restart) before executing
    with pytest.raises(Exception):
        s.runner.decide(TEXT, session, CLAUDE, first, True)
    assert s.L.q1("SELECT COUNT(*) FROM task")[0] == 0 and s.result_files() == []
