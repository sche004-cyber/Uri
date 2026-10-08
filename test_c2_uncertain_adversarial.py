"""C2/C5 second review: an attempt that may have run stays uncertain and is never re-dispatched.

Adversarial paths through the REAL paired app and real client persistence: idle expiry,
user cancellation, a client receipt that claims "cancelled" after dispatch, a crash between
the provider-wait and settle steps, server restarts, and replay of saved requests.
"""
import time
import uuid

import pytest

from test_c5_intent_discovery import NOBRAIN, Stack, two_reports, say
from uri_core.client_runtime.turn_runner import TurnRunner


def uid():
    return str(uuid.uuid4())


@pytest.fixture
def s():
    stack = Stack(18243)
    yield stack
    stack.close()


def crashed_after_claim(s, monkeypatch):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    assert approval["state"] == "approval_required"

    def crash(self, *a, **k):
        raise RuntimeError("executor crashed after claim")
    monkeypatch.setattr(TurnRunner, "_run_local", crash)
    with pytest.raises(RuntimeError):
        s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    turns = s.app.state.client_service._load()["turns"]
    record = turns[approval["turn_id"]]
    assert record["state"] == "executing"
    return session, awaiting, approval, record


def reconfirm_is_refused(s, session, awaiting):
    before = len(s.calls)
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["code"] == "INTENT_EXECUTION_UNCERTAIN", again
    assert not any(p.endswith(("/approval", "/claim")) for _, p in s.calls[before:])
    assert s.memory(session) == []


def control(s, session, record):
    return {"server_id": s.cred["server_id"], "client_id": s.cred["client_id"],
            "principal_id": s.cm.data["principal_id"], "session_id": session,
            "expected_version": record["version"], "idempotency_key": uid()}


def test_idle_expiry_never_erases_a_claimed_attempt(s, monkeypatch):
    session, awaiting, approval, _ = crashed_after_claim(s, monkeypatch)
    service = s.app.state.client_service
    service.clock = lambda: time.time() + 3 * 3600          # well past the 15 min / 1 h live limits
    reconfirm_is_refused(s, session, awaiting)
    state = service._load()["turns"][approval["turn_id"]]["state"]
    assert state == "execution_uncertain"
    service.clock = lambda: time.time() + 40 * 86400         # and past the 30-day pruning horizon
    service.expire()
    assert service._load()["turns"][approval["turn_id"]]["state"] == "execution_uncertain"
    reconfirm_is_refused(s, session, awaiting)


def test_settled_uncertain_turn_is_not_relabelled_by_expiry(s, monkeypatch):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    monkeypatch.setattr(TurnRunner, "_run_local", lambda self, *a, **k: ("execution_uncertain", [], "UNKNOWN"))
    final = s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    assert final["code"] == "SETTLED_EXECUTION_UNCERTAIN"
    s.app.state.client_service.clock = lambda: time.time() + 3 * 3600
    reconfirm_is_refused(s, session, awaiting)
    assert s.app.state.client_service._load()["turns"][approval["turn_id"]]["state"] == "execution_uncertain"


def test_user_cancel_releases_session_but_keeps_uncertainty_across_restart(s, monkeypatch):
    session, awaiting, approval, record = crashed_after_claim(s, monkeypatch)
    status, out = s.runner.call("POST", f"/client/v1/turns/{approval['turn_id']}/cancel", control(s, session, record))
    assert status == 200 and out["state"] == "execution_uncertain" and out["code"] == "EXECUTION_UNCERTAIN_NOT_CANCELLED"
    # A second cancel (new key) can never turn it into "cancelled" either.
    record = s.app.state.client_service._load()["turns"][approval["turn_id"]]
    status, out = s.runner.call("POST", f"/client/v1/turns/{approval['turn_id']}/cancel", control(s, session, record))
    assert out["state"] == "execution_uncertain"
    reconfirm_is_refused(s, session, awaiting)
    s.start()                                                 # real restart of the app over the same roots
    reconfirm_is_refused(s, session, awaiting)


