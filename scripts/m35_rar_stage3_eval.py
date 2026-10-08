"""Evaluation Harness for M35 URIv1 Batch A2.5 Stage 3: Realistic Blind RAR Qualification.

Extends the Stage 2 scoring pattern (scripts/m35_rar_deterministic_eval.py) with:
- automatic-resolution precision / deterministic coverage
- safe-abstention breakdown (correct/incorrect UNKNOWN, correct/incorrect AMBIGUOUS)
- rule-level attempt/correct-binding/wrong-binding/correct-abstention table
- order-perturbation robustness check (separate from the 100-case score)
- A/B/C/D/E residual classification scaffolding for every non-fully-matched case

Resolution semantics (resolve_rar_deterministic_extended) are NOT modified or
tuned by this script. This is a harness/reporting extension only, run once
against the frozen Stage 3 fixture set.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from uri_v1.turn.rar_contracts import RAROutcome
from uri_v1.turn.rar_deterministic import DeterministicRARTrace, resolve_rar_deterministic_extended
from uri_v1.turn.rar_stage3_blind_fixtures import (
    get_rar_stage3_fixtures,
    get_rar_stage3_order_perturbation_pairs,
)

FIXTURE_FILE = REPO_ROOT / "uri_v1" / "turn" / "rar_stage3_blind_fixtures.py"


def score_case(fix, res, cand_ids):
    """Mirrors Stage 2's exact scoring rules (outcome match, candidate match, wrong binding)."""
    outcome_match = res.outcome == fix.expected_outcome
    candidate_match = False
    wrong_binding = False

    if fix.expected_outcome == RAROutcome.RESOLVED:
        if res.outcome == RAROutcome.RESOLVED:
            if res.candidate_id == fix.expected_candidate_id:
                candidate_match = True
            else:
                wrong_binding = True
    elif fix.expected_outcome == RAROutcome.AMBIGUOUS:
        if res.outcome == RAROutcome.AMBIGUOUS:
            if set(res.ambiguous_candidate_ids) == set(fix.expected_ambiguous_candidate_ids):
                candidate_match = True
            else:
                candidate_match = len(set(res.ambiguous_candidate_ids) & set(fix.expected_ambiguous_candidate_ids)) >= 2
        elif res.outcome == RAROutcome.RESOLVED:
            wrong_binding = True
    elif fix.expected_outcome == RAROutcome.UNKNOWN:
        if res.outcome == RAROutcome.UNKNOWN:
            candidate_match = True
        elif res.outcome == RAROutcome.RESOLVED:
            wrong_binding = True

    return outcome_match, candidate_match, wrong_binding


def classify_residual(fix, res, outcome_match: bool, candidate_match: bool) -> str:
    """A/B/C/D/E residual classification for a non-fully-matched case.

    A - Better state/metadata would plausibly fix it (owner field unused,
        missing recency ordering, missing parent-attachment link, etc.)
    B - Additional safe deterministic reasoning might help (identified only,
        never implemented this batch).
    C - Bounded candidate set, narrow linguistic discrimination -- a small
        specialist classifier/reranker plausibly helps.
    D - Genuine broader semantic reasoning required.
    E - Correctly unresolvable; abstention is itself the right answer
        (used when the case is a safe-abstention success, not a failure).
    """
    if outcome_match and candidate_match:
        return "N/A_FULL_MATCH"
    if fix.expected_outcome in (RAROutcome.UNKNOWN, RAROutcome.AMBIGUOUS) and outcome_match and candidate_match:
        return "E"
    if "ownership" in fix.category:
        return "A"
    if "stale_pointer" in fix.category:
        return "A"
    if "missing_metadata" in fix.category:
        return "A"
    if "email_attachment_relation" in fix.category:
        return "A"
    if "generic_terms" in fix.category or "lexical_overlap" in fix.category:
        return "C"
    if "contrast_residual" in fix.category or "multi_reference" in fix.category:
        return "C"
    if fix.expected_outcome == RAROutcome.UNKNOWN and res.outcome == RAROutcome.UNKNOWN:
        return "E"
    if fix.expected_outcome == RAROutcome.AMBIGUOUS and res.outcome == RAROutcome.AMBIGUOUS:
        return "E"
    return "D"


