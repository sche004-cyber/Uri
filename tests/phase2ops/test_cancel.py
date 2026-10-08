"""Mid-run cancellation through the supervised worker protocol: before the approval is posted, between approval and
dispatch, while the executor (and its descendants) run, and after a terminal state. Every cancel is checked against
the ledger and the operating system, never only against the record's label."""
import threading
import time

import psutil
import pytest

from phase2ops.conftest import TEXT, begin, cancel, listing, status, wait_running, wait_terminal
from uri_core.client_runtime.turn_runner import TurnError
from uri_supervisor import winproc


def _dead(pid, create_time=None):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if create_time is not None:
            if winproc.identity_state(pid, create_time) in ("DEAD", "PID_REUSED"):
                return True
        elif not psutil.pid_exists(pid):
            return True
        time.sleep(0.1)
    return False


def test_cancel_before_the_approval_is_posted_denies_the_turn(stack, monkeypatch):
    """The thread has not reached the server yet: the cancel turns the pending approval into a DENIAL."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    gate, entered = threading.Event(), threading.Event()
    original = stack.service._runner

    def slow_runner():
        entered.set()
        gate.wait(20)
        return original()
    turn = stack.start(TEXT)
    stack.service._runner = slow_runner       # only the execution thread is gated; turn_start used the real runner
    eid = begin(stack, turn)["execution_id"]
    assert entered.wait(10)
    rep = cancel(stack, eid)
    assert rep["cancel"] == "requested" and rep["kill"] == {"granted": False, "reason": "NOT_DISPATCHED"}
    gate.set()
    final = wait_terminal(stack, eid)
    assert final["state"] == "cancelled" and final["reason"] == "CANCELLED_BEFORE_APPROVAL" and final["code"] == "APPROVAL_DENIED"
    assert final["decision"] == "deny" and final["task_id"] is None and final["ledger"] is None
    assert final["server_turn"]["state"] == "cancelled"
    assert stack.tasks() == 0 and stack.result_files() == []
    with pytest.raises(TurnError, match="EXECUTION_TERMINAL"):
        cancel(stack, eid)


def test_cancel_between_approval_and_dispatch_never_spawns(stack, monkeypatch):
    """The approval and claim were posted; the cancel lands before the bridge submits the task."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    gate, at_dispatch = threading.Event(), threading.Event()
    original = stack.runner._run_harness

    def gated(session, request, reasoning):
        at_dispatch.set()
        gate.wait(20)
        return original(session, request, reasoning)
    monkeypatch.setattr(stack.runner, "_run_harness", gated)
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    assert at_dispatch.wait(10)
    assert status(stack, eid)["state"] == "starting"
    cancel(stack, eid)
    gate.set()
    final = wait_terminal(stack, eid)
    assert final["state"] == "cancelled" and final["reason"] == "CANCELLED_BEFORE_START"
    assert final["failure_category"] == "NOT_STARTED:CANCELLED" and final["code"] == "SETTLED_FAILED"
    assert final["task_id"] is not None and final["ledger"]["task"] is None          # the bridge refused: no task row
    assert stack.tasks() == 0 and stack.result_files() == []
    assert stack.turn_record(turn["turn_id"])["execution_closed"] is True


def test_cancel_while_running_kills_the_executor_and_settles_uncertain(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
    stack.bridge.timeout_s = stack.bridge.inactivity_s = 60
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    running = wait_running(stack, eid)
    att = running["ledger"]["attempts"][-1]
    assert psutil.pid_exists(att["pid"]) and winproc.identity_state(att["pid"], att["pid_create_time"]).startswith("ALIVE")
    t0 = time.monotonic()
    rep = cancel(stack, eid)
    assert rep["kill"]["granted"] is True and rep["cancel"] == "requested"
    final = wait_terminal(stack, eid)
    assert time.monotonic() - t0 < 30
    assert final["state"] == "uncertain" and final["reason"] == "CANCELLED_AFTER_DISPATCH" and final["cancel_requested"] is True
    assert final["failure_category"].startswith("CANCELLED_AFTER_DISPATCH") and final["code"] == "SETTLED_EXECUTION_UNCERTAIN"
    assert _dead(att["pid"], att["pid_create_time"])                                  # the harness is really gone
    assert final["ledger"]["attempts"] and final["ledger"]["attempts"][-1]["end_reason"] == "cancelled_killed"
    assert final["ledger"]["task"]["state"] == "FAILED" and final["ledger"]["open_authorizations"] == 0
    assert final["journal"]["state"] == "execution_uncertain" and final["server_turn"]["state"] == "execution_uncertain"
    assert stack.L.q1("SELECT COUNT(*) FROM attempt")[0] == 1                       # never retried
    with pytest.raises(TurnError, match="EXECUTION_TERMINAL"):
        cancel(stack, eid)
    assert listing(stack)["active"] is None


def test_cancel_kills_descendants_too(stack, monkeypatch, tmp_path):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "grandchild")
    pidfile = tmp_path / "grandchild.pid"
    monkeypatch.setenv("URI_FAKE_PIDFILE", str(pidfile))
    stack.bridge.timeout_s = stack.bridge.inactivity_s = 60
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    running = wait_running(stack, eid)
    deadline = time.monotonic() + 15
    while not pidfile.is_file() and time.monotonic() < deadline:
        time.sleep(0.1)
    grandchild = int(pidfile.read_text())
    assert psutil.pid_exists(grandchild)
    att = running["ledger"]["attempts"][-1]
    cancel(stack, eid)
    final = wait_terminal(stack, eid)
    assert final["state"] == "uncertain"
    assert _dead(att["pid"], att["pid_create_time"]) and _dead(grandchild)


def test_cancel_after_terminal_is_refused_and_changes_nothing(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    final = wait_terminal(stack, eid)
    assert final["state"] == "completed"
    with pytest.raises(TurnError, match="EXECUTION_TERMINAL"):
        cancel(stack, eid)
    again = status(stack, eid)
    assert again["state"] == "completed" and again["cancel_requested"] is False and again["ledger"]["task"]["state"] == "COMPLETE"


def test_close_during_execution_withdraws_and_leaves_a_terminal_record(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
    stack.bridge.timeout_s = stack.bridge.inactivity_s = 60
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    att = wait_running(stack, eid)["ledger"]["attempts"][-1]
    closed = stack.service.executions.close(30)
    assert closed["active"] == eid and closed["state"] == "uncertain"
    assert _dead(att["pid"], att["pid_create_time"])
    assert status(stack, eid)["state"] == "uncertain"