def test_client_receipt_cannot_cancel_a_dispatched_attempt(s, monkeypatch):
    """A 'cancelled' receipt after dispatch would be a false terminal state hiding a possible effect."""
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    monkeypatch.setattr(TurnRunner, "_run_local", lambda self, *a, **k: ("cancelled", [], "CLIENT_SAYS_CANCELLED"))
    with pytest.raises(Exception):
        s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    record = s.app.state.client_service._load()["turns"][approval["turn_id"]]
    assert record["state"] == "executing" and not record.get("execution_closed")
    # The session stays locked to the in-flight attempt until the user cancels, which releases it
    # without relabelling the attempt.
    status, out = s.runner.call("POST", f"/client/v1/turns/{approval['turn_id']}/cancel", control(s, session, record))
    assert status == 200 and out["state"] == "execution_uncertain"
    reconfirm_is_refused(s, session, awaiting)


def test_dispatched_provider_wait_never_becomes_cancelled_or_rerunnable(s, monkeypatch):
    """A dispatched attempt parked in a provider wait, then cancelled or abandoned by a crash, stays guarded."""
    session, awaiting, approval, record = crashed_after_claim(s, monkeypatch)
    service = s.app.state.client_service
    turn = service._load()["turns"][approval["turn_id"]]
    turn["state"] = "waiting_for_model"                 # as left by a provider-quota pause before its settle
    data = service._load(); data["turns"][approval["turn_id"]] = turn
    from uri_core.core.runtime_identity import atomic_json
    atomic_json(service.path, data)
    reconfirm_is_refused(s, session, awaiting)
    status, out = s.runner.call("POST", f"/client/v1/turns/{approval['turn_id']}/cancel", control(s, session, turn))
    assert status == 200 and out["state"] == "execution_uncertain"
    s.start()
    reconfirm_is_refused(s, session, awaiting)
    service = s.app.state.client_service
    service.clock = lambda: time.time() + 40 * 86400
    service.expire()
    assert service._load()["turns"][approval["turn_id"]]["state"] == "execution_uncertain"   # never pruned


def test_saved_requests_replayed_after_restart_never_dispatch(s, monkeypatch):
    session, awaiting, approval, record = crashed_after_claim(s, monkeypatch)
    s.start()
    # Replaying the old approval (same digest) cannot re-issue a ticket: pending state is gone.
    body = control(s, session, record) | {"decision": "approve",
                                          "approval_digest": approval["approval_request"]["approval_digest"]}
    status, out = s.runner.call("POST", f"/client/v1/turns/{approval['turn_id']}/approval", body)
    assert status != 200
    # Replaying the original turn start (same idempotency key, same body) never re-runs the coordinator.
    reconfirm_is_refused(s, session, awaiting)
    assert s.memory(session) == []


def test_verified_intent_cannot_be_replayed_from_older_client_state(s):
    """After a verified execution, restoring the pre-execution session (rollback/replay) and
    confirming again must not execute the same confirmed intent a second time."""
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    pre_execution = s.session_state(session)
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    final = s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    assert final["code"] == "SETTLED_VERIFIED" and len(s.memory(session)) == 1
    s.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session",
                                          {"session_id": session}, pre_execution)])
    before = len(s.calls)
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["state"] == "reply", again
    assert not any(p.endswith(("/approval", "/claim")) for _, p in s.calls[before:])
    assert len(s.memory(session)) == 1


def test_verified_intent_lineage_survives_ledger_pruning(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    pre_execution = s.session_state(session)
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    assert s.runner.decide("Confirm", session, NOBRAIN, approval, True)["code"] == "SETTLED_VERIFIED"
    service = s.app.state.client_service
    service.clock = lambda: time.time() + 40 * 86400
    service.expire()
    assert not any(t.get("intent_id") for t in service._load()["turns"].values())   # pruned...
    s.start()
    s.app.state.client_service.clock = lambda: time.time() + 40 * 86400
    s.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session",
                                          {"session_id": session}, pre_execution)])
    before = len(s.calls)
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["state"] == "reply", again                                         # ...but the guard holds
    assert not any(p.endswith(("/approval", "/claim")) for _, p in s.calls[before:])
    assert len(s.memory(session)) == 1


