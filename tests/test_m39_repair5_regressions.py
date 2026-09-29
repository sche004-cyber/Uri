"""Regressions for the independent audit of 736464a
(/mnt/project-files/audits/M39_INDEPENDENT_AUDIT_736464a.md).

- F3: the escalation consent screen names the harness and says the file
  contents go to its external model provider (it used to say "never the
  network").
- N3: the HARNESS_FAILED reply no longer says "Nothing was written to your
  files" when the harness itself changed an original during the run.
- N1: M39's own frozen-scope guard fails when a frozen M37/M38 file is rolled
  back to a pre-freeze version (the KNOWN_UPSTREAM_REPAIRS exemption is gone).

F4 (/dev/null) is fixed in place in test_m39_repair4_regressions.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import tests.test_m39_boundaries as boundaries
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.office import request as req
from uri_v1.office.flow import StepResult
from uri_v1.office.view import render
from tests.m39_office_support import answer_asks, request_names, OfficeEnv, SALES, make_workbook, script as script_text

ROOT = Path(__file__).resolve().parents[1]
EVIL = ROOT / "fixtures" / "m39_office" / "evil_claude_office.py"
REQUEST = "make report.py work with sales.xlsx"


def start(env, raw=REQUEST):
    parsed = req.parse(raw)
    assert parsed.ok, parsed
    turn_id, trace_id = env.turn()
    step = env.session.start(raw, session_id="session-r5", turn_id=turn_id, trace_id=trace_id, parsed=parsed)
    return answer_asks(env, step, request_names(raw, parsed), session_id="session-r5")


def confirm(env, task_id, raw="yes, run it"):
    turn_id, trace_id = env.turn()
    return env.session.confirm_escalation(task_id, raw, session_id="session-r5", turn_id=turn_id, trace_id=trace_id)


def escalating_env(tmp, monkeypatch, *, with_harness=True, scenario=None):
    env = OfficeEnv(tmp, monkeypatch, with_harness=with_harness)
    if scenario:
        home = tmp / "home"; home.mkdir(exist_ok=True)
        env.session.adapter = ClaudeCodeAdapter((sys.executable, str(EVIL)), home=home)
        monkeypatch.setenv("URI_PROBE_SCENARIO", scenario)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="Amt"))  # abbreviation forces escalation
    return env


# -- F3 --------------------------------------------------------------------------------------------

def test_f3_escalation_screen_names_the_harness_and_its_external_provider(tmp_path, monkeypatch):
    env = escalating_env(tmp_path, monkeypatch)
    step = start(env)
    assert step.kind == "ESCALATION_PROPOSAL", step
    assert step.harness == "CLAUDE_CODE"
    text = render(step)
    assert "never the network" not in text
    assert "Harness: Claude Code." in text
    assert "sent to Claude Code" in text and "external model provider" in text
    assert "script, workbook" in text
    # The posture line no longer reads as if no data leaves the machine.
    assert "does not stop the file contents above from reaching the provider" in text


def test_f3_escalation_screen_without_a_configured_harness_says_so(tmp_path, monkeypatch):
    env = escalating_env(tmp_path, monkeypatch, with_harness=False)
    step = start(env)
    assert step.kind == "ESCALATION_PROPOSAL", step
    assert step.harness is None
    text = render(step)
    assert "never the network" not in text
    assert "No harness is configured" in text


# -- N3 --------------------------------------------------------------------------------------------

def test_n3_harness_writing_the_original_is_reported_truthfully(tmp_path, monkeypatch):
    """The audit's `write_original` probe: the harness writes the authorized
    report.py itself during the run. URI flags it (unchanged) and the reply
    must now say the original was changed and the task stays open."""
    env = escalating_env(tmp_path, monkeypatch, scenario="write_original")
    monkeypatch.setenv("URI_PROBE_ORIGINAL", str(env.root / "report.py"))
    step = start(env)
    assert step.kind == "ESCALATION_PROPOSAL", step
    result = confirm(env, step.task_id)
    assert result.kind == "HARNESS_FAILED", result
    assert "ORIGINAL_MODIFIED_DURING_RUN" in result.safety_flags
    assert result.originals_changed == ("report.py",)
    assert "written by the harness directly" in (env.root / "report.py").read_text()
    text = render(result)
    assert "Nothing was written" not in text
    assert "your original file(s) were changed during the harness run" in text
    assert "(Claude Code): report.py" in text
    assert "The task stays open and is not complete." in text


def test_n3_original_changed_during_verification_is_reported(tmp_path, monkeypatch):
    env = escalating_env(tmp_path, monkeypatch, scenario="touch_original")
    monkeypatch.setenv("URI_PROBE_ORIGINAL", str(env.root / "sales.xlsx"))
    step = start(env)
    result = confirm(env, step.task_id)
    assert result.kind == "HARNESS_FAILED", result
    assert "ORIGINAL_MODIFIED_DURING_VERIFICATION" in result.safety_flags
    text = render(result)
    assert "Nothing was written" not in text
    assert "changed during verification of the harness's output" in text
    assert "The task stays open" in text


@pytest.mark.parametrize("flags,expect,forbid", [
    ((), "Nothing was written to your files. The task stays open", "changed during"),
    (("CONTAINMENT_VIOLATION",), "URI wrote nothing back to your files.", "Nothing was written"),
    (("PROCESS_NOT_SETTLED",), "URI wrote nothing back to your files.", "Nothing was written"),
    (("ORIGINAL_MODIFIED_DURING_RUN",), "one or more of your original files", "Nothing was written"),
])
def test_n3_render_only_claims_nothing_was_written_without_safety_flags(flags, expect, forbid):
    text = render(StepResult("HARNESS_FAILED", task_id="t", verification_status="FAILED", safety_flags=flags))
    assert expect in text
    assert forbid not in text


# -- N1 --------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def clone(tmp_path_factory):
    dest = tmp_path_factory.mktemp("m39_guard_clone") / "repo"
    subprocess.run(["git", "clone", "-q", "--shared", str(ROOT), str(dest)], check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    subprocess.run(["git", "checkout", "-q", "--detach", head], cwd=dest, check=True)
    return dest


def test_n1_exemption_is_gone():
    assert not hasattr(boundaries, "KNOWN_UPSTREAM_REPAIRS")
    assert not hasattr(boundaries, "_matches_some_upstream_repair")


@pytest.mark.parametrize("rev,relpath", [
    ("763d8e7", "uri_v1/execution/workspace.py"),
    ("763d8e7", "uri_v1/execution/verify.py"),
    ("763d8e7", "uri_v1/edge/resolver.py"),
    ("b013dba", "uri_v1/execution/harness/runner.py"),
    ("b013dba", "uri_v1/execution/harness/contracts.py"),
])
def test_n1_rolling_a_frozen_file_back_to_a_pre_freeze_version_fails_the_guard(clone, monkeypatch, rev, relpath):
    """Run on a disposable clone, never the working checkout."""
    target = clone / relpath
    current = target.read_bytes()
    old = subprocess.check_output(["git", "show", f"{rev}:{relpath}"], cwd=clone)
    assert old != current, "probe must actually roll the file back"
    target.write_bytes(old)
    monkeypatch.setattr(boundaries, "ROOT", clone)
    try:
        with pytest.raises(AssertionError) as info:
            boundaries.test_m36_m37_m38_and_frozen_files_unchanged()
        assert relpath in str(info.value)
    finally:
        target.write_bytes(current)
    boundaries.test_m36_m37_m38_and_frozen_files_unchanged()  # clean clone passes again
