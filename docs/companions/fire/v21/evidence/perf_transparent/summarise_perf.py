"""Summarise the Ember V2.1 perf series (run_ember_perf_v21.ps1 output) into summary.json and a table."""
import json, statistics as st
from pathlib import Path
H = Path(__file__).resolve().parent
rows = {}
for d in sorted(H.glob("*_r[12]")):
    gid = "solar" if "solar" in d.name else "ember"
    g = json.loads((d / f"{gid}_gpu.json").read_text(encoding="utf-8-sig"))
    p = json.loads((d / f"{gid}_perf.json").read_text(encoding="utf-8-sig"))
    s = [x for x in g["samples"] if x["dedicated_mb"]]
    fr = p["frames"]
    tot = sorted(f["total_ms"] for f in fr)
    secs = p["seconds_per_state"] * len({f["state"] for f in fr})
    rss = p.get("rss") or []
    rssmax = max((r.get("rss_mb", r) if isinstance(r, dict) else r for r in rss), default=None) if rss else None
    rows[d.name] = dict(
        brain_pids=g["brain_pids_at_start"], samples=len(s),
        gpu3d_median=st.median(x["gpu3d_pct"] for x in s), gpu3d_max=max(x["gpu3d_pct"] for x in s),
        vram_median=st.median(x["dedicated_mb"] for x in s), vram_max=max(x["dedicated_mb"] for x in s),
        shared_median=st.median(x["shared_mb"] for x in s),
        frames=len(fr), frames_per_s=round(len(fr) / secs, 1),
        p50=tot[len(tot) // 2], p99=tot[int(len(tot) * 0.99) - 1],
        ember_resident_mib=round((p.get("ember_resident_bytes") or 0) / 1048576, 1), rss_max=rssmax)
(H / "summary.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
print("| Run | Brain | GPU 3D median (max) % | Dedicated VRAM median (max) MB | Shared MB | Frames/s | p50 / p99 ms | Decoded atlases MiB |")
print("|---|---|---|---|---|---|---|---|")
for k, r in rows.items():
    print(f"| {k} | {'yes' if r['brain_pids'] else 'no'} | {r['gpu3d_median']:.2f} ({r['gpu3d_max']:.2f}) | {r['vram_median']:.1f} ({r['vram_max']:.1f}) | {r['shared_median']:.1f} | {r['frames_per_s']} | {r['p50']:.2f} / {r['p99']:.2f} | {r['ember_resident_mib'] or '-'} |")
