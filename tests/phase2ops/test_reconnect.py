"""Reconnect and restart: a new worker-side service on the same client (what a reopened UI gets) sees every earlier
execution from the durable register, re-reads the ledger/journal/server for its truth, marks whatever was in flight
`uncertain` (`WORKER_RESTARTED`), never relaunches, and cannot be talked into a second execution of the same work."""
import pytest

from phase2b.conftest import CLAUDE, uid
from phase2ops.conftest import TEXT, begin, cancel, listing, status, wait_running, wait_terminal
from uri_core.client_runtime.turn_runner import TurnError


def test_completed_execution_survives_a_worker_restart(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    before = wait_terminal(stack, eid)
    fresh = stack.new_service()                                    # the UI reopened: a new worker on the same client
    rows = listing(stack, fresh)
    assert rows["active"] is None and rows["startup"]["executions"] == [] and [r["execution_id"] for r in rows["executions"]] == [eid]
    after = status(stack, eid, fresh)
    assert after["state"] == before["state"] == "completed" and after["task_id"] == before["task_id"]
    assert after["ledger"]["task"]["state"] == "COMPLETE" and after["server_turn"]["state"] == "reply"
    with pytest.raises(TurnError, match="EXECUTION_TERMINAL"):
        cancel(stack, eid, fresh)
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):           # the old approval is dead in the new worker
        begin(stack, turn, service=fresh)
    assert stack.tasks() == 1 and len(stack.result_files()) == 1


