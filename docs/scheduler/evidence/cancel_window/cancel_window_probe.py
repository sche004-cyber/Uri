"""Measure the residual cancellation window R7-1 on the real accepted supervisor (evidence tool, not a test).

Worst case: the owner's cancel arrives after the harness's last post-admission check and before the supervisor spawns
the executor. The harness then pre-arms the supervisor's kill set; the supervisor kills at its first supervision poll.
This probe injects the cancel exactly there (by wrapping `Supervisor.run_attempt`) and uses EAGER executors that try to
write a marker file into the workspace the instant they start, before reading stdin:

  python  a Python process (startup comparable to the synthetic fixture)
  batch   a Windows batch file (cmd.exe; starts in a few milliseconds: far faster than Claude Code's Node start-up)

For each run it records whether the marker exists after the run (= an effect before the kill), the attempt's end
reason and the spawn-to-end time from the supervisor ledger.

  python docs/scheduler/evidence/cancel_window/cancel_window_probe.py --runs 30 --out <dir>
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from uri_scheduler.harness import ClaudeHarness  # noqa: E402

EAGER_PY = "import pathlib,time\npathlib.Path('marker.txt').write_text(str(time.time()))\nimport sys\nsys.stdin.read()\n"
EAGER_BAT = "@echo off\r\necho %TIME%> marker.txt\r\nmore > nul\r\n"


def one(kind, base: Path, i: int, cancel=True) -> dict:
    d = base / f"{kind}_{i}_{int(cancel)}"
    d.mkdir(parents=True)
    if kind == "python":
        script = d / "eager.py"
        script.write_text(EAGER_PY, encoding="utf-8")
        h = ClaudeHarness(d / "state", mode="fixture", fixture_script=script, timeout_s=30, inactivity_s=30)
    else:
        bat = d / "eager.bat"
        bat.write_text(EAGER_BAT, encoding="ascii")
        h = ClaudeHarness(d / "state", mode="fixture", fixture_script=bat, fixture_python=str(bat), timeout_s=30,
                          inactivity_s=30)
    h.open()
    try:
        real = h.sup.run_attempt
        key = f"probe:{kind}:{i}"
        tid = h.task_id_for(key)

        def cancel_then_run(admitted, **kw):
            r = h.cancel(tid)                    # arrives after the harness's post-admission check, before spawn
            assert r.get("reason") == "PRE_ARMED_BEFORE_ACTIVE", r
            return real(admitted, **kw)

        if cancel:
            h.sup.run_attempt = cancel_then_run
        ws = d / "ws"
        ws.mkdir()
        out = h.run(attempt_key=key, principal="owner", workspace=ws, instructions=b"x" * 64, gate=h.gate())
        att = h.sup.ledger.q1("SELECT end_reason, spawned_at_us, ended_at_us FROM attempt WHERE task_id=?", (tid,))
        return {"kind": kind, "run": i, "cancelled": cancel, "outcome": out.status, "reason": out.reason, "end_reason": att["end_reason"],
                "spawn_to_end_ms": round((att["ended_at_us"] - att["spawned_at_us"]) / 1000, 1) if att["spawned_at_us"] else None,
                "effect_before_kill": (ws / "marker.txt").exists()}
    finally:
        h.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    with tempfile.TemporaryDirectory(prefix="cwp_") as tmp:
        for kind in ("python", "batch"):
            for i in range(a.runs):
                rows.append(one(kind, Path(tmp), i))
            for i in range(3):                   # positive control: the same executor, not cancelled, does write
                rows.append(one(kind, Path(tmp), i, cancel=False))
    summary = {}
    for kind in ("python", "batch"):
        r = [x for x in rows if x["kind"] == kind and x["cancelled"]]
        ctl = [x for x in rows if x["kind"] == kind and not x["cancelled"]]
        t = sorted(x["spawn_to_end_ms"] for x in r if x["spawn_to_end_ms"] is not None)
        summary[kind] = {"runs": len(r), "effects_before_kill": sum(x["effect_before_kill"] for x in r),
                         "end_reasons": sorted({x["end_reason"] for x in r}),
                         "spawn_to_end_ms_median": t[len(t) // 2] if t else None, "spawn_to_end_ms_max": t[-1] if t else None,
                         "control_runs": len(ctl), "control_effects": sum(x["effect_before_kill"] for x in ctl)}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cancel_window_runs.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (out / "cancel_window_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
