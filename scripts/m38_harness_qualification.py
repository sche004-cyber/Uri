"""M38 offline harness qualification: fake Claude Code emitting real stream-json, adversarial scenarios, frozen gate.

Writes docs/plans/M38_QUALIFICATION_RESULTS.json. The fake harness (fixtures/m38_harness/fake_claude.py)
exercises the runner, posture, supervision and verification paths deterministically; it says nothing
about a real model's competence (that is the live pilot's job).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.m37_edge_qualification import _Patch, lf  # noqa: E402
from tests.m38_harness_support import escalated, fake_adapter  # noqa: E402
from uri_v1.execution.harness.adapters import FORBIDDEN_FLAGS  # noqa: E402
from uri_v1.execution.harness.contracts import Limits  # noqa: E402
from uri_v1.execution.verify import process_alive  # noqa: E402

GATE = ROOT / "fixtures/m38_harness/threshold_gate.json"
RESULTS = ROOT / "docs/plans/M38_QUALIFICATION_RESULTS.json"
SECRETS = (b"sk-live",)


def _alive(pid: int) -> bool:
    return process_alive(pid)


def run_scenario(name: str, tmp: Path) -> dict:
    env, esc, runner, home = escalated(tmp, _Patch())
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"s": {"command": "x", "env": {"K": "sk-live-SECRET"}}}}))
    saved = dict(os.environ)
    os.environ.update(URI_FAKE_SCENARIO=name, URI_FAKE_ORIGINAL=str(env.root / "report.py"), URI_FAKE_CHILD_PID=str(tmp / "child.pid"),
                      URI_FAKE_ARGV_OUT=str(tmp / "argv.json"))
    try:
        limits = Limits(timeout_s=3, inactivity_s=3) if name.startswith("hang") else Limits(timeout_s=60, inactivity_s=30)
        out = runner.run(esc, fake_adapter(home), session_id="session", limits=limits)
    finally:
        os.environ.clear(); os.environ.update(saved)
    child = tmp / "child.pid"
    unkilled = 0
    if child.exists():
        pid = int(child.read_text()); deadline = time.monotonic() + 5
        while _alive(pid) and time.monotonic() < deadline: time.sleep(0.1)
        unkilled = int(_alive(pid))
    argv = json.loads((tmp / "argv.json").read_text()) if (tmp / "argv.json").exists() else []
    memory_bytes = b"".join(p.read_bytes() for p in env.log.path.rglob("*") if p.is_file())
    records = memory_bytes + env.store.path.read_bytes()
    original_now = hashlib.sha256((env.root / "report.py").read_bytes()).hexdigest()
    original_changed = original_now != esc.inputs[[i.role for i in esc.inputs].index("script")].content_sha256
    return {"scenario": name, "verified": out.verified, "verification_status": out.verification_status,
            "claimed_outcome": out.claimed_outcome, "flags": list(out.safety_flags), "unkilled": unkilled,
            "bypass_flags": sorted(FORBIDDEN_FLAGS.intersection(argv)), "secrets_in_records": any(s in records for s in SECRETS),
            "session_id_in_memory": b"fake-session-0001" in memory_bytes,
            "original_modified": original_changed, "original_modified_detected": "ORIGINAL_MODIFIED_DURING_RUN" in out.safety_flags,
            "metrics": {k: out.metrics.get(k) for k in ("input_tokens", "output_tokens", "cost_usd", "num_turns", "tool_calls",
                                                         "capsule_instructions_bytes", "duration_ms")}}


def main():
    gate = json.loads(lf(GATE))
    runs = []
    for _ in range(gate["runs"]):
        rs = []
        for name in gate["scenarios"]:
            with tempfile.TemporaryDirectory(prefix="m38q-") as d:
                rs.append(run_scenario(name, Path(d)))
        runs.append(rs)
    first = runs[0]; exp = gate["scenarios"]
    def match(r):
        e = exp[r["scenario"]]
        return (r["verified"], r["verification_status"], r["claimed_outcome"], sorted(r["flags"])) == (e["verified"], e["verification_status"], e["claimed_outcome"], sorted(e["flags"]))
    allr = [r for run in runs for r in run]
    m = {"scenario_accuracy": sum(map(match, first)) / len(first),
         "false_verified": sum(1 for r in allr if r["verified"] and not exp[r["scenario"]]["verified"]),
         "originals_modified_undetected": sum(1 for r in allr if r["original_modified"] and not r["original_modified_detected"]),
         "unkilled_processes": sum(r["unkilled"] for r in allr),
         "bypass_flags_emitted": sum(len(r["bypass_flags"]) for r in allr),
         "secrets_in_records": sum(1 for r in allr if r["secrets_in_records"]),
         "session_ids_in_memory": sum(1 for r in allr if r["session_id_in_memory"]),
         "determinism_mismatches": sum(1 for a, b in zip(runs[0], runs[1]) if (a["verified"], a["verification_status"], a["claimed_outcome"], a["flags"]) != (b["verified"], b["verification_status"], b["claimed_outcome"], b["flags"]))}
    ops = {"==": lambda a, b: a == b}
    checks = {k: {"value": m[k], "threshold": v, "pass": ops[v["op"]](m[k], v["value"])} for k, v in gate["thresholds"].items()}
    passed = all(c["pass"] for c in checks.values())
    RESULTS.write_text(json.dumps({"schema_version": "m38.qualification-results.v1", "gate_sha256": hashlib.sha256(lf(GATE)).hexdigest(),
                                   "python": sys.version.split()[0], "platform": sys.platform, "gate_passed": passed,
                                   "checks": checks, "metrics": m, "runs": runs}, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"gate_passed": passed, "metrics": m}, indent=1))
    for r in first: print(r["scenario"], r["verified"], r["verification_status"], r["claimed_outcome"], r["flags"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
