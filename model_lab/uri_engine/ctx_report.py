"""Markdown tables for the repeated-URI-context runs (section 1/2 of URI_ENGINE_STRATA_RESEARCH.md).

  python model_lab/uri_engine/ctx_report.py ctx_control ctx_prod ctx_prod_split ...
Prints, per run: a scenario x size table of prompt_n / excess_recompute / TTFT (medians over the 2 sequences),
the A_fresh prefill rate (tok/s), and the resource line. Read-only.
"""
from __future__ import annotations

import glob
import json
import re
import statistics
import sys
from pathlib import Path

EVID = Path(__file__).resolve().parent.parent / "evidence" / "uri_engine" / "context_reuse"
SCEN = ["A_fresh", "B_repeat", "C_new_turn", "A_reprime", "D_evidence_changed", "A_reprime2", "E_permission_changed", "A_after_E"]


def latest(name):
    fs = sorted(f for f in EVID.glob(f"{name}_*.json") if re.fullmatch(rf"{re.escape(name)}_\d{{8}}-\d{{6}}", f.stem))
    return json.loads(fs[-1].read_text(encoding="utf-8")) if fs else None


def med(rows, k):
    v = [r[k] for r in rows if r.get(k) is not None]
    return statistics.median(v) if v else None


def main(names):
    runs = {n: latest(n) for n in names}
    sizes = [4000, 16000, 30000]
    print("| run | layout | extra flags | binary | load s | peak VRAM MiB | peak RSS MiB | min free RAM MiB | A_fresh prefill tok/s (30k) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n, d in runs.items():
        if not d:
            print(f"| {n} | missing |")
            continue
        r = d["resources"]
        af = [x for x in d["rows"] if x["scenario"] == "A_fresh" and x["size"] == 30000 and x["prompt_n"] and x["prompt_n"] > 20000]
        tps = statistics.median(x["prompt_n"] / (x["prompt_ms"] / 1000) for x in af) if af else None
        b0 = d["argv"][0].replace("\\", "/")
        binary = ("release" if "/runtime/" in b0 else "stock self-built (SDK glslc)" if "/stock2/" in b0 else "patched self-built (SDK glslc)" if "/rsseq2/" in b0
                  else "stock self-built (old glslc)" if "/stock/" in b0 else "patched self-built (old glslc)")
        extra = " ".join(a for a in d["argv"][d["argv"].index("--load-mode") + 2:] if not a.endswith(".gguf") and a != "--mmproj")
        print(f"| {n} | {d['layout']} | `{extra}` | {binary} | {d['load_seconds']} | {r.get('peak_vram_dedicated_mib')} | {r.get('peak_server_rss_mib')} | "
              f"{r.get('min_system_available_ram_mib')} | {round(tps) if tps else '-'} |")
    print()
    print("Cells: prompt_n recomputed / excess over the logical change / TTFT s (median of the two sequences per size).")
    print()
    hdr = "| size : scenario | logical new | " + " | ".join(names) + " |"
    print(hdr)
    print("|---|---|" + "---|" * len(names))
    for size in sizes:
        for sc in SCEN:
            cells = []
            new = None
            for n in names:
                d = runs[n]
                rows = [x for x in (d["rows"] if d else []) if x["size"] == size and x["scenario"] == sc]
                if not rows:
                    cells.append("-")
                    continue
                new = med(rows, "logical_new_tokens")
                cells.append(f"{int(med(rows, 'prompt_n'))} / {int(med(rows, 'excess_recompute'))} / {med(rows, 'ttft_s'):.2f}")
            print(f"| {size // 1000}k : {sc} | {int(new) if new is not None else '-'} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
