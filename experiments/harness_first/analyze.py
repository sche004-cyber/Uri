"""Tables for the H3 report: configuration comparison, per-group results, per-job Edge evidence,
trivial-turn latency, reproducibility across runs, and the failure list.

Usage: python analyze.py runs/dev_r1.jsonl [--rerun runs/dev_r2.jsonl] [--app runs/app_latency.jsonl]
        [--pair SELECT_ACTION=granite_json,EXTRACT=granite_json,LABEL=granite_json] > results/dev_tables.md
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import score as S


def pct(xs, q):
    return S.pct(xs, q)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def edge_job_evidence(recs):
    """Per Edge arm and job: invoked, accepted by URI, correct when accepted, latency, prompt size."""
    rows = []
    arms = sorted({a for r in recs for a in (r.get("edge") or {})})
    for arm in arms:
        by = defaultdict(list)
        for r in recs:
            e = (r.get("edge") or {}).get(arm)
            if not e:
                continue
            job = r["harness"]["residue"]["job"]
            fin = S.model_outcome(e["decision"])
            accepted = fin is not None and fin.get("status") != "UNRESOLVED" and fin.get("by") != "model"
            ok = S.judge(r, fin, ["edge"])[0] if accepted else None
            flags = S.judge(r, fin, ["edge"])[1] if accepted else set()
            by[job].append({"accepted": accepted, "ok": ok, "flags": flags, "ms": e.get("stage_ms") or 0,
                            "chars": e.get("prompt_chars") or 0, "abstain": e["decision"].get("status") == "ABSTAIN",
                            "exp": r["expected"]["outcome"]})
        for job, xs in sorted(by.items()):
            acc = [x for x in xs if x["accepted"]]
            rows.append([arm, job, len(xs), len(acc), sum(1 for x in acc if x["ok"]),
                         f"{(sum(1 for x in acc if x['ok']) / len(acc)):.2f}" if acc else "-",
                         sum(1 for x in xs if x["abstain"]),
                         sum(1 for x in acc if "false_success" in x["flags"]),
                         sum(1 for x in acc if x["flags"] & {"wrong_action", "wrong_binding", "wrong_extraction_accepted", "wrong_label_accepted"}),
                         pct([x["ms"] for x in xs], .5), pct([x["ms"] for x in xs], .95),
                         int(statistics.mean(x["chars"] for x in xs))])
    return table(["Edge arm", "Job", "Invoked", "Accepted by URI", "Correct", "Precision when accepted", "Abstained",
                  "False success", "Wrong accepted", "p50 ms", "p95 ms", "Mean prompt chars"], rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--rerun")
    ap.add_argument("--app")
    ap.add_argument("--pair", action="append", default=[])
    a = ap.parse_args()
    recs = S.load(a.run)
    edges = sorted({k for r in recs for k in (r.get("edge") or {})})
    configs = ["current_proxy", "main_only", "harness_only", "harness_main"] + [f"harness_{e}" for e in edges]         + [f"harness_{e}@REPLIED" for e in edges]
    results = [S.score(recs, c) for c in configs] + [S.score(recs, "pair", dict(kv.split("=") for kv in p.split(","))) for p in a.pair]
    print("## Configuration comparison (development corpus, n=%d)\n" % len(recs))
    rows = []
    for r in results:
        c = r["classes"]
        rows.append([r["config"], f"{r['correct']}/{r['n']} ({(r['accuracy'] or 0):.3f})", c.get("HARNESS_COMPLETE", 0),
                     c.get("HARNESS_PLUS_EDGE", 0), c.get("HARNESS_PLUS_MAIN", 0) + c.get("MAIN", 0), c.get("CLARIFY", 0),
                     c.get("SAFE_FAILURE", 0), r["critical"]["false_success"], r["critical"]["bypassed_clarification"],
                     r["critical"]["underspecified_executed"], r["critical"]["wrong_binding"], r["critical"]["wrong_action"],
                     r["critical"]["wrong_extraction_accepted"] + r["critical"]["wrong_label_accepted"],
                     r["correct_escalation_rate"], r["main_invoked_on_bounded"], r["edge_then_main"],
                     r["latency_ms"]["p50"], r["latency_ms"]["p95"]])
    print(table(["Config", "Correct", "HARNESS_COMPLETE", "+EDGE", "+MAIN", "CLARIFY", "SAFE_FAILURE", "False success",
                 "Bypassed S1 clarify", "Underspecified executed", "Wrong binding", "Wrong action", "Wrong extract/label accepted",
                 "Correct escalation", "Main on bounded", "Edge then Main", "p50 ms", "p95 ms"], rows))
    print("\n## Per task group: correct / n, and p50 latency ms\n")
    groups = sorted({g for r in results for g in r["groups"]})
    rows = []
    for g in groups:
        row = [g, max(r["groups"].get(g, {}).get("n", 0) for r in results)]
        for r in results:
            x = r["groups"].get(g)
            row.append(f"{x['correct']} / {x['p50_ms']}" if x else "-")
        rows.append(row)
    print(table(["Group", "n"] + [r["config"] for r in results], rows))
    print("\n## Edge evidence per job (only residues the harness admitted)\n")
    print(edge_job_evidence(recs))
    print("\n## Trivial and bounded turns: latency by configuration (ms)\n")
    rows = []
    for r in results:
        triv = [x for x in r["rows"] if x["group"] == "trivial"]
        det = [x for x in r["rows"] if x["group"] == "deterministic"]
        rows.append([r["config"], pct([x["lat"] for x in triv], .5), pct([x["lat"] for x in triv], .95),
                     max((x["lat"] for x in triv), default=None), sum(x["ok"] for x in triv), len(triv),
                     pct([x["lat"] for x in det], .5), pct([x["lat"] for x in det], .95)])
    print(table(["Config", "Trivial p50", "Trivial p95", "Trivial max", "Trivial correct", "Trivial n",
                 "Deterministic p50", "Deterministic p95"], rows))
    if a.app:
        app = [json.loads(l) for l in Path(a.app).read_text(encoding="utf-8").splitlines() if l.strip()]
        print("\n## Real app /ask latency (preserved app, Needle pre-route bypassed, local qwen3.5:9b)\n")
        by = defaultdict(list)
        for x in app:
            by[x["text"]].append(x)
        rows = [[t, len(v), round(statistics.median(y["ms"] for y in v)), round(max(y["ms"] for y in v)),
                 Counter(y["status"] for y in v).most_common(1)[0][0]] for t, v in by.items()]
        print(table(["Turn", "Runs", "Median ms", "Max ms", "Status"], rows))
    if a.rerun:
        rec2 = {r["id"]: r for r in S.load(a.rerun)}
        print("\n## Reproducibility (run 1 vs run 2, same corpus)\n")
        rows = []
        for c in configs:
            s1 = {x["id"]: x for x in S.score(recs, c)["rows"]}
            s2 = {x["id"]: x for x in S.score(list(rec2.values()), c)["rows"]}
            common = set(s1) & set(s2)
            flips = sum(1 for i in common if (s1[i]["final"], s1[i]["ok"]) != (s2[i]["final"], s2[i]["ok"]))
            both = sum(1 for i in common if s1[i]["ok"] and s2[i]["ok"])
            rows.append([c, len(common), flips, both, sum(s2[i]["ok"] for i in common)])
        print(table(["Config", "Cases", "Outcome flips", "Correct in both", "Correct run 2"], rows))
    print("\n## Failures of the best harness+Edge configuration\n")
    best = max(results[4:4 + len(edges)] or results, key=lambda r: r["correct"])
    rows = [[x["id"], x["group"], x["expected"], x["cls"], x["final"], ",".join(x["flags"]), round(x["lat"])]
            for x in best["rows"] if not x["ok"]]
    print(f"Configuration: {best['config']}\n")
    print(table(["Case", "Group", "Expected", "Class", "Final", "Flags", "ms"], rows))


if __name__ == "__main__":
    main()
