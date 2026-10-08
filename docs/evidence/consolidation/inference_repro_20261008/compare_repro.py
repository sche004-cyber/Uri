"""Compare the 2026-10-08 Runtime v1 reproduction runs with the frozen 2026-10-06 qualification runs.

Read-only. Inputs: model_lab/evidence/runs/<name>/<ts>/results.jsonl + summary.json in the
uri-phase1-integration worktree. Output: JSON on stdout (per suite: n, mean score, median gen tok/s,
median prefill tok/s, median total s, errors) for each run, restricted to the suites the reproduction ran.
"""
import json
import statistics
import sys
from pathlib import Path

RUNS = Path(r"C:/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/model_lab/evidence/runs")
PAIRS = {
    "frozen_mtp2": "ue_cand_mtp2",
    "frozen_nomtp": "ue_cand",
    "repro_mtp2": "repro20261008_mtp2",
    "repro_nomtp": "repro20261008_nomtp",
}
SUITES = ["F", "D", "DG", "C", "H", "S", "O", "R", "P", "V"]


def latest(name):
    dirs = sorted(p for p in (RUNS / name).iterdir() if p.is_dir())
    return dirs[-1]


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 2) if xs else None


def summarize(d):
    rows = [json.loads(l) for l in (d / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    out = {}
    for s in SUITES:
        r = [x for x in rows if x.get("suite") == s]
        if not r:
            continue
        scores = [x["score"] for x in r if isinstance(x.get("score"), (int, float))]
        out[s] = {
            "n": len(r),
            "score_mean": round(sum(scores) / len(scores), 3) if scores else None,
            "gen_tps_p50": med([x.get("gen_tps") for x in r]),
            "prefill_tps_p50": med([x.get("prefill_tps") for x in r]),
            "total_s_p50": med([x.get("total_s") for x in r]),
            "errors": sum(1 for x in r if x.get("error")),
        }
    allr = [x for x in rows if x.get("suite") in SUITES]
    out["_all"] = {"n": len(allr), "gen_tps_p50": med([x.get("gen_tps") for x in allr]),
                   "errors": sum(1 for x in allr if x.get("error"))}
    meta = {}
    sp = d / "summary.json"
    if sp.exists():
        m = json.loads(sp.read_text(encoding="utf-8")).get("meta", {})
        meta = {"started": m.get("started"), "model_sha256": m.get("model_sha256"), "load": m.get("load"),
                "argv": m.get("argv")}
    return {"dir": str(d), "meta": meta, "suites": out}


def main():
    res = {}
    for k, name in PAIRS.items():
        try:
            res[k] = summarize(latest(name))
        except FileNotFoundError:
            res[k] = None
    json.dump(res, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
