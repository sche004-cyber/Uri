"""Boundary research (user direction 2026-10-01, items 2-3): could EXISTING deterministic URI checks
have prevented the specialists' incorrect executions, before any new model-based verification?

Offline replay of recorded holdout outputs; no model call. Checks are existing URI code, imported read-only:
  D1  M36 negated(text)                                  uri_v1/memory/contracts.py (frozen)
  D2  M36 affirmative_context on the request with the proposal's verbatim arguments removed
      (mirrors affirmative_around in uri_v1/memory/uri_adapter/envelope.py)  (frozen)
  D3  deterministic RAR on attachment references         uri_v1/turn/rar_deterministic.py
      (candidates come from the trusted conversation state; AMBIGUOUS or UNKNOWN -> clarify,
       RESOLVED to a different file than proposed -> block)
  D4  capability relevance: the proposed action must be among uri_core plausible_matches for the
      request text (top-k, discriminating score > 0)        uri_core/core/capability_relevance.py
Each check is applied to every proposal that URI containment would have EXECUTED (read-only,
approval-free) and reported as: incorrect executions blocked, correct executions lost.
Blocked proposals then fall back to the recorded Main Brain output for the end-to-end replay.

Output: results/boundary_replay.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")

import compose  # noqa: E402
import scorer  # noqa: E402
from catalogue import ACTIONS  # noqa: E402
from integration import DIRECTORY  # noqa: E402  (real CapabilityDirectory, built offline)
from uri_core.core.capability_relevance import plausible_matches  # noqa: E402
from uri_v1.memory.contracts import affirmative_context, negated  # noqa: E402
from uri_v1.turn.rar_contracts import RARCandidate, RARQuery  # noqa: E402
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended  # noqa: E402

CASES = compose.cases


def attachments_from_context(ctx: str | None):
    if not ctx:
        return []
    m = re.search(r"attachments[^=]*=\s*\[([^\]]*)\]", ctx)
    if m:
        return [x.strip() for x in m.group(1).split(",") if x.strip()]
    m = re.search(r"last_attachment\s*=\s*(\S+)", ctx)
    return [m.group(1)] if m else []


def d1(case, call):
    return negated(case["text"])


def d2(case, call):
    t = case["text"]
    for v in (call.get("arguments") or {}).values():
        if isinstance(v, str) and v and v in t:
            t = t.replace(v, " ")
    return not affirmative_context(t)


def d3(case, call):
    if call["name"] not in ("read_attached_file", "convert_document", "drive_upload"):
        return False
    files = attachments_from_context(case.get("context"))
    if not files:
        return False  # no candidate set: RAR is not applicable
    cands = tuple(RARCandidate(id=f"c{i}", title=f, candidate_type="document", recency_rank=len(files) - 1 - i,
                               is_attachment=True) for i, f in enumerate(files))
    r = resolve_rar_deterministic_extended(RARQuery(reference_expression=case["text"], candidates=cands)).resolution
    outcome = r.outcome.value
    if outcome != "RESOLVED":
        return True
    chosen = next(c.title for c in cands if c.id == r.candidate_id)
    proposed = [v for v in (call.get("arguments") or {}).values() if isinstance(v, str)]
    return bool(proposed) and chosen not in proposed


def d4_factory(k):
    def d4(case, call):
        ids = [c["capability"] for c in plausible_matches(DIRECTORY, case["text"], limit=k, min_discriminating_score=1e-9)]
        return call["name"] not in ids
    return d4


CHECKS = {"D1_m36_negated": d1, "D2_m36_affirmative_context": d2, "D3_rar_reference": d3,
          "D4_relevance_top3": d4_factory(3), "D4_relevance_top5": d4_factory(5)}
COMBOS = {"D1+D3": ["D1_m36_negated", "D3_rar_reference"],
          "D1+D3+D4top5": ["D1_m36_negated", "D3_rar_reference", "D4_relevance_top5"],
          "D1+D2+D3": ["D1_m36_negated", "D2_m36_affirmative_context", "D3_rar_reference"],
          "all": list(CHECKS)}


def single_action(rec):
    acts = [c for c in rec["calls"] if c["name"] in ACTIONS]
    return acts[0] if len(acts) == 1 else None


def main(paths, arms):
    by = compose.load(paths)
    out = {"per_check": {}, "end_to_end": {}, "examples": defaultdict(list)}
    ids = sorted(i for i, c in CASES.items() if c["split"] == "holdout" and c["kind"] == "select")
    for arm in arms:
        tally = {n: Counter() for n in list(CHECKS) + list(COMBOS)}
        for cid in ids:
            c, rec = CASES[cid], by[arm][cid]
            ev = scorer.eval_select(c, rec)
            if ev["containment"] not in ("EXECUTED_CORRECT", "EXECUTED_INCORRECT"):
                continue
            call = single_action(rec)
            hits = {n: f(c, call) for n, f in CHECKS.items()}
            hits.update({n: any(hits[x] for x in xs) for n, xs in COMBOS.items()})
            kind = "incorrect" if ev["containment"] == "EXECUTED_INCORRECT" else "correct"
            for n, h in hits.items():
                tally[n][f"{kind}_n"] += 1
                tally[n][f"{kind}_blocked"] += int(h)
            if kind == "incorrect" and not hits["all"]:
                out["examples"][arm].append({"case": cid, "family": c["family"], "text": c["text"], "proposal": call})
        out["per_check"][arm] = {n: dict(v) for n, v in tally.items()}
    # end-to-end: hybrid = M36 gate -> det rules -> specialist -> (combo filter) -> Brain on block or rejection
    for arm in arms:
        for combo in ["none"] + list(COMBOS):
            res = Counter()
            brain = 0
            for cid in sorted(i for i, c in CASES.items() if c["split"] == "holdout"):
                c = CASES[cid]
                if c["kind"] == "select" and negated(c["text"]):
                    final, _, _ = compose.stage(c, by["brain_P1"][cid]); brain += 1
                    res[final] += 1
                    continue
                d = compose.det_stage(c, by["deterministic"].get(cid))
                if d is not None and not d[1]:
                    res[d[0]] += 1
                    continue
                rec = by[arm][cid]
                final, fb, _ = compose.stage(c, rec)
                blocked = False
                if combo != "none" and c["kind"] == "select" and final in ("SUCCESS", "INCORRECT") and not fb:
                    call = single_action(rec)
                    if call is not None:
                        blocked = any(CHECKS[x](c, call) for x in COMBOS[combo])
                if fb or blocked:
                    final, _, _ = compose.stage(c, by["brain_P1"][cid]); brain += 1
                res[final] += 1
            out["end_to_end"][f"{arm}|{combo}"] = {**res, "brain_calls": brain}
    out["examples"] = dict(out["examples"])
    (HERE / "results" / "boundary_replay.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for arm, d in out["per_check"].items():
        print(f"\n{arm}")
        for n, t in d.items():
            print(f"  {n:28s} incorrect blocked {t.get('incorrect_blocked',0)}/{t.get('incorrect_n',0)}  correct lost {t.get('correct_blocked',0)}/{t.get('correct_n',0)}")
    print()
    for k, v in out["end_to_end"].items():
        print(k, v)


if __name__ == "__main__":
    main(["runs/holdout_main.jsonl", "runs/holdout_det.jsonl"], ["granite_json_P1", "needle_P1", "granite_native_P1"])
