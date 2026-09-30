"""EPQ-1 deterministic scorer. Reads raw run JSONL plus the frozen battery; no model calls.

Usage: python scorer.py runs/<file>.jsonl [...more] --out results/<name>.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from catalogue import ACTIONS, CONTROLS, CONTROL_CLASS  # noqa: E402

IDENT = {"roll_number", "attachment_name", "url", "spreadsheet_id", "range", "file_name", "recipient", "subject",
         "title", "format", "target_format"}
FREE = {"query", "question", "fact", "purpose"}


# ------------------------------------------------------------------ helpers
def cp_lower(k, n, alpha=0.05):
    """One-sided Clopper-Pearson lower bound."""
    if n == 0 or k == 0:
        return 0.0
    lo, hi = 0.0, k / n
    for _ in range(60):
        mid = (lo + hi) / 2
        # P(X >= k | p=mid)
        tail = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(k, n + 1))
        if tail < alpha:
            lo = mid
        else:
            hi = mid
    return round(lo, 4)


def cp_upper(k, n, alpha=0.05):
    if n == 0:
        return 1.0
    if k == n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        cdf = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(0, k + 1))
        if cdf < alpha:
            hi = mid
        else:
            lo = mid
    return round(hi, 4)


def toks(s):
    return re.findall(r"\w+", unicodedata.normalize("NFKC", str(s)).casefold())


def f1(a, b):
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    ca, cb = Counter(ta), Counter(tb)
    ov = sum((ca & cb).values())
    if ov == 0:
        return 0.0
    p, r = ov / len(ta), ov / len(tb)
    return 2 * p * r / (p + r)


def lenient(s):
    s = unicodedata.normalize("NFKC", str(s)).strip().casefold()
    s = re.sub(r"^the\s+", "", s)
    return s.rstrip(" .,;:")


def is_absent(v):
    return v is None or (isinstance(v, str) and v.strip() in ("", "ABSENT", "absent", "N/A", "null", "None"))


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = max(0, min(len(xs) - 1, math.ceil(q * len(xs)) - 1))
    return round(xs[i], 1)


# ------------------------------------------------------------------ per-call evaluation
def eval_select(case, rec):
    calls = rec["calls"]
    acts = [c for c in calls if c["name"] in ACTIONS]
    ctrls = [c for c in calls if c["name"] in CONTROLS]
    other = [c for c in calls if c["name"] not in ACTIONS and c["name"] not in CONTROLS]
    exp = case["expected"]
    ev = {"n_calls": len(calls), "suppressed_only": bool(rec.get("suppressed")) and not calls}
    if rec.get("error"):
        ev["outcome"] = "ERROR"
    elif rec.get("malformed"):
        ev["outcome"] = "MALFORMED"
    elif rec.get("model_failure") and not calls:
        ev["outcome"] = "MODEL_FAILURE"
    elif "action" in exp:
        if other:
            ev["outcome"] = "INVALID_TOOL"
        elif len(acts) > 1:
            ev["outcome"] = "MULTI_CALL"
        elif not acts:
            ev["outcome"] = "FALSE_ABSTAIN"
        elif acts[0]["name"] not in case["offered"]:
            ev["outcome"] = "NOT_OFFERED"
        elif acts[0]["name"] != exp["action"]:
            ev["outcome"] = "WRONG_TOOL"
        else:
            ev["outcome"] = "CORRECT"
            if rec.get("cond") != "R1":
                ev.update(arg_diag(exp["args"], acts[0].get("arguments") or {}))
    else:
        if acts or other:
            ev["outcome"] = "FALSE_ACCEPT"
            ev["false_accept_tool"] = (acts or other)[0]["name"]
        else:
            ev["outcome"] = "CORRECT"
            if ctrls:
                ev["abstain_class"] = CONTROL_CLASS[ctrls[0]["name"]]
                ev["abstain_class_match"] = ev["abstain_class"] == exp["no_action"]
    ev["correct"] = ev["outcome"] == "CORRECT"
    ev["containment"] = contain_select(case, acts, other, real=rec.get("cond") == "R1")
    return ev


def arg_diag(exp_args, got):
    ident_ok, free_scores = True, []
    for k, v in exp_args.items():
        g = got.get(k)
        if k in IDENT:
            if g != v:
                ident_ok = False
        else:
            free_scores.append(f1(g or "", v))
    extra = [k for k in got if k not in exp_args]
    return {"args_ident_exact": ident_ok if any(k in IDENT for k in exp_args) else None,
            "args_free_f1": round(min(free_scores), 3) if free_scores else None,
            "args_extra_keys": extra}


def trusted_text(case):
    return (case["text"] or "") + "\n" + (case.get("context") or "")


def contain_select(case, acts, other, real=False):
    """URI containment layer L1 (PREREGISTRATION §4, items 1-4). Returns the post-containment outcome."""
    exp = case["expected"]
    if not acts and not other:
        return "NO_ACTION"
    if other or len(acts) > 1:
        return "CONTAINED_MULTI_OR_INVALID"
    a = acts[0]
    if a["name"] not in case["offered"]:
        return "CONTAINED_NOT_OFFERED"
    tool = ACTIONS[a["name"]]
    args = a.get("arguments") or {}
    if real:
        # R1: real URI schemas take request_text (URI supplies the verbatim request) or nothing;
        # the model's argument values are discarded, so only the action choice decides the outcome.
        executable = tool["_effect"] == "read_only" and tool["_approval"] == "none"
        right = "action" in exp and a["name"] == exp["action"]
        if not executable:
            return "HELD_CORRECT" if right else "HELD_INCORRECT"
        return "EXECUTED_CORRECT" if right else "EXECUTED_INCORRECT"
    req = tool["parameters"]["required"]
    tt = trusted_text(case)
    for p in req:
        v = args.get(p)
        if not isinstance(v, str) or not v:
            return "CONTAINED_MISSING_ARG"
        if tool["parameters"]["properties"][p].get("enum"):
            if v not in tool["parameters"]["properties"][p]["enum"]:
                return "CONTAINED_BAD_ENUM"
            continue
        if v not in tt:
            return "CONTAINED_UNGROUNDED_ARG"
    executable = tool["_effect"] == "read_only" and tool["_approval"] == "none"
    right = "action" in exp and a["name"] == exp["action"] and args_match(exp["args"], args)
    if not executable:
        return "HELD_CORRECT" if right else "HELD_INCORRECT"
    return "EXECUTED_CORRECT" if right else "EXECUTED_INCORRECT"


def args_match(exp_args, got):
    for k, v in exp_args.items():
        g = got.get(k)
        if k in IDENT or k not in FREE:
            if g != v:
                return False
        elif f1(g or "", v) < 0.8:
            return False
    return True


def eval_route(case, rec):
    calls = rec["calls"]
    if rec.get("error"):
        o = "ERROR"
    elif rec.get("malformed"):
        o = "MALFORMED"
    elif rec.get("model_failure") and not calls:
        o = "MODEL_FAILURE"
    elif not calls:
        o = "NO_OUTPUT"
    elif len(calls) > 1:
        o = "MULTI_CALL"
    elif calls[0]["name"] != case["expected"]["route"]:
        o = "WRONG_ROUTE"
    else:
        o = "CORRECT"
    return {"outcome": o, "correct": o == "CORRECT", "got": calls[0]["name"] if calls else None,
            "suppressed_only": bool(rec.get("suppressed")) and not calls}


def eval_extract(case, rec):
    calls = [c for c in rec["calls"] if c["name"] == "record_fields"]
    exp = case["expected"]["fields"]
    ev = {"fields": {}}
    if rec.get("error"):
        ev["outcome"] = "ERROR"
    elif rec.get("malformed"):
        ev["outcome"] = "MALFORMED"
    elif rec.get("model_failure") and not calls:
        ev["outcome"] = "MODEL_FAILURE"
    elif not calls:
        ev["outcome"] = "NO_OUTPUT"
    elif len(calls) > 1:
        ev["outcome"] = "MULTI_CALL"
    else:
        ev["outcome"] = None
    got = (calls[0].get("arguments") or {}) if calls and len(calls) == 1 and not ev["outcome"] else {}
    doc = case["document"] or ""
    allok = ev["outcome"] is None
    for f, v in exp.items():
        g = got.get(f) if isinstance(got, dict) else None
        if ev["outcome"] is not None:
            fo = "NO_OUTPUT"
        elif v == "ABSENT":
            fo = "ABSENT_OK" if is_absent(g) else "INVENTED"
        elif is_absent(g):
            fo = "MISSED"
        elif g == v:
            fo = "EXACT"
        elif lenient(g) == lenient(v):
            fo = "LENIENT_ONLY"
        else:
            fo = "WRONG"
        # N5 containment: accepted only if absent or a verbatim span of the document
        if fo == "NO_OUTPUT":
            n5 = "REJECTED"
        elif is_absent(g):
            n5 = "ACCEPTED_ABSENT"
        elif not isinstance(g, str) or g not in doc:
            n5 = "REJECTED"
        else:
            n5 = "ACCEPTED_CORRECT" if g == v else "ACCEPTED_INCORRECT"
        if f in case.get("enums", {}):
            # enum values are not spans; containment is the closed enum
            n5 = "ACCEPTED_CORRECT" if g == v else ("REJECTED" if g not in case["enums"][f] else "ACCEPTED_INCORRECT")
        ev["fields"][f] = {"exp": v, "got": g, "outcome": fo, "n5": n5}
        if fo not in ("EXACT", "ABSENT_OK"):
            allok = False
    if ev["outcome"] is None:
        ev["outcome"] = "CORRECT" if allok else "FIELD_ERRORS"
    ev["correct"] = ev["outcome"] == "CORRECT"
    return ev


def eval_label(case, rec):
    calls = rec["calls"]
    if rec.get("error"):
        o = "ERROR"
    elif rec.get("malformed"):
        o = "MALFORMED"
    elif rec.get("model_failure") and not calls:
        o = "MODEL_FAILURE"
    elif not calls:
        o = "NO_OUTPUT"
    elif len(calls) > 1:
        o = "MULTI_CALL"
    else:
        v = (calls[0].get("arguments") or {}).get("value")
        o = "CORRECT" if v == case["expected"]["value"] else ("INVALID_VALUE" if v not in case["enum"] else "WRONG_VALUE")
    return {"outcome": o, "correct": o == "CORRECT", "suppressed_only": bool(rec.get("suppressed")) and not calls}


EVAL = {"select": eval_select, "route": eval_route, "extract": eval_extract, "label": eval_label}


# ------------------------------------------------------------------ aggregation
def load(paths):
    recs, meta = [], []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            (recs if r["type"] == "call" else meta).append(r)
    return recs, meta


def score(paths):
    cases = {c["id"]: c for c in json.loads((HERE / "battery" / "cases.json").read_text(encoding="utf-8"))}
    recs, meta = load(paths)
    per = defaultdict(list)  # (arm, case) -> [ev]
    lat = defaultdict(list)
    for r in recs:
        c = cases[r["case"]]
        ev = EVAL[c["kind"]](c, r)
        ev["rep"] = r["rep"]
        ev["wall_ms"] = r.get("wall_ms")
        per[(r["arm"], r["case"])].append(ev)
        if r.get("wall_ms") is not None and not r.get("error"):
            warm = not r.get("agent_build_ms")
            lat[r["arm"]].append((r["wall_ms"], warm, (r.get("ollama") or {}).get("load_duration")))
    arms = sorted({a for a, _ in per})
    out = {"arms": {}, "cases": {}}
    for arm in arms:
        fam = defaultdict(lambda: defaultdict(int))
        field = Counter()
        cont = Counter()
        abst = Counter()
        flips = 0
        ncases = 0
        for (a, cid), evs in per.items():
            if a != arm:
                continue
            c = cases[cid]
            ncases += 1
            worst = all(e["correct"] for e in evs)
            outs = {e["outcome"] for e in evs}
            if len({e["correct"] for e in evs}) > 1 or len(outs) > 1:
                flips += 1
            F = fam[c["family"]]
            F["n"] += 1
            F["correct_worst"] += int(worst)
            for e in evs:
                F["o_" + e["outcome"]] += 1
                if e.get("suppressed_only"):
                    F["suppressed_only"] += 1
            e0 = evs[0]
            if c["kind"] == "select":
                for e in evs:
                    cont[e["containment"]] += 1
                    if e["containment"] == "EXECUTED_INCORRECT":
                        F["executed_incorrect"] += 1
                    if e["containment"] == "EXECUTED_CORRECT":
                        F["executed_correct"] += 1
                    if e["containment"].startswith("CONTAINED"):
                        F["contained"] += 1
                    if "abstain_class" in e:
                        abst["match" if e["abstain_class_match"] else "mismatch"] += 1
                    if e.get("args_ident_exact") is not None:
                        F["arg_ident_n"] += 1
                        F["arg_ident_ok"] += int(e["args_ident_exact"])
                    if e.get("args_free_f1") is not None:
                        F["arg_free_n"] += 1
                        F["arg_free_ok"] += int(e["args_free_f1"] >= 0.8)
                if "no_action" in c["expected"]:
                    F["no_action_n"] += 1
                    F["false_accept_any_rep"] += int(any(e["outcome"] == "FALSE_ACCEPT" for e in evs))
                else:
                    F["action_n"] += 1
            if c["kind"] == "extract":
                for e in evs:
                    for f, fv in e["fields"].items():
                        field["f_" + fv["outcome"]] += 1
                        field["n5_" + fv["n5"]] += 1
                        kind = "absent" if fv["exp"] == "ABSENT" else "present"
                        field[f"{kind}_n"] += 1
                        field[f"{kind}_ok"] += int(fv["outcome"] in ("EXACT", "ABSENT_OK"))
                        if fv["n5"] == "ACCEPTED_INCORRECT":
                            F["executed_incorrect"] += 1
            out["cases"].setdefault(cid, {})[arm] = [{k: v for k, v in e.items() if k != "fields"} | (
                {"fields": {f: (x["got"], x["outcome"]) for f, x in e["fields"].items()}} if "fields" in e else {}) for e in evs]
        fams = {}
        for f, F in sorted(fam.items()):
            n, k = F["n"], F["correct_worst"]
            F = dict(F)
            F["acc_worst"] = round(k / n, 4)
            F["cp_lower95"] = cp_lower(k, n)
            fams[f] = F
        tot_n = sum(F["n"] for F in fams.values())
        tot_k = sum(F["correct_worst"] for F in fams.values())
        L = lat[arm]
        allw = [x for x, _, _ in L]
        warm = [x for x, w, _ in L if w]
        out["arms"][arm] = {
            "cases": ncases, "overall_acc_worst": round(tot_k / tot_n, 4) if tot_n else None,
            "overall_cp_lower95": cp_lower(tot_k, tot_n), "families": fams, "containment": dict(cont),
            "abstain_class": dict(abst), "extract_fields": dict(field), "flip_cases": flips,
            "latency_ms": {"n": len(allw), "median": pct(allw, .5), "mean": round(statistics.mean(allw), 1) if allw else None,
                           "p95": pct(allw, .95), "max": pct(allw, 1.0),
                           "warm_n": len(warm), "warm_median": pct(warm, .5), "warm_p95": pct(warm, .95)},
        }
    out["meta"] = meta
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = score(a.paths)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for arm, A in res["arms"].items():
        print(f"\n== {arm}: cases={A['cases']} acc_worst={A['overall_acc_worst']} lat={A['latency_ms']}")
        for f, F in A["families"].items():
            print(f"  {f:12s} {F['correct_worst']}/{F['n']} ({F['acc_worst']}) lb={F['cp_lower95']} "
                  + " ".join(f"{k}={v}" for k, v in F.items() if k.startswith(("o_", "false", "exec", "contained", "arg_", "suppr")) and v))
        print("  containment", A["containment"], "abstain", A["abstain_class"], "fields", A["extract_fields"])
