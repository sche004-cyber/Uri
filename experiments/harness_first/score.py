"""Composes end-to-end configurations from run.py records and scores them.

Configurations:
  current_proxy   live app today, approximated: approval resumption is deterministic, every other turn
                  goes to the Main Brain with the full catalogue (one call; the live app makes two for
                  chat turns, measured separately by app_latency.py)
  main_only       every turn to the Main Brain with the full catalogue
  harness_only    deterministic stages only; any residue is an unresolved SAFE_FAILURE
  harness_main    deterministic stages, residue to the Main Brain (prepared problem)
  harness_<edge>  deterministic stages, admitted residue to one Edge model, rejection/abstention to Main
  pair:<spec>     per job class, a named Edge model (e.g. pair:SELECT_ACTION=granite_json,EXTRACT=needle)

Usage: python score.py runs/dev_r1.jsonl [--pair SELECT_ACTION=granite_json,EXTRACT=granite_json,LABEL=granite_json]
        [--out results/dev_r1.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ID_ARGS = ("attachment_name", "url", "roll_number", "spreadsheet_id", "file_name")
EXECUTING = {"EXECUTED", "HELD"}


def load(path):
    recs = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in recs if r.get("type") == "case" and "crash" not in r]


def model_outcome(d):
    """Normalise a model-stage decision into a final outcome, or None when it falls through."""
    s = d.get("status")
    if s in EXECUTING or s in ("REPLIED", "EXTRACTED", "LABELLED", "CLARIFY"):
        return d
    if s == "ABSTAIN":
        return {"status": {"CLARIFY": "CLARIFY", "DECLINE": "DECLINED", "ESCALATE": "UNRESOLVED"}[d["control"]], "by": "model"}
    return None


def compose(rec, config, pair=None):
    """Returns (cls, final, stages_invoked, latency_ms)."""
    h = rec["harness"]
    lat = h["harness_ms"]
    if config in ("main_only", "current_proxy"):
        if config == "current_proxy" and h["decided"] and h["outcome"].get("status") == "APPROVAL_DECIDED":
            return "HARNESS_COMPLETE", h["outcome"], [], lat
        m = rec.get("main_only")
        if not m:
            return None
        fin = model_outcome(m["decision"]) or {"status": "SAFE_FAILURE", "why": m["decision"]}
        cls = "CLARIFY" if fin["status"] == "CLARIFY" else ("SAFE_FAILURE" if fin["status"] in ("SAFE_FAILURE", "DECLINED", "UNRESOLVED") else "MAIN")
        return cls, fin, ["main"], (m.get("wall_ms") or 0)
    if h["decided"]:
        o = h["outcome"]
        cls = "CLARIFY" if o.get("status") == "CLARIFY" else "HARNESS_COMPLETE"
        return cls, o, [], lat
    res = h["residue"]
    stages = []
    if config == "harness_only":
        return "SAFE_FAILURE", {"status": "UNRESOLVED", "why": "residue_needs_model"}, [], lat
    edge_arm = None
    only = None
    if config.startswith("harness_") and config not in ("harness_main",):
        edge_arm = config[len("harness_"):]
        if "@" in edge_arm:                      # e.g. harness_needle@REPLIED: accept only that Edge outcome
            edge_arm, only = edge_arm.split("@", 1)
    if pair is not None:
        edge_arm = pair.get(res["job"])
    if edge_arm and res["admitted"] and edge_arm in (rec.get("edge") or {}):
        e = rec["edge"][edge_arm]
        stages.append("edge")
        lat += e.get("stage_ms") or 0
        fin = model_outcome(e["decision"])
        if fin is not None and fin.get("status") != "UNRESOLVED" and not (fin.get("by") == "model")                 and (only is None or fin.get("status") == only):
            cls = "CLARIFY" if fin["status"] == "CLARIFY" else "HARNESS_PLUS_EDGE"
            return cls, fin, stages, lat
    m = rec.get("main_prepared")
    if not m:
        return "SAFE_FAILURE", {"status": "UNRESOLVED", "why": "no_main"}, stages, lat
    stages.append("main")
    lat += m.get("stage_ms") or 0
    fin = model_outcome(m["decision"]) or {"status": "SAFE_FAILURE", "why": m["decision"]}
    cls = "CLARIFY" if fin["status"] == "CLARIFY" else (
        "SAFE_FAILURE" if fin["status"] in ("SAFE_FAILURE", "DECLINED", "UNRESOLVED") else "HARNESS_PLUS_MAIN")
    return cls, fin, stages, lat


def judge(rec, fin, stages):
    """Correctness against the expected outcome plus critical-gate counters."""
    e = rec["expected"]
    out = e["outcome"]
    s = fin.get("status")
    flags = set()
    action = fin.get("action")
    args = fin.get("args") or {}
    s1_required = any(st.get("stage") == "rar_s1" and st.get("state") == "CLARIFY" for st in rec["harness"]["stages"])
    if s in EXECUTING and s1_required:
        flags.add("bypassed_clarification")       # RAR/S1 required a clarification and something still ran
    if s in EXECUTING and out == "ESCALATE" and stages and stages[-1] == "main":
        # The Main Brain owns escalated work and may use tools for it; one call here is its first step.
        flags.add("main_first_step_only")
        return True, flags
    if s in EXECUTING:
        if out != "ACTION":
            flags.add("wrong_action")
            if out == "CLARIFY":
                flags.add("underspecified_executed")
        elif action != e["action"]:
            flags.add("wrong_action")
        else:
            exp_id = e.get("binding", "").split(":", 1)[1] if e.get("binding") else None
            for k in ID_ARGS:
                if k in (e.get("args") or {}):
                    exp_id = e["args"][k]
            got = next((args[k] for k in ID_ARGS if k in args), None)
            if exp_id is not None and got is not None and got != exp_id:
                flags.add("wrong_binding")
        if s == "EXECUTED" and flags - {"underspecified_executed"}:
            flags.add("false_success")
        return (not flags), flags
    if out == "ACTION":
        return False, flags
    if out == "CLARIFY":
        return s == "CLARIFY", flags
    if out == "ESCALATE":
        return "main" in stages, flags
    if out == "DECLINE":
        return s in ("DECLINED", "CLARIFY", "REPLIED"), flags   # nothing ran and the user got an answer
    if out == "REPLY":
        return s == "REPLIED" and (fin.get("intent") in (None, e["intent"])), flags
    if out == "APPROVAL":
        return s == "APPROVAL_DECIDED" and fin.get("approve") == e["approve"], flags
    if out == "LIFECYCLE":
        return s == "LIFECYCLE_PROPOSED" and fin.get("operation") == e["operation"] and fin.get("target") == e["target"], flags
    if out == "EXTRACT":
        if s != "EXTRACTED":
            return False, flags
        vals = fin.get("values") or {}
        ok = all((vals.get(f) in (None, "", "ABSENT")) if v == "ABSENT" else vals.get(f) == v for f, v in e["fields"].items())
        if not ok:
            flags.add("wrong_extraction_accepted")
        return ok, flags
    if out == "LABEL":
        ok = s == "LABELLED" and fin.get("value") == e["value"]
        if s == "LABELLED" and not ok:
            flags.add("wrong_label_accepted")
        return ok, flags
    return False, flags


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return round(xs[k], 1)


GROUP = {"TRIVIAL": "trivial", "TRIVIAL_NEAR_MISS": "trivial_near_miss", "APPROVAL_FOLLOWUP": "deterministic",
         "LIFECYCLE": "deterministic", "SESSION_REFERENCE": "reference", "REFERENCE": "reference", "AMBIGUITY": "ambiguity",
         "MAIN_REQUIRED": "main_required", "ESCALATE": "main_required", "MULTISTEP": "main_required",
         "ADVERSARIAL_TARGET": "adversarial", "INJECTION": "adversarial", "NEGATION": "negation", "UNSUPPORTED": "unsupported",
         "ARGS": "tool_action", "SELECT": "tool_action", "EXTRACT": "extract", "SEMANTIC": "label"}


def score(recs, config, pair=None):
    rows = []
    for r in recs:
        c = compose(r, config, pair)
        if c is None:
            continue
        cls, fin, stages, lat = c
        ok, flags = judge(r, fin, stages)
        rows.append({"id": r["id"], "family": r["family"], "group": GROUP.get(r["family"], r["family"]), "cls": cls,
                     "final": fin.get("status"), "ok": ok, "flags": sorted(flags), "stages": stages, "lat": lat,
                     "expected": r["expected"]["outcome"]})
    n = len(rows)
    tot = Counter(x["cls"] for x in rows)
    fl = Counter(f for x in rows for f in x["flags"])
    exp_esc = [x for x in rows if x["expected"] == "ESCALATE"]
    bounded = [x for x in rows if x["expected"] not in ("ESCALATE",)]
    groups = defaultdict(list)
    for x in rows:
        groups[x["group"]].append(x)
    out = {
        "config": config if pair is None else "pair:" + ",".join(f"{k}={v}" for k, v in pair.items()),
        "n": n, "correct": sum(x["ok"] for x in rows), "accuracy": round(sum(x["ok"] for x in rows) / n, 4) if n else None,
        "classes": dict(tot), "critical": {k: fl.get(k, 0) for k in ("false_success", "bypassed_clarification", "wrong_binding",
                                                                     "wrong_action", "underspecified_executed",
                                                                     "wrong_extraction_accepted", "wrong_label_accepted",
                                                                     "main_first_step_only")},
        "correct_escalation_rate": round(sum("main" in x["stages"] for x in exp_esc) / len(exp_esc), 3) if exp_esc else None,
        "main_invoked_on_bounded": sum("main" in x["stages"] for x in bounded),
        "edge_then_main": sum(x["stages"] == ["edge", "main"] for x in rows),
        "latency_ms": {"p50": pct([x["lat"] for x in rows], .5), "p95": pct([x["lat"] for x in rows], .95),
                       "mean": round(statistics.mean(x["lat"] for x in rows), 1) if rows else None},
        "groups": {g: {"n": len(v), "correct": sum(x["ok"] for x in v), "classes": dict(Counter(x["cls"] for x in v)),
                       "p50_ms": pct([x["lat"] for x in v], .5), "p95_ms": pct([x["lat"] for x in v], .95)}
                   for g, v in sorted(groups.items())},
        "rows": rows,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--pair", action="append", default=[])
    ap.add_argument("--out")
    a = ap.parse_args()
    recs = []
    for p in a.runs:
        recs += load(p)
    edges = sorted({k for r in recs for k in (r.get("edge") or {})})
    configs = ["current_proxy", "main_only", "harness_only", "harness_main"] + [f"harness_{e}" for e in edges]
    results = [score(recs, c) for c in configs]
    for p in a.pair:
        results.append(score(recs, "pair", dict(kv.split("=") for kv in p.split(","))))
    for r in results:
        print(f"{r['config']:<60} n={r['n']} acc={r['accuracy']} classes={r['classes']} crit={r['critical']} "
              f"esc={r['correct_escalation_rate']} lat={r['latency_ms']}")
    if a.out:
        Path(a.out).parent.mkdir(exist_ok=True)
        Path(a.out).write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
