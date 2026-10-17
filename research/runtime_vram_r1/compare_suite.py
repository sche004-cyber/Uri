"""Case-level comparison of a run_bench run against the frozen qualification run ue_cand_mtp2 (20261006-223100).

    python -I compare_suite.py <run_dir> [<baseline_dir>] [--write]
Lists every case whose score differs, and the per-suite scores side by side. It writes compare_vs_ue_cand_mtp2.json
into the run directory only when that file does not exist yet, or with --write (so a re-check never rewrites
committed evidence). Paths in the file are repo-relative.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "model_lab" / "evidence" / "runs" / "ue_cand_mtp2" / "20261006-223100"


def load(d):
    rows = {}
    for line in open(Path(d) / "results.jsonl", encoding="utf-8"):
        r = json.loads(line)
        rows[(r.get("path"), r.get("suite"), r.get("id") or r.get("case"), r.get("rep", 0))] = r
    return rows


def suite_summary(rows):
    """Per-suite mean score and median gen_tps from results.jsonl (when run_bench ended before writing summary.json)."""
    import statistics
    by = {}
    for (path, suite, _, _), r in rows.items():
        by.setdefault(f"{path}/{suite}", []).append(r)
    return {k: {"n": len(v), "score": round(statistics.mean(float(x.get("score") or 0) for x in v), 3),
                "gen_tps_p50": (round(statistics.median([x["gen_tps"] for x in v if x.get("gen_tps")]), 1)
                                if any(x.get("gen_tps") for x in v) else None)} for k, v in by.items()}


def main():
    args = [a for a in sys.argv[1:] if a != "--write"]
    force = "--write" in sys.argv[1:]
    run = Path(args[0]).resolve()
    base = Path(args[1]).resolve() if len(args) > 1 else BASE
    a, b = load(base), load(run)
    diffs, common = [], 0
    for k in sorted(set(a) & set(b), key=str):
        common += 1
        if round(float(a[k].get("score") or 0), 3) != round(float(b[k].get("score") or 0), 3):
            diffs.append({"case": k, "baseline": a[k].get("score"), "run": b[k].get("score")})
    sa = json.load(open(base / "summary.json"))["summary"]
    sb = suite_summary(b) if not (run / "summary.json").exists() else json.load(open(run / "summary.json"))["summary"]
    suites = {k: {"baseline": sa.get(k, {}).get("score"), "run": v.get("score"), "n": v.get("n"),
                  "gen_tps_p50": v.get("gen_tps_p50"), "baseline_gen_tps_p50": sa.get(k, {}).get("gen_tps_p50")}
              for k, v in sb.items()}
    rel = lambda p: p.resolve().relative_to(REPO).as_posix() if p.resolve().is_relative_to(REPO) else str(p)
    out = {"baseline": rel(base), "run": rel(run), "common_cases": common, "only_baseline": len(set(a) - set(b)),
           "only_run": len(set(b) - set(a)), "score_changing": len(diffs), "diffs": diffs, "suites": suites}
    target = run / "compare_vs_ue_cand_mtp2.json"
    if force or not target.exists():
        target.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8", newline="\n")
    print(json.dumps({k: out[k] for k in ("common_cases", "only_baseline", "only_run", "score_changing")}))
    for d in diffs:
        print("DIFF", d)
    for k, v in suites.items():
        print(k, v)


if __name__ == "__main__":
    main()
