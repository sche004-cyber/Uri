"""CAP-1 (Phase 2 closure, 2026-10-08): an `approval_required` turn the worker abandons on its own must not keep
holding server capacity.

The frozen server allows one active turn per (client, session) and four per server (`client_service.py:169-174`);
an undecided `approval_required` turn stays active for 15 minutes idle. Before this repair a wrong digest echo dropped
the pending turn worker-side only, so the same session was blocked (`TURN_CAPACITY`) and four such drops blocked every
new turn on the server. The worker now releases the turn through the server's own cancel route."""
import pytest

from phase2b.conftest import uid
from phase2ops.conftest import TEXT, begin, wait_terminal
from uri_core.client_runtime.turn_runner import TurnError


def test_cap1_digest_mismatch_releases_the_session(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = stack.start(TEXT, session=session)
    with pytest.raises(TurnError, match="PROPOSAL_DIGEST_MISMATCH"):
        begin(stack, turn, proposal_digest="0" * 64)
    assert stack.server_status(turn["turn_id"])["state"] == "cancelled"
    assert stack.service.released[-1]["released"] is True and stack.service.released[-1]["why"] == "PROPOSAL_DIGEST_MISMATCH"
    again = stack.start(TEXT, session=session)                       # was SERVER_REFUSED:TURN_CAPACITY
    assert again["state"] == "approval_required"
    final = wait_terminal(stack, begin(stack, again)["execution_id"])
    assert final["state"] == "completed" and stack.tasks() == 1     # the released turn never ran


def test_cap1_four_abandoned_cards_no_longer_block_the_server(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    for wrong in ("approval", "proposal", "approval", "proposal"):
        turn = stack.start(TEXT, session=uid())
        with pytest.raises(TurnError, match="DIGEST_MISMATCH"):
            begin(stack, turn, **{wrong + "_digest": "0" * 64})
    assert stack.start(TEXT, session=uid())["state"] == "approval_required"
    assert stack.tasks() == 0


def test_cap1_turn_decide_digest_mismatch_releases_too(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    turn = stack.start(TEXT, session=session)
    with pytest.raises(TurnError, match="APPROVAL_DIGEST_MISMATCH"):
        stack.decide(turn, True, digest="0" * 64)
    assert stack.server_status(turn["turn_id"])["state"] == "cancelled"
    assert stack.start(TEXT, session=session)["state"] == "approval_required"


def test_cap1_close_releases_every_pending_card(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turns = [stack.start(TEXT, session=uid()) for _ in range(3)]
    out = stack.service.release_pending("WORKER_CLOSED")
    assert [o["released"] for o in out] == [True, True, True] and stack.service.pending == {}
    assert all(stack.server_status(t["turn_id"])["state"] == "cancelled" for t in turns)
    assert stack.tasks() == 0


def test_cap1_release_never_relabels_a_turn_that_moved(stack, monkeypatch):
    """The release is version-checked by the frozen server: a turn that advanced is refused, recorded, not hidden."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    entry = stack.service.pending[turn["turn_id"]]
    final = wait_terminal(stack, begin(stack, turn)["execution_id"])
    assert final["state"] == "completed"
    out = stack.service.release_turn(entry, "TEST_STALE_ENTRY")
    assert out["released"] is False and out["status"] in (409, 400) and out["code"] in ("TURN_TERMINAL", "VERSION_CONFLICT")
    assert stack.server_status(turn["turn_id"])["state"] == "reply"            # the settled turn is untouched


def test_cap1_release_with_the_server_down_is_reported_not_raised(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    entry = stack.service.pending.pop(turn["turn_id"])

    def down(method, path, body):
        raise OSError("connection refused")
    monkeypatch.setattr(stack.service.runner, "call", down)
    out = stack.service.release_turn(entry, "TEST_SERVER_DOWN")
    assert out == {"turn_id": turn["turn_id"], "why": "TEST_SERVER_DOWN", "released": False, "error": "OSError"}


def test_cap1_val1_final_refusal_releases_the_session(stack, monkeypatch):
    """VAL-1 double refusal: the execution ends `failed` (nothing applied) AND the turn is released."""
    import time
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    coordinator = stack.app.state.client_service.coordinator
    session = uid()
    turn = stack.start(TEXT, session=session)
    base = float(int(time.time())) + 0.999
    real_issue, real_check = coordinator.clock, coordinator.control.clock
    coordinator.clock, coordinator.control.clock = (lambda: base), (lambda: base + 0.002)
    try:
        final = wait_terminal(stack, begin(stack, turn)["execution_id"])
    finally:
        coordinator.clock, coordinator.control.clock = real_issue, real_check
    assert final["state"] == "failed" and final["reason"].startswith("APPROVAL_REFUSED_NOT_APPLIED")
    assert stack.server_status(turn["turn_id"])["state"] == "cancelled"
    assert stack.start(TEXT, session=session)["state"] == "approval_required"
