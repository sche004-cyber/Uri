"""Combined-configuration evaluation (report C). No model calls.

Each configuration is composed from the per-arm raw records of the same split and
repeat. A model's output on a case does not depend on another model having run, so a
sequential or selective configuration is scored by replaying the recorded outputs through
the configuration's routing rule. End-to-end latency is the sum of the measured wall times
of the stages that configuration would invoke, plus the measured containment cost.
A small live end-to-end run (integration.py) checks that composed and live results agree.

Final outcome categories per case:
  SUCCESS            the user-visible result equals the oracle
  INCORRECT          something executed, was held for approval, or was returned that the oracle does not allow
  SAFE_FAIL          nothing wrong happened, but the request was not completed (e.g. abstained on an action case)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
import scorer  # noqa: E402
from uri_v1.memory.contracts import negated  # noqa: E402

cases = {c["id"]: c for c in json.loads((HERE / "battery" / "cases.json").read_text(encoding="utf-8"))}


def load(paths, rep=1):
    by = defaultdict(dict)  # arm -> case -> record
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["type"] == "call" and r.get("rep", 1) == rep:
                by[r["arm"]][r["case"]] = r
    return by


def stage(case, rec):
    """Evaluate one model stage on a case. Returns (final, needs_fallback, ms)."""
    ev = scorer.EVAL[case["kind"]](case, rec)
    ms = rec.get("wall_ms") or 0.0
    k = case["kind"]
    if k == "select":
        c = ev["containment"]
        if c in ("EXECUTED_CORRECT", "HELD_CORRECT"):
            return "SUCCESS", False, ms
        if c in ("EXECUTED_INCORRECT", "HELD_INCORRECT"):
            return "INCORRECT", False, ms
        if c == "NO_ACTION":
            if "no_action" in case["expected"]:
                return "SUCCESS", False, ms
            # abstained on an action case: escalation target may complete it
            return "SAFE_FAIL", True, ms
        return "SAFE_FAIL", True, ms  # contained: rejected proposal goes to fallback
    if k == "extract":
        f = ev.get("fields", {})
        if any(x["n5"] == "ACCEPTED_INCORRECT" for x in f.values()):
            # a wrong but verbatim value passes N5: this is an incorrect result
            return "INCORRECT", False, ms
        if ev["outcome"] in ("ERROR", "MALFORMED", "NO_OUTPUT", "MULTI_CALL", "MODEL_FAILURE") or any(
                x["n5"] == "REJECTED" for x in f.values()):
            return "SAFE_FAIL", True, ms
        return ("SUCCESS" if ev["correct"] else "INCORRECT"), False, ms
    # route and label: no deterministic check can tell a wrong enum from a right one
    if ev["outcome"] in ("ERROR", "MALFORMED", "NO_OUTPUT", "MULTI_CALL", "MODEL_FAILURE", "INVALID_VALUE"):
        return "SAFE_FAIL", True, ms
    return ("SUCCESS" if ev["correct"] else "INCORRECT"), False, ms


def det_stage(case, rec):
    if not rec or not rec.get("handled"):
        return None
    ms = rec.get("wall_ms", 0.0)
    if not rec["calls"]:
        ok = "no_action" in case["expected"]
        return ("SUCCESS" if ok else "SAFE_FAIL"), (not ok), ms
    return stage(case, rec)


def run_config(name, plan, by, split_ids, assign=None):
    """plan: list of stage names; a stage is an arm name, 'det', 'm36' or 'assigned'."""
    res = {"final": Counter(), "fam": defaultdict(Counter), "ms": [], "brain_calls": 0, "model_calls": 0,
           "edge_resolved": 0, "per_case": {}}
    for cid in split_ids:
        c = cases[cid]
        total, final = 0.0, None
        bypass = False
        if "m36" in plan:
            t = time.perf_counter()
            bypass = c["kind"] == "select" and negated(c["text"])
            total += (time.perf_counter() - t) * 1000
        for st in plan:
            if st == "m36":
                continue
            if st == "det":
                r = det_stage(c, by["deterministic"].get(cid))
                if r is None:
                    continue
                final, fb, ms = r
                total += ms
                if not fb:
                    break
                continue
            arm = assign(c) if st == "assigned" else st
            if arm is None or (bypass and not arm.startswith("brain")):
                continue
            rec = by[arm].get(cid)
            if rec is None:
                raise SystemExit(f"{name}: missing record {arm} {cid}")
            final, fb, ms = stage(c, rec)
            total += ms
            res["model_calls"] += 1
            if arm.startswith("brain"):
                res["brain_calls"] += 1
            if not fb:
                break
        if final is None:
            # nothing produced a result: a bypassed or unhandled request with no fallback stage
            final = "SUCCESS" if (c["kind"] == "select" and "no_action" in c["expected"] and bypass) else "SAFE_FAIL"
        res["final"][final] += 1
        res["fam"][c["family"]][final] += 1
        res["ms"].append(total)
        res["per_case"][cid] = final
    n = len(split_ids)
    s = res["final"]["SUCCESS"]
    return {"config": name, "n": n, "success": s, "success_rate": round(s / n, 4),
            "success_cp_lower95": scorer.cp_lower(s, n), "incorrect": res["final"]["INCORRECT"],
            "safe_fail": res["final"]["SAFE_FAIL"], "brain_calls": res["brain_calls"],
            "brain_call_share": round(res["brain_calls"] / n, 4), "model_calls_per_case": round(res["model_calls"] / n, 3),
            "latency_ms": {"median": scorer.pct(res["ms"], .5), "mean": round(statistics.mean(res["ms"]), 1),
                           "p95": scorer.pct(res["ms"], .95)},
            "families": {f: dict(v) for f, v in sorted(res["fam"].items())}, "per_case": res["per_case"]}


def family_winner(by, arms, split_ids):
    """Per-family best arm by development accuracy (ties: lower median latency)."""
    acc = defaultdict(dict)
    for arm in arms:
        for fam in {cases[i]["family"] for i in split_ids}:
            ids = [i for i in split_ids if cases[i]["family"] == fam]
            ok = sum(scorer.EVAL[cases[i]["kind"]](cases[i], by[arm][i])["correct"] for i in ids)
            ms = statistics.median(by[arm][i].get("wall_ms") or 0 for i in ids)
            acc[fam][arm] = (ok / len(ids), -ms)
    return {fam: max(v, key=v.get) for fam, v in acc.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--assign", help="JSON file with family->arm assignment chosen on dev")
    ap.add_argument("--needle", default="needle_P1")
    ap.add_argument("--granite", default="granite_json_P1")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    by = load(a.paths)
    ids = sorted(i for i, c in cases.items() if c["split"] == a.split)
    N, G = a.needle, a.granite
    if a.assign:
        assign_map = json.loads(Path(a.assign).read_text())
    else:
        assign_map = family_winner(by, [N, G], ids)
    assign = lambda c: assign_map.get(c["family"])  # noqa: E731
    have_brain = "brain_P1" in by and len(by["brain_P1"]) >= len(ids)
    configs = [
        ("C0_deterministic_only", ["det"]),
        ("C1_needle_alone", ["m36", N]),
        ("C2_granite_alone", ["m36", G]),
        ("C3_pair_selective", ["m36", "assigned"]),
        ("C4_pair_sequential_needle_then_granite", ["m36", N, G]),
        ("C4b_pair_sequential_granite_then_needle", ["m36", G, N]),
    ]
    if have_brain:
        configs += [
            ("C5_main_brain_alone", ["brain_P1"]),
            ("C6_hybrid_det_selective_edge_then_brain", ["m36", "det", "assigned", "brain_P1"]),
            ("C6b_hybrid_det_granite_then_brain", ["m36", "det", G, "brain_P1"]),
            ("C6c_hybrid_det_needle_then_brain", ["m36", "det", N, "brain_P1"]),
            ("C7_det_then_brain", ["m36", "det", "brain_P1"]),
        ]
    out = {"split": a.split, "assignment": assign_map, "needle_arm": N, "granite_arm": G,
           "configs": [run_config(n, p, by, ids, assign) for n, p in configs]}
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("assignment", assign_map)
    for c in out["configs"]:
        print(f"{c['config']:45s} success {c['success']}/{c['n']} ({c['success_rate']}) lb={c['success_cp_lower95']} "
              f"incorrect={c['incorrect']} safe_fail={c['safe_fail']} brain={c['brain_call_share']} "
              f"calls/case={c['model_calls_per_case']} lat={c['latency_ms']}")
