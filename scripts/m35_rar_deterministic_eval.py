"""Evaluation Harness for M35 URIv1 Batch A2.5 Stage 2: Legacy-Derived Deterministic RAR.

Evaluates the 7-level deterministic RAR stack across the full tranche of 24 diagnostic
fixtures in uri_v1.turn.rar_fixtures under strict invariant validation and scoring rules.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from uri_v1.turn.rar_contracts import RAROutcome
from uri_v1.turn.rar_deterministic import (
    DeterministicRARTrace,
    resolve_rar_deterministic_extended,
)
from uri_v1.turn.rar_fixtures import get_rar_diagnostic_fixtures


def run_rar_deterministic_evaluation() -> Dict[str, Any]:
    """Runs all 24 diagnostic fixtures through resolve_rar_deterministic_extended."""
    fixtures = get_rar_diagnostic_fixtures()
    results: List[Dict[str, Any]] = []

    latencies: List[float] = []
    full_matches = 0
    outcome_matches = 0
    wrong_bindings = 0
    invented_candidates = 0
    rule_counts: Dict[str, int] = {}
    category_stats: Dict[str, Dict[str, int]] = {}

    for fix in fixtures:
        cat = fix.category
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0, "wrong_binding": 0}
        category_stats[cat]["total"] += 1

        cand_ids = {c.id for c in fix.query.candidates}
        trace: DeterministicRARTrace = resolve_rar_deterministic_extended(fix.query)
        res = trace.resolution

        # Check candidate invention
        if res.candidate_id and res.candidate_id not in cand_ids:
            invented_candidates += 1
        for cid in res.ambiguous_candidate_ids:
            if cid not in cand_ids:
                invented_candidates += 1

        # Check outcome match
        outcome_match = (res.outcome == fix.expected_outcome)
        if outcome_match:
            outcome_matches += 1

        # Check full match
        candidate_match = False
        wrong_binding = False

        if fix.expected_outcome == RAROutcome.RESOLVED:
            if res.outcome == RAROutcome.RESOLVED:
                if res.candidate_id == fix.expected_candidate_id:
                    candidate_match = True
                else:
                    wrong_binding = True
                    wrong_bindings += 1
            else:
                candidate_match = False
        elif fix.expected_outcome == RAROutcome.AMBIGUOUS:
            if res.outcome == RAROutcome.AMBIGUOUS:
                # Compare sets of ambiguous IDs
                if set(res.ambiguous_candidate_ids) == set(fix.expected_ambiguous_candidate_ids):
                    candidate_match = True
                else:
                    # Partial match on ambiguous candidates
                    candidate_match = len(set(res.ambiguous_candidate_ids).intersection(fix.expected_ambiguous_candidate_ids)) >= 2
            else:
                candidate_match = False
        elif fix.expected_outcome == RAROutcome.UNKNOWN:
            if res.outcome == RAROutcome.UNKNOWN:
                candidate_match = True
            elif res.outcome == RAROutcome.RESOLVED:
                wrong_binding = True
                wrong_bindings += 1

        full_match = outcome_match and candidate_match
        if full_match:
            full_matches += 1
            category_stats[cat]["correct"] += 1
        if wrong_binding:
            category_stats[cat]["wrong_binding"] += 1

        rule_name = trace.rule_used.value
        rule_counts[rule_name] = rule_counts.get(rule_name, 0) + 1
        latencies.append(trace.latency_ms)

        results.append({
            "fixture_id": fix.id,
            "fixture_name": fix.name,
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
            "latency_ms": round(trace.latency_ms, 3),
            "outcome_match": outcome_match,
            "candidate_match": candidate_match,
            "full_match": full_match,
            "wrong_binding": wrong_binding,
            "eliminated_candidates": list(trace.eliminated_candidate_ids),
        })

    # Summary metrics
    n = len(fixtures)
    sorted_latencies = sorted(latencies)
    mean_lat = statistics.mean(latencies) if latencies else 0.0
    median_lat = statistics.median(latencies) if latencies else 0.0
    p95_lat = sorted_latencies[int(len(sorted_latencies) * 0.95)] if latencies else 0.0

    summary = {
        "total_fixtures": n,
        "full_matches": full_matches,
        "full_match_rate": round(full_matches / n, 4),
        "outcome_matches": outcome_matches,
        "outcome_match_rate": round(outcome_matches / n, 4),
        "wrong_bindings": wrong_bindings,
        "invented_candidates": invented_candidates,
        "latency_mean_ms": round(mean_lat, 3),
        "latency_median_ms": round(median_lat, 3),
        "latency_p95_ms": round(p95_lat, 3),
        "rule_breakdown": rule_counts,
        "category_stats": category_stats,
        "results": results,
    }

    # Save to disk
    out_path = Path("scripts/rar_deterministic_qualification_results.json")
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def print_evaluation_report(summary: Dict[str, Any]) -> None:
    """Prints a clean human-readable report."""
    print("=" * 80)
    print("M35 URIv1 BATCH A2.5 STAGE 2 — DETERMINISTIC RAR QUALIFICATION REPORT")
    print("=" * 80)
    print(f"Total Diagnostic Fixtures : {summary['total_fixtures']}")
    print(f"Full Matches (Target)    : {summary['full_matches']}/{summary['total_fixtures']} ({summary['full_match_rate']*100:.1f}%)")
    print(f"Outcome Matches          : {summary['outcome_matches']}/{summary['total_fixtures']} ({summary['outcome_match_rate']*100:.1f}%)")
    print(f"Wrong Bindings           : {summary['wrong_bindings']} (Mandated: 0)")
    print(f"Invented Candidates      : {summary['invented_candidates']} (Mandated: 0)")
    print(f"Latency Mean             : {summary['latency_mean_ms']:.3f} ms")
    print(f"Latency Median           : {summary['latency_median_ms']:.3f} ms")
    print(f"Latency P95              : {summary['latency_p95_ms']:.3f} ms")
    print("-" * 80)
    print("CATEGORY BREAKDOWN:")
    for cat, stats in summary["category_stats"].items():
        rate = (stats["correct"] / stats["total"]) * 100
        print(f"  - {cat:25s}: {stats['correct']}/{stats['total']} ({rate:.0f}%) | Wrong: {stats['wrong_binding']}")
    print("-" * 80)
    print("RULE BREAKDOWN:")
    for rule, count in sorted(summary["rule_breakdown"].items(), key=lambda x: -x[1]):
        pct = (count / summary["total_fixtures"]) * 100
        print(f"  - {rule:25s}: {count:2d} ({pct:.1f}%)")
    print("-" * 80)
    print("FIXTURE RESULTS:")
    print(f"{'ID':<12} | {'Category':<18} | {'Ref Expression':<22} | {'Expected':<10} | {'Actual':<10} | {'Rule':<20} | {'Status'}")
    print("-" * 110)
    for r in summary["results"]:
        status = "PASS" if r["full_match"] else "FAIL"
        print(f"{r['fixture_id']:<12} | {r['category']:<18} | {r['reference_expression']:<22} | {r['expected_outcome']:<10} | {r['actual_outcome']:<10} | {r['rule_used']:<20} | {status}")
    print("=" * 80)


if __name__ == "__main__":
    summary = run_rar_deterministic_evaluation()
    print_evaluation_report(summary)
