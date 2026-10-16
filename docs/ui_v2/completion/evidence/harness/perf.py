"""Resource and responsiveness summary per live run: python tools/perf.py <label> [<label> ...]

From the session host samples (every 3 s): the UI process (uri_ui.exe built from the candidate) GPU dedicated
memory, CPU % (of one core) and RSS; the Brain's GPU memory. From the driver: Brain tokens per second of each
turn and the engine frame timings of the labelled windows. Writes evidence/perf_summary.json.
"""
import json, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def stats(v):
    v = [x for x in v if x is not None]
    if not v:
        return None
    v = sorted(v)
    return {"n": len(v), "median": round(statistics.median(v), 1), "p95": round(v[int((len(v) - 1) * .95)], 1),
            "max": round(v[-1], 1)}


out = {}
for label in sys.argv[1:]:
    d = ROOT / f"evidence/live/{label}"
    samples = json.loads((d / "resource-samples.json").read_text(encoding="utf-8"))
    ui_gpu, ui_cpu, ui_rss, brain_gpu = [], [], [], []
    for s in samples:
        for pid, g in (s.get("gpu") or {}).items():
            if g.get("name") == "uri_ui.exe":
                ui_pids = {o["pid"] for o in s.get("owned", []) if o["name"] == "uri_ui"}
                if int(pid) in ui_pids:
                    ui_gpu.append(g["dedicated_mib"])
            if g.get("name") == "llama-server.exe":
                brain_gpu.append(g["dedicated_mib"])
        for o in s.get("owned", []):
            if o["name"] == "uri_ui":
                ui_cpu.append(o.get("cpu_pct"))
                ui_rss.append(o.get("rss_mib"))
    obs = sorted(d.glob("observations-*.json"))
    tps, windows = [], {}
    for f in obs:
        for x in json.loads(f.read_text(encoding="utf-8")):
            if x["label"] == "turn":
                m = x.get("metrics") or {}
                if m.get("predicted_per_second") and (m.get("predicted_n") or 0) >= 40:
                    tps.append(m["predicted_per_second"])
            if x["label"] == "perf-window":
                windows[x["window"]] = {k: x.get(k) for k in ("frames", "build_ms_p95", "raster_ms_p95", "total_ms_p95", "over_16ms")}
                m = x.get("metrics") or {}
                if m.get("predicted_per_second"):
                    tps.append(m["predicted_per_second"])
    ex = json.loads((d / "native-execution.json").read_text(encoding="utf-8")) if (d / "native-execution.json").exists() else {}
    out[label] = {"visual": ex.get("visual"), "source_head": ex.get("source_head"),
                  "ui_gpu_dedicated_mib": stats(ui_gpu), "ui_cpu_pct": stats(ui_cpu), "ui_rss_mib": stats(ui_rss),
                  "brain_gpu_dedicated_mib": stats(brain_gpu), "brain_tokens_per_s": stats(tps), "frame_windows": windows}
    print(label, json.dumps(out[label], indent=1))
prev = json.loads((ROOT / "evidence/perf_summary.json").read_text()) if (ROOT / "evidence/perf_summary.json").exists() else {}
prev.update(out)
(ROOT / "evidence/perf_summary.json").write_text(json.dumps(prev, indent=1))