def run_stage3_evaluation() -> Dict[str, Any]:
    fixtures = get_rar_stage3_fixtures()
    freeze_hash = hashlib.sha256(FIXTURE_FILE.read_bytes()).hexdigest()

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []

    total = len(fixtures)
    full_matches = 0
    outcome_matches = 0
    wrong_bindings = 0
    invented_candidates = 0

    auto_resolved = 0
    auto_resolved_correct = 0
    auto_resolved_wrong = 0

    correct_unknown = 0
    incorrect_unknown = 0
    correct_ambiguous = 0
    incorrect_ambiguous = 0

    first_item_ambiguity_violations = 0

    rule_table: Dict[str, Dict[str, int]] = {}
    residual_counts: Dict[str, int] = {}
    residual_cases: List[Dict[str, Any]] = []

    for fix in fixtures:
        cand_ids = {c.id for c in fix.query.candidates}
        trace: DeterministicRARTrace = resolve_rar_deterministic_extended(fix.query)
        res = trace.resolution

        if res.candidate_id and res.candidate_id not in cand_ids:
            invented_candidates += 1
        for cid in res.ambiguous_candidate_ids:
            if cid not in cand_ids:
                invented_candidates += 1

        if res.outcome == RAROutcome.AMBIGUOUS and len(res.ambiguous_candidate_ids) >= 2:
            ordered_ids = [c.id for c in fix.query.candidates]
            if set(res.ambiguous_candidate_ids) == set(ordered_ids[:1]):
                first_item_ambiguity_violations += 1

        outcome_match, candidate_match, wrong_binding = score_case(fix, res, cand_ids)
        full_match = outcome_match and candidate_match

        if outcome_match:
            outcome_matches += 1
        if full_match:
            full_matches += 1
        if wrong_binding:
            wrong_bindings += 1

        rule_name = trace.rule_used.value
        rt = rule_table.setdefault(rule_name, {
            "attempts": 0, "correct_bindings": 0, "wrong_bindings": 0,
            "correct_abstentions": 0, "other_failures": 0,
        })
        rt["attempts"] += 1

        if res.outcome == RAROutcome.RESOLVED:
            auto_resolved += 1
            if candidate_match:
                auto_resolved_correct += 1
                rt["correct_bindings"] += 1
            else:
                auto_resolved_wrong += 1
                rt["wrong_bindings"] += 1
        elif res.outcome == RAROutcome.UNKNOWN:
            if fix.expected_outcome == RAROutcome.UNKNOWN:
                correct_unknown += 1
                rt["correct_abstentions"] += 1
            else:
                incorrect_unknown += 1
                rt["other_failures"] += 1
        elif res.outcome == RAROutcome.AMBIGUOUS:
            if fix.expected_outcome == RAROutcome.AMBIGUOUS:
                correct_ambiguous += 1
                rt["correct_abstentions"] += 1
            else:
                incorrect_ambiguous += 1
                rt["other_failures"] += 1

        latencies.append(trace.latency_ms)

        residual_class = None
        if not full_match:
            residual_class = classify_residual(fix, res, outcome_match, candidate_match)
            residual_counts[residual_class] = residual_counts.get(residual_class, 0) + 1
            residual_cases.append({
                "fixture_id": fix.id, "category": fix.category,
                "reference_expression": fix.query.reference_expression,
                "expected_outcome": fix.expected_outcome.value,
                "actual_outcome": res.outcome.value,
                "residual_class": residual_class,
                "ground_truth_reason": fix.description,
            })

        results.append({
            "fixture_id": fix.id, "category": fix.category,
            "reference_expression": fix.query.reference_expression,
            "expected_outcome": fix.expected_outcome.value,
            "actual_outcome": res.outcome.value,
            "expected_candidate_id": fix.expected_candidate_id,
            "actual_candidate_id": res.candidate_id,
            "expected_ambiguous_ids": list(fix.expected_ambiguous_candidate_ids),
            "actual_ambiguous_ids": list(res.ambiguous_candidate_ids),
            "rule_used": rule_name,
            "failure_class": trace.failure_class.value if trace.failure_class else None,
            "latency_ms": round(trace.latency_ms, 4),
            "outcome_match": outcome_match,
            "candidate_match": candidate_match,
            "full_match": full_match,
            "wrong_binding": wrong_binding,
            "residual_class": residual_class,
        })

    # --- Order-perturbation robustness ---
    base_by_id = {fx.id: fx for fx in fixtures}
    order_results = []
    order_mismatches = 0
    for fid, reordered_query in get_rar_stage3_order_perturbation_pairs():
        fix = base_by_id[fid]
        original_trace = resolve_rar_deterministic_extended(fix.query)
        reordered_trace = resolve_rar_deterministic_extended(reordered_query)
        same = (
            original_trace.resolution.outcome == reordered_trace.resolution.outcome
            and original_trace.resolution.candidate_id == reordered_trace.resolution.candidate_id
            and set(original_trace.resolution.ambiguous_candidate_ids) == set(reordered_trace.resolution.ambiguous_candidate_ids)
        )
        if not same:
            order_mismatches += 1
        order_results.append({
            "fixture_id": fid,
            "original_outcome": original_trace.resolution.outcome.value,
            "original_candidate": original_trace.resolution.candidate_id,
            "reordered_outcome": reordered_trace.resolution.outcome.value,
            "reordered_candidate": reordered_trace.resolution.candidate_id,
            "order_stable": same,
        })

    n = total
    sorted_lat = sorted(latencies)
    mean_lat = statistics.mean(latencies) if latencies else 0.0
    median_lat = statistics.median(latencies) if latencies else 0.0
    p95_lat = sorted_lat[int(len(sorted_lat) * 0.95)] if latencies else 0.0
    max_lat = sorted_lat[-1] if latencies else 0.0

    auto_precision = round(auto_resolved_correct / auto_resolved, 4) if auto_resolved else None
    deterministic_coverage = round(auto_resolved / n, 4)

    summary = {
        "dataset_freeze_sha256": freeze_hash,
        "total_cases": n,
        "full_matches": full_matches,
        "overall_accuracy": round(full_matches / n, 4),
        "outcome_matches": outcome_matches,
        "outcome_match_rate": round(outcome_matches / n, 4),
        "incorrect_outcomes": n - outcome_matches,
        "automatic_resolution": {
            "auto_resolved_count": auto_resolved,
            "auto_resolved_correct": auto_resolved_correct,
            "auto_resolved_wrong": auto_resolved_wrong,
            "automatic_resolution_precision": auto_precision,
            "deterministic_coverage": deterministic_coverage,
        },
        "safe_abstention": {
            "correct_unknown": correct_unknown,
            "incorrect_unknown": incorrect_unknown,
            "correct_ambiguous": correct_ambiguous,
            "incorrect_ambiguous": incorrect_ambiguous,
            "total_safe_abstentions": correct_unknown + correct_ambiguous,
        },
        "safety": {
            "wrong_bindings": wrong_bindings,
            "invented_candidate_ids": invented_candidates,
            "first_item_ambiguity_violations": first_item_ambiguity_violations,
        },
        "performance_ms": {
            "mean": round(mean_lat, 4), "median": round(median_lat, 4),
            "p95": round(p95_lat, 4), "max": round(max_lat, 4),
        },
        "rule_table": rule_table,
        "residual_counts": residual_counts,
        "residual_cases": residual_cases,
        "order_perturbation": {
            "pairs_tested": len(order_results),
            "mismatches": order_mismatches,
            "results": order_results,
        },
        "results": results,
    }

    out_path = REPO_ROOT / "scripts" / "rar_stage3_qualification_results.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def print_report(summary: Dict[str, Any]) -> None:
    print("=" * 88)
    print("M35 URIv1 BATCH A2.5 STAGE 3 — REALISTIC BLIND DETERMINISTIC RAR QUALIFICATION")
    print("=" * 88)
    print(f"Dataset SHA-256          : {summary['dataset_freeze_sha256']}")
    print(f"Total Cases              : {summary['total_cases']}")
    print(f"Overall Accuracy         : {summary['full_matches']}/{summary['total_cases']} ({summary['overall_accuracy']*100:.1f}%)")
    ar = summary["automatic_resolution"]
    print(f"Auto-Resolved            : {ar['auto_resolved_count']} (correct {ar['auto_resolved_correct']}, wrong {ar['auto_resolved_wrong']})")
    print(f"Auto-Resolution Precision: {ar['automatic_resolution_precision']}")
    print(f"Deterministic Coverage   : {ar['deterministic_coverage']}")
    sa = summary["safe_abstention"]
    print(f"Safe Abstentions         : {sa['total_safe_abstentions']} (UNKNOWN ok={sa['correct_unknown']} bad={sa['incorrect_unknown']}, AMBIGUOUS ok={sa['correct_ambiguous']} bad={sa['incorrect_ambiguous']})")
    sf = summary["safety"]
    print(f"Wrong Bindings           : {sf['wrong_bindings']}")
    print(f"Invented Candidate IDs   : {sf['invented_candidate_ids']}")
    print(f"First-Item Ambiguity     : {sf['first_item_ambiguity_violations']}")
    pf = summary["performance_ms"]
    print(f"Latency mean/median/p95/max (ms): {pf['mean']}/{pf['median']}/{pf['p95']}/{pf['max']}")
    print("-" * 88)
    print("RULE TABLE:")
    print(f"{'Rule':<22} | {'Attempts':>8} | {'CorrectBind':>11} | {'WrongBind':>9} | {'CorrectAbst':>11} | {'Other':>6}")
    for rule, stats in sorted(summary["rule_table"].items(), key=lambda x: -x[1]["attempts"]):
        print(f"{rule:<22} | {stats['attempts']:>8} | {stats['correct_bindings']:>11} | {stats['wrong_bindings']:>9} | {stats['correct_abstentions']:>11} | {stats['other_failures']:>6}")
    print("-" * 88)
    print("RESIDUAL CLASSIFICATION COUNTS:", summary["residual_counts"])
    op = summary["order_perturbation"]
    print(f"Order Perturbation: {op['pairs_tested']} pairs tested, {op['mismatches']} mismatches")
    print("=" * 88)


if __name__ == "__main__":
    summary = run_stage3_evaluation()
    print_report(summary)
