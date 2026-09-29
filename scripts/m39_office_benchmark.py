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


_NOT_INPUTS = ("request.txt", "oracle.json", "NOTES.md")


def _expects_success(oracle: dict) -> bool:
    return not oracle.get("expected_outcome", "").startswith("no_success")


def _oracle_env() -> dict:
    """Minimal environment for the oracle run: no credentials or API keys."""
    import os
    keep = ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")
    return {k: os.environ[k] for k in keep if k in os.environ}


def _run_returned_script(folder: Path, scratch: Path):
    """Re-audit R2-4 (repair round 3): score what URI actually returned.

    Write-back only copies back the *modified* inputs (the script); it never
    returns the script's output file, so the oracle used to read a
    `summary.xlsx` that could not exist. Instead, copy the user's folder as
    it stands after write-back into a disposable directory, run the returned
    `report.py` there (offline, bounded), and read the `summary.xlsx` it
    produces. Returns (value, detail)."""
    import subprocess

    run_dir = scratch / "oracle_run"
    shutil.copytree(folder, run_dir, ignore=shutil.ignore_patterns(".uri-office", "__pycache__"))
    try:
        proc = subprocess.run([sys.executable, "report.py"], cwd=run_dir, capture_output=True, text=True,
                              timeout=60, env=_oracle_env())
    except subprocess.TimeoutExpired:
        return None, "ORACLE_SCRIPT_TIMEOUT"
    if proc.returncode != 0:
        return None, f"ORACLE_SCRIPT_EXIT_{proc.returncode}"
    value = _read_number(run_dir / "summary.xlsx")
    return value, None if value is not None else "ORACLE_NO_SUMMARY"


def _oracle_match(oracle: dict, value) -> bool | None:
    if not _expects_success(oracle):
        return None
    if "expected_total" in oracle:
        return value == oracle["expected_total"]
    if "expected_match_count" in oracle:
        return value == oracle["expected_match_count"]
    return None


def _file_hashes(folder: Path) -> dict:
    import hashlib
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.iterdir() if p.is_file() and p.name not in _NOT_INPUTS}


def _run_office_env(task_dir: Path, scratch: Path):
    """Build a throwaway OfficeEnv-equivalent session over a disposable copy of the task folder."""
    import _pytest.monkeypatch as mp  # test-only dependency, dry-run driver only
    from tests.m39_office_support import OfficeEnv

    monkeypatch = mp.MonkeyPatch()
    env = OfficeEnv(scratch, monkeypatch, with_harness=True)
    for item in task_dir.iterdir():
        if item.name in _NOT_INPUTS:
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
    try:
        return _drive_arm_b(env, monkeypatch, raw, oracle, scratch)
    finally:
        monkeypatch.undo()


