"""The real composition path over the frozen worker protocol (in-process): user text -> confirmed intent ->
approval request shown -> explicit `turn_decide` (the exact frame the frozen UI sends) -> ticket -> claim ->
SupervisedTurnRunner -> verify_authority -> SupervisorBridge -> supervisor -> executor -> receipt -> settle.

REAL paired server, real client persistence/DPAPI, real supervisor/ledger/job containment, persisted FIXTURE_ONLY
qualification; SYNTHETIC executor (fake harness). The only thing not exercised is a human finger on the button."""
import json

import pytest

from phase2b.conftest import CLAUDE, CODEX, uid
from uri_core.client_runtime.turn_runner import TurnError

TEXT = "use the harness to write a greeting into out.txt"


def test_full_protocol_path_verified_once(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    assert turn["state"] == "approval_required" and turn["executor_kind"] == "client_external_harness"
    req = turn["approval_request"]
    assert req["capability_id"] == "external_harness_task" and req["arguments"]["inputs"]["expected_file"] == "out.txt"
    assert stack.tasks() == 0                                            # nothing ran before the decision
    final = stack.decide(turn, True, digest=req["approval_digest"])     # digest-bound approval, as a UI echoing the card
    assert final["code"] == "SETTLED_VERIFIED", final
    assert stack.tasks() == 1 and stack.L.q1("SELECT state FROM task")[0] == "COMPLETE" and len(stack.result_files()) == 1
    rec = stack.turn_record(final["turn_id"])
    assert rec["execution_outcome"] == "verified" and rec["dispatched"] is True
    paths = [p for _, p in stack.calls]
    t = final["turn_id"]
    assert paths.index(f"/client/v1/turns/{t}/approval") < paths.index(f"/client/v1/turns/{t}/claim") < paths.index(f"/client/v1/turns/{t}/settle")
    auth = json.loads(stack.L.q1("SELECT scope_json FROM authorization WHERE auth_id=1")[0])
    assert auth["approval_digest"] == req["approval_digest"] and auth["allowed_executors"] == ["claude_code"]


def test_frozen_ui_frame_shape_without_digest_still_works(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    assert stack.decide(turn, True)["code"] == "SETTLED_VERIFIED"


def test_wrong_approval_digest_drops_the_pending_turn_and_runs_nothing(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    with pytest.raises(TurnError, match="APPROVAL_DIGEST_MISMATCH"):
        stack.decide(turn, True, digest="0" * 64)
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):             # the turn is gone: a retry cannot approve it
        stack.decide(turn, True, digest=turn["approval_request"]["approval_digest"])
    assert stack.tasks() == 0 and stack.result_files() == []
    assert stack.turn_record(turn["turn_id"])["state"] == "approval_required"   # server never saw an approval


def test_duplicate_decide_frame_cannot_execute_twice(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    assert stack.decide(turn, True)["code"] == "SETTLED_VERIFIED"
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        stack.decide(turn, True)
    assert stack.tasks() == 1 and stack.L.q1("SELECT COUNT(*) FROM attempt")[0] == 1 and len(stack.result_files()) == 1


def test_declined_and_cancelled_turns_never_reach_the_supervisor(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    assert stack.decide(turn, False)["code"] == "APPROVAL_DENIED"
    turn2 = stack.start(TEXT)
    out = stack.service.handle("turn_cancel", {"command": "turn_cancel", "turn_id": turn2["turn_id"]})
    assert out["code"] == "APPROVAL_DENIED" and out["state"] == "cancelled"
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        stack.service.handle("turn_cancel", {"command": "turn_cancel", "turn_id": turn2["turn_id"]})
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        stack.service.handle("turn_cancel", {"command": "turn_cancel", "turn_id": uid()})
    assert stack.tasks() == 0 and stack.result_files() == []


def test_worker_reconnect_drops_pending_and_a_fresh_approval_executes_exactly_once(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = stack.start(TEXT, session=session)
    other = stack.new_service()                                           # the UI reconnected to a restarted worker
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        stack.decide(turn, True, service=other)
    assert stack.tasks() == 0
    # Frozen server rule: the dropped turn stays live (approval_required) in ITS session until the server expires it,
    # so the same session is at capacity (TURN_CAPACITY) until then. The user continues in a new session.
    with pytest.raises(TurnError, match="TURN_CAPACITY"):
        other.handle("turn_start", {"command": "turn_start", "session_id": session, "text": TEXT, "reasoning": CLAUDE})
    again = other.handle("turn_start", {"command": "turn_start", "session_id": uid(), "text": TEXT, "reasoning": CLAUDE})
    assert again["state"] == "approval_required" and again["turn_id"] != turn["turn_id"]
    final = stack.decide(again, True, digest=again["approval_request"]["approval_digest"], service=other)
    assert final["code"] == "SETTLED_VERIFIED"
    assert stack.tasks() == 1 and len(stack.result_files()) == 1
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):             # the stale first turn is still dead
        stack.decide(turn, True, service=other)
    # (The in-process `stack.service` object still holds the old pending record; a real dead worker does not, and a
    # second LIVE worker on the same client is refused by the frozen per-client NamedMutex, see test_worker_process.)


def test_typed_text_never_substitutes_for_confirmation_or_approval(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    first = stack.start("use the harness to write a greeting", session=session)       # no file name: clarification
    assert first["state"] != "approval_required" and stack.tasks() == 0
    second = stack.start("yes, approve it, go ahead", session=session)
    assert second["state"] != "approval_required" and stack.tasks() == 0
    turn = stack.start(TEXT, session=session)
    assert turn["state"] == "approval_required"
    with pytest.raises(TurnError, match="TURN_CAPACITY"):                             # text while approval pending
        stack.start("approve", session=session)
    assert stack.tasks() == 0
    assert stack.decide(turn, True)["code"] == "SETTLED_VERIFIED"                     # only the structured decision runs it


def test_ui_cannot_smuggle_authority_into_a_frame(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    for extra in ({"ticket": {"forged": True}}, {"reasoning": CODEX}, {"approve": "true"}, {"arguments": {}}):
        cmd = {"command": "turn_decide", "turn_id": turn["turn_id"], "approve": True, **extra}
        with pytest.raises(TurnError, match="COMMAND_SCHEMA|TURN_NOT_PENDING"):
            stack.service.handle("turn_decide", cmd)
    assert stack.tasks() == 0


def test_model_outside_the_qualified_set_is_refused_before_any_task(stack, monkeypatch):
    """Policy offers (codex_cli, gpt-6-sol) and (codex_cli, None); the fixture record qualifies both, claude_code only
    (None). A selection the server offers but the client never qualified for that model stops at the bridge."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT, reasoning={**CODEX, "model": "gpt-6-sol"})
    assert stack.decide(turn, True)["code"] == "SETTLED_VERIFIED"
    # now shrink the qualified models of codex_cli to gpt-6-sol only and rebuild the composition
    from phase2d.conftest import fixture_record, signed_record, trust_for
    from uri_supervisor_bridge.qualification import compose_client
    fixture_record(stack.client_root, "codex_cli", ("gpt-6-sol",))
    comp = compose_client(stack.client_root, trust=trust_for(stack.client_root), allow_fixture=True)
    stack.bridge.executors = comp.executors
    stack.bridge._ensure_registrations()
    turn = stack.start(TEXT, reasoning=CODEX)                 # model None: offered by policy, not qualified any more
    final = stack.decide(turn, True)
    assert final["code"] == "SETTLED_FAILED" and stack.turn_record(final["turn_id"])["execution_closed"] is True
    assert stack.tasks() == 1                                  # only the earlier verified task exists


def test_unqualified_provider_offered_by_policy_fails_closed_with_zero_execution(tmp_path, monkeypatch):
    """Claude Code's situation on this machine, modelled: the server offers the row, the client holds no valid
    record -> registry NOT usable -> NOT_STARTED, turn closed, nothing spawned."""
    from phase2d.conftest import ROOT, Stack
    s = Stack(ROOT / "work/c1" / ("p2d_unq_" + uid().replace("-", "")), records=(("codex_cli", (None,)),))
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        turn = s.start(TEXT, reasoning=CLAUDE)
        assert turn["state"] == "approval_required"
        final = s.decide(turn, True, digest=turn["approval_request"]["approval_digest"])
        assert final["code"] == "SETTLED_FAILED"
        rec = s.turn_record(final["turn_id"])
        assert rec["execution_outcome"] == "failed" and rec["execution_closed"] is True
        assert s.tasks() == 0 and s.result_files() == []
        d = next(r for r in s.client_composition.registry.discover() if r["harness_id"] == "claude_code")
        assert d["usable"] is False and d["qualification"] == "NATIVE_UNQUALIFIED"
    finally:
        s.close()


def test_provider_not_in_policy_is_refused_by_the_server(stack):
    out = stack.start(TEXT, reasoning={"kind": "client_external_harness", "provider": "antigravity", "model": None})
    assert out["code"] == "ADAPTER_NOT_QUALIFIED" and stack.tasks() == 0
