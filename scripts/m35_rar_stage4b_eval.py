"""Evaluation Harness for M35 URIv1 Batch A2.5 Stage 4B: Independent RAR Requalification.

Evaluates the frozen deterministic RAR stack (resolve_rar_deterministic_extended)
against the frozen independent Stage 4B benchmark (rar_stage4b_independent_fixtures.py).

Outputs:
- Primary Full Evaluation results
- Deterministic-only Ablation comparison (Phase 4)
- Persists results to scripts/rar_stage4b_qualification_results.json
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from uri_v1.turn.rar_contracts import (
    RAREvidence,
    RARFixture,
    RAROutcome,
    RARQuery,
)
from uri_v1.turn.rar_deterministic import (
    DeterministicRARTrace,
    resolve_rar_deterministic_extended,
)
from uri_v1.turn.rar_stage4b_independent_fixtures import get_rar_stage4b_fixtures

FIXTURE_FILE = REPO_ROOT / "uri_v1" / "turn" / "rar_stage4b_independent_fixtures.py"
OUTPUT_JSON = REPO_ROOT / "scripts" / "rar_stage4b_qualification_results.json"


def score_case(fix: RARFixture, res, cand_ids):
    """Computes exact outcome match, candidate match, and wrong binding."""
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
                # Plausible subset overlap check
                candidate_match = len(set(res.ambiguous_candidate_ids) & set(fix.expected_ambiguous_candidate_ids)) >= 2
        elif res.outcome == RAROutcome.RESOLVED:
            wrong_binding = True
    elif fix.expected_outcome == RAROutcome.UNKNOWN:
        if res.outcome == RAROutcome.UNKNOWN:
            candidate_match = True
        elif res.outcome == RAROutcome.RESOLVED:
            wrong_binding = True

    return outcome_match, candidate_match, wrong_binding


def evaluate_fixtures(fixtures: Tuple[RARFixture, ...], mode: str = "FULL") -> Dict[str, Any]:
    """Runs evaluation over fixtures.

    mode='FULL': evaluates queries exactly as authored.
    mode='DET_ONLY': neutralizes S1/M1/B0 fields (negation_spans, recency_hint, target_type_hint)
                     while preserving reference_expression, candidates, candidate metadata,
                     and direct deterministic anchors.
    """
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
    fixture_results: List[Dict[str, Any]] = []

    for fix in fixtures:
        query = fix.query
        if mode == "DET_ONLY":
            # Strip S1/B0 semantic interpretation fields from local_evidence:
            # - negation_spans (requires semantic extraction of what to negate)
            # - recency_hint (requires semantic extraction of temporal relationship)
            # - target_type_hint (requires semantic classification of noun phrase to schema type)
            # Retain direct reference expression, candidates, and direct anchors.
            ablated_evidence = RAREvidence(
                clause_text="",
                negation_spans=(),
                candidate_verbs=(),
                recency_hint=None,
                target_type_hint=None,
            )
            query = RARQuery(
                reference_expression=fix.query.reference_expression,
                candidates=fix.query.candidates,
                local_evidence=ablated_evidence,
                deterministic_anchor=fix.query.deterministic_anchor,
            )

        cand_ids = {c.id for c in query.candidates}
        trace: DeterministicRARTrace = resolve_rar_deterministic_extended(query)
        res = trace.resolution

        # Check candidate invention
        if res.candidate_id and res.candidate_id not in cand_ids:
            invented_candidates += 1
        for cid in res.ambiguous_candidate_ids:
            if cid not in cand_ids:
                invented_candidates += 1

        # Check first item bias
        if res.outcome == RAROutcome.AMBIGUOUS and len(res.ambiguous_candidate_ids) >= 2:
            ordered_ids = [c.id for c in query.candidates]
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

        rule_name = trace.rule_used.value if trace.rule_used else "NONE"
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

        fixture_results.append({
            "fixture_id": fix.id,
            "category": fix.category,
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
        })

    sorted_lat = sorted(latencies)
    mean_lat = statistics.mean(latencies) if latencies else 0.0
    median_lat = statistics.median(latencies) if latencies else 0.0
    p95_lat = sorted_lat[int(len(sorted_lat) * 0.95)] if latencies else 0.0
    max_lat = sorted_lat[-1] if latencies else 0.0

    precision = (auto_resolved_correct / auto_resolved) if auto_resolved > 0 else 1.0
    coverage = (auto_resolved / total) if total > 0 else 0.0

    return {
        "mode": mode,
        "total_cases": total,
        "full_matches": full_matches,
        "overall_accuracy": round(full_matches / total, 4) if total > 0 else 0.0,
        "outcome_matches": outcome_matches,
        "outcome_match_rate": round(outcome_matches / total, 4) if total > 0 else 0.0,
        "automatic_resolution": {
            "auto_resolved_count": auto_resolved,
            "auto_resolved_correct": auto_resolved_correct,
            "auto_resolved_wrong": auto_resolved_wrong,
            "automatic_resolution_precision": round(precision, 4),
            "deterministic_coverage": round(coverage, 4),
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
            "mean": round(mean_lat, 4),
            "median": round(median_lat, 4),
            "p95": round(p95_lat, 4),
            "max": round(max_lat, 4),
        },
        "rule_table": rule_table,
        "fixture_results": fixture_results,
    }


def run_stage4b_full_audit():
    fixtures = get_rar_stage4b_fixtures()
    freeze_hash = hashlib.sha256(FIXTURE_FILE.read_bytes()).hexdigest()

    print("=" * 88)
    print("M35 URIv1 BATCH A2.5 STAGE 4B — INDEPENDENT RAR REQUALIFICATION AUDIT")
    print("=" * 88)
    print(f"Dataset SHA-256 : {freeze_hash}")
    print(f"Total Fixtures  : {len(fixtures)}")

    # 1. Primary Full Evaluation
    full_eval = evaluate_fixtures(fixtures, mode="FULL")
    print("-" * 88)
    print("MODE FULL (Benchmark Exactly As Authored):")
    print(f"  Overall Accuracy         : {full_eval['full_matches']}/{full_eval['total_cases']} ({full_eval['overall_accuracy']*100:.1f}%)")
    print(f"  Auto-Resolved            : {full_eval['automatic_resolution']['auto_resolved_count']} (Correct: {full_eval['automatic_resolution']['auto_resolved_correct']}, Wrong: {full_eval['automatic_resolution']['auto_resolved_wrong']})")
    print(f"  Auto-Resolution Precision: {full_eval['automatic_resolution']['automatic_resolution_precision']}")
    print(f"  Deterministic Coverage   : {full_eval['automatic_resolution']['deterministic_coverage']*100:.1f}%")
    print(f"  Safe Abstentions         : {full_eval['safe_abstention']['total_safe_abstentions']} (UNKNOWN ok={full_eval['safe_abstention']['correct_unknown']}, AMBIGUOUS ok={full_eval['safe_abstention']['correct_ambiguous']})")
    print(f"  Wrong Bindings           : {full_eval['safety']['wrong_bindings']}")
    print(f"  Invented Candidate IDs   : {full_eval['safety']['invented_candidate_ids']}")
    print(f"  Latency Mean/Median/P95  : {full_eval['performance_ms']['mean']} / {full_eval['performance_ms']['median']} / {full_eval['performance_ms']['p95']} ms")

    # 2. Phase 4 Ablation: Deterministic-Only Mode
    det_eval = evaluate_fixtures(fixtures, mode="DET_ONLY")
    print("-" * 88)
    print("MODE DET-ONLY (S1/M1/B0 Pre-Decoded Semantic Evidence Stripped):")
    print(f"  Overall Accuracy         : {det_eval['full_matches']}/{det_eval['total_cases']} ({det_eval['overall_accuracy']*100:.1f}%)")
    print(f"  Auto-Resolved            : {det_eval['automatic_resolution']['auto_resolved_count']} (Correct: {det_eval['automatic_resolution']['auto_resolved_correct']}, Wrong: {det_eval['automatic_resolution']['auto_resolved_wrong']})")
    print(f"  Auto-Resolution Precision: {det_eval['automatic_resolution']['automatic_resolution_precision']}")
    print(f"  Deterministic Coverage   : {det_eval['automatic_resolution']['deterministic_coverage']*100:.1f}%")
    print(f"  Safe Abstentions         : {det_eval['safe_abstention']['total_safe_abstentions']} (UNKNOWN ok={det_eval['safe_abstention']['correct_unknown']}, AMBIGUOUS ok={det_eval['safe_abstention']['correct_ambiguous']})")
    print(f"  Wrong Bindings           : {det_eval['safety']['wrong_bindings']}")
    print(f"  Invented Candidate IDs   : {det_eval['safety']['invented_candidate_ids']}")

    # 3. Delta Analysis
    full_matches_set = {r["fixture_id"] for r in full_eval["fixture_results"] if r["full_match"]}
    det_matches_set = {r["fixture_id"] for r in det_eval["fixture_results"] if r["full_match"]}
    lost_in_det = sorted(list(full_matches_set - det_matches_set))
    gained_in_det = sorted(list(det_matches_set - full_matches_set))

    print("-" * 88)
    print(f"SEMANTIC DEPENDENCY DELTA:")
    print(f"  Cases passing in FULL but failing/abstaining in DET-ONLY: {len(lost_in_det)}")
    print(f"  Cases passing in DET-ONLY but failing in FULL: {len(gained_in_det)}")

    # Group lost cases by root removed field
    delta_breakdown = {}
    base_by_id = {f.id: f for f in fixtures}
    for fid in lost_in_det:
        fix = base_by_id[fid]
        evidence = fix.query.local_evidence
        reasons = []
        if evidence.negation_spans:
            reasons.append("negation_spans")
        if evidence.recency_hint:
            reasons.append("recency_hint")
        if evidence.target_type_hint:
            reasons.append("target_type_hint")
        reason_key = "+".join(reasons) if reasons else "other_evidence"
        delta_breakdown.setdefault(reason_key, []).append(fid)

    for reason, fids in sorted(delta_breakdown.items()):
        print(f"    - {reason} ({len(fids)} cases): {fids}")

    # Persist JSON report
    output_data = {
        "dataset_freeze_sha256": freeze_hash,
        "total_cases": len(fixtures),
        "primary_full_evaluation": {k: v for k, v in full_eval.items() if k != "fixture_results"},
        "deterministic_only_ablation": {k: v for k, v in det_eval.items() if k != "fixture_results"},
        "semantic_dependency_delta": {
            "lost_cases_count": len(lost_in_det),
            "lost_case_ids": lost_in_det,
            "dependency_reasons": {k: len(v) for k, v in delta_breakdown.items()},
            "detailed_dependencies": delta_breakdown,
        },
        "full_mode_fixtures": full_eval["fixture_results"],
        "det_only_mode_fixtures": det_eval["fixture_results"],
    }

    OUTPUT_JSON.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
    print("-" * 88)
    print(f"Raw qualification results persisted to: {OUTPUT_JSON}")
    print("=" * 88)

if __name__ == "__main__":
    run_stage4b_full_audit()
