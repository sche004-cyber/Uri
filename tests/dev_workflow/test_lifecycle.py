"""uri-development-lifecycle driver tests (TEST ONLY, NOT A URI MILESTONE).

Every scenario builds a throwaway git fixture (baseline, defective candidate, bare "canonical" remote) and drives
``scripts.dev_workflow.lifecycle`` with scripted reviewer/implementer *processes*
(``lifecycle_fixture/worker.py``). The live demonstration with real separate Claude processes is
``scripts/dev_workflow/lifecycle_demo.py``; scripted processes do not qualify the independence claim.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow.state_machine import InvalidTransitionError, WorkflowState as S

WORKER = Path(__file__).parent / "lifecycle_fixture" / "worker.py"
PY = sys.executable


def g(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout.strip()


def make_fixture(tmp: Path, defect=True, break_other=False):
    repo = tmp / "repo"
    repo.mkdir()
    g(repo, "init", "-q", "-b", "canon")
    g(repo, "config", "user.email", "t@example.invalid")
    g(repo, "config", "user.name", "fixture")
    (repo / "pkg").mkdir()
    (repo / "core").mkdir()
    (repo / "tests").mkdir()
    (repo / "pkg/__init__.py").write_text("")
    (repo / "pkg/calc.py").write_text("def safe_div(a, b):\n    return a / b\n")
    (repo / "pkg/other.py").write_text("VALUE = 2\n")
    (repo / "core/frozen.py").write_text("FROZEN = True\n")
    (repo / "tests/test_calc.py").write_text("from pkg.calc import safe_div\n\n\ndef test_div():\n"
                                             "    assert safe_div(4, 2) == 2\n")
    (repo / "tests/test_other.py").write_text("from pkg.other import VALUE\n\n\ndef test_value():\n"
                                              "    assert VALUE == 2\n")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
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
    if not defect:
        (wt / "pkg/calc.py").write_text("def safe_div(a, b):\n    if b == 0:\n        return None\n    return a / b\n")
    if break_other:
        (wt / "pkg/other.py").write_text("VALUE = 3\n")
    g(wt, "add", "-A")
    g(wt, "commit", "-qm", "feature (candidate)")
    return repo, wt, base, remote


def config(tmp, repo, wt, *, milestone="DEVTEST-LC", reviewer="check", implementer="fix", independent=True,
           integration=None, gates=None, limits=None):
    cfg = {
        "milestone": milestone, "repo": str(repo),
        "baseline": {"ref": "origin/canon"},
        "candidate": {"branch": "feature", "worktree": str(wt)},
        "state_dir": str(tmp / "state"), "work_dir": str(tmp / "work"),
        "acceptance_criteria": ["safe_div(a, 0) returns None", "no change under core/"],
        "protected_paths": ["core/"], "permitted_paths": ["pkg/**", "tests/**"],
        "reviewer": {"provider": "command", "argv": [PY, str(WORKER), "reviewer", reviewer],
                     "counts_as_independent": independent},
        "implementer": {"provider": "command", "argv": [PY, str(WORKER), "implementer", implementer]},
        "regression_runner": ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        "gates": gates if gates is not None else [{"id": "unit", "kind": "pytest", "cmd": ["{python}", "-m", "pytest", "-q", "tests"]}],
        "integration": integration or {"mode": "fast-forward", "remote": "origin", "target_ref": "canon", "authorized": True},
        "commit_trailers": ["Lifecycle-Test: yes"],
    }
    if limits:
        cfg["limits"] = limits
    p = tmp / "cfg.json"
    p.write_text(json.dumps(cfg))
    return L.load_config(p)


def remote_tip(remote):
    return g(remote, "rev-parse", "refs/heads/canon")


# ---------------------------------------------------------------- L-AC1 transitions

def test_illegal_transition_is_refused(tmp_path):
    repo, wt, base, _ = make_fixture(tmp_path)
    st = L.State(config(tmp_path, repo, wt))
    st.to(S.ACCEPTED)
    with pytest.raises(InvalidTransitionError):
        st.to(S.VERIFIED)


# ---------------------------------------------------------------- L-AC5/7/8/13: reject -> repair -> re-audit -> integrate

def test_defect_rejected_repaired_reaudited_and_integrated(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    assert L.run(cfg) == S.COMPLETE
    s = L.status(cfg)
    assert [r["verdict"] for r in s["reviewers"]] == ["REJECT", "ACCEPT"]
    assert s["reviewers"][0]["candidate"] != s["reviewers"][1]["candidate"]
    assert s["reviewers"][1]["candidate"] == s["candidate"]
    rep = s["repairs"][0]
    assert rep["status"] == "COMMITTED" and rep["commit"] == s["candidate"]
    proof = json.loads((tmp_path / "state/repairs/P1/repair.json").read_text())["regression"]
    assert proof["ok"] and proof["tests"]["tests/test_zero.py"]["before_exit"] != 0
    assert proof["tests"]["tests/test_zero.py"]["after_exit"] == 0
    assert "Lifecycle-Test: yes" in g(wt, "log", "-1", "--format=%B")
    assert remote_tip(remote) == s["candidate"]
    assert s["integration"]["status"] == "INTEGRATED" and s["integration"]["target_tip_before"] == base
    assert (tmp_path / "state/RECEIPT.md").is_file() and not L.verify(cfg)
    assert (repo / "core/frozen.py").read_text() == "FROZEN = True\n"


# ---------------------------------------------------------------- L-AC2/3: no false ACCEPT

def test_scripted_reviewer_never_verifies_a_real_milestone(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt, milestone="W9-REAL", independent=False)
    assert L.run(cfg) == S.WAITING_FOR_MODEL
    s = L.status(cfg)
    assert s["reviewers"][0]["status"] == "NOT_INDEPENDENT" and remote_tip(remote) == base
    with pytest.raises(L.LifecycleError):
        config(tmp_path, repo, wt, milestone="W9-REAL", independent=True)


def test_missing_reviewer_cannot_accept_and_rounds_are_bounded(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt, limits={"max_rounds": 2, "max_repair_attempts": 3})
    cfg["reviewer"] = {"provider": "claude_cli", "binary": str(tmp_path / "no-such-claude")}
    assert L.run(cfg) == S.WAITING_FOR_MODEL
    assert L.run(cfg) == S.WAITING_FOR_MODEL
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "ROUND_LIMIT" and all(r["verdict"] is None for r in s["reviewers"])
    assert remote_tip(remote) == base and not s["evidence_ok_for_candidate"]


def test_reviewer_label_accept_with_high_finding_is_reject(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt, reviewer="accept_with_high", implementer="noop",
                 limits={"max_rounds": 6, "max_repair_attempts": 1})
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["reviewers"][0]["reviewer_label"] == "ACCEPT" and s["reviewers"][0]["verdict"] == "REJECT"
    assert remote_tip(remote) == base


# ---------------------------------------------------------------- L-AC6/12: protected path, owner decisions

def test_repair_touching_protected_path_is_refused_and_stops(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt, implementer="protected")
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "OWNER_DECISION" and "core/frozen.py" in s["blocker"]["reason"]
    assert (wt / "core/frozen.py").read_text() == "FROZEN = True\n" and not L.worktree_changes(wt)
    assert len(g(wt, "log", "--format=%H").split()) == 2 and remote_tip(remote) == base


def test_owner_decision_finding_stops_and_unblock_resumes(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt, reviewer="owner")
    assert L.run(cfg) == S.BLOCKED
    assert L.status(cfg)["blocker"]["kind"] == "OWNER_DECISION"
    assert L.unblock(cfg, "owner: proceed with re-review") == S.READY_TO_RESUME
    assert L.run(cfg) == S.BLOCKED
    assert len(L.status(cfg)["reviewers"]) == 2


def test_integration_without_owner_authorisation_stops_with_command(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt, integration={"mode": "fast-forward", "remote": "origin", "target_ref": "canon",
                                                  "authorized": False})
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "OWNER_AUTHORIZATION" and s["blocker"]["needs"].startswith("git push origin ")
    assert remote_tip(remote) == base


# ---------------------------------------------------------------- L-AC7: regression proof required

def test_repair_without_regression_test_is_not_committed(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt, implementer="notest")
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "REPAIR_FAILED" and len(s["repairs"]) == 3
    assert all(r["status"] == "REFUSED" and r["reason"].startswith("REGRESSION") for r in s["repairs"])
    assert len(g(wt, "log", "--format=%H").split()) == 2


# ---------------------------------------------------------------- L-AC9: retry limit

def test_same_finding_after_three_repairs_stops(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt, reviewer="always_reject", implementer="marker")
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "RETRY_LIMIT"
    assert [r["status"] for r in s["repairs"]] == ["COMMITTED"] * 3 and len(s["reviewers"]) == 4
    assert remote_tip(remote) == base


# ---------------------------------------------------------------- L-AC10: gates by identity, failure blocks integration

def test_new_gate_failure_prevents_integration(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False, break_other=True)
    cfg = config(tmp_path, repo, wt, implementer="noop")
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    gate = list(s["gates"].values())[0]
    assert gate["ok"] is False and gate["new_failures"]["unit"] == ["tests.test_other::test_value"]
    assert remote_tip(remote) == base and s["integration"] is None


def test_gate_failure_is_routed_to_repair_and_then_reaudited(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False, break_other=True)
    cfg = config(tmp_path, repo, wt, implementer="break_gate_fix")
    assert L.run(cfg) == S.COMPLETE
    s = L.status(cfg)
    assert s["repairs"][0]["addresses"][0].startswith("GATE-unit")
    assert len(s["reviewers"]) == 2 and remote_tip(remote) == s["candidate"]


def test_compare_by_identity_and_cause():
    base = {"failures": {"a::x": "ImportError", "a::y": "AssertionError"}}
    cand = {"failures": {"a::x": "ImportError", "a::y": "KeyError", "a::z": "AssertionError", "f::q": "Timeout"}}
    c = L.compare(cand, base, ["f::*"])
    assert c["new_failures"] == ["a::z"] and c["changed_cause"] == ["a::y"] and not c["ok"]
    assert c["historical_failures"] == ["a::x", "a::y"]


def test_flutter_machine_parser():
    lines = [{"type": "testStart", "test": {"id": 1, "name": "loading", "url": "f.dart"}},
             {"type": "testDone", "testID": 1, "result": "success", "hidden": True},
             {"type": "testStart", "test": {"id": 2, "name": "renders", "url": "package:flutter_test/src/widget_tester.dart",
                                            "root_url": "file:///tmp/wt_a/uri_ui/test/f_test.dart"}},
             {"type": "error", "testID": 2, "error": "TestFailure: Expected: 1"},
             {"type": "testDone", "testID": 2, "result": "failure"},
             {"type": "testStart", "test": {"id": 3, "name": "ok", "url": "f.dart"}},
             {"type": "testDone", "testID": 3, "result": "success", "skipped": True}]
    r = L.parse_flutter_machine("\n".join(json.dumps(x) for x in lines))
    assert r["failures"] == {"test/f_test.dart::renders": "TestFailure"} and (r["passed"], r["skipped"]) == (0, 1)
    assert r["ids"] == ["test/f_test.dart::renders", "f.dart::ok"] and r["parsed"] is False  # no "done" event


def test_gpu_gate_without_lease_blocks(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt, gates=[{"id": "gpu", "kind": "command", "gpu": True, "cmd": ["{python}", "-c", "0"]}])
    assert L.run(cfg) == S.BLOCKED
    assert L.status(cfg)["blocker"]["kind"] == "RESOURCE" and remote_tip(remote) == base


# ---------------------------------------------------------------- L-AC14: resume without bypass

def test_interrupted_run_resumes_and_tampering_cannot_skip_gates(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt, integration={"mode": "none"})
    assert L.run(cfg, max_steps=3) == S.BLOCKED  # interrupted (step limit) after the review
    assert L.status(cfg)["blocker"]["kind"] == "STEP_LIMIT"
    L.unblock(cfg, "resume after interruption")
    assert L.run(cfg) == S.VERIFIED
    # a commit made outside the driver after VERIFIED invalidates the evidence
    (wt / "pkg/feature.py").write_text("def feature():\n    return 2\n")
    g(wt, "commit", "-qam", "outside change")
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "EVIDENCE" and s["candidate"] == g(wt, "rev-parse", "HEAD")
    assert not s["evidence_ok_for_candidate"]


def test_forged_stage_without_evidence_is_blocked(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    st = L.State(cfg)
    L.init(cfg, st)
    st.d["stage"] = "VERIFIED"  # forged
    st.save()
    assert L.run(cfg) == S.BLOCKED
    assert L.status(cfg)["blocker"]["kind"] == "TAMPER" and remote_tip(remote) == base


# ---------------------------------------------------------------- L-AC15: tamper-evident receipts

def test_verify_detects_rewritten_verdict(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    L.run(cfg)
    assert L.verify(cfg) == []
    p = tmp_path / "state/rounds/R1/round.json"
    rec = json.loads(p.read_text())
    rec["effective_verdict"] = "ACCEPT"
    p.write_text(json.dumps(rec))
    errs = L.verify(cfg)
    assert any("R1 round.json missing or changed" in e for e in errs)
    assert L.run(cfg) == S.COMPLETE
    assert json.loads((tmp_path / "state/events.jsonl").read_text().splitlines()[-1])["kind"] == "TAMPER_DETECTED"


# ---------------------------------------------------------------- L-AC16: status + A2UI

def test_status_surface_is_valid_a2ui(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    L.run(cfg)
    surf = L.status_surface(cfg)
    msgs = surf.messages()
    assert msgs[0]["createSurface"]["surfaceId"].startswith("dev.lifecycle.")
    texts = json.dumps(msgs)
    assert "COMPLETE" in texts and "R2" in texts


# ---------------------------------------------------------------- relayed reviews only tighten

def _relayed(tmp_path, wt, verdict, findings):
    f = tmp_path / "relayed.txt"
    head = g(wt, "rev-parse", "HEAD")
    f.write_text("summary\nAUDIT_RESULT_BEGIN\n" + json.dumps({"candidate": head, "verdict": verdict,
                                                                "findings": findings}) + "\nAUDIT_RESULT_END\n")
    return f


def test_imported_reject_is_routed_to_repair(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    f = _relayed(tmp_path, wt, "REJECT", [{"id": "X1", "severity": "MEDIUM", "blocking": True, "category": "code",
                                           "title": "safe_div divides by zero", "files": ["pkg/calc.py:2"]},
                                          {"id": "X2", "severity": "MEDIUM", "blocking": False, "title": "minor"}])
    assert L.import_review(cfg, f, "ccr_session", "session_x", "remote") == S.FIXING
    assert L.run(cfg) == S.COMPLETE
    s = L.status(cfg)
    assert s["reviewers"][0]["independent"] is False and s["reviewers"][-1]["independent"] is True
    assert s["repairs"][0]["addresses"] == ["X1"] and not L.verify(cfg)


def test_imported_accept_is_never_evidence(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt)
    assert L.import_review(cfg, _relayed(tmp_path, wt, "ACCEPT", []), "ccr_session", "s", "remote") == S.AUDITING
    st = L.State(cfg)
    assert L.accepted_review(cfg, st, st.d["candidate"]) is None
    assert L.run(cfg) == S.COMPLETE
    assert len(L.status(cfg)["reviewers"]) == 2  # a real review ran after the import


def test_regression_proof_rules(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    st = L.State(cfg)
    L.init(cfg, st)
    sha = g(wt, "rev-parse", "HEAD")

    def commit(files):
        for k, v in files.items():
            (wt / k).write_text(v)
        g(wt, "add", "-A")
        g(wt, "commit", "-qm", "x")
        return g(wt, "rev-parse", "HEAD")
    feat = "from pkg.feature import feature\n\n\ndef test_f():\n    assert feature() == 1\n"
    c1 = commit({"tests/test_feature.py": feat})
    # a coverage-only test passes before: fine for a coverage finding, not enough for a defect
    assert L.regression_proof(cfg, sha, c1, ["tests/test_feature.py"], tmp_path / "p1", need_fail_before=False)["ok"]
    p = L.regression_proof(cfg, sha, c1, ["tests/test_feature.py"], tmp_path / "p2", need_fail_before=True)
    assert not p["ok"] and "no regression test fails" in p["reason"]
    c2 = commit({"pkg/calc.py": "def safe_div(a, b):\n    if b == 0:\n        return None\n    return a / b\n",
                 "tests/test_zero.py": "from pkg.calc import safe_div\n\n\ndef test_z():\n    assert safe_div(1, 0) is None\n"})
    p = L.regression_proof(cfg, sha, c2, ["tests/test_feature.py", "tests/test_zero.py"], tmp_path / "p3")
    assert p["ok"] and p["tests"]["tests/test_zero.py"]["before_exit"] != 0
    p = L.regression_proof(cfg, sha, c2, ["tests/test_feature.py"], tmp_path / "p4", need_fail_before=False,
                           must_fail={"tests/test_feature.py"})
    assert not p["ok"] and "gate test" in p["reason"]
    # a hanging regression test is a refusal, not a crash (DEV-LIFECYCLE-1 R1-08)
    c3 = commit({"tests/test_hang.py": "import time\n\n\ndef test_h():\n    time.sleep(30)\n"})
    cfg["regression_runners"] = [{"suffix": "test_hang.py", "cmd": cfg["regression_runner"], "timeout_s": 2}]
    p = L.regression_proof(cfg, sha, c3, ["tests/test_hang.py"], tmp_path / "p5", need_fail_before=False)
    assert not p["ok"] and p["tests"]["tests/test_hang.py"]["after_state"] == "TIMED_OUT"


def test_reviewer_that_touches_the_implementation_worktree_is_not_independent(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt)
    script = tmp_path / "evil_reviewer.py"
    script.write_text(
        "import sys, subprocess, json\nsys.stdin.read()\n"
        f"open({str(wt / 'pkg/calc.py')!r}, 'a').write('# tampered\\n')\n"
        "h = subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()\n"
        "print('AUDIT_RESULT_BEGIN'); print(json.dumps({'candidate': h, 'verdict': 'ACCEPT', 'findings': []}))\n"
        "print('AUDIT_RESULT_END')\n")
    cfg["reviewer"] = {"provider": "command", "argv": [PY, str(script)], "counts_as_independent": True}
    assert L.run(cfg) == S.WAITING_FOR_MODEL
    r = L.status(cfg)["reviewers"][0]
    assert r["independent"] is False and r["status"] == "NOT_INDEPENDENT" and remote_tip(remote) == base


def test_worker_timeout_kills_the_process_group(tmp_path):
    from scripts.dev_workflow.lifecycle_providers import run_worker
    script = tmp_path / "slow.py"
    child = tmp_path / "child.py"
    marker = tmp_path / "child_alive"
    child.write_text(f"import time\ntime.sleep(3)\nopen({str(marker)!r}, 'w').close()\n")
    script.write_text(f"import subprocess, sys, time\nsubprocess.Popen([sys.executable, {str(child)!r}])\ntime.sleep(30)\n")
    rec = run_worker({"provider": "command", "argv": [PY, str(script)]}, "reviewer", "", tmp_path, tmp_path / "log",
                     timeout_s=1)
    import time
    time.sleep(4)
    assert rec["status"] == "TIMED_OUT" and not marker.exists()



# ---------------------------------------------------------------- DEV-LIFECYCLE-1 R1 regressions

def _script_worker(tmp_path, name, body):
    f = tmp_path / name
    f.write_text("import sys, json, subprocess, os\nsys.stdin.read()\n" + body)
    return [PY, str(f)]


def test_r1_01_forged_reviewer_binary_is_not_independent(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = json.loads((config(tmp_path, repo, wt, milestone="W9-REAL", independent=False) and
                      (tmp_path / "cfg.json")).read_text())
    cfg["reviewer"] = {"provider": "claude_cli", "binary": "/bin/echo"}
    p = tmp_path / "forged.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(L.LifecycleError, match="binary override"):
        L.load_config(p)
    # and a round produced by a non-default executable is never independent for a real milestone
    rec = {"integrity": {"ok": True}, "worker": {"provider": "claude_cli", "status": "COMPLETED", "session_id": "x",
                                                 "binary_is_default": False, "binary_realpath": "/tmp/fake"}}
    ok, why = L.is_independent({"milestone": "W9-REAL", "reviewer": {}}, rec)
    assert not ok and "not the installed CLI" in why


def test_r1_02_edited_state_verdict_is_detected_and_blocks(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt, reviewer="always_reject", implementer="noop",
                 limits={"max_rounds": 6, "max_repair_attempts": 1})
    assert L.run(cfg) == S.BLOCKED
    sp = tmp_path / "state/state.json"
    d = json.loads(sp.read_text())
    d["rounds"][0]["effective_verdict"] = "ACCEPT"
    d["rounds"][0]["result"]["findings"] = []
    d["stage"], d["blocker"] = "VERIFYING", None
    sp.write_text(json.dumps(d))
    assert any("differs" in e for e in L.verify(cfg))
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "TAMPER" and remote_tip(remote) == base


def test_r1_03_planted_hook_cannot_smuggle_files_into_the_repair(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    hooks = Path(g(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "hooks"
    cfg["implementer"] = {"provider": "command", "argv": _script_worker(tmp_path, "hooker.py", f"""
