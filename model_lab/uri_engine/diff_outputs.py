"""Compare two run_bench.py evidence runs case by case: scores, outputs (byte-identical or not), latency.

  python model_lab/uri_engine/diff_outputs.py <baseline results.jsonl> <candidate results.jsonl> [label]

Greedy decoding with the same seed should give byte-identical `content` for configurations that only change
caching/checkpointing; speculative decoding must also be byte-identical; batch/ubatch changes may differ in
floating-point order, which shows up as text differences that must not move suite scores.
"""
import json
import statistics
import sys
from pathlib import Path

EVID = Path(__file__).resolve().parent.parent / "evidence" / "uri_engine"


def load(p):
    rows = {}
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        rows[(r["path"], r["suite"], r["id"])] = r
    return rows


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else "diff"
    common = sorted(set(a) & set(b))
    by_suite = {}
    details = []
    for k in common:
        ra, rb = a[k], b[k]
        s = by_suite.setdefault(f"{k[0]}/{k[1]}", {"n": 0, "score_a": 0.0, "score_b": 0.0, "identical": 0, "lat_a": [], "lat_b": []})
        s["n"] += 1
        s["score_a"] += ra.get("score", 0)
        s["score_b"] += rb.get("score", 0)
        ta = ra.get("content") if "content" in ra else ra.get("raw")
        tb = rb.get("content") if "content" in rb else rb.get("raw")
        same = ta == tb
        s["identical"] += int(same)
        s["lat_a"].append(ra.get("total_s") or ra.get("latency_s"))
        s["lat_b"].append(rb.get("total_s") or rb.get("latency_s"))
        if not same or ra.get("score") != rb.get("score"):
            details.append({"id": k[2], "suite": k[1], "score_a": ra.get("score"), "score_b": rb.get("score"), "identical": same,
                            "a": (ta or "")[:160], "b": (tb or "")[:160]})
    out = {"baseline": sys.argv[1], "candidate": sys.argv[2], "common_cases": len(common), "suites": {}, "differences": details}
    for k, s in by_suite.items():
        la = [x for x in s["lat_a"] if x]
        lb = [x for x in s["lat_b"] if x]
        out["suites"][k] = {"n": s["n"], "score_a": round(s["score_a"] / s["n"], 3), "score_b": round(s["score_b"] / s["n"], 3),
                            "identical_outputs": s["identical"], "lat_a_p50": round(statistics.median(la), 3) if la else None,
                            "lat_b_p50": round(statistics.median(lb), 3) if lb else None}
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / f"diff_{label}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, s in out["suites"].items():
        print(f"{k:12s} n={s['n']:3d} score {s['score_a']:.3f} -> {s['score_b']:.3f}  identical {s['identical_outputs']}/{s['n']}  p50 {s['lat_a_p50']} -> {s['lat_b_p50']}")
    print("differences:", len(details))
    for d in details[:12]:
        print(" ", d["id"], d["score_a"], "->", d["score_b"], "identical" if d["identical"] else "DIFF")


if __name__ == "__main__":
    main()
