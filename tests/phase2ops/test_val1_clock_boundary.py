"""VAL-1 root-cause reproduction (Phase 2 closure, 2026-10-08).

The frozen coordinator stamps the execution ticket with `issued_at = int(coordinator.clock())`
(`uri_core/core/paired_coordinator.py:303`) and the frozen execution control then refuses the ticket unless
`issued_at == int(control.clock())` (`uri_core/core/client_execution_control.py:77`). The `_authority` callback runs
between the two reads. When the wall clock crosses a whole-second boundary inside that window the control raises
`TICKET_CLOCK_OR_GENERATION`, which the coordinator re-raises as `ClientControlError(..., 403)`
(`paired_coordinator.py:314-316`). The turn is left at `approval_required` with its version unchanged, because
`ClientService.act` only bumps the version after the step returns. That is exactly the VAL-1 signature: one HTTP 403 on
the approval POST, server turn `approval_required` v0.

These tests do not modify any frozen file. They inject the clock at the boundary to prove the mechanism
deterministically, and they measure the real window to estimate how often it happens."""
import time

import pytest

from phase2ops.conftest import TEXT, begin, wait_terminal


def _coordinator(stack):
    coordinator = stack.app.state.client_service.coordinator
    assert coordinator is not None and coordinator.control is not None
    return coordinator


