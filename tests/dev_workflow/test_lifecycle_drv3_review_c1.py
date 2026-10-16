"""DEV-LIFECYCLE-3B: imported independent review C1 of fd2b0713 (TEST ONLY).

C1-01 "prepare": false on a Dart command gate (flutter analyze --no-pub) re-opened the analyze false pass;
C1-02 regression proofs for Dart runners had no dependency preparation (infrastructure failure read as a test failure);
C1-03 a test_setup step's own tracked-file changes were attributed to dependency preparation;
C1-04 a justified zero-test run was labelled EXECUTED and a pytest run that collected nothing (exit 5) was a failure.
"""
import sys

from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow.state_machine import WorkflowState as S

from tests.dev_workflow.test_lifecycle import g
from tests.dev_workflow.test_lifecycle_drv3_flutter_gates import fake_tool, flag, flutter_gate, make_dart_fixture, run_cfg

PY = sys.executable


def setup_function():
    getattr(L, "_TOOLCHAIN", {}).clear()


def test_c1_01_prepare_off_command_gate_without_dependencies_blocks(tmp_path):
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    analyze = {"id": "analyze", "kind": "command", "cwd": "app", "cmd": [tool, "analyze", "--no-pub"], "prepare": False}
    cfg = run_cfg(tmp_path, [analyze])
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "RESOURCE" and "INFRA dependencies not available" in s["blocker"]["reason"]
    assert not s["evidence_ok_for_candidate"]


def test_c1_01_prepare_off_is_fine_when_test_setup_provides_the_dependencies(tmp_path):
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    analyze = {"id": "analyze", "kind": "command", "cwd": "app", "cmd": [tool, "analyze", "--no-pub"], "prepare": False}
    cfg = run_cfg(tmp_path, [analyze])
    cfg["test_setup"] = [{"cmd": [tool, "pub", "get"], "cwd": "app"}]
    assert L.run(cfg) == S.VERIFIED


def test_c1_02_regression_proof_prepares_dart_runners(tmp_path):
    repo, wt, base, _ = make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool)])
    cfg["regression_runners"] = [{"suffix": "_test.dart", "cwd": "app", "cmd": [tool, "test", "--no-pub"]}]
    (wt / "app/test").mkdir(exist_ok=True)
    (wt / "app/test/a_test.dart").write_text("// fixture\n")
    g(wt, "add", "-A")
    g(wt, "commit", "-qm", "dart test file")
    sha = g(wt, "rev-parse", "HEAD")
    p = L.regression_proof(cfg, base, sha, ["app/test/a_test.dart"], tmp_path / "p1", need_fail_before=False)
    assert p["ok"], p                                    # prepared: the fake runs its tests on both sides
    flag(tool, "offline_fail")
    p = L.regression_proof(cfg, base, sha, ["app/test/a_test.dart"], tmp_path / "p2", need_fail_before=False)
    assert not p["ok"] and p.get("infra") and p["reason"].startswith("INFRA regression runner"), p


def test_c1_03_test_setup_changes_are_not_blamed_on_preparation(tmp_path):
    make_dart_fixture(tmp_path)
    tool = fake_tool(tmp_path)
    cfg = run_cfg(tmp_path, [flutter_gate(tool)])
    touch = [PY, "-c", "import pathlib; p = pathlib.Path('pkg/calc.py'); p.write_text(p.read_text() + '# setup\\n')"]
    cfg["test_setup"] = [{"cmd": touch}]
    assert L.run(cfg) == S.VERIFIED                      # preparation itself changed nothing tracked


def test_c1_04_justified_zero_test_pytest_gate_is_labelled_and_passes(tmp_path):
    make_dart_fixture(tmp_path)
    gate = {"id": "unit", "kind": "pytest", "cmd": ["{python}", "-m", "pytest", "-q", "app"],
            "allow_zero_tests": "app holds no Python tests by design (fixture)"}
    cfg = run_cfg(tmp_path, [gate])
    assert L.run(cfg) == S.VERIFIED
    c = list(L.status(cfg)["gates"].values())[0]["counts"]["unit"]["candidate"]
    assert c["evidence"] == "ZERO_TESTS_JUSTIFIED" and c["executed"] == 0 and c["failed"] == 0