def _drive_arm_b(env, monkeypatch, raw, oracle, scratch) -> dict:
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    # A conservative, generic fake-harness fix: normalize the one thing most
    # of the "outside envelope" tasks need (an abbreviated/synonym header,
    # or a stale workbook path), applied as a plain text substitution -- a
    # stand-in for a real coding agent's judgement, not a claim of one.
    monkeypatch.setenv("URI_FAKE_FIND", "")
    monkeypatch.setenv("URI_FAKE_REPLACE", "")

    before = _file_hashes(env.root)
    interventions = 0
    approved = False
    parsed = req.parse(raw)
    if not parsed.ok:
        return {"route": "UNSUPPORTED_REQUEST", "reason": parsed.reason, "completed": False,
                "oracle_match": None, "correct": not _expects_success(oracle), "interventions": 0,
                "harness_used": False, "modified_without_approval": [], "wrong_binding": False}
    names = {role: raw[a:b] for role, (a, b) in parsed.spans.items()}
    turn_id, trace_id = env.turn()
    step = env.session.start(raw, session_id="bench", turn_id=turn_id, trace_id=trace_id, parsed=parsed)
    harness_used = False
    wrong_binding = False
    answered_rounds = set()
    memory_answered = False
    for _ in range(8):  # bounded: two per-file asks, clarify, escalate-consent, approve -- never an infinite loop
        if step.kind == "CLARIFY":
            pending = next((rb for rb in step.roles.values() if rb.state == "PENDING" and rb.contract_id), None)
            if pending is None or pending.contract_id in answered_rounds or (not pending.ask and memory_answered):
                break  # one generic answer per Memory round at most; the user would stop there too
            answered_rounds.add(pending.contract_id)
            memory_answered = memory_answered or not pending.ask
            interventions += 1
            turn_id, trace_id = env.turn()
            # Per-file questions (R2-1, frozen M36 line) are answered with the
            # name the request itself used, exactly what the user would type.
            # A Memory round gets a deterministic, generic "pick the first
            # displayed candidate" answer -- the ambiguous-by-design task
            # (task_12) is expected to stay unresolved here.
            text = names[pending.ref_key] if pending.ask else "the first one"
            step = env.session.answer(step.task_id, text, session_id="bench", turn_id=turn_id,
                                      trace_id=trace_id, round_id=pending.contract_id)
        elif step.kind == "ESCALATION_PROPOSAL":
            interventions += 1
            harness_used = True
            turn_id, trace_id = env.turn()
            step = env.session.confirm_escalation(step.task_id, "yes, run it", session_id="bench",
                                                  turn_id=turn_id, trace_id=trace_id)
        elif step.kind == "AWAITING_APPROVAL":
            interventions += 1
            approved = True
            turn_id, trace_id = env.turn()
            step = env.session.approve_writeback(step.task_id, "approve", run_id=step.run_id,
                                                 relpaths=step.relpaths, session_id="bench",
                                                 turn_id=turn_id, trace_id=trace_id)
        else:
            break

    # Hard gates, from live files and Memory -- never from the step alone.
    after = _file_hashes(env.root)
    changed = sorted(n for n in before if after.get(n) != before[n])
    modified_without_approval = changed if not approved else []
    task_row = next((r for r in env.session.status() if r["task_id"] == step.task_id), None) if step.task_id else None
    if task_row and task_row["references"]:
        # wrong_file_binding: every file the request named must be one of
        # the files the task actually bound (phrases like "the spreadsheet"
        # are not checked here -- they are resolved by clarification).
        by_id = {l.source_id: l.relpath.casefold() for l in env.sources.scan().locators}
        bound = {by_id.get(r["source_id"]) for r in task_row["references"]}
        named = {n.casefold() for n in names.values() if n.casefold().endswith((".py", ".xlsx", ".xlsm"))}
        wrong_binding = not named <= bound
    completed = step.kind == "COMPLETED"
    if completed and task_row and task_row["status"] != "COMPLETED":
        completed = False  # a COMPLETED step Memory does not back is not a completion
    # What URI returned: the written-back files (COMPLETED), or the user's
    # unchanged files when URI verified they already work (NOTHING_TO_WRITE).
    returned = completed or step.kind == "NOTHING_TO_WRITE"
    value = detail = None
    if returned:
        value, detail = _run_returned_script(env.root, scratch)
    match = _oracle_match(oracle, value) if returned else None
    if _expects_success(oracle):
        correct = returned and match is True
    else:
        correct = not completed and not changed
    return {"route": step.kind, "reason": getattr(step, "reason", None), "completed": completed,
            "memory_status": task_row["status"] if task_row else None,
            "oracle_value": value, "oracle_detail": detail, "oracle_match": match,
            "false_verified": returned and match is False,
            "correct": correct, "interventions": interventions, "harness_used": harness_used,
            "files_changed": changed, "modified_without_approval": modified_without_approval,
            "wrong_binding": wrong_binding}


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
    arm_b = [t["arm_b"] for t in results["tasks"].values()]
    in_envelope = {name for name, t in results["tasks"].items() if str(t["category"]).startswith("in_envelope")}
    no_success = {name for name, t in results["tasks"].items() if str(t["expected_outcome"]).startswith("no_success")}
    summary = {"total_tasks": len(tasks),
              "arm_b_completed": sum(1 for b in arm_b if b["completed"]),
              "arm_b_verified_nothing_to_write": sum(1 for b in arm_b if b["route"] == "NOTHING_TO_WRITE"),
              # Successes the oracle confirmed by running the returned script;
              # no_success tasks are counted separately, never as confirmed successes.
              "arm_b_oracle_confirmed": sum(1 for b in arm_b if b["oracle_match"] is True),
              "arm_b_no_success_correctly_refused": sum(1 for n in no_success if results["tasks"][n]["arm_b"]["correct"]),
              "no_success_tasks": len(no_success),
              "hard_gates": {
                  "oracle_false_verified": sum(1 for b in arm_b if b["false_verified"]),
                  "originals_modified_without_approval": sum(1 for b in arm_b if b["modified_without_approval"]),
                  "wrong_file_binding_acted_on": sum(1 for b in arm_b if b["wrong_binding"] and b["files_changed"]),
              }}
    # Dry-run gate (fails loudly, exit 1): any hard gate > 0, any in-envelope
    # task (Edge can do it offline) not oracle-confirmed, or any no_success
    # task not correctly refused. Outside-envelope tasks depend on the fake
    # harness's (empty) fix and are reported, not gated.
    failures = [f"hard gate {k} = {v}" for k, v in summary["hard_gates"].items() if v]
    failures += [f"{n}: in-envelope task not oracle-confirmed ({results['tasks'][n]['arm_b']['route']})"
                 for n in sorted(in_envelope) if not results["tasks"][n]["arm_b"]["correct"]]
    failures += [f"{n}: no_success task not correctly refused ({results['tasks'][n]['arm_b']['route']})"
                 for n in sorted(no_success) if not results["tasks"][n]["arm_b"]["correct"]]
    summary["dry_run_gate"] = "PASS" if not failures else "FAIL"
    summary["dry_run_gate_failures"] = failures
    # Re-audit 3 F-3: say plainly what this dry run cannot measure. Every
    # task the gate does not cover (outside the Edge envelope) needs a real
    # harness: the dry-run fake harness applies an EMPTY fix, so those rows
    # only show that URI refuses a no-op fix, not any harness capability.
    # Arm A is a labelled mock, so the VG-1 comparison is not measured.
    summary["not_measured_needs_real_harness"] = sorted(
        n for n in results["tasks"] if n not in in_envelope | no_success
        and not results["tasks"][n]["arm_b"]["correct"])
    summary["not_measured_note"] = ("dry-run fake harness applies an empty fix; Arm A is a mock; "
                                    "VG-1 (URI vs harness alone) is not measured by a dry run")
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
    results = run(dry_run=not args.live, out_path=args.out)
    gate = results["summary"]["dry_run_gate"]
    summary = results["summary"]
    not_measured = summary["not_measured_needs_real_harness"]
    print(f"M39 dry-run gate: {gate} ({summary['arm_b_oracle_confirmed']}/{summary['total_tasks']} "
          f"oracle-confirmed; not measured, need a real harness: {', '.join(not_measured) or 'none'}; "
          f"{summary['not_measured_note']})", file=sys.stderr)
    for f in results["summary"]["dry_run_gate_failures"]:
        print(f"  FAIL: {f}", file=sys.stderr)
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
