"""Summarise VRAM-efficiency screening loads (research only).

    python summarize_screen.py [prefix=vS_]

Reads research/adaptive_runtime/evidence/<prefix>*.json (bench_runtime.py records) and the matching server logs
(llama.cpp's own buffer-size lines) and prints one markdown table: device memory per component as llama.cpp reports
it, the Windows per-process residency at the end of the load, and the performance phases. Only records with
healthy_end true and no fatal are marked VALID (CLAUDE.md evidence rule).
"""
import glob
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The report-local copies (vS_*.json here, server logs in server_logs/) are the evidence of record; the harness
# writes to ../adaptive_runtime/evidence, which is used only when no local copy exists.
EVID = HERE if list(HERE.glob("vS_*.json")) else HERE.parents[0] / "adaptive_runtime" / "evidence"
LOGS = HERE / "server_logs" if (HERE / "server_logs").exists() else EVID
BUF = re.compile(r"(?P<what>model buffer|KV buffer|compute buffer|RS buffer|output buffer)[^=]*?size\s*=\s*(?P<mib>[\d.]+) MiB")


def p50(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 2) if xs else None


TOTAL = re.compile(r"Total device: (?P<d>[\d.]+) (?P<du>[KMG]i?B|B), total host: (?P<h>[\d.]+) (?P<hu>[KMG]i?B|B)")
UNIT = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1.0, "GiB": 1024.0}


def buffers(log_path):
    """Peak device-local and host-visible allocation of the server, from GGML_VK_MEMORY_LOGGER lines (the request
    llama.cpp makes, before the driver decides what stays resident)."""
    peak_d = peak_h = 0.0
    try:
        for line in Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines():
            m = TOTAL.search(line)
            if m:
                peak_d = max(peak_d, float(m["d"]) * UNIT[m["du"]])
                peak_h = max(peak_h, float(m["h"]) * UNIT[m["hu"]])
    except OSError:
        pass
    return {"device": round(peak_d), "host": round(peak_h)} if peak_d else {}


def row(d):
    dec = (d.get("decode") or {}).get("rows") or []
    dcs = (d.get("decision") or {}).get("rows") or []
    vis = (d.get("vision") or {}).get("rows") or []
    pre = d.get("prefill") or {}
    end = (d.get("end") or {}).get("server_gpu_memory_mib") or {}
    drafted = sum(r.get("draft_n") or 0 for r in dec)
    accepted = sum(r.get("draft_n_accepted") or 0 for r in dec)
    errors = sum(1 for r in dec + dcs + vis if r.get("error"))
    return {
        "valid": bool(d.get("healthy_end")) and not d.get("fatal"),
        "load_s": d.get("load_seconds"),
        "local": end.get("local usage"), "nonlocal": end.get("non local usage"),
        "decode": p50([r.get("predicted_per_second") for r in dec]),
        "decision": p50([r.get("total_s") for r in dcs]),
        "pre": {k: round((v.get("fresh") or {}).get("prompt_per_second") or 0) for k, v in pre.items()},
        "ttft30k": ((pre.get("30000") or {}).get("fresh") or {}).get("ttft_s"),
        "vision": p50([r.get("total_s") for r in vis]),
        "accept": round(accepted / drafted, 3) if drafted else None,
        "errors": errors,
    }


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "vS_"
    print("| run | valid | extra args | requested device / host-visible MiB (llama.cpp log, peak) | local / non-local MiB (end) | load s | "
          "decode tok/s p50 | MTP accept | decision s p50 | prefill tok/s 1k / 8k / 30k | TTFT 30k s | vision s p50 | errors |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for f in sorted(glob.glob(str(EVID / (prefix + "*.json")))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        log = LOGS / ("server_%s_%s.log" % (d["name"], d["stamp"]))
        b = buffers(log)
        r = row(d)
        pre = r["pre"]
        print("| %s | %s | `%s` | %s / %s | %s / %s | %s | %s | %s | %s | %s / %s / %s | %s | %s | %s |" % (
            d["name"], "yes" if r["valid"] else "NO", " ".join(d.get("extra_args") or []) or "(frozen)",
            b.get("device"), b.get("host"), r["local"], r["nonlocal"], r["load_s"],
            r["decode"], r["accept"], r["decision"], pre.get("1000"), pre.get("8000"), pre.get("30000"), r["ttft30k"],
            r["vision"], r["errors"]))


if __name__ == "__main__":
    main()
