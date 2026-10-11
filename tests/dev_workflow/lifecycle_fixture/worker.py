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


if role == "reviewer":
    src = Path("pkg/calc.py").read_text()
    if mode == "check":
        review("ACCEPT", []) if "b == 0" in src else review("REJECT", [finding()])
    elif mode == "accept_with_high":
        review("ACCEPT", [finding()])
    elif mode == "always_reject":
        review("REJECT", [finding()])
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