open('pkg/calc.py','w').write('def safe_div(a, b):\\n    if b == 0:\\n        return None\\n    return a / b\\n')
open('tests/test_zero.py','w').write('from pkg.calc import safe_div\\n\\n\\ndef test_z():\\n    assert safe_div(1, 0) is None\\n')
h = {str(hooks)!r} + '/pre-commit'
open(h,'w').write('#!/bin/sh\\necho x > OUT_OF_SCOPE.txt; echo P > core/frozen.py; git add OUT_OF_SCOPE.txt core/frozen.py\\n')
os.chmod(h, 0o755)
""")}
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "TAMPER" and "hooks" in s["blocker"]["reason"]
    assert len(g(wt, "log", "--format=%H").split()) == 2 and not L.worktree_changes(wt)
    assert (wt / "core/frozen.py").read_text() == "FROZEN = True\n" and remote_tip(remote) == base


def test_r1_03_driver_git_ignores_hooks(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    hooks = Path(g(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "hooks"
    (hooks / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
    (hooks / "pre-commit").chmod(0o755)
    (wt / "pkg/x.py").write_text("X = 1\n")
    L.git(wt, "add", "-A")
    L.git(wt, "commit", "-qm", "driver commit despite a failing hook")
    assert "driver commit" in g(wt, "log", "-1", "--format=%s")


def test_r1_04_crashed_or_empty_test_run_is_a_failure(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    (wt / "tests/conftest.py").write_text("raise ImportError('boom')\n")
    g(wt, "add", "-A")
    g(wt, "commit", "-qm", "broken conftest")
    cfg = config(tmp_path, repo, wt, implementer="noop", limits={"max_rounds": 6, "max_repair_attempts": 1})
    assert L.run(cfg) == S.BLOCKED
    gate = list(L.status(cfg)["gates"].values())[0]
    assert gate["ok"] is False and "unit::__run__" in gate["new_failures"]["unit"]


def test_r1_04_vanished_tests_are_failures():
    base = {"failures": {}, "ids": ["a::x", "a::y"]}
    cand = {"failures": {}, "ids": ["a::x"]}
    c = L.compare(cand, base, [])
    assert c["vanished"] == ["a::y"] and not c["ok"]


def test_r1_05_uncommitted_files_do_not_decide_the_gates(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False, break_other=True)
    (wt / "pkg/other.py").write_text("VALUE = 2\n")  # uncommitted "fix" in the implementation worktree
    cfg = config(tmp_path, repo, wt)
    st = L.State(cfg)
    L.init(cfg, st)
    q = L.qualify(cfg, st, g(wt, "rev-parse", "HEAD"))
    assert not q["ok"] and q["gates"]["unit"]["comparison"]["new_failures"] == ["tests.test_other::test_value"]


def test_r1_06_detached_child_of_a_worker_is_killed(tmp_path):
    from scripts.dev_workflow.lifecycle_providers import run_worker
    marker = tmp_path / "late"
    argv = _script_worker(tmp_path, "late.py", f"subprocess.Popen(['sh','-c','sleep 2; echo LATE > {marker}'],"
                                                "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n")
    rec = run_worker({"provider": "command", "argv": argv}, "implementer", "", tmp_path, tmp_path / "log")
    import time
    time.sleep(3)
    assert rec["status"] == "COMPLETED" and not marker.exists()


def test_r1_07_refused_repair_leaves_no_staged_files(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    cfg["implementer"] = {"provider": "command", "argv": _script_worker(tmp_path, "stager.py", """
open('pkg/newfile.py','w').write('N = 1\\n')
subprocess.run(['git','add','pkg/newfile.py'])
open('core/frozen.py','w').write('P = 1\\n')
""")}
    assert L.run(cfg) == S.BLOCKED
    assert L.status(cfg)["blocker"]["kind"] == "OWNER_DECISION"
    assert not L.worktree_changes(wt) and not (wt / "pkg/newfile.py").exists()


def test_r1_09_malformed_severity_is_blocking():
    for f in ({"severity": "High"}, {"severity": "MEDIUM", "blocking": "true"}, {"severity": "MEDIUM"},
              {"severity": "critical"}, {"severity": "LOW", "blocking": "True"}):
        assert L.effective_verdict({"verdict": "ACCEPT", "findings": [f]})[0] == "REJECT", f
    assert L.effective_verdict({"verdict": "accept", "findings": [{"severity": "LOW"}]})[0] == "ACCEPT WITH FINDINGS"
    assert L.effective_verdict({"verdict": "ACCEPT", "findings": [{"severity": "MEDIUM", "blocking": False}]})[0] \
        == "ACCEPT WITH FINDINGS"


def test_r1_10_test_substring_is_not_devtest(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    assert not L.is_devtest("W2_TEST_COVERAGE") and L.is_devtest("DEVTEST-LC")
    with pytest.raises(L.LifecycleError):
        config(tmp_path, repo, wt, milestone="W2_TEST_COVERAGE", independent=True)


def test_c1_unrelated_branch_moves_do_not_break_integrity(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt)
    script = _script_worker(tmp_path, "rev_other.py", f"""
subprocess.run(['git','-C',{str(repo)!r},'branch','-f','someone-else',{base!r}])
h = subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
print('AUDIT_RESULT_BEGIN'); print(json.dumps({{'candidate': h, 'verdict': 'ACCEPT', 'findings': []}})); print('AUDIT_RESULT_END')
""")
    cfg["reviewer"] = {"provider": "command", "argv": script, "counts_as_independent": True}
    assert L.run(cfg) == S.COMPLETE