def test_in_flight_execution_is_uncertain_after_restart_and_is_never_relaunched(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
    stack.bridge.timeout_s = stack.bridge.inactivity_s = 60
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    running = wait_running(stack, eid)
    fresh = stack.new_service()                                    # restart while the attempt runs (in-process model)
    try:
        rows = listing(stack, fresh)
        assert rows["startup"]["executions"] == [{"execution_id": eid, "was": "running", "state": "uncertain", "reason": "WORKER_RESTARTED"}]
        st = status(stack, eid, fresh)
        assert st["state"] == "uncertain" and st["reason"] == "WORKER_RESTARTED" and st["previous_state"] == "running"
        assert st["restart_ledger"]["task_id"] == running["task_id"]
        with pytest.raises(TurnError, match="EXECUTION_TERMINAL"):
            cancel(stack, eid, fresh)
        with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
            begin(stack, turn, service=fresh)
        with pytest.raises(TurnError, match="TURN_CAPACITY"):           # frozen rule: the session is held by that turn
            fresh.handle("turn_start", {"command": "turn_start", "session_id": turn["execution_proposal"]["session_id"],
                                        "text": TEXT, "reasoning": CLAUDE})
        assert stack.tasks() == 1 and stack.L.q1("SELECT COUNT(*) FROM attempt")[0] == 1
    finally:
        stack.bridge.cancel(running["task_id"])                      # the old (in-process) thread is withdrawn
        stack.service.executions._thread.join(40)


def test_server_unreachable_at_settle_is_uncertain_not_completed(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    original = stack.runner.call

    def failing(method, path, body):
        if path.endswith("/settle"):
            return 503, {"detail": "SERVER_RESTARTING"}
        return original(method, path, body)
    monkeypatch.setattr(stack.runner, "call", failing)
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    final = wait_terminal(stack, eid)
    assert final["state"] == "uncertain" and final["reason"].startswith("EXCEPTION:SERVER_REFUSED")
    assert final["bridge_outcome"] == "verified"                      # the work happened; URI will not call it done
    assert final["ledger"]["task"]["state"] == "COMPLETE" and final["journal"]["state"] == "verified"
    assert final["server_turn"]["state"] == "executing"                # the server never received the receipt
    rows = listing(stack, stack.new_service())["executions"]
    assert rows[0]["state"] == "uncertain"


def test_stale_ui_state_cannot_override_the_record(stack, monkeypatch):
    """A UI that still believes an execution runs asks again: it gets the terminal state, and nothing it sends
    (cancel, begin, decide) can move a terminal execution or re-run its work."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    wait_terminal(stack, eid)
    for _ in range(3):
        assert status(stack, eid)["state"] == "completed"
    with pytest.raises(TurnError, match="EXECUTION_TERMINAL"):
        cancel(stack, eid)
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        begin(stack, turn)
    with pytest.raises(TurnError, match="TURN_NOT_PENDING"):
        stack.decide(turn, True)
    assert stack.tasks() == 1 and stack.L.q1("SELECT COUNT(*) FROM attempt")[0] == 1


def test_unreadable_record_reports_uncertain_never_a_crash(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    eid = begin(stack, turn)["execution_id"]
    wait_terminal(stack, eid)
    p = stack.client_root / "control/supervisor/executions" / (eid + ".json")
    p.write_text("{not json", encoding="utf-8")
    st = status(stack, eid)
    assert st["state"] == "uncertain" and st["reason"] == "RECORD_UNREADABLE"
    p.write_text('{"schema": "other"}', encoding="utf-8")
    assert status(stack, eid)["reason"] == "RECORD_SCHEMA"


# -- independent review round 1: OPS-1 (register state constrained by facts), OPS-2 (valid-JSON malformed record) ----

def _forge(stack, **fields):
    import json
    from uri_supervisor_bridge.execution import SCHEMA
    eid = "f" * 31 + "0"
    rec = {"schema": SCHEMA, "execution_id": eid, "turn_id": None, "session_id": None, "state": "completed",
           "reason": None, "code": "SETTLED_VERIFIED", "task_id": None,
           "proposal": {"proposal_digest": "0" * 64, "kind": "server_local_model", "provider": "uri-deterministic", "model": None},
           "queued_at": 1.0, "cancel_requested": False, **fields}
    (stack.client_root / "control/supervisor/executions" / (eid + ".json")).write_text(json.dumps(rec), encoding="utf-8")
    return eid


def test_ops1_a_record_claiming_completed_is_uncertain_unless_ledger_journal_and_server_agree(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    # (a) forged local record, no task, no turn: nothing corroborates it
    eid = _forge(stack)
    st = status(stack, eid)
    assert st["state"] == "uncertain" and st["recorded_state"] == "completed"
    assert st["reason"].startswith("UNCORROBORATED_COMPLETION:") and {"OPERATION_MISSING", "SERVER_UNAVAILABLE", "JOURNAL_NOT_VERIFIED"} <= set(st["corroboration"]["gaps"])
    row = next(r for r in listing(stack)["executions"] if r["execution_id"] == eid)
    assert row["state"] == "uncertain" and row["recorded_state"] == "completed"
    # (b) forged record pointing at a REAL cancelled task and its REAL uncertain turn: the facts win
    turn = stack.start(TEXT + " (fake scenario: hang)")
    real = begin(stack, turn)["execution_id"]
    running = wait_running(stack, real)
    cancel(stack, real)
    final = wait_terminal(stack, real)
    assert final["state"] == "uncertain"
    eid2 = _forge(stack, task_id=running["task_id"], turn_id=turn["turn_id"])
    st2 = status(stack, eid2)
    assert st2["state"] == "uncertain" and st2["recorded_state"] == "completed"
    assert {"LEDGER_NOT_COMPLETE", "JOURNAL_NOT_VERIFIED", "SERVER_TURN_NOT_REPLY", "SERVER_SESSION_MISMATCH"} <= set(st2["corroboration"]["gaps"])
    # (c) a genuinely completed execution still reports completed, with the corroboration recorded
    turn = stack.start(TEXT)
    ok = wait_terminal(stack, begin(stack, turn)["execution_id"])
    assert ok["state"] == "completed" and ok["corroboration"] == {"checked": True, "gaps": []}
    assert ok["ledger"]["request"]["turn_id"] == turn["turn_id"] and ok["ledger"]["request"]["provider"] == "claude_code"
    # (c2) a forged record borrowing THAT completed task and turn, but claiming another selection: not completed
    eid3 = _forge(stack, task_id=ok["task_id"], turn_id=ok["turn_id"], session_id=ok["session_id"],
                  proposal={**ok["proposal"], "provider": "codex_cli", "model": "gpt-6-sol"})
    st3 = status(stack, eid3)
    assert st3["state"] == "uncertain" and {"LEDGER_REQUEST_MISMATCH", "LEDGER_EXECUTION_MISMATCH"} <= set(st3["corroboration"]["gaps"])
    # (c3, review round 2 OPS-1R) a faithful copy of EVERY field under another execution id is still not that
    # execution: the ledger task row names the one record the bridge ran for
    eid4 = _forge(stack, task_id=ok["task_id"], turn_id=ok["turn_id"], session_id=ok["session_id"], proposal=dict(ok["proposal"]))
    st4 = status(stack, eid4)
    assert st4["state"] == "uncertain" and "LEDGER_EXECUTION_MISMATCH" in st4["corroboration"]["gaps"]
    assert ok["ledger"]["request"]["execution_id"] == ok["execution_id"]
    row4 = next(r for r in listing(stack)["executions"] if r["execution_id"] == eid4)
    assert row4["state"] == "uncertain" and "LEDGER_EXECUTION_MISMATCH" in row4["corroboration"]["gaps"]
    # (c4) the genuine record with a tampered record-level session: not corroborated either
    import json as _json
    p = stack.client_root / "control/supervisor/executions" / (ok["execution_id"] + ".json")
    rec = _json.loads(p.read_text(encoding="utf-8"))
    rec["session_id"] = "11111111-1111-4111-8111-111111111111"
    p.write_text(_json.dumps(rec), encoding="utf-8")
    st5 = status(stack, ok["execution_id"])
    assert st5["state"] == "uncertain" and {"LEDGER_REQUEST_MISMATCH", "SERVER_SESSION_MISMATCH"} <= set(st5["corroboration"]["gaps"])
    rec["session_id"] = ok["session_id"]
    p.write_text(_json.dumps(rec), encoding="utf-8")
    assert status(stack, ok["execution_id"])["state"] == "completed"
    # (c5, review round 3 OPS-1R residual) a harness-kind record that OMITS its task cannot take the local branch:
    # the server's operation is a supervisor task, and the proposal kind says harness
    eid6 = _forge(stack, turn_id=ok["turn_id"], session_id=ok["session_id"], proposal=dict(ok["proposal"]))   # task_id None
    st6 = status(stack, eid6)
    assert st6["state"] == "uncertain" and "TASK_OMITTED" in st6["corroboration"]["gaps"]
    row6 = next(r for r in listing(stack)["executions"] if r["execution_id"] == eid6)
    assert row6["state"] == "uncertain" and "TASK_OMITTED" in row6["corroboration"]["gaps"]
    # (c6, review round 4 OPS-1R residual) a LOCAL (no-task) duplicate borrowing a genuine local reply: the ticket
    # operation was claimed by the genuine execution when its ticket verified; a copy under another id does not own it
    deterministic = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}
    lt = stack.start("remember that the ops review ran on 2026-10-07", reasoning=deterministic)
    local = wait_terminal(stack, begin(stack, lt)["execution_id"])
    assert local["state"] == "completed" and local["task_id"] is None and local["operation_owner"] == local["execution_id"]
    eid7 = _forge(stack, turn_id=local["turn_id"], session_id=local["session_id"], proposal=dict(local["proposal"]),
                  operation_id=local["operation_id"])
    st7 = status(stack, eid7)
    assert st7["state"] == "uncertain" and st7["corroboration"]["gaps"] == ["OPERATION_NOT_OWNED"]
    row7 = next(r for r in listing(stack)["executions"] if r["execution_id"] == eid7)
    assert row7["state"] == "uncertain" and row7["corroboration"]["gaps"] == ["OPERATION_NOT_OWNED"]
    eid8 = _forge(stack, turn_id=local["turn_id"], session_id=local["session_id"], proposal=dict(local["proposal"]))   # no operation at all
    assert "OPERATION_MISSING" in status(stack, eid8)["corroboration"]["gaps"]
    # (d) and loses that status the moment a fact disappears (journal gone)
    (stack.client_root / "control/execution-journal.sqlite3").unlink()
    again = status(stack, ok["execution_id"])
    assert again["state"] == "uncertain" and again["reason"] == "UNCORROBORATED_COMPLETION:JOURNAL_NOT_VERIFIED"


def test_ops2_valid_json_but_malformed_records_never_break_listing_or_restart(stack, monkeypatch):
    import json
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    good = begin(stack, turn)["execution_id"]
    wait_terminal(stack, good)
    d = stack.client_root / "control/supervisor/executions"
    (d / ("a" * 32 + ".json")).write_text(json.dumps({"schema": "uri.phase2ops.execution.v1", "state": "running"}), encoding="utf-8")   # no id
    (d / ("b" * 32 + ".json")).write_text(json.dumps({"schema": "uri.phase2ops.execution.v1", "execution_id": "c" * 32, "state": "running"}), encoding="utf-8")  # wrong id
    (d / ("d" * 32 + ".json")).write_text(json.dumps({"schema": "uri.phase2ops.execution.v1", "execution_id": "d" * 32, "state": 7}), encoding="utf-8")  # bad state
    (d / ("e" * 32 + ".json")).write_text("[]", encoding="utf-8")
    base = {"schema": "uri.phase2ops.execution.v1", "state": "completed", "code": "SETTLED_VERIFIED"}
    typed = {"1" * 32: {"queued_at": [1]}, "2" * 32: {"proposal": [1]}, "3" * 32: {"evidence": {"x": 1}}, "4" * 32: {"cancel_requested": "yes"},
             "5" * 32: {"task_id": 7}, "6" * 32: {"ended_at": True}, "7" * 32: {"state": "done"}, "8" * 32: {"restart_ledger": "x"},
             # round 3, OPS-2R residual: nested shapes the UI decodes
             "9" * 32: {"proposal": {"proposal_digest": "0" * 64, "provider": [1]}}, "a0" * 16: {"proposal": {"proposal_digest": "0" * 64, "session_id": {"x": 1}}},
             "b0" * 16: {"proposal": {"proposal_digest": "0" * 64, "arguments": [1]}}, "c0" * 16: {"proposal": {"provider": "x"}},
             "d0" * 16: {"evidence": [[1]]}, "e0" * 16: {"proposal": {"proposal_digest": "0" * 64, "reversible": "yes"}},
             # round 4, OPS-2R residual: evidence item contents the card reads
             "f0" * 16: {"evidence": [{"output_sha256": [1]}]}, "f1" * 16: {"evidence": [{"output_bytes": "x"}]},
             "f2" * 16: {"evidence": [{"matched": "yes"}]}, "f3" * 16: {"operation_id": 5}}
    for bad, fields in typed.items():                                # review round 2, OPS-2R: wrong TYPES, valid JSON
        (d / (bad + ".json")).write_text(json.dumps({**base, "execution_id": bad, **fields}), encoding="utf-8")
    rows = {r["execution_id"]: r for r in listing(stack)["executions"]}
    assert rows[good]["state"] == "completed"
    for bad in ("a" * 32, "b" * 32, "d" * 32, "e" * 32, *typed):
        assert rows[bad]["state"] == "uncertain" and rows[bad]["reason"] == "RECORD_SCHEMA", bad
        assert status(stack, bad)["state"] == "uncertain"
    fresh = stack.new_service()                                    # restart reconciliation must not abort either
    assert fresh.executions.startup["executions"] == []            # stubs are already terminal; nothing re-marked
    assert {r["execution_id"] for r in listing(stack, fresh)["executions"]} >= {good, "a" * 32, "e" * 32}
