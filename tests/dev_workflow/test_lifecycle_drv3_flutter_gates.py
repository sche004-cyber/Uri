"""DEV-LIFECYCLE-3B / DRV-3: gates must give real execution evidence (TEST ONLY).

DRV-3 (UI-V2-COMPLETION-r2, 2026-10-16): the Flutter gates ran with --no-pub in fresh qualify/baseline worktrees that
had no .dart_tool/package_config.json. Both sides failed with "cannot run without a dependency on package:flutter_test"
(no test report); the identical baseline failure was classed historical and the gate reported ok. These tests
reproduce that false pass with a fake `flutter` and pin the repaired behaviour.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow.state_machine import WorkflowState as S

from tests.dev_workflow.test_lifecycle import config, g

FAKE = Path(__file__).parent / "lifecycle_fixture" / "fake_flutter.py"


def fake_tool(tmp: Path) -> str:
    d = tmp / "bin"
    d.mkdir()
    # The driver gives gate commands a copy of the environment taken at import time, so the fake is steered by flag
    # files in its own folder (FAKE_FLAGS), never by variables set during a test.
    if sys.platform == "win32":
        p = d / "flutter.bat"
        p.write_text(f'@set "FAKE_FLAGS={d}"\r\n@"{sys.executable}" "{FAKE}" %*\r\n')
    else:
        p = d / "flutter"
        p.write_text(f'#!/bin/sh\nFAKE_FLAGS="{d}" exec "{sys.executable}" "{FAKE}" "$@"\n')
        p.chmod(0o755)
    return str(p)


def flag(tool: str, name: str, value: str = "1") -> None:
    (Path(tool).parent / name).write_text(value)


def make_dart_fixture(tmp: Path, base_tests="a=pass b=pass", cand_tests="a=pass b=pass"):
    """Repo with a Dart package app/ (pubspec.yaml + pubspec.lock + tests.txt) and a Python test, a bare remote and a
    candidate worktree. tests.txt lists what the fake `flutter test` runs on each side."""
    repo = tmp / "repo"
    repo.mkdir()
    g(repo, "init", "-q", "-b", "canon")
    g(repo, "config", "user.email", "t@example.invalid")
    g(repo, "config", "user.name", "fixture")
    for d in ("pkg", "core", "tests", "app"):
        (repo / d).mkdir()
    (repo / "pkg/__init__.py").write_text("")
    (repo / "pkg/calc.py").write_text("def safe_div(a, b):\n    if b == 0:\n        return None\n    return a / b\n")
    (repo / "core/frozen.py").write_text("FROZEN = True\n")
    (repo / "tests/test_calc.py").write_text("from pkg.calc import safe_div\n\n\ndef test_div():\n"
                                             "    assert safe_div(4, 2) == 2\n")
    (repo / "app/pubspec.yaml").write_text("name: app\n")
    (repo / "app/pubspec.lock").write_text("packages: {}\n")
    (repo / "app/tests.txt").write_text(base_tests + "\n")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n.dart_tool/\n")
    g(repo, "add", "-A")
    g(repo, "commit", "-qm", "baseline")
    base = g(repo, "rev-parse", "HEAD")
    remote = tmp / "canonical.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    g(repo, "remote", "add", "origin", str(remote))
    g(repo, "push", "-q", "origin", "canon")
    wt = tmp / "impl"
    g(repo, "worktree", "add", "-q", "-b", "feature", str(wt), base)
    (wt / "pkg/feature.py").write_text("def feature():\n    return 1\n")
    (wt / "app/tests.txt").write_text(cand_tests + "\n")
    g(wt, "add", "-A")
    g(wt, "commit", "-qm", "feature (candidate)")
    return repo, wt, base, remote


def flutter_gate(tool, **extra):
    return {"id": "flutter", "kind": "flutter", "cwd": "app", "cmd": [tool, "test", "--no-pub"], **extra}


def run_cfg(tmp, gates):
    repo, wt = tmp / "repo", tmp / "impl"
    return config(tmp, repo, wt, implementer="noop", integration={"mode": "none"}, gates=gates)


def setup_function():
    getattr(L, "_TOOLCHAIN", {}).clear()


def test_drv3_original_false_pass_is_now_blocked(tmp_path):
    """The DRV-3 condition exactly: dependency preparation off, both sides cannot run -> BLOCKED, never ok."""
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool, prepare=False)])
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "RESOURCE" and "INFRA no test execution" in s["blocker"]["reason"]
    gate = list(s["gates"].values())[0]
    assert gate["ok"] is False
    c = gate["counts"]["flutter"]
    assert c["candidate"]["evidence"] == "NO_TEST_REPORT" and c["baseline"]["evidence"] == "NO_TEST_REPORT"
    assert c["candidate"]["executed"] == 0 and not s["evidence_ok_for_candidate"]


def test_drv3_dependencies_are_prepared_and_tests_really_execute(tmp_path):
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool),
                             {"id": "analyze", "kind": "command", "cwd": "app", "cmd": [tool, "analyze", "--no-pub"]}])
    assert L.run(cfg) == S.VERIFIED
    s = L.status(cfg)
    gate = list(s["gates"].values())[0]
    assert gate["ok"] is True
    c = gate["counts"]["flutter"]
    assert c["candidate"] == {"status": "COMPLETED_WITH_RESULT", "exit_code": 0, "evidence": "EXECUTED",
                              "executed": 2, "passed": 2, "skipped": 0, "failed": 0, "prepared": True}
    assert c["baseline"]["evidence"] == "EXECUTED" and c["baseline"]["executed"] == 2
    assert gate["counts"]["analyze"]["candidate"]["exit_code"] == 0
    st = L.State(cfg)
    q = st.d["gates"][s["candidate"]]["gates"]["flutter"]["candidate"]
    assert q["prepare"]["cmd"][1:] == ["pub", "get", "--enforce-lockfile", "--offline"]
    assert q["prepare"]["pubspec_lock_sha256"] == L.sha256((tmp_path / "impl/app/pubspec.lock").read_bytes())
    ev = [e for e in L._chained_events(st) if e["kind"] == "QUALIFICATION"][-1]
    assert ev["data"]["counts"]["flutter"]["candidate"]["executed"] == 2  # counts are in the hash chain
    assert L.verify(cfg) == []


def test_drv3_offline_dependency_failure_blocks_transparently(tmp_path):
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    flag(tool, "offline_fail")
    cfg = run_cfg(tmp_path, [flutter_gate(tool)])
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "RESOURCE"
    assert "INFRA dependency preparation failed" in s["blocker"]["reason"] and "version solving failed" in \
        s["blocker"]["reason"]
    assert not s["evidence_ok_for_candidate"]


def test_drv3_candidate_that_cannot_run_is_a_new_failure_against_a_working_baseline(tmp_path):
    """Infrastructure is fine (the baseline runs); the candidate breaks its own test run -> repairable failure."""
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    wt = tmp_path / "impl"
    (wt / "app/pubspec.lock").unlink()  # fake: no lock -> prepare still ok; make the run itself fail instead
    (wt / "app/pubspec.lock").write_text("packages: {}\n")
    (wt / "app/tests.txt").write_text("")
    g(wt, "add", "-A")
    g(wt, "commit", "-qm", "candidate runs no tests")
    cfg = run_cfg(tmp_path, [flutter_gate(tool)])
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    gate = list(s["gates"].values())[-1]
    assert gate["ok"] is False and "flutter::__run__" in gate["new_failures"]["flutter"]
    assert gate["counts"]["flutter"]["candidate"]["evidence"] == "ZERO_TESTS"


def test_drv3_baseline_that_cannot_run_gives_no_excuse(tmp_path):
    """Baseline executes nothing; candidate executes with a failure -> the failure counts as new (strict compare)."""
    make_dart_fixture(tmp_path, base_tests="", cand_tests="a=pass b=fail")
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool)])
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    gate = list(s["gates"].values())[0]
    assert gate["counts"]["flutter"]["baseline"]["evidence"] == "ZERO_TESTS"
    assert gate["new_failures"]["flutter"] == ["test/a_test.dart::b"]


def test_drv3_zero_tests_on_both_sides_blocks_unless_justified(tmp_path):
    make_dart_fixture(tmp_path, base_tests="", cand_tests="")
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool, allow_zero_tests=True)])  # a bare flag is not a justification
    assert L.run(cfg) == S.BLOCKED
    assert "ZERO_TESTS" in L.status(cfg)["blocker"]["reason"]


def test_drv3_zero_tests_with_written_justification_is_allowed(tmp_path):
    make_dart_fixture(tmp_path, base_tests="", cand_tests="")
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool, allow_zero_tests="package has no tests by design (fixture)")])
    assert L.run(cfg) == S.VERIFIED


def test_drv3_pytest_gate_with_no_tests_is_not_a_pass(tmp_path):
    make_dart_fixture(tmp_path)
    cfg = run_cfg(tmp_path, [{"id": "unit", "kind": "pytest", "cmd": ["{python}", "-m", "pytest", "-q", "app"]}])
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert "ZERO_TESTS" in s["blocker"]["reason"] and not s["evidence_ok_for_candidate"]


def test_drv3_baseline_cache_follows_toolchain_and_gate_schema(tmp_path, monkeypatch):
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool)])
    assert L.run(cfg) == S.VERIFIED
    st = L.State(cfg)
    sha = st.d["candidate"]

    def baseline_runs():
        return len([e for e in L._chained_events(L.State(cfg)) if e["kind"] == "BASELINE_GATE"])

    assert baseline_runs() == 1
    L.qualify(cfg, st, sha)  # same toolchain, same schema: cached baseline reused
    assert baseline_runs() == 1
    flag(tool, "rev", "rev2")
    L._TOOLCHAIN.clear()
    st = L.State(cfg)
    L.qualify(cfg, st, sha)
    assert baseline_runs() == 2
    monkeypatch.setattr(L, "GATE_SCHEMA", L.GATE_SCHEMA + 1)
    st = L.State(cfg)
    L.qualify(cfg, st, sha)
    assert baseline_runs() == 3


def test_drv3_python_and_command_gates_keep_their_behaviour(tmp_path):
    make_dart_fixture(tmp_path)
    cfg = run_cfg(tmp_path, [{"id": "unit", "kind": "pytest", "cmd": ["{python}", "-m", "pytest", "-q", "tests"]},
                             {"id": "cmd", "kind": "command", "cmd": ["{python}", "-c", "0"]}])
    assert L.run(cfg) == S.VERIFIED
    c = list(L.status(cfg)["gates"].values())[0]["counts"]
    assert c["unit"]["candidate"]["evidence"] == "EXECUTED" and c["unit"]["candidate"]["passed"] == 1
    assert c["unit"]["candidate"]["prepared"] is False and c["cmd"]["candidate"]["exit_code"] == 0
