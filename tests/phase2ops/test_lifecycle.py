"""Execution lifecycle over the worker protocol: proposal-bound approval, non-blocking begin, authoritative status
(record + ledger + journal + server turn), terminal states that never invent success, replay and smuggling refusals."""
import pytest

from phase2b.conftest import CLAUDE, CODEX, uid
from phase2ops.conftest import TEXT, begin, cancel, listing, status, wait_running, wait_terminal
from uri_core.client_contracts import digest
from uri_core.client_runtime.turn_runner import TurnError
from uri_supervisor_bridge.execution import AUTHORITY_FIELDS, TERMINAL_STATES, execution_proposal


def test_approval_surface_carries_the_full_proposal(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = stack.start(TEXT, session=session, reasoning={**CODEX, "model": "gpt-6-sol"})
    assert turn["state"] == "approval_required"
    p, req = turn["execution_proposal"], turn["approval_request"]
    assert p["provider"] == "codex_cli" and p["model"] == "gpt-6-sol" and p["kind"] == "client_external_harness"
    assert p["session_id"] == session and p["turn_id"] == turn["turn_id"] and p["client_id"] == stack.cm.data["client_id"]
    assert p["capability_id"] == "external_harness_task" and p["approval_digest"] == req["approval_digest"]
    assert p["argument_digest"] == req["argument_digest"] and p["arguments"] == req["arguments"]
    assert p["expected_file"] == "out.txt" and "greeting" in p["instruction"] and p["effect"] == "local_write"
    assert p["qualification"]["level"] == "FIXTURE_ONLY" and p["qualification"]["status"] == "QUALIFIED"
    assert p["proposal_digest"] == digest({k: p[k] for k in AUTHORITY_FIELDS})
    assert "ticket" not in p and "signature" not in p and "token" not in str(p).lower()


def test_begin_returns_at_once_and_settles_to_completed_with_receipt(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "slow_honest")
    monkeypatch.setenv("URI_FAKE_SLEEP", "1.5")
    turn = stack.start(TEXT)
    out = begin(stack, turn)
    assert out["state"] == "queued" and out["turn_id"] == turn["turn_id"] and len(out["execution_id"]) == 32
    eid = out["execution_id"]
    first = status(stack, eid)
    assert first["state"] in ("queued", "approving", "starting", "running")      # the frame loop answered mid-run
    final = wait_terminal(stack, eid)
    assert final["state"] == "completed" and final["code"] == "SETTLED_VERIFIED" and final["bridge_outcome"] == "verified"
    assert final["ledger"]["task"]["state"] == "COMPLETE" and final["ledger"]["open_authorizations"] == 0
    assert final["ledger"]["attempts"][-1]["status"] in ("ENDED", "FENCED") and final["ledger"]["attempts"][-1]["pid"]
    assert final["journal"] == {"operation_id": final["task_id"], "state": "verified", "receipted": True}
    assert final["operation_id"] == final["task_id"] and final["operation_owner"] == final["execution_id"]
    assert final["server_turn"]["state"] == "reply" and final["server_turn"]["operation_id"] == final["task_id"]
    assert final["evidence"][0]["matched"] is True and len(final["evidence"][0]["output_sha256"]) == 64
    assert final["queued_at"] <= final["approving_at"] <= final["starting_at"] <= final["running_at"] <= final["ended_at"]
    assert final["cancel_requested"] is False and final["proposal"]["provider"] == "claude_code"
    rec = stack.turn_record(turn["turn_id"])
    assert rec["execution_outcome"] == "verified" and rec["dispatched"] is True
    assert stack.tasks() == 1 and len(stack.result_files()) == 1
    rows = listing(stack)["executions"]
    assert [r["execution_id"] for r in rows] == [eid] and rows[0]["state"] == "completed" and listing(stack)["active"] is None


def test_wrong_approval_or_proposal_digest_drops_the_turn_and_runs_nothing(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    with pytest.raises(TurnError, match="APPROVAL_DIGEST_MISMATCH"):
        begin(stack, turn, approval_digest="0" * 64)
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        begin(stack, turn)
    turn = stack.start(TEXT)
    with pytest.raises(TurnError, match="PROPOSAL_DIGEST_MISMATCH"):
        begin(stack, turn, proposal_digest="0" * 64)
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        begin(stack, turn)
    assert stack.tasks() == 0 and listing(stack)["executions"] == []


def test_changing_an_authority_field_invalidates_the_approval(stack, monkeypatch):
    """The UI approved the card for (claude_code, None). A proposal for the same turn but another provider or model
    has another digest: the earlier approval cannot start it, and the pending turn is dropped."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    p = turn["execution_proposal"]
    for other in ({**CODEX}, {**CLAUDE, "model": "other-model"}):
        swapped = execution_proposal(p["client_id"], p["session_id"], p["turn_id"], other, turn["approval_request"])
        assert swapped["proposal_digest"] != p["proposal_digest"]
    swapped = execution_proposal(p["client_id"], p["session_id"], p["turn_id"], CODEX, turn["approval_request"])
    with pytest.raises(TurnError, match="PROPOSAL_DIGEST_MISMATCH"):
        begin(stack, turn, proposal_digest=swapped["proposal_digest"])
    assert stack.tasks() == 0
    # and the worker-side record itself cannot be bent: a mutated pending selection no longer matches the shown card
    turn = stack.start(TEXT)
    text, session, reasoning, pending = stack.service.pending[turn["turn_id"]]
    stack.service.pending[turn["turn_id"]] = (text, session, {**reasoning, "provider": "codex_cli"}, pending)
    with pytest.raises(TurnError, match="PROPOSAL_DIGEST_MISMATCH"):
        begin(stack, turn)
    assert stack.tasks() == 0 and listing(stack)["executions"] == []


def test_typed_text_never_begins_an_execution(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = stack.start(TEXT, session=session)
    for words in ("approve", "yes run it", "execution_begin"):
        with pytest.raises(TurnError, match="TURN_CAPACITY"):
            stack.start(words, session=session)
    assert listing(stack)["executions"] == [] and stack.tasks() == 0
    final = wait_terminal(stack, begin(stack, turn)["execution_id"])
    assert final["state"] == "completed" and stack.tasks() == 1


def test_duplicate_begin_and_replay_cannot_execute_twice(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    with pytest.raises(TurnError, match="TURN_NOT_PENDING|EXECUTION_IN_PROGRESS"):
        begin(stack, turn)
    wait_terminal(stack, eid)
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        begin(stack, turn)                                                   # replay of the exact frame
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        stack.decide(turn, True, digest=turn["approval_request"]["approval_digest"])
    assert stack.tasks() == 1 and stack.L.q1("SELECT COUNT(*) FROM attempt")[0] == 1 and len(stack.result_files()) == 1
    assert len(listing(stack)["executions"]) == 1


def test_one_execution_at_a_time_everything_else_waits(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
    other = stack.start(TEXT)                      # a second pending turn, in its own session
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    try:
        wait_running(stack, eid)
        for kind, cmd in (("turn_start", {"command": "turn_start", "session_id": uid(), "text": TEXT, "reasoning": CLAUDE}),
                          ("turn_decide", {"command": "turn_decide", "turn_id": other["turn_id"], "approve": True}),
                          ("turn_cancel", {"command": "turn_cancel", "turn_id": other["turn_id"]})):
            with pytest.raises(TurnError, match="EXECUTION_IN_PROGRESS"):
                stack.service.handle(kind, cmd)
        with pytest.raises(TurnError, match="EXECUTION_IN_PROGRESS"):
            begin(stack, other)
        assert listing(stack)["active"] == eid and stack.tasks() == 1
        assert status(stack, eid)["state"] == "running"                    # status stays answerable while it runs
    finally:
        cancel(stack, eid)
        wait_terminal(stack, eid)
    assert listing(stack)["active"] is None
    out = stack.service.handle("turn_cancel", {"command": "turn_cancel", "turn_id": other["turn_id"]})
    assert out["code"] == "APPROVAL_DENIED" and stack.tasks() == 1


@pytest.mark.parametrize("scenario,expect_state,expect_reason", [
    # a harness claim after dispatch that URI could not verify is settled UNCERTAIN by the frozen server, never failed-clean
    ("false_claim", "uncertain", None), ("empty_output", "uncertain", None), ("wrong_file", "uncertain", None),
    ("quota", "quota_paused", "PROVIDER_QUOTA_EXHAUSTED"), ("partial_then_die", None, None)])
def test_failure_shapes_never_become_completed(stack, monkeypatch, scenario, expect_state, expect_reason):
    monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
    turn = stack.start(TEXT)
    final = wait_terminal(stack, begin(stack, turn)["execution_id"], timeout=60)
    assert final["state"] != "completed" and final["state"] in TERMINAL_STATES
    if expect_state:
        assert final["state"] == expect_state, final
    if expect_reason:
        assert final["reason"] == expect_reason
    assert final["reason"] or final["code"]
    assert final["ledger"]["task"]["state"] != "COMPLETE" or final["state"] == "completed"
    assert stack.result_files() == []


def test_unqualified_provider_fails_closed_before_any_task(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    from phase2d.conftest import fixture_record, trust_for
    from uri_supervisor_bridge.qualification import compose_client
    fixture_record(stack.client_root, "codex_cli", ("gpt-6-sol",))
    comp = compose_client(stack.client_root, trust=trust_for(stack.client_root), allow_fixture=True)
    stack.bridge.executors = comp.executors
    stack.bridge._ensure_registrations()
    turn = stack.start(TEXT, reasoning=CODEX)                 # offered by policy, model None not qualified any more
    final = wait_terminal(stack, begin(stack, turn)["execution_id"])
    assert final["state"] == "failed" and final["failure_category"].startswith("NOT_STARTED:")
    assert final["task_id"] is not None and final["ledger"]["task"] is None   # dispatched to the bridge, no task created
    assert stack.tasks() == 0 and stack.turn_record(turn["turn_id"])["execution_closed"] is True


def test_frames_cannot_smuggle_or_probe(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    base = {"command": "execution_begin", "turn_id": turn["turn_id"], "approval_digest": turn["approval_request"]["approval_digest"],
            "proposal_digest": turn["execution_proposal"]["proposal_digest"]}
    for extra in ({"ticket": {}}, {"reasoning": CODEX}, {"approve": True}, {"arguments": {}}):
        with pytest.raises(TurnError, match="COMMAND_SCHEMA"):
            stack.service.handle("execution_begin", {**base, **extra})
    for bad in ("", "../x", "0" * 31, 42, None):
        with pytest.raises(TurnError, match="EXECUTION_ID_INVALID"):
            stack.service.handle("execution_status", {"command": "execution_status", "execution_id": bad})
    with pytest.raises(TurnError, match="EXECUTION_UNKNOWN"):
        status(stack, "f" * 32)
    with pytest.raises(TurnError, match="EXECUTION_UNKNOWN"):
        cancel(stack, "f" * 32)
    assert stack.tasks() == 0 and listing(stack)["executions"] == []
    final = wait_terminal(stack, begin(stack, turn)["execution_id"])      # the untouched pending turn still works
    assert final["state"] == "completed"


def test_record_never_contains_secrets_or_tickets(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    wait_terminal(stack, eid)
    raw = (stack.client_root / "control/supervisor/executions" / (eid + ".json")).read_text(encoding="utf-8")
    for needle in ("signature", "ticket", "Bearer", "token", "private", "dpapi"):
        assert needle.lower() not in raw.lower(), needle


def test_deterministic_row_runs_through_the_same_lifecycle(stack):
    """The no-Brain row (local capability, no supervisor task) uses the same frames: proposal, begin, status, receipt.
    No harness, no ledger task, `running_at` stays None (never dispatched to the bridge)."""
    deterministic = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}
    turn = stack.start("remember that the supervised screen was wired on 2026-10-07", reasoning=deterministic)
    assert turn["state"] == "approval_required", turn
    p = turn["execution_proposal"]
    assert p["kind"] == "server_local_model" and p["provider"] == "uri-deterministic" and p["qualification"] is None
    assert p["capability_id"] == "remember_fact"
    final = wait_terminal(stack, begin(stack, turn)["execution_id"])
    assert final["state"] == "completed" and final["code"] == "SETTLED_VERIFIED"
    assert final["task_id"] is None and final["ledger"] is None and final["running_at"] is None
    assert final["journal"]["state"] == "verified" and final["operation_id"] == final["server_turn"]["operation_id"]
    assert final["operation_owner"] == final["execution_id"] and final["corroboration"] == {"checked": True, "gaps": []}
    assert final["starting_at"] is not None and final["server_turn"]["state"] == "reply"
    assert stack.tasks() == 0
