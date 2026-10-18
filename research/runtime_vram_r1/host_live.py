"""Live check of the real Brain host with a resource profile: start, READY + calibration, restart (recovery), stop.

Runs `scripts/ws_brain_host.py --profile <ctx>,<vision>,<mtp>` (production host code, Runtime v1 port 18470, the GPU
lease with the profile's measured request), drives it only through its documented request file, and records the
report at each state. The host stops the server it started and releases the lease on exit.

    python -I host_live.py --profile 65536,off,0
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from uri_operational_intelligence import brain_health as BH  # noqa: E402
from uri_operational_intelligence import gpu_lease as G  # noqa: E402


def read(rep):
    try:
        return json.loads((rep / BH.REPORT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def wait_state(rep, states, timeout, after=0.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        r = read(rep)
        if r.get("state") in states and (r.get("updated_at") or 0) >= after:
            return r, round(time.monotonic() - t0, 1)
        time.sleep(1)
    return read(rep), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    a = ap.parse_args()
    run = HERE / "evidence" / "host_live" / f"{time.strftime('%Y%m%d-%H%M%S')}_{a.profile.replace(',', '_')}"
    rep = run / "control"
    rep.mkdir(parents=True, exist_ok=True)
    out = {"profile_arg": a.profile, "steps": []}
    log = open(run / "host.log", "wb")
    host = subprocess.Popen([sys.executable, "-I", str(REPO / "scripts" / "ws_brain_host.py"), "--report-dir", str(rep),
                             "--minutes", "15", "--profile", a.profile], cwd=str(REPO), stdout=log,
                            stderr=subprocess.STDOUT)
    try:
        r, s = wait_state(rep, ("READY", "DEGRADED", "FAILED", "WAITING_FOR_GPU"), 600)
        out["steps"].append({"step": "start", "seconds": s, "state": r.get("state"), "detail": r.get("detail"),
                             "profile": r.get("profile"), "calibration": r.get("calibration"),
                             "lease_status": G.status(), "gpu": (r.get("gpu") or {}).get("fit")})
        if r.get("state") in ("READY", "DEGRADED"):
            t = time.time()
            BH.write_host_request(rep, "restart")
            r2, _ = wait_state(rep, ("STOPPING", "RELEASE_WAIT", "STARTING", "LOADING"), 60, after=t)
            r2, s2 = wait_state(rep, ("READY", "DEGRADED", "FAILED"), 600, after=t + 1)
            out["steps"].append({"step": "restart", "seconds": s2, "state": r2.get("state"),
                                 "calibration": r2.get("calibration"), "release": r2.get("release_measurement"),
                                 "history": r2.get("history")[-8:]})
            t = time.time()
            BH.write_host_request(rep, "stop")
            r3, s3 = wait_state(rep, ("STOPPED",), 120, after=t)
            out["steps"].append({"step": "stop", "seconds": s3, "state": r3.get("state"), "detail": r3.get("detail"),
                                 "lease": r3.get("lease")})
    finally:
        (REPO / "work" / "oi" / "state" / "runtime_v1.stop").parent.mkdir(parents=True, exist_ok=True)
        (REPO / "work" / "oi" / "state" / "runtime_v1.stop").write_text("stop")
        try:
            host.wait(120)
        except subprocess.TimeoutExpired:
            host.terminate()
        out["host_exit"] = host.returncode
        out["final_report"] = read(rep)
        out["lease_after"] = G.status()
        (run / "host_live.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"steps": [{k: v for k, v in s.items() if k in ("step", "seconds", "state", "detail")}
                                for s in out["steps"]], "host_exit": out["host_exit"]}, indent=1))
    print("EVIDENCE", run)


if __name__ == "__main__":
    main()
