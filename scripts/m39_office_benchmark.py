"""Q-O4 VG-1 benchmark driver (M39 plan §5.4). Runs Arms A/B/C against the 12
task fixtures under `fixtures/m39_office/benchmark/`.

`--dry-run` (the default, and the ONLY mode this milestone's own qualification
uses) runs entirely offline: Arm B's harness escalations go through the fake
adapter (`fixtures/m39_office/fake_claude_office.py`, no network, no cost),
and Arm A is a labelled MOCK stand-in (copies the task folder unchanged; it is
NOT a measurement of a real coding agent and every mock result is marked
`"mock": true`). `--live` would run Arm A against a real installed harness and
Arm B's escalations against a real Claude Code CLI -- it is wired for a future
session but INTENTIONALLY REFUSES TO RUN in this one (see `_refuse_live`):
this milestone's implementation session is authorized for dry-run mock mode
only (M39 plan §8 stop conditions; no live spend, no Q-O3/Q-O4 campaign here).

Usage:
    python3 scripts/m39_office_benchmark.py --dry-run [--out results.json]
    python3 scripts/m39_office_benchmark.py --live      # refuses, see above
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openpyxl import load_workbook

from uri_v1.office import request as req
from uri_v1.office.flow import OfficeSession

BENCH = ROOT / "fixtures" / "m39_office" / "benchmark"
GATE = ROOT / "fixtures" / "m39_office" / "viability_gate.json"


def _refuse_live():
    raise SystemExit(
        "REFUSED: --live is not authorized in this session (M39 plan §8 S-5/no-spend; the calling "
        "session's brief explicitly excludes running the live benchmark campaign). Re-run with "
        "--dry-run, or have an authorized session with a granted budget run --live.")


def _read_number(path: Path, sheet="Summary"):
    if not path.is_file():
        return None
    try:
        wb = load_workbook(path, data_only=True)
        ws = wb[sheet] if sheet in wb.sheetnames else wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return None
        return rows[1][0]
    except Exception:
        return None


def _oracle_match(oracle: dict, output_path: Path) -> bool | None:
    """None means "not applicable / no_success expected" (scored separately)."""
    if oracle.get("expected_outcome", "").startswith("no_success"):
        return None
    value = _read_number(output_path)
    if "expected_total" in oracle:
        return value == oracle["expected_total"]
    if "expected_match_count" in oracle:
        return value == oracle["expected_match_count"]
    return None


def _run_office_env(task_dir: Path, scratch: Path):
    """Build a throwaway OfficeEnv-equivalent session over a disposable copy of the task folder."""
    import _pytest.monkeypatch as mp  # test-only dependency, dry-run driver only
    from tests.m39_office_support import OfficeEnv

    monkeypatch = mp.MonkeyPatch()
    env = OfficeEnv(scratch, monkeypatch, with_harness=True)
    for item in task_dir.iterdir():
        if item.name in ("request.txt", "oracle.json", "NOTES.md"):
            continue
        dest = env.root / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    return env, monkeypatch


def _run_arm_b_dry(task_dir: Path, scratch: Path) -> dict:
    raw = (task_dir / "request.txt").read_text().strip()
    oracle = json.loads((task_dir / "oracle.json").read_text())
    env, monkeypatch = _run_office_env(task_dir, scratch)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    # A conservative, generic fake-harness fix: normalize the one thing most
    # of the "outside envelope" tasks need (an abbreviated/synonym header,
    # or a stale workbook path), applied as a plain text substitution -- a
    # stand-in for a real coding agent's judgement, not a claim of one.
    monkeypatch.setenv("URI_FAKE_FIND", "")
    monkeypatch.setenv("URI_FAKE_REPLACE", "")

    interventions = 0
    parsed = req.parse(raw)
    if not parsed.ok:
        return {"route": "UNSUPPORTED_REQUEST", "reason": parsed.reason, "verified": False,
               "oracle_match": None, "interventions": 0, "harness_used": False}
    turn_id, trace_id = env.turn()
    step = env.session.start(raw, session_id="bench", turn_id=turn_id, trace_id=trace_id, parsed=parsed)
    harness_used = False
    for _ in range(4):  # bounded: clarify -> escalate-consent -> approve, never an infinite loop
        if step.kind == "CLARIFY":
            pending = next((rb for rb in step.roles.values() if rb.state == "PENDING"), None)
            if pending is None:
                break
            interventions += 1
            turn_id, trace_id = env.turn()
            # Deterministic, generic "pick the first displayed candidate" answer -- the
            # ambiguous-by-design tasks (task_12) are expected to stay unresolved here.
            step = env.session.answer(step.task_id, "the first one", session_id="bench", turn_id=turn_id,
                                      trace_id=trace_id, round_id=pending.contract_id)
        elif step.kind == "ESCALATION_PROPOSAL":
            interventions += 1
            harness_used = True
            turn_id, trace_id = env.turn()
            step = env.session.confirm_escalation(step.task_id, "yes, run it", session_id="bench",
                                                  turn_id=turn_id, trace_id=trace_id)
        elif step.kind == "AWAITING_APPROVAL":
            interventions += 1
            turn_id, trace_id = env.turn()
            step = env.session.approve_writeback(step.task_id, "approve", run_id=step.run_id,
                                                 relpaths=step.relpaths, session_id="bench",
                                                 turn_id=turn_id, trace_id=trace_id)
        else:
            break

    verified = step.kind == "COMPLETED"
    output = env.root / "summary.xlsx"
    oracle_match = _oracle_match(oracle, output) if verified else (
        True if not verified and oracle.get("expected_outcome", "").startswith("no_success") else False)
    return {"route": step.kind, "reason": getattr(step, "reason", None), "verified": verified,
           "oracle_match": oracle_match, "interventions": interventions, "harness_used": harness_used}


def _run_arm_a_mock(task_dir: Path, scratch: Path) -> dict:
    """Labelled MOCK stand-in only (see module docstring): no coding agent runs here."""
    scratch.mkdir(parents=True, exist_ok=True)
    for item in task_dir.iterdir():
        if item.name in ("request.txt", "oracle.json", "NOTES.md"):
            continue
        dest = scratch / item.name
        if item.is_dir(): shutil.copytree(item, dest)
        else: shutil.copy2(item, dest)
    return {"mock": True, "route": "MOCK_NO_OP", "verified": False, "oracle_match": None, "interventions": 0}


def run(dry_run: bool, out_path: Path | None):
    if not dry_run:
        _refuse_live()
    tasks = sorted(p for p in BENCH.iterdir() if p.is_dir() and p.name.startswith("task_"))
    results = {"mode": "dry-run (mock Arm A, fake-harness Arm B)", "tasks": {}}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for task_dir in tasks:
            oracle = json.loads((task_dir / "oracle.json").read_text())
            arm_a = _run_arm_a_mock(task_dir, tmp / task_dir.name / "arm_a")
            arm_b = _run_arm_b_dry(task_dir, tmp / task_dir.name / "arm_b")
            results["tasks"][task_dir.name] = {"category": oracle.get("category"),
                                               "expected_outcome": oracle.get("expected_outcome"),
                                               "arm_a": arm_a, "arm_b": arm_b}
    summary = {"total_tasks": len(tasks),
              "arm_b_verified": sum(1 for t in results["tasks"].values() if t["arm_b"]["verified"]),
              "arm_b_oracle_confirmed": sum(1 for t in results["tasks"].values() if t["arm_b"]["oracle_match"] is True)}
    results["summary"] = summary
    text = json.dumps(results, indent=2, sort_keys=True, default=str)
    if out_path:
        out_path.write_text(text + "\n")
    else:
        print(text)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="mock/fake-harness mode (default)")
    mode.add_argument("--live", action="store_true", help="real harness + spend; refused in this session")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    run(dry_run=not args.live, out_path=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