def test_val1_second_boundary_between_issue_and_prepare_is_a_403_that_leaves_the_turn_pending(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    coordinator = _coordinator(stack)
    turn = stack.start(TEXT)
    before = stack.server_status(turn["turn_id"])
    assert before["state"] == "approval_required"

    # The ticket is stamped at second S; the control reads second S + 1. Nothing else changes.
    base = float(int(time.time())) + 0.999
    real_issue, real_check = coordinator.clock, coordinator.control.clock
    coordinator.clock = lambda: base
    coordinator.control.clock = lambda: base + 0.002
    captured = []
    real_request = stack.http.request

    at_first_refusal = []

    def capture(method, path, **kw):
        r = real_request(method, path, **kw)
        captured.append((method, path, r.status_code, r.json()))
        if r.status_code == 403 and path.endswith("/approval") and not at_first_refusal:
            at_first_refusal.append(real_request("GET", f"/client/v1/turns/{turn['turn_id']}/status", headers=stack.headers).json())
        return r
    monkeypatch.setattr(stack.http, "request", capture)
    try:
        out = begin(stack, turn)
        final = wait_terminal(stack, out["execution_id"])
    finally:
        coordinator.clock, coordinator.control.clock = real_issue, real_check

    approvals = [c for c in captured if c[0] == "POST" and c[1].endswith("/approval")]
    assert approvals and approvals[0][2] == 403 and approvals[0][3] == {"detail": "TICKET_CLOCK_OR_GENERATION"}
    after = at_first_refusal[0]                                   # the server's own view right after the 403
    assert after["state"] == "approval_required" and after["version"] == before["version"]     # VAL-1 signature
    assert stack.server_status(turn["turn_id"])["state"] == "cancelled"                        # then released (CAP-1)
    # Mitigation: exactly one resend of the same approval (the boundary is pinned here, so it is refused again);
    # the execution ends `failed` (provably nothing applied), never `completed`, never retried a third time.
    assert len(approvals) == 2 and all(a[2] == 403 for a in approvals)
    assert final["state"] == "failed" and final["reason"].startswith("APPROVAL_REFUSED_NOT_APPLIED:")
    assert final["approval_retries"] == 1 and final["approval_retry_reason"] == "SERVER_REFUSED:TICKET_CLOCK_OR_GENERATION"
    assert stack.tasks() == 0 and stack.result_files() == []
    ops = coordinator.control._load()["operations"]
    assert all(o["turn_id"] != turn["turn_id"] for o in ops.values())                         # no ticket was prepared


def test_val1_same_second_is_accepted(stack, monkeypatch):
    """Control: identical injection without the boundary crossing succeeds, so the refusal above is the boundary."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    coordinator = _coordinator(stack)
    turn = stack.start(TEXT)
    base = float(int(time.time())) + 0.100
    real_issue, real_check = coordinator.clock, coordinator.control.clock
    coordinator.clock = lambda: base
    coordinator.control.clock = lambda: base + 0.002
    try:
        out = begin(stack, turn)
        final = wait_terminal(stack, out["execution_id"])
    finally:
        coordinator.clock, coordinator.control.clock = real_issue, real_check
    assert final["state"] == "completed" and final["code"] == "SETTLED_VERIFIED"


def test_val1_window_is_measured_not_assumed(stack, monkeypatch):
    """Measure the real time between the issue stamp and the control's check on this machine (in-process server).
    The per-approval refusal probability is about window / 1 s. Reported, not asserted against a target."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    coordinator = _coordinator(stack)
    stamps = []
    real_issue, real_check = coordinator.clock, coordinator.control.clock

    def issue():
        stamps.append(("issue", time.perf_counter()))
        return real_issue()

    def check():
        stamps.append(("check", time.perf_counter()))
        return real_check()
    coordinator.clock, coordinator.control.clock = issue, check
    try:
        turn = stack.start(TEXT)
        stamps.clear()
        final = wait_terminal(stack, begin(stack, turn)["execution_id"])
    finally:
        coordinator.clock, coordinator.control.clock = real_issue, real_check
    assert final["state"] == "completed"
    kinds = [k for k, _ in stamps]
    i = kinds.index("issue")
    j = kinds.index("check", i)
    window = stamps[j][1] - stamps[i][1]
    assert 0 < window < 1.0
    print(f"VAL1_WINDOW_SECONDS={window:.6f}")


def test_val1_one_boundary_crossing_is_absorbed_by_one_resend(stack, monkeypatch):
    """The realistic case: the boundary is crossed once. The single resend of the same approval succeeds and the
    execution completes normally; the record keeps the fact that a resend happened."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    coordinator = _coordinator(stack)
    turn = stack.start(TEXT)
    real_issue, real_check = coordinator.clock, coordinator.control.clock
    calls = []

    def issue():
        calls.append("issue")
        if calls.count("issue") == 1:
            return float(int(real_issue())) + 0.999        # first stamp: last instant of a second
        return real_issue()

    def check():
        if calls.count("issue") == 1 and "crossed" not in calls:
            calls.append("crossed")
            return float(int(real_issue())) + 1.001        # first check: the next second
        return real_check()
    coordinator.clock, coordinator.control.clock = issue, check
    try:
        final = wait_terminal(stack, begin(stack, turn)["execution_id"])
    finally:
        coordinator.clock, coordinator.control.clock = real_issue, real_check
    assert final["state"] == "completed" and final["code"] == "SETTLED_VERIFIED"
    assert final["approval_retries"] == 1 and stack.tasks() == 1 and len(stack.result_files()) == 1


def test_val1_no_resend_unless_the_server_proves_the_turn_unchanged(stack, monkeypatch):
    """The resend precondition is checked against the server, not assumed: if the server turn is not
    `approval_required` at the approved version and session, or the record shows progress, there is no resend."""
    from uri_supervisor_bridge.execution import ExecutionController
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.service.pending[stack.start(TEXT)["turn_id"]][3]     # the worker's own copy, as `_run` holds it
    assert type(turn.get("version")) is int
    rec = {"state": "approving", "operation_id": None, "task_id": None}
    ctl = ExecutionController.__new__(ExecutionController)          # a bare controller: only the server view is used
    status_now = stack.server_status(turn["turn_id"])
    ctl._server_status = lambda tid: dict(status_now)
    assert ExecutionController._approval_provably_unapplied(ctl, rec, turn, status_now.get("session_id"))
    assert not ExecutionController._approval_provably_unapplied(ctl, rec, turn, "another-session")
    ctl._server_status = lambda tid: {**status_now, "version": status_now["version"] + 1}
    assert not ExecutionController._approval_provably_unapplied(ctl, rec, turn, status_now.get("session_id"))
    ctl._server_status = lambda tid: {**status_now, "state": "ticket_issued"}
    assert not ExecutionController._approval_provably_unapplied(ctl, rec, turn, status_now.get("session_id"))
    for moved in ({"state": "starting"}, {"operation_id": "x"}, {"task_id": "y"}):
        assert not ExecutionController._approval_provably_unapplied(ctl, {**rec, **moved}, turn, status_now.get("session_id"))
    ctl._server_status = lambda tid: (_ for _ in ()).throw(OSError("down"))
    assert not ExecutionController._approval_provably_unapplied(ctl, rec, turn, status_now.get("session_id"))


def test_val1_resend_rules_on_the_decide_seam():
    """Unit check of the single seam: one resend at most, only for an approval, only for the two refusal codes,
    never after a cancel request, never when the server view does not prove the turn unchanged."""
    from uri_core.client_runtime.turn_runner import TurnError
    from uri_supervisor_bridge.execution import ExecutionController

    class Runner:
        def __init__(self, errors):
            self.errors, self.calls = list(errors), 0

        def decide(self, *a):
            self.calls += 1
            if self.errors:
                raise TurnError(self.errors.pop(0))
            return {"code": "SETTLED_VERIFIED"}

    class Register:
        def __init__(self):
            self.rec = {"state": "approving"}

        def get(self, eid):
            return dict(self.rec)

        def update(self, eid, **kw):
            self.rec.update(kw)

    def controller(server_ok=True, cancelled=False):
        import threading
        c = ExecutionController.__new__(ExecutionController)
        c._lock, c._cancel, c.register = threading.RLock(), ({"e"} if cancelled else set()), Register()
        c._server_status = lambda tid: {"state": "approval_required" if server_ok else "ticket_issued", "version": 3, "session_id": "s"}
        return c
    turn = {"turn_id": "t", "version": 3}
    for code in ("SERVER_REFUSED:HTTP_403", "SERVER_REFUSED:TICKET_CLOCK_OR_GENERATION"):
        c, r = controller(), Runner([code])
        assert c._decide("e", r, "x", "s", {}, turn, True) == {"code": "SETTLED_VERIFIED"} and r.calls == 2
        assert c.register.rec["approval_retries"] == 1
    cases = [(controller(), Runner(["SERVER_REFUSED:HTTP_403", "SERVER_REFUSED:HTTP_403"]), True),      # never a third
             (controller(), Runner(["SERVER_REFUSED:HTTP_409"]), True),                                  # other code
             (controller(), Runner(["SERVER_REFUSED:HTTP_403"]), False),                                 # a denial
             (controller(cancelled=True), Runner(["SERVER_REFUSED:HTTP_403"]), True),                    # cancel asked
             (controller(server_ok=False), Runner(["SERVER_REFUSED:HTTP_403"]), True)]                   # server moved
    for c, r, approve in cases:
        try:
            c._decide("e", r, "x", "s", {}, turn, approve)
            raise AssertionError("must raise")
        except TurnError:
            pass
    assert [r.calls for _, r, _ in cases] == [2, 1, 1, 1, 1]
