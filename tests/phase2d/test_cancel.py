"""Phase 2D cancellation propagation at the bridge/supervisor level (SYNTHETIC executor).

Before admission: nothing starts. Between admission and spawn: the attempt ends spawn_failed, nothing starts.
While running: the executor is killed through its job, the task is never re-admitted, and the outcome is
`execution_uncertain` (a cancellation after dispatch is never a clean close). The task id is spent for ever."""
import threading
import time

from phase2b.conftest import CLAUDE
from uri_supervisor import winproc
from uri_supervisor_bridge.bridge import NOT_STARTED


def test_cancel_before_execution_starts_nothing(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    signed, request, now = authority.issue()
    work = authority.verify(signed, request, CLAUDE, now=now)
    bridge.cancel(work.task_id)
    assert bridge.execute(work) == ("failed", [], NOT_STARTED + "CANCELLED")
    assert bridge.L.q1("SELECT COUNT(*) FROM task")[0] == 0


def test_cancel_while_running_kills_the_executor_and_never_retries(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
    bridge.inactivity_s, bridge.timeout_s = 30, 30
    signed, request, now = authority.issue()
    work = authority.verify(signed, request, CLAUDE, now=now)
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("r", bridge.execute(work)))
    t.start()
    deadline = time.monotonic() + 15
    pid = None
    while time.monotonic() < deadline:
        row = bridge.L.q1("SELECT pid,pid_create_time FROM attempt WHERE task_id=? AND status='RUNNING'", (work.task_id,))
        if row and row["pid"]:
            pid = row
            break
        time.sleep(0.05)
    assert pid is not None, "executor never reached RUNNING"
    rep = bridge.cancel(work.task_id)
    assert rep["kill"]["granted"] is True
    t.join(30)
    assert not t.is_alive()
    outcome, evidence, failure = out["r"]
    assert outcome == "execution_uncertain" and failure.startswith("CANCELLED_AFTER_DISPATCH")
    att = [dict(r) for r in bridge.L.q("SELECT end_reason FROM attempt WHERE task_id=? ORDER BY attempt_id", (work.task_id,))]
    assert att == [{"end_reason": "cancelled_killed"}]                  # one attempt, killed, no retry
    task = bridge.L.task(work.task_id)
    assert task["state"] == "FAILED" and task["reason_code"] == "BRIDGE_SETTLED_CANCELLED"
    assert winproc.identity_state(pid["pid"], pid["pid_create_time"]) in ("DEAD", "PID_REUSED")
    open_auth = bridge.L.q1("SELECT COUNT(*) FROM authorization WHERE task_id=? AND superseded_at_us IS NULL AND (valid_until_us IS NULL OR valid_until_us>?)",
                            (work.task_id, bridge.L.now_us()))[0]
    assert open_auth == 0
    assert bridge.execute(work) == ("execution_uncertain", [], "DUPLICATE_OPERATION")


def test_cancel_unknown_task_is_recorded_but_kills_nothing(bridge):
    rep = bridge.cancel("00000000-0000-0000-0000-000000000000")
    assert rep["kill"] == {"granted": False, "reason": "NOT_RUNNING"}


def test_supervisor_request_cancel_refuses_attempts_it_does_not_run(bridge):
    assert bridge.sup.request_cancel(999) == {"granted": False, "reason": "NOT_RUNNING_HERE"}
