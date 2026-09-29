"""M39 repair round 4: regressions for the LOW items of the re-audit of 7838479
(audits/m39_reaudit3, report M39_REPAIR3_REAUDIT_REPORT.md).

- F-1: a concurrent task-head change no longer loses the partial-write record.
- F-2: an interrupt during or after the write is re-raised, but the write is
  recorded first.
- F-3: the benchmark summary names the tasks a dry run cannot measure.
- F-4: "cancel" while a question is pending leaves the task (ABANDONED, from
  the user's own words) instead of being asked again forever.
"""
from __future__ import annotations

import io

import pytest

from uri_v1.execution.workspace import Workspace
from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.office.__main__ import run_repl
from uri_v1.office.view import render
from tests.test_m39_repair3_regressions import SID, _bench, approve, confirmed_start, local_fixable, task_head
from tests.m39_office_support import OfficeEnv


def _to_approval(env):
    original = local_fixable(env)
    step = confirmed_start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step
    return step, original


# -- F-1 -------------------------------------------------------------------------------------------

def test_f1_concurrent_head_change_still_records_the_partial_write(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    step, original = _to_approval(env)

    def checkpoint_then_fail(*a, **k):
        # Another trusted writer advances the task head after the write.
        head = task_head(env, step.task_id)
        turn_id, trace_id = env.turn()
        intake = URIIntake().capture(env.user, SID, turn_id, trace_id, "note", spans={})
        assert env.recorder.task_state(step.task_id, head.record_id, intake=intake,
                                       next_step="concurrent checkpoint").persisted
        raise ValueError("SIMULATED_AFTER_CONCURRENT_CHANGE")
    monkeypatch.setattr(env.recorder, "invoke_verifier", checkpoint_then_fail)

    refused = approve(env, step)
    assert refused.kind == "WRITEBACK_REFUSED"
    assert [w["relpath"] for w in refused.written] == ["report.py"]
    assert (env.root / "report.py").read_text() != original
    assert refused.partial_record == "FAILED"
    head = task_head(env, step.task_id)
    assert head.payload["status"] == "FAILED"
    assert "report.py" in head.payload["next_step"]["text"]


# -- F-2 -------------------------------------------------------------------------------------------

def test_f2_interrupt_after_write_is_reraised_and_recorded(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    step, original = _to_approval(env)

    def interrupt(*a, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(env.recorder, "invoke_verifier", interrupt)

    with pytest.raises(KeyboardInterrupt):
        approve(env, step)
    assert (env.root / "report.py").read_text() != original
    head = task_head(env, step.task_id)
    assert head.payload["status"] == "FAILED"
    assert "INTERRUPTED:KeyboardInterrupt" in head.payload["next_step"]["text"]
    assert "report.py" in head.payload["next_step"]["text"]


def test_f2_interrupt_during_the_write_records_what_landed(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    step, original = _to_approval(env)
    real = Workspace.write_back

    def write_then_interrupt(self, *a, **k):
        real(self, *a, **k)
        raise KeyboardInterrupt()
    monkeypatch.setattr(Workspace, "write_back", write_then_interrupt)

    with pytest.raises(KeyboardInterrupt):
        approve(env, step)
    assert (env.root / "report.py").read_text() != original
    head = task_head(env, step.task_id)
    assert head.payload["status"] == "FAILED"
    assert "INTERRUPTED" in head.payload["next_step"]["text"]


def test_f2_interrupt_before_anything_is_written_leaves_the_task_open(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    step, original = _to_approval(env)

    def interrupt(self, *a, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(Workspace, "write_back", interrupt)

    with pytest.raises(KeyboardInterrupt):
        approve(env, step)
    assert (env.root / "report.py").read_text() == original
    assert task_head(env, step.task_id).payload["status"] == "OPEN"


# -- F-3 -------------------------------------------------------------------------------------------

def test_f3_benchmark_names_what_a_dry_run_cannot_measure(capsys):
    bench = _bench()
    assert bench.main(["--dry-run", "--out", "/dev/null"]) == 0
    err = capsys.readouterr().err
    results = bench.run(dry_run=True, out_path=None)
    capsys.readouterr()
    summary = results["summary"]
    not_measured = summary["not_measured_needs_real_harness"]
    assert not_measured == ["task_05", "task_06", "task_08", "task_09", "task_10"]
    for name in not_measured:
        assert name in err
        assert results["tasks"][name]["arm_b"]["route"] == "HARNESS_FAILED"
    assert "empty fix" in err and "Arm A is a mock" in err


# -- F-4 -------------------------------------------------------------------------------------------

def _repl(env, lines):
    buf = io.StringIO()
    run_repl(env.session, env.user, in_stream=io.StringIO("".join(l + "\n" for l in lines)), out=buf)
    return buf.getvalue()


def test_f4_cancel_while_a_file_question_is_pending_abandons_the_task(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    original = local_fixable(env)
    out = _repl(env, ["make report.py work with sales.xlsx", "cancel", "report.py"])
    assert '"cancel" to stop' in out
    assert "[CANCELLED]" in out
    (row,) = env.session.status()
    assert row["status"] == "ABANDONED"
    # After cancelling, "report.py" is not taken as an answer to the old question.
    assert "[UNSUPPORTED]" in out.split("[CANCELLED]", 1)[1]
    assert (env.root / "report.py").read_text() == original


def test_f4_stop_is_not_a_declaration_and_says_how_to_cancel(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    out = _repl(env, ["make report.py work with sales.xlsx", "stop", "cancel"])
    assert 'type "cancel" on its own' in out
    assert "[CANCELLED]" in out
    assert [r["status"] for r in env.session.status()] == ["ABANDONED"]


def test_f4_memory_round_render_has_no_empty_reason(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    (env.root / "old").mkdir()
    from tests.m39_office_support import SALES, make_workbook
    make_workbook(env.root / "old" / "sales.xlsx", SALES)
    step = confirmed_start(env, "make report.py work with sales.xlsx")
    text = render(step)
    assert "; )" not in text
    assert '"cancel" to stop' in text
