"""Resource/latency facts per model run (load time, VRAM, RSS, generation and prefill speed)."""
import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = []
for p in sorted(glob.glob(str(HERE / "evidence/runs/*/*/summary.json"))):
    model, stamp = Path(p).parent.parent.name, Path(p).parent.name
    if model.startswith("dbg"):
        continue
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    m, s = d["meta"], d["summary"]
    load, end = m.get("load") or {}, m.get("resources_end") or {}
    fast_d = s.get("fast/D") or s.get("fast/DG") or {}
    fast_f = s.get("fast/F") or {}
    rows.append({"model": model, "run": stamp, "paths": m["args"]["paths"], "load_s": load.get("load_seconds"),
                 "vram_mib": max(load.get("peak_vram_dedicated_mib") or 0, end.get("peak_vram_dedicated_mib") or 0) or None,
                 "rss_start_mib": load.get("server_rss_now_mib"), "rss_end_mib": end.get("server_rss_now_mib"),
                 "min_avail_ram_mib": end.get("min_system_available_ram_mib"), "cpu_pct": end.get("mean_server_cpu_pct_of_machine"),
                 "gen_tps": fast_d.get("gen_tps_p50") or fast_f.get("gen_tps_p50"), "prefill_tps_D": fast_d.get("prefill_tps_p50"),
                 "D_ttft_p50": fast_d.get("ttft_p50"), "D_total_p50": fast_d.get("total_p50"), "F_total_p50": fast_f.get("total_p50"),
                 "model_sha256": m.get("model_sha256")})
(HERE / "evidence" / "resources_table.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
for r in rows:
    if "fast" in r["paths"]:
        print(f"{r['model']:28s} load={r['load_s']} vram={r['vram_mib']} rss={r['rss_start_mib']}->{r['rss_end_mib']} "
              f"cpu={r['cpu_pct']} gen={r['gen_tps']} preD={r['prefill_tps_D']} Dttft={r['D_ttft_p50']} Dtot={r['D_total_p50']} F={r['F_total_p50']}")
