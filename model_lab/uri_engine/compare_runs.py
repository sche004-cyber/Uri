"""Tabulate bench_uri.py runs: one row per variant, the URI-relevant medians side by side.

  python model_lab/uri_engine/compare_runs.py            # all runs, latest per name
  python model_lab/uri_engine/compare_runs.py --json out.json
"""
import argparse
import json
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "evidence" / "uri_engine" / "runs"


def latest_per_name():
    out = {}
    for f in sorted(RUNS.glob("*.json")):
        if f.name.endswith(".calls.jsonl"):
            continue
        s = json.loads(f.read_text(encoding="utf-8"))
        out[s["name"]] = (f, s)
    return out


def row(s):
    a = s["agg"]
    r = s.get("resources", {})
    long = {x["id"] + ":" + x["role"]: x for x in s.get("long", [])}

    def L(k, f):
        x = long.get(k)
        return x.get(f) if x else None

    return {
        "name": s["name"], "serial": s.get("serial", s.get("reorder")), "load_s": s.get("load_seconds"),
        "dec_prompt_n": a["session_proposer"]["prompt_n_p50"], "dec_cache_n": a["session_proposer"]["cache_n_p50"],
        "dec_prompt_ms": a["session_proposer"]["prompt_ms_p50"], "dec_ttft": a["session_proposer"]["ttft_p50"],
        "dec_total": a["session_proposer"]["total_p50"],
        "rep_cache_n": a["repeat_proposer"]["cache_n_p50"], "rep_ttft": a["repeat_proposer"]["ttft_p50"], "rep_total": a["repeat_proposer"]["total_p50"],
        "interp_prompt_ms": a["session_interpreter"]["prompt_ms_p50"], "interp_total": a["session_interpreter"]["total_p50"],
        "answer_total": a["session_answer"]["total_p50"],
        "identical_ttft": a["identical"]["ttft_p50"],
        "trivial_ttft": a["trivial"]["ttft_p50"], "trivial_total": a["trivial"]["total_p50"],
        "gen_tps": a["decode"]["gen_tps_p50"],
        "l16k_fresh_s": L("l_16k:long_fresh", "prompt_ms"), "l16k_follow_cache": L("l_16k:long_followup", "cache_n"),
        "l16k_follow_ms": L("l_16k:long_followup", "prompt_ms"),
        "l29k_fresh_s": L("l_29k:long_fresh", "prompt_ms"), "l29k_follow_ms": L("l_29k:long_followup", "prompt_ms"),
        "l29k_follow_cache": L("l_29k:long_followup", "cache_n"),
        "vram_mib": r.get("peak_vram_dedicated_mib"), "rss_mib": r.get("peak_server_rss_mib"), "min_free_ram_mib": r.get("min_system_available_ram_mib"),
        "errors": sum(v.get("errors", 0) for v in a.values()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--names", nargs="*")
    a = ap.parse_args()
    runs = latest_per_name()
    names = a.names or list(runs)
    rows = [row(runs[n][1]) for n in names if n in runs]
    cols = list(rows[0].keys()) if rows else []
    w = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print(" ".join(c.ljust(w[c]) for c in cols))
    for r in rows:
        print(" ".join(str(r[c]).ljust(w[c]) for c in cols))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
