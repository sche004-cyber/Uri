"""Table of every live UI V2 run in evidence/live/: profile, mode, checks, failures, Brain phases, Brain residency.

    python -I tools/summarize_live.py [label ...]
Writes evidence/live_summary.json.
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows = []
labels = sys.argv[1:] or sorted(Path(p).name for p in glob.glob(str(ROOT / "evidence" / "live" / "*")))
for lab in labels:
    d = ROOT / "evidence" / "live" / lab
    try:
        start = json.loads((d / "session-start.json").read_text())
        fin = json.loads((d / "ui-finished.json").read_text())
        phases = json.loads((d / "brain-phases.json").read_text())
    except (OSError, ValueError):
        rows.append({"label": lab, "complete": False})
        continue
    mode = fin.get("mode")
    obs_f = d / f"observations-{mode}.json"
    obs = json.loads(obs_f.read_text()) if obs_f.exists() else []
    checks = [x for x in obs if x.get("label") == "check"]
    samples = json.loads((d / "resource-samples.json").read_text()) if (d / "resource-samples.json").exists() else []
    ls = [v for s in samples for v in (s.get("gpu") or {}).values() if v.get("name") == "llama-server.exe"]
    ui = [v for s in samples for v in (s.get("gpu") or {}).values() if v.get("name") == "uri_ui.exe"]
    ready = {}
    try:
        ready = json.loads((d / "brain-ready.json").read_text()).get("host", {})
    except (OSError, ValueError):
        pass
    native = json.loads((d / "native-execution.json").read_text()) if (d / "native-execution.json").exists() else {}
    rows.append({
        "label": lab, "complete": True, "profile": (start.get("profile") or {}).get("id"), "mode": mode,
        "checks": len(checks), "passed": sum(1 for c in checks if c.get("result") == "PASS"),
        "failures": fin.get("failures"), "flutter_exit": native.get("exit_code"),
        "source_head": native.get("source_head"),
        "brain_phases": [(p["state"], round(p["t"]), p.get("detail")) for p in phases],
        "calibration_tps": (ready.get("calibration") or {}).get("decode_tps"),
        "fit_at_start": ((ready.get("gpu") or {}).get("fit") or {}).get("verdict"),
        "margin_at_start": ((ready.get("gpu") or {}).get("fit") or {}).get("margin_mib"),
        "brain_dedicated_max": max((v["dedicated_mib"] for v in ls), default=None),
        "brain_non_local_max": max((v.get("non_local_mib") or 0 for v in ls), default=None),
        "ui_dedicated_max": max((v["dedicated_mib"] for v in ui), default=None)})
(ROOT / "evidence" / "live_summary.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
for r in rows:
    if not r.get("complete"):
        print(r["label"], "INCOMPLETE")
        continue
    print(f"{r['label']:14} {str(r['profile']):22} {r['mode']:9} {r['passed']}/{r['checks']} fail={r['failures']} "
          f"cal={r['calibration_tps']} fit={r['fit_at_start']}({r['margin_at_start']}) brain={r['brain_dedicated_max']}/"
          f"{r['brain_non_local_max']} ui={r['ui_dedicated_max']} last={r['brain_phases'][-1]}")
