"""Build the R2 evidence tables (markdown) from the harness records, watchdog summaries and suite runs.
  python r2/summarize_r2.py > evidence/R2_SUMMARY_TABLES.md
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RA = HERE.parent
EV = RA / "evidence"
ROOT = RA.parents[1]
RUNS = ROOT / "model_lab" / "evidence" / "runs"


def load_records(prefix):
    out = []
    for f in sorted(glob.glob(str(EV / f"{prefix}*.json"))):
        r = json.load(open(f, encoding="utf-8"))
        if "decode" in r or "fatal" in r:
            out.append((Path(f).name, r))
    return out


def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def pct(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * p
    f, c = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[f] + (vals[c] - vals[f]) * (k - f), 1)


def fmt(v, nd=1):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def table_loads(prefix, title):
    rows = load_records(prefix)
    print(f"\n### {title}\n")
    print("| run | blocks | load s | VRAM at start | local / non-local MiB (end) | decode tok/s p50 (min) | decision s p50 / p95 | prefill tok/s 1k / 8k / 30k | TTFT 30k fresh / repeat | vision s p50 | errors | watchdog state (first degraded s) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    stats = {}
    for name, r in rows:
        env = r.get("server_env", {}).get("GGML_VK_SUBALLOCATION_BLOCK_SIZE")
        blocks = "128 MiB" if env == "134217728" else ("256 MiB" if env == "268435456" else "default 1 GiB")
        end = g(r, "end", "server_gpu_memory_mib") or {}
        d50, dmin = g(r, "decode", "tps", "p50"), g(r, "decode", "tps", "min")
        dc50, dc95 = g(r, "decision", "total", "p50"), g(r, "decision", "total", "p95")
        p = r.get("prefill") or {}
        pps = [g(p, s, "fresh", "prompt_per_second") for s in ("1000", "8000", "30000")]
        t30 = (g(p, "30000", "fresh", "ttft_s"), g(p, "30000", "repeat", "ttft_s"))
        v = r.get("vision")
        v50 = g(v, "total", "p50") if isinstance(v, dict) else None
        errs = (g(r, "decode", "errors") or 0) + (g(r, "decision", "errors") or 0) + ((g(v, "errors") or 0) if isinstance(v, dict) else 0)
        wd = {}
        wf = EV / "r2_watch" / f"{r['name']}.summary.json"
        if wf.exists():
            wd = json.load(open(wf, encoding="utf-8"))
        wstate = f"{wd.get('final_state', '-')} ({fmt(wd.get('first_degraded_at_s'))})" if wd else "-"
        fatal = f" FATAL: {r['fatal'][:60]}" if r.get("fatal") else ""
        print(f"| {r['name']}{fatal} | {blocks} | {fmt(r.get('load_seconds'))} | {fmt(r.get('vram_dedicated_at_start_mib'), 0)} | "
              f"{end.get('local usage', '-')} / {end.get('non local usage', '-')} | {fmt(d50)} ({fmt(dmin)}) | {fmt(dc50, 2)} / {fmt(dc95, 2)} | "
              f"{fmt(pps[0], 0)} / {fmt(pps[1], 0)} / {fmt(pps[2], 0)} | {fmt(t30[0], 2)} / {fmt(t30[1], 2)} | {fmt(v50, 2)} | {errs} | {wstate} |")
        s = stats.setdefault(blocks, {"decode": [], "decision": [], "pp30": [], "pp1": [], "pp8": [], "vision": [], "n": 0, "slow": 0})
        s["n"] += 1
        s["decode"].append(d50); s["decision"].append(dc50); s["pp1"].append(pps[0]); s["pp8"].append(pps[1]); s["pp30"].append(pps[2]); s["vision"].append(v50)
        if d50 is not None and d50 < 60:
            s["slow"] += 1
    if stats:
        print("\n| blocks | loads | loads with decode p50 < 60 tok/s | decode p50 across loads: min / p50 / max | decision p50: min / p50 / max | prefill 30k p50 | prefill 8k p50 | prefill 1k p50 | vision p50 |")
        print("|---|---|---|---|---|---|---|---|---|")
        for b, s in stats.items():
            dec = [x for x in s["decode"] if x is not None]
            dcs = [x for x in s["decision"] if x is not None]
            print(f"| {b} | {s['n']} | {s['slow']} | {fmt(min(dec) if dec else None)} / {fmt(pct(dec, 0.5))} / {fmt(max(dec) if dec else None)} | "
                  f"{fmt(min(dcs) if dcs else None, 2)} / {fmt(pct(dcs, 0.5), 2)} / {fmt(max(dcs) if dcs else None, 2)} | {fmt(pct(s['pp30'], 0.5), 0)} | "
                  f"{fmt(pct(s['pp8'], 0.5), 0)} | {fmt(pct(s['pp1'], 0.5), 0)} | {fmt(pct(s['vision'], 0.5), 2)} |")
    return rows


def suite_rows(name):
    fs = sorted(glob.glob(str(RUNS / name / "*" / "results.jsonl")))
    if not fs:
        return None, None
    rows = [json.loads(l) for l in open(fs[-1], encoding="utf-8") if l.strip()]
    summ = json.load(open(Path(fs[-1]).parent / "summary.json", encoding="utf-8"))
    return rows, summ


def key(r):
    return (r["suite"], r["id"], r.get("rep", 0), r.get("mode"))


def table_suites(names, baseline="ue_cand_mtp2"):
    base_rows, base_summ = suite_rows(baseline)
    print(f"\n### Regression suites (fast path; baseline `{baseline}`)\n")
    print("| run | blocks / pressure | load s | VRAM peak | cases | score-changing vs baseline | errors | D score | DG | C | F | H | S | O | L | P | R | RH | V | D total p50 / p95 s | F total p50 | gen tok/s p50 (D) | wall s |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n in [baseline] + names:
        rows, summ = suite_rows(n)
        if rows is None:
            print(f"| {n} | (no run) |")
            continue
        s = summ["summary"]
        meta = summ["meta"]
        changed = []
        if n != baseline and base_rows:
            b = {key(r): r for r in base_rows}
            for r in rows:
                k = key(r)
                if k in b and abs(b[k]["score"] - r["score"]) > 1e-9:
                    changed.append(f"{r['suite']}/{r['id']}: {b[k]['score']}->{r['score']}")
        env = meta.get("env_blocks") or ("128 MiB" if "sub128" in n else "default")
        press = "pressure" if "pressure" in n else "idle"
        sc = lambda su: fmt(g(s, f"fast/{su}", "score"), 3)
        print(f"| {n} | {env} / {press} | {fmt(g(meta, 'load', 'load_seconds'))} | {fmt(g(meta, 'load', 'peak_vram_dedicated_mib'), 0)} | {len(rows)} | "
              f"{len(changed)}{(' (' + '; '.join(changed[:6]) + ')') if changed else ''} | {sum(1 for r in rows if r.get('error'))} | "
              f"{sc('D')} | {sc('DG')} | {sc('C')} | {sc('F')} | {sc('H')} | {sc('S')} | {sc('O')} | {sc('L')} | {sc('P')} | {sc('R')} | {sc('RH')} | {sc('V')} | "
              f"{fmt(g(s, 'fast/D', 'total_p50'), 2)} / {fmt(g(s, 'fast/D', 'total_p95'), 2)} | {fmt(g(s, 'fast/F', 'total_p50'), 3)} | "
              f"{fmt(g(s, 'fast/D', 'gen_tps_p50'))} | {fmt(g(meta, 'path_wall_s', 'fast'))} |")


def table_watch():
    print("\n### Watchdog summaries (isolated, read-only, attached per server)\n")
    print("| run | samples | final state | ever degraded | ever at risk | first demoted s | first degraded s | window tok/s min / p50 / max | demoted MiB min / max | local / non-local last |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for f in sorted(glob.glob(str(EV / "r2_watch" / "*.summary.json"))):
        w = json.load(open(f, encoding="utf-8"))
        wt = w.get("window_tps", {})
        dm = w.get("demoted_mib", {})
        print(f"| {Path(f).name.replace('.summary.json', '')} | {w.get('n_samples')} | {w.get('final_state')} | {w.get('ever_degraded')} | {w.get('ever_at_risk')} | "
              f"{fmt(w.get('first_demoted_at_s'))} | {fmt(w.get('first_degraded_at_s'))} | {fmt(wt.get('min'))} / {fmt(wt.get('p50'))} / {fmt(wt.get('max'))} | "
              f"{fmt(dm.get('min'))} / {fmt(dm.get('max'))} | {w.get('local_mib_last')} / {w.get('nonlocal_mib_last')} |")


def table_soak():
    f = EV / "r2_soak" / "soak_final.json"
    if not f.exists():
        return
    s = json.load(open(f, encoding="utf-8"))
    print(f"\n### Soak (`r2_soak/soak_final.json`): {s.get('minutes_requested')} min requested, started {s.get('started')}, ended {s.get('ended')}, "
          f"load {s.get('load_seconds')} s, calls {s.get('total_calls')}, errors {s.get('total_errors')}, invalid {s.get('total_invalid')}\n")
    print("| kind | n | errors | invalid | truncated | wall p50 s | first third | last third | gen tok/s p50 | cache_n p50 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for k, v in s.get("summary", {}).items():
        print(f"| {k} | {v['n']} | {v['errors']} | {v['invalid']} | {v['truncated']} | {fmt(v['wall_p50'], 3)} | {fmt(v['wall_first_third'], 3)} | {fmt(v['wall_last_third'], 3)} | {fmt(v['gen_tps_p50'])} | {fmt(v['cache_n_p50'], 0)} |")
    rr = s.get("restart_reconnect")
    if rr:
        print(f"\nrestart + reconnect mid-run: error while down `{rr.get('error_while_down')}`, reload {rr.get('reload_seconds')} s, first call after restart {fmt(rr.get('first_call_wall_s'), 3)} s, error {rr.get('first_call', {}).get('error')}")
    print(f"\nmemory: {json.dumps(s.get('memory'))}; windows events during run: {len(s.get('windows_events_during_run') or [])}")


if __name__ == "__main__":
    print("# R2 evidence tables (generated by r2/summarize_r2.py)")
    table_loads("r2P_", "Controlled pressure loads (1.09 GB consumer resident; interleaved; prefill 1k/8k/30k, 3 decode, 4 decision, 2 vision)")
    table_loads("r2I_", "Idle-desktop loads (no consumer)")
    table_loads("r2V_", "Planner profiles next to the 1.09 GB consumer (fit-under-budget validation)")
    table_loads("r2N_", "NVMe vs HDD load placement")
    table_watch()
    table_suites(["repro20261008_mtp2", "r2S_sub128_idle", "r2S_sub128_pressure", "r2S_default_pressure"])
    table_soak()
