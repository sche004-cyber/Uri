"""Scripted lifecycle worker for the tool's own tests (TEST ONLY, NOT A URI MILESTONE).

Runs as a separate process: reads the prompt on stdin, inspects/edits the checkout in its cwd, prints a result block.
    worker.py reviewer <mode>     modes: check | accept_with_high | always_reject | owner
    worker.py implementer <mode>  modes: fix | protected | notest | marker | noop | break_gate_fix
"""
import json
import re
import subprocess
import sys
from pathlib import Path

role, mode = sys.argv[1], sys.argv[2]
prompt = sys.stdin.read()
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
rnd = (re.search(r"round R(\d+)", prompt) or re.search(r"(\d+)", "1")).group(1)


def review(verdict, findings):
    print("reviewed", head)
    print("AUDIT_RESULT_BEGIN")
    print(json.dumps({"candidate": head, "baseline": "x", "verdict": verdict, "findings": findings,
                      "prior_findings": [], "tests_run": [], "unverified": []}))
    print("AUDIT_RESULT_END")


def finding(sev="HIGH", **kw):
    f = {"id": f"R{rnd}-01", "severity": sev, "blocking": sev != "LOW", "category": "code",
         "title": "safe_div divides by zero", "files": ["pkg/calc.py:2"], "evidence": "safe_div(1, 0) raises",
         "suggested_fix": "return None when b == 0"}
    f.update(kw)
    return f


if "DIAGNOSING a recurring defect" in prompt:  # any worker can be asked for a diagnosis
    print("DIAGNOSIS_BEGIN")
    print(json.dumps({"root_cause": "missing zero check in safe_div", "why_earlier_repairs_failed": "marker files only",
                      "evidence": ["pkg/calc.py:2"], "proposed_fix": "return None when b == 0", "needs_owner": False}))
    print("DIAGNOSIS_END")
    sys.exit(0)
if mode == "quota_once":  # out of quota once (flag next to the worktree), then repairs like "fix"
    flag = Path("..") / "quota_used"
    if not flag.exists():
        flag.write_text("x")
        mode = "quota"
    else:
        mode = "fix"
if mode == "quota":
    sys.stderr.write("API Error: 429 rate limit exceeded, retry later\n")
    sys.exit(1)
if mode == "auth":  # a CLI whose sign-in expired (auditor fallback policy)
    sys.stderr.write("Failed to authenticate: OAuth session expired and could not be refreshed\n")
    sys.exit(1)
if mode == "disconnect":  # the connection drops mid-review: partial output, no result block
    print("reviewing", head)
    sys.exit(1)
if mode == "fail_401":  # a failed review whose own text mentions 401 (not a sign-in failure, S1-02)
    print("the handler returns 401 unauthorized for bad tokens")
    sys.exit(1)
if mode == "wrong_sha_then_disconnect":  # a wrong-SHA result once (flag next to the worktree), then drops (S1-01)
    flag = Path("..") / "wrong_sha_used"
    if flag.exists():
        print("reviewing", head)
        sys.exit(1)
    flag.write_text("x")
    mode = "wrong_sha"
if mode == "disconnect_once":  # drops once (flag next to the worktree), then reviews like "check"
    flag = Path("..") / "disconnect_used"
    if not flag.exists():
        flag.write_text("x")
        print("reviewing", head)
        sys.exit(1)
    mode = "check"

if role == "reviewer":
    src = Path("pkg/calc.py").read_text()
    if mode == "check":
        review("ACCEPT", []) if "b == 0" in src else review("REJECT", [finding()])
    elif mode == "wrong_sha":  # a result for another commit
        head = "0" * 40
        review("ACCEPT", [])
    elif mode == "accept_with_high":
        review("ACCEPT", [finding()])
    elif mode == "always_reject":
        review("REJECT", [finding()])
    elif mode == "new_until_8":  # a genuinely new defect each round, earlier ones confirmed fixed, then accept
        n = int(rnd)
        if n < 8:
            print("AUDIT_RESULT_BEGIN")
            print(json.dumps({"candidate": head, "verdict": "REJECT",
                              "findings": [{"id": f"R{n}-01", "severity": "MEDIUM", "blocking": True, "category": "code",
                                            "title": f"distinct defect number {n} in module m{n}", "files": [f"pkg/m{n}.py:1"]}],
                              "prior_findings": [{"id": f"R{k}-01", "status": "FIXED"} for k in range(1, n)]}))
            print("AUDIT_RESULT_END")
        else:
            review("ACCEPT", [])
    elif mode == "owner":
        review("REJECT", [finding(owner_decision=True, title="fix needs the frozen core module")])
    sys.exit(0)

# implementer
if mode == "break_gate_fix":
    Path("pkg/other.py").write_text("VALUE = 2\n")
elif mode == "fix":
    Path("pkg/calc.py").write_text("def safe_div(a, b):\n    if b == 0:\n        return None\n    return a / b\n")
    Path("tests/test_zero.py").write_text("from pkg.calc import safe_div\n\n\ndef test_zero():\n"
                                          "    assert safe_div(1, 0) is None\n")
elif mode == "helper_fix":  # a helper module under tests/ plus the real test that uses it
    Path("pkg/calc.py").write_text("def safe_div(a, b):\n    if b == 0:\n        return None\n    return a / b\n")
    Path("tests/helpers.py").write_text("ZERO = 0\n")
    Path("tests/test_zero.py").write_text("import os\nimport sys\nsys.path.insert(0, os.path.dirname(__file__))\n"
                                          "from helpers import ZERO  # noqa: E402\nfrom pkg.calc import safe_div  # noqa: E402\n\n\n"
                                          "def test_z():\n    assert safe_div(1, ZERO) is None\n")
elif mode == "protected":
    Path("core/frozen.py").write_text("PATCHED = True\n")
elif mode == "notest":
    Path("pkg/calc.py").write_text("def safe_div(a, b):\n    if b == 0:\n        return None\n    return a / b\n")
elif mode == "marker":
    n = len(list(Path("tests").glob("test_marker_*.py"))) + 1
    Path(f"pkg/marker_{n}.txt").write_text("x")
    Path(f"tests/test_marker_{n}.py").write_text(
        f"from pathlib import Path\n\n\ndef test_marker():\n    assert Path('pkg/marker_{n}.txt').exists()\n")
print("REPAIR_RESULT_BEGIN")
print(json.dumps({"repaired": ["R1-01"], "not_repaired": [], "regression_tests": [], "notes": mode}))
print("REPAIR_RESULT_END")
