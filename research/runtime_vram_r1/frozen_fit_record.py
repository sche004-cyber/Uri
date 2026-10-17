"""Audit finding 4: record the frozen config's lease fit on the current desktop with the Brain host itself.

Non-destructive by construction: the host's own fit function (gpu_lease.assess_fit with the frozen request) runs
first. The host is started only when that verdict is CONTENDED, the state in which the host refuses to start the
Brain and waits (WAITING_FOR_GPU / GPU_CONTENDED). It is stopped through its stop file once that state is reported.
If the pre-check is not CONTENDED, the host is NOT started (it could start the frozen Brain) and only the pre-check
is saved.

    python -I frozen_fit_record.py
"""
from __future__ import annotations

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

out_dir = HERE / "evidence" / "frozen_fit" / time.strftime("%Y%m%d-%H%M%S")
rep = out_dir / "control"
rep.mkdir(parents=True, exist_ok=True)
c = G.census()
pre = G.assess_fit(c)
rec = {"pre_check": {"fit": pre, "census_t": c.get("t"), "explain": G.explain(pre)}, "lease": G.status()}
if pre["verdict"] != G.CONTENDED or rec["lease"]["state"] != "FREE":
    rec["host_started"] = False
    rec["reason"] = "pre-check not CONTENDED or lease not free: host not started (it could start the frozen Brain)"
else:
    stop = REPO / "work" / "oi" / "state" / "runtime_v1.stop"
    stop.unlink(missing_ok=True)
    log = open(out_dir / "host.log", "wb")
    host = subprocess.Popen([sys.executable, "-I", str(REPO / "scripts" / "ws_brain_host.py"), "--report-dir",
                             str(rep), "--minutes", "5"], cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT)
    rec["host_started"] = True
    t0 = time.monotonic()
    report = {}
    while time.monotonic() - t0 < 180:
        try:
            report = json.loads((rep / BH.REPORT_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report = {}
        if report.get("state") in ("WAITING_FOR_GPU", "STARTING", "LOADING", "READY", "FAILED"):
            break
        time.sleep(1)
    rec["host_report"] = report
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text("stop")
    try:
        host.wait(120)
    except subprocess.TimeoutExpired:
        host.terminate()
    rec["host_exit"] = host.returncode
    rec["lease_after"] = G.status()
(out_dir / "frozen_fit.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
hr = rec.get("host_report") or {}
fit = ((hr.get("gpu") or {}).get("fit")) or {}
print(json.dumps({"pre": {k: pre.get(k) for k in ("verdict", "free_mib", "required_mib", "margin_mib")},
                  "host_started": rec["host_started"], "host_state": hr.get("state"), "host_detail": hr.get("detail"),
                  "host_fit": {k: fit.get(k) for k in ("verdict", "free_mib", "required_mib", "margin_mib")},
                  "host_exit": rec.get("host_exit")}, indent=1))
print("EVIDENCE", out_dir)
