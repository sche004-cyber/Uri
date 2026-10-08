"""Build the markdown result tables of the round-1 report from the evidence JSON files (reproducible).

  python summarize_evidence.py > evidence/SUMMARY_TABLES.md
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVID = HERE / "evidence"


def latest(prefix):
    fs = sorted(glob.glob(str(EVID / f"{prefix}_*.json")))
    return json.load(open(fs[-1], encoding="utf-8")) if fs else None


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def fmt(v, nd=2):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def mem(d):
    m = g(d, "end", "server_gpu_memory_mib") or g(d, "after_load", "server_gpu_memory_mib") or {}
    return f"{m.get('local usage', '-')} / {m.get('non local usage', '-')}"


RUNS = [
    ("base_b11425_mtp", "frozen v1 (32k, vision, MTP), b11425, HDD, first load"),
    ("probe_v32k_full", "frozen v1 again (started before previous server released VRAM)"),
    ("probe_v16k", "frozen v1 with -c 16384 (started before previous server released VRAM)"),
    ("probe_v32k_novision", "frozen v1 without the vision projector"),
    ("probe_v32k_nomtp", "frozen v1 without MTP"),
    ("probe_v24k", "frozen v1 with -c 24576"),
    ("expM_b11425_memlog", "frozen v1 + GGML_VK_MEMORY_LOGGER=1 (NVMe copies)"),
    ("expA_b11425_memprio", "frozen v1 + GGML_VK_ENABLE_MEMORY_PRIORITY=1"),
    ("expU_b11425_ub512", "frozen v1 with -ub 512"),
    ("expN_b11425_mmproj_cpu", "frozen v1 with --no-mmproj-offload (vision encoder on CPU)"),
    ("expB_b11510_plain", "frozen v1 flags on upstream b11510"),
    ("expC_b11510_memprio", "upstream b11510 + GGML_VK_ENABLE_MEMORY_PRIORITY=1"),
    ("expS_memprio_soak", "200-turn soak, frozen v1 + memory priority"),
    ("rep1_plain", "repeat load 1, frozen v1"), ("rep1_memprio", "repeat load 1, + memory priority"),
    ("rep2_plain", "repeat load 2, frozen v1"), ("rep2_memprio", "repeat load 2, + memory priority"),
    ("rep3_plain", "repeat load 3, frozen v1"), ("rep3_memprio", "repeat load 3, + memory priority"),
    ("rep4_plain", "repeat load 4, frozen v1"), ("rep4_memprio", "repeat load 4, + memory priority"),
    ("expP_pressure_plain", "frozen v1 next to a ~1 GB research VRAM consumer"),
    ("expP_pressure_mmprojcpu", "vision-on-CPU next to the same consumer"),
    ("expP_pressure_memprio", "memory priority next to the same consumer"),
    ("expP2_mmprojcpu_nomtp", "vision-on-CPU + no MTP next to the same consumer"),
    ("expP2_mmprojcpu_memprio", "vision-on-CPU + memory priority next to the same consumer"),
    ("expP2_c16k_mmprojcpu", "vision-on-CPU + -c 16384 next to the same consumer"),
    ("expP3_plain_suballoc256", "frozen v1 + GGML_VK_SUBALLOCATION_BLOCK_SIZE=256MiB next to the same consumer"),
    ("expP3_mmprojcpu_suballoc256", "vision-on-CPU + 256 MiB suballocation blocks next to the same consumer"),
    ("expP4_plain_suballoc128", "frozen v1 + 128 MiB suballocation blocks next to the same consumer"),
    ("expP4_mmprojcpu_suballoc128", "vision-on-CPU + 128 MiB suballocation blocks next to the same consumer"),
    ("expI_suballoc256_idle", "frozen v1 + 256 MiB suballocation blocks, idle desktop"),
    ("expP5_plain_suballoc128_r1", "frozen v1 + 128 MiB blocks next to the consumer, repeat 1"),
    ("expP5_plain_suballoc128_r2", "frozen v1 + 128 MiB blocks next to the consumer, repeat 2"),
    ("expP5_plain_suballoc128_r3", "frozen v1 + 128 MiB blocks next to the consumer, repeat 3"),
    ("expP5_plain_default_r1", "frozen v1, default 1 GiB blocks next to the consumer, repeat (control)"),
    ("expI_suballoc128_idle_r1", "frozen v1 + 128 MiB blocks, idle desktop, 1"),
    ("expI_suballoc128_idle_r2", "frozen v1 + 128 MiB blocks, idle desktop, 2"),
]


def main():
    print("### A. Server profile runs (decode p50/p95 tok/s; decision turn p50/p95 s; server GPU local / non-local MiB)\n")
    print("| run | configuration | load s | decode tok/s p50 / p95 | decision total p50 / p95 s | decision TTFT p50 s | prefill 1k / 8k / 30k tok/s | 30k fresh TTFT s | GPU local / non-local MiB | adapter peak MiB | RSS MiB |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name, desc in RUNS:
        d = latest(name)
        if not d:
            continue
        pf = d.get("prefill") or {}
        pps = " / ".join(fmt(g(pf, k, "fresh", "prompt_per_second"), 0) for k in ("1000", "8000", "30000"))
        print(f"| `{name}` | {desc} | {fmt(d.get('load_seconds'), 1)} | {fmt(g(d, 'decode', 'tps', 'p50'), 1)} / {fmt(g(d, 'decode', 'tps', 'p95'), 1)} | "
              f"{fmt(g(d, 'decision', 'total', 'p50'))} / {fmt(g(d, 'decision', 'total', 'p95'))} | {fmt(g(d, 'decision', 'ttft', 'p50'))} | {pps} | "
              f"{fmt(g(pf, '30000', 'fresh', 'ttft_s'))} | {mem(d)} | {fmt(g(d, 'end', 'peak_vram_dedicated_mib'), 0)} | {fmt(g(d, 'end', 'server_rss_now_mib'), 0)} |")

    print("\n### B. Prompt-cache behaviour per run (prompt_n fresh / repeat cache_n / new-turn prompt_n; TTFT s)\n")
    print("| run | 1k fresh / repeat / new turn | 8k | 30k |")
    print("|---|---|---|---|")
    for name, _ in RUNS:
        d = latest(name)
        pf = (d or {}).get("prefill") or {}
        if not pf:
            continue
        cells = []
        for k in ("1000", "8000", "30000"):
            s = pf.get(k) or {}
            cells.append(f"{g(s, 'fresh', 'prompt_n')} / {g(s, 'repeat', 'cache_n')} / {g(s, 'new_turn', 'prompt_n')} ; "
                         f"TTFT {fmt(g(s, 'fresh', 'ttft_s'))} / {fmt(g(s, 'repeat', 'ttft_s'))} / {fmt(g(s, 'new_turn', 'ttft_s'))}")
        print(f"| `{name}` | " + " | ".join(cells) + " |")

    print("\n### C. Vision, cancellation, timeout, stability\n")
    print("| run | vision total p50 s (prompt_n) | disconnect mid-gen: follow-up s / healthy | client timeout in prefill: follow-up s / healthy | stability n / errors / total p50 / p95 / first-third / last-third |")
    print("|---|---|---|---|---|")
    for name, _ in RUNS:
        d = latest(name)
        if not d:
            continue
        v = d.get("vision") if isinstance(d.get("vision"), dict) else {}
        vrow = v.get("rows") or []
        c = d.get("cancel") or {}
        s = d.get("stability") or {}
        print(f"| `{name}` | {fmt(g(v, 'total', 'p50'))} ({vrow[0].get('prompt_n') if vrow else '-'}) | "
              f"{fmt(g(c, 'follow_up_after_disconnect', 'total_s'))} / {c.get('healthy_after_disconnect', '-')} | "
              f"{fmt(g(c, 'follow_up_after_timeout', 'total_s'))} / {c.get('healthy_after_timeout', '-')} | "
              f"{s.get('n', '-')} / {s.get('errors', '-')} / {fmt(g(s, 'total', 'p50'))} / {fmt(g(s, 'total', 'p95'))} / {fmt(s.get('first_third_total_p50'))} / {fmt(s.get('last_third_total_p50'))} |")

    print("\n### D. llama-bench (kernel level, no server, no MTP)\n")
    for f in sorted(glob.glob(str(EVID / "llama_bench_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        print(f"\n`{Path(f).name}` binary sha256 {d['binary_sha256'][:12]}... env {d.get('env')}\n")
        print("| test | avg t/s | stddev | build |")
        print("|---|---|---|---|")
        for run in d["runs"]:
            for row in run.get("json") or []:
                print(f"| pp{row.get('n_prompt')} tg{row.get('n_gen')} | {fmt(row.get('avg_ts'), 1)} | {fmt(row.get('stddev_ts'), 1)} | {row.get('build_commit')} |")


if __name__ == "__main__":
    main()
