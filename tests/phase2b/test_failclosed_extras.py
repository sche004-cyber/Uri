"""Fail-closed extras: an unverified ticket path, and the new Phase 2A postcondition checker."""
from pathlib import Path

from phase2b.conftest import CLAUDE
from uri_supervisor.postconditions import CHECKERS, EvalContext


def test_runner_without_its_own_ticket_validation_never_executes(bridge_stack, monkeypatch):
    """If a journal was injected whose validation never goes through the runner (so the bridge never saw a verified
    ticket), the bridge refuses before starting anything: NOT_STARTED, settled failed, no task, no effect."""
    from uri_core.client_runtime.execution_journal import ExecutionJournal
    s = bridge_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    s.runner.journal = ExecutionJournal(s.cm.data["client_root"], validate_ticket=lambda value: True)
    final = s.run()
    assert final["code"] == "SETTLED_FAILED", final
    assert s.L.q1("SELECT COUNT(*) FROM task")[0] == 0 and s.result_files() == []


def test_file_regular_nonempty_checker(tmp_path):
    fn = CHECKERS["file_regular_nonempty"]
    ctx = EvalContext({}, None, "recovery")
    missing = tmp_path / "missing.txt"
    assert fn({"path": str(missing)}, ctx).status == "FAIL"
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    assert fn({"path": str(empty)}, ctx).status == "FAIL"
    d = tmp_path / "dir.txt"
    d.mkdir()
    assert fn({"path": str(d)}, ctx).status == "FAIL"
    ok = tmp_path / "ok.txt"
    ok.write_text("x")
    c = fn({"path": str(ok)}, ctx)
    assert c.status == "PASS" and c.observation["bytes"] == 1
