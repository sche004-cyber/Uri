"""Phase 2 closure regression chain (2026-10-08). Runs every gate SEQUENTIALLY (the Phase 1 full suite rewrites part of
the source pin, so nothing runs concurrently) and writes one evidence directory. It never cuts a candidate itself; it
prints a summary and exits non-zero when any gate's outcome is not the expected one, so a candidate is only cut from a
green chain (lesson of review round 3: suite counts alone are not enough).

Gates, in order:
  1. phase2        python -I scripts/phase2d_regression.py phase2          (all Phase 2 suites, incl. tests/phase2ops)
  2. authority     ... authority                                           (Phase 1 authority suites; baseline 134)
  3. phase1-full   ... phase1-full                                         (baseline 2675 passed / 12 skipped / 11 failed)
  4. residue       removes ONLY the two zero-byte files the Phase 1 full suite plants at the tree root
  5. flutter       flutter test (whole uri_ui/test)
  6. bridge xN     scripts/phase2ops_validate_ui_bridge.py, N runs, + every CLIENT_REFUSAL line of each server log
  7. native        scripts/phase2ops_native_execution.py --provider codex_cli --model gpt-6-sol   (REAL Codex; optional)

Usage: .venv/Scripts/python.exe -I scripts/phase2close_chain.py <evidence_dir> [--bridge-runs 10] [--no-native] [--only g1,g2]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RESIDUE = ("STALE_BOOTSTRAP_EXECUTED", "STALE_LAZY_EXECUTED")


def run(cmd, log, cwd=ROOT, env=None, timeout=7200):
    t0 = time.time()
    with open(log, "wb") as fh:
        fh.write((" ".join(map(str, cmd)) + "\n").encode())
        fh.flush()
        try:
            r = subprocess.run(cmd, cwd=str(cwd), stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                               env=env, timeout=timeout)
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = "TIMED_OUT"
        fh.write(f"\nEXIT={code} DURATION_S={round(time.time() - t0, 1)}\n".encode())
    return code


def pytest_counts(log):
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    tail = [l for l in text.splitlines() if re.search(r"\d+ (passed|failed)", l)]
    line = tail[-1] if tail else ""
    get = lambda k: int(m.group(1)) if (m := re.search(r"(\d+) " + k, line)) else 0
    return {"passed": get("passed"), "failed": get("failed"), "skipped": get("skipped"), "errors": get("error"), "line": line.strip()}


def failed_ids(log):
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    return sorted(set(re.findall(r"^FAILED (\S+)", text, re.M)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence")
    ap.add_argument("--bridge-runs", type=int, default=10)
    ap.add_argument("--no-native", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--baseline-full-log", default=str(ROOT.parent / "evidence" / "phase2ops_r6" / "phase1_full.log"))
    a = ap.parse_args()
    ev = Path(a.evidence)
    ev.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    want = lambda g: not only or g in only
    summary = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "gates": {}}
    ok = True

    def record(name, result, passed):
        nonlocal ok
        summary["gates"][name] = {**result, "PASS": bool(passed)}
        ok = ok and bool(passed)
        print(name, json.dumps(summary["gates"][name])[:400], flush=True)
        (ev / "chain_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    reg = [PY, "-I", "scripts/phase2d_regression.py"]
    if want("phase2"):
        code = run(reg + ["phase2"], ev / "phase2_all.log")
        c = pytest_counts(ev / "phase2_all.log")
        record("phase2", {"exit": code, **c}, code == 0 and c["failed"] == 0 and c["errors"] == 0 and c["passed"] > 0)
    if want("authority"):
        code = run(reg + ["authority"], ev / "phase1_authority.log")
        c = pytest_counts(ev / "phase1_authority.log")
        record("authority", {"exit": code, **c}, code == 0 and c["passed"] == 134 and c["failed"] == 0)
    if want("phase1-full"):
        code = run(reg + ["phase1-full"], ev / "phase1_full.log", timeout=14400)
        c = pytest_counts(ev / "phase1_full.log")
        now, base = failed_ids(ev / "phase1_full.log"), failed_ids(a.baseline_full_log) if Path(a.baseline_full_log).is_file() else None
        same = base is not None and now == base
        record("phase1-full", {"exit": code, **c, "failed_ids": now, "baseline_log": a.baseline_full_log,
                               "SAME_FAILURE_SET": same},
               c["passed"] == 2675 and c["skipped"] == 12 and c["failed"] == 11 and same)
    if want("residue"):
        removed = []
        for name in RESIDUE:
            p = ROOT / name
            if p.is_file() and p.stat().st_size == 0:
                p.unlink()
                removed.append(name)
        record("residue", {"removed": removed}, all(not (ROOT / n).exists() for n in RESIDUE))
    if want("flutter"):
        flutter = Path.home() / "flutter/bin/flutter.bat"
        code = run([str(flutter), "test"], ev / "flutter_all.log", cwd=ROOT / "uri_ui")
        text = (ev / "flutter_all.log").read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"\+(\d+)(?: ~(\d+))?(?: -(\d+))?: (All tests passed!|Some tests failed\.)", text)
        last = m[-1] if m else ("0", "0", "0", "")
        res = {"exit": code, "passed": int(last[0]), "skipped": int(last[1] or 0), "failed": int(last[2] or 0), "verdict": last[3]}
        record("flutter", res, code == 0 and res["verdict"] == "All tests passed!")
    if want("bridge"):
        results, refusals = [], []
        for i in range(1, a.bridge_runs + 1):
            code = run([PY, "-I", "scripts/phase2ops_validate_ui_bridge.py", "--log", str(ev / f"ui_bridge_live_{i}.json")],
                       ev / f"ui_bridge_stdout_{i}.txt", timeout=1800)
            data = {}
            try:
                data = json.loads((ev / f"ui_bridge_live_{i}.json").read_text(encoding="utf-8"))
                slog = Path(data["base"]) / "server" / "state" / "logs" / "phase2-server.log"
                cand = [slog] + list(Path(data["base"]).rglob("phase2-server.log"))
                for logp in cand:
                    if logp.is_file():
                        refusals += [f"run{i} " + l for l in logp.read_text(encoding="utf-8", errors="replace").splitlines()
                                     if l.startswith("CLIENT_REFUSAL")]
                        break
            except Exception as exc:  # noqa: BLE001
                data = {"error": type(exc).__name__}
            results.append({"run": i, "exit": code, "flutter_exit": data.get("exit")})
        (ev / "refusals.txt").write_text("\n".join(refusals) + ("\n" if refusals else ""), encoding="utf-8")
        passed = sum(1 for r in results if r["exit"] == 0 and r["flutter_exit"] == 0)
        record("bridge", {"runs": len(results), "passed": passed, "refusal_lines": len(refusals), "results": results},
               passed == len(results))
    if want("native") and not a.no_native:
        nat = ev / "native"
        nat.mkdir(exist_ok=True)
        code = run([PY, "-I", "scripts/phase2ops_native_execution.py", "--provider", "codex_cli", "--model", "gpt-6-sol",
                    "--evidence", str(nat)], ev / "native_codex_stdout.txt", timeout=3600)
        # The native script prints a one-line summary (`{"tag": ..., "runs": [{name, state, reason, code,
        # pid_after_cancel}]}`) before `REPORT <path>`; the report JSON keeps the raw per-run material instead.
        runs = {}
        try:
            lines = (ev / "native_codex_stdout.txt").read_text(encoding="utf-8", errors="replace").splitlines()
            summ = json.loads([l for l in lines if l.startswith('{"tag"')][-1])
            runs = {r.get("name"): {k: r.get(k) for k in ("state", "reason", "code", "pid_after_cancel")} for r in summ.get("runs") or []}
            runs["_qualification"] = summ.get("qualification")
            runs["_report"] = [l[7:] for l in lines if l.startswith("REPORT ")][-1:]
        except Exception as exc:  # noqa: BLE001
            runs = {"error": type(exc).__name__}
        good = (runs.get("lifecycle", {}).get("state") == "completed" and runs.get("lifecycle", {}).get("code") == "SETTLED_VERIFIED"
                and runs.get("mid_run_cancel", {}).get("state") == "uncertain"
                and runs.get("mid_run_cancel", {}).get("reason") == "CANCELLED_AFTER_DISPATCH"
                and runs.get("mid_run_cancel", {}).get("pid_after_cancel") == "DEAD")
        record("native", {"exit": code, "runs": runs}, code == 0 and good)
    summary["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    summary["ALL_PASS"] = ok
    (ev / "chain_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("ALL_PASS" if ok else "CHAIN_FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