def test_local_write_cannot_be_paused_for_quota_and_closed_as_cancelled(s, monkeypatch):
    """Review hardening: only provider-executed tasks may use the quota pause. A remember_fact attempt
    paused and settled 'cancelled' would close a write that may already have happened."""
    session, awaiting, approval, record = crashed_after_claim(s, monkeypatch)
    status, out = s.runner.call("POST", f"/client/v1/turns/{approval['turn_id']}/wait",
                                control(s, session, record) | {"checkpoint_digest": "a" * 64})
    assert status != 200
    assert s.app.state.client_service._load()["turns"][approval["turn_id"]]["state"] == "executing"
    status, out = s.runner.call("POST", f"/client/v1/turns/{approval['turn_id']}/cancel", control(s, session, record))
    assert out["state"] == "execution_uncertain"
    reconfirm_is_refused(s, session, awaiting)


# ---- third review: a "failed" receipt after dispatch is not evidence that nothing happened ------------
# Review decision 3. Before this repair the server closed such an attempt as failed, the client kept the
# confirmed intent, and re-confirming obtained a fresh approval and a SECOND execution, although the
# failure could have followed an effect (the real runner reports READBACK_MISMATCH after a write landed).

def test_failed_receipt_after_dispatch_is_uncertain_and_never_rerun(s, monkeypatch):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    original = TurnRunner._run_local

    def wrote_then_failed(self, *a, **k):
        original(self, *a, **k)                      # the write really lands
        return "failed", [], "READBACK_MISMATCH"     # ...but the client reports a failure
    monkeypatch.setattr(TurnRunner, "_run_local", wrote_then_failed)
    final = s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    assert final["code"] == "SETTLED_EXECUTION_UNCERTAIN" and final["state"] == "execution_uncertain"
    assert "cannot confirm" in final["message"]
    record = s.app.state.client_service._load()["turns"][approval["turn_id"]]
    assert record["state"] == "execution_uncertain" and not record.get("execution_closed")
    assert s.session_state(session)["active_workflow"]["status"] == "EXECUTION_UNCERTAIN"
    stored = s.memory(session)
    assert len(stored) == 1
    # Neither the client's current state nor replayed older state (from before execution) re-runs it,
    # including after a real server restart.
    before = len(s.calls)
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["code"] == "INTENT_EXECUTION_UNCERTAIN", again
    s.start()                                                 # app restart over the same durable roots
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["code"] == "INTENT_EXECUTION_UNCERTAIN", again
    assert not any(p.endswith(("/approval", "/claim")) for _, p in s.calls[before:])
    assert s.memory(session) == stored


def test_pre_launch_refusal_closes_the_attempt_and_allows_an_explicit_retry(s, monkeypatch):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    monkeypatch.setattr(TurnRunner, "_run_local", lambda self, *a, **k: ("failed", [], "NOT_STARTED:NO_LOCAL_EXECUTOR"))
    final = s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    assert final["code"] == "SETTLED_FAILED" and s.memory(session) == []


def test_settled_uncertain_turn_does_not_lock_the_session(s, monkeypatch):
    """Third review: a settled execution_uncertain turn stayed 'active', so every new turn in the session was
    refused with TURN_CAPACITY until idle expiry, although nothing can advance that turn."""
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    monkeypatch.setattr(TurnRunner, "_run_local", lambda self, *a, **k: ("execution_uncertain", [], "UNKNOWN"))
    assert s.runner.decide("Confirm", session, NOBRAIN, approval, True)["code"] == "SETTLED_EXECUTION_UNCERTAIN"
    monkeypatch.undo()
    # Plain text is never turned into a fresh confirmation of the possibly-executed request: it is set aside.
    aside = say(s, session, "hello")
    assert aside["code"] == "INTENT_EXECUTION_UNCERTAIN" and "confirmation" not in aside
    assert s.session_state(session)["active_workflow"] is None
    assert say(s, session, "hello")["code"] == "CONVERSATION"
    # Replaying the old confirmation (older client state) still never dispatches.
    before = len(s.calls)
    assert s.runner.confirm(session, NOBRAIN, awaiting)["code"] in {"INTENT_EXECUTION_UNCERTAIN", "INTENT_DECISION_STALE"}
    assert not any(p.endswith(("/approval", "/claim")) for _, p in s.calls[before:])
    # A genuinely new request in the user's own words still works in the same session.
    assert say(s, session, "remember that the venue is booked")["state"] == "approval_required"
