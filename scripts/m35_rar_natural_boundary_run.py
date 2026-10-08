"""M35 URIv1 -- RAR Natural-Boundary Execution Runner.

Runs the frozen corpus through the five approved cells (S1xC1, S1xC2, S1xC3,
S2xC1, S2xC2) against the real, unmodified TurnFrame builder and RAR
deterministic resolver. Writes per-case-per-reference telemetry and a
scored aggregate summary. No RAR/TurnFrame/contract file is modified.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from m35_rar_natural_boundary_harness import (  # noqa: E402
    FIXTURE_PATH,
    SENSITIVITY_EXCLUDE_CASE_IDS,
    TELEMETRY_PATH,
    build_candidate_pool,
    load_fixture,
    run_s1_extraction,
    s1_query_for_expression,
    s2_query_for_reference,
    sha256_of,
)
from uri_v1.turn.rar_contracts import RAROutcome, RARDeterministicAnchor  # noqa: E402
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended  # noqa: E402

CELLS = ("S1xC1", "S1xC2", "S1xC3", "S2xC1", "S2xC2")


def find_matching_found_expr(gt_span: Optional[str], found_exprs: Sequence[str], used: set) -> Optional[str]:
    """Mechanical overlap check between a TurnFrame-found expression and the
    oracle's human-marked span for the SAME case. Never used to feed RAR --
    only to attribute which (if any) TurnFrame output corresponds to this
    ground-truth reference, so SILENT_STEP1_MISS is observable."""
    if not gt_span:
        return None
    gt_lower = gt_span.lower()
    for expr in found_exprs:
        if expr in used:
            continue
        if expr.lower() in gt_lower:
            return expr
    return None


def classify_reference_result(
    expected_outcome: str,
    intended_candidate_ids: Sequence[str],
    actual_outcome: Optional[str],
    actual_candidate_id: Optional[str],
    invoked: bool,
) -> str:
    """Scoring-level bucket (distinct from RAR's own internal failure_class)."""
    if not invoked:
        return "SILENT_STEP1_MISS"

    if actual_outcome == "RESOLVED":
        if expected_outcome == "RESOLVED" and actual_candidate_id in intended_candidate_ids:
            return "CORRECT_RESOLUTION"
        return "INCORRECT_CONFIDENT_BINDING"

    # actual is AMBIGUOUS or UNKNOWN (safe, non-binding)
    if expected_outcome == "RESOLVED":
        return "MISSED_RESOLVABLE_CASE"
    if expected_outcome in ("AMBIGUOUS", "UNKNOWN"):
        if actual_outcome == expected_outcome:
            return "CORRECT_ABSTENTION"
        return "CORRECT_ABSTENTION_FAMILY_MISMATCH"
    return "UNCLASSIFIED_OBSERVED_OUTCOME"


def run_reference_cell(
    ref_expr: str,
    candidates,
    negation_spans_or_none,
    is_s1: bool,
    gt_ref: Optional[dict],
):
    if is_s1:
        query = s1_query_for_expression(ref_expr, candidates, negation_spans_or_none)
    else:
        query = s2_query_for_reference(gt_ref, candidates)
    trace = resolve_rar_deterministic_extended(query)
    return trace, query


def main() -> None:
    data = load_fixture()
    library = data["candidate_library"]
    cases = data["cases"]

    telemetry: List[dict] = []

    for case in cases:
        case_id = case["case_id"]
        category = case["category"]
        raw_text = case["raw_user_text"]
        turn_attachments = case["conversation_context"]["turn_attachments"]
        gt_refs = case["ground_truth_references"]
        gt_by_key = {r["ref_key"]: r for r in gt_refs}

        # --- S1 extraction: run TurnFrame ONCE per case (candidate-condition independent) ---
        s1_extraction = run_s1_extraction(raw_text, turn_attachments)
        found_exprs = list(s1_extraction.found_reference_exprs)

        # Attribute each found expression to a ground-truth reference (or none).
        used_exprs: set = set()
        match_for_ref: Dict[str, Optional[str]] = {}
        for ref_key, gt in gt_by_key.items():
            m = find_matching_found_expr(gt.get("human_marked_span"), found_exprs, used_exprs)
            match_for_ref[ref_key] = m
            if m is not None:
                used_exprs.add(m)
        unattributed_found = [e for e in found_exprs if e not in used_exprs]

        variants_by_cond = {v["candidate_condition"]: v for v in case["variants"]}

        for cell in CELLS:
            s_axis, c_axis = cell.split("x")
            is_s1 = s_axis == "S1"

            if c_axis == "C3":
                candidate_ids: Sequence[str] = ()
                variant = None
            else:
                variant = variants_by_cond[c_axis]
                candidate_ids = variant["available_candidates"]

            expected_by_ref = {}
            if variant is not None:
                for eb in variant["expected_by_reference"]:
                    expected_by_ref[eb["ref_key"]] = eb

            oracle_recency = not is_s1  # S2 uses created_at-derived ranking; S1 mirrors real hardcoded rank=0
            candidates = build_candidate_pool(candidate_ids, library, oracle_recency=oracle_recency)

            # --- No-reference (K) cases: check for Step-1 false positives ---
            if not gt_refs:
                if is_s1 and found_exprs:
                    for expr in found_exprs:
                        trace, query = run_reference_cell(expr, candidates, s1_extraction.turn_frame_negation_spans, True, None)
                        telemetry.append({
                            "case_id": case_id, "category": category, "cell": cell,
                            "ref_key": None, "reference_expression": expr,
                            "expected_outcome": "NO_REFERENCE",
                            "intended_candidate_ids": [],
                            "rar_invoked": True,
                            "candidate_ids_supplied": list(candidate_ids),
                            "signals_supplied": {
                                "recency_hint": query.local_evidence.recency_hint,
                                "negation_spans": list(query.local_evidence.negation_spans),
                                "target_type_hint": query.local_evidence.target_type_hint,
                            },
                            "actual_outcome": trace.resolution.outcome.value,
                            "actual_candidate_id": trace.resolution.candidate_id,
                            "actual_ambiguous_ids": list(trace.resolution.ambiguous_candidate_ids),
                            "rar_failure_class": trace.failure_class.value if trace.failure_class else None,
                            "rule_used": trace.rule_used.value if trace.rule_used else None,
                            "latency_ms": trace.latency_ms,
                            "scoring_class": "K_FALSE_POSITIVE_BINDING" if trace.resolution.outcome == RAROutcome.RESOLVED else "K_FALSE_POSITIVE_SAFE_ABSTENTION",
                            "step1_found_reference": True,
                        })
                else:
                    telemetry.append({
                        "case_id": case_id, "category": category, "cell": cell,
                        "ref_key": None, "reference_expression": None,
                        "expected_outcome": "NO_REFERENCE",
                        "intended_candidate_ids": [],
                        "rar_invoked": False,
                        "candidate_ids_supplied": list(candidate_ids),
                        "signals_supplied": {},
                        "actual_outcome": "NO_REFERENCE" if is_s1 else None,
                        "actual_candidate_id": None,
                        "actual_ambiguous_ids": [],
                        "rar_failure_class": None,
                        "rule_used": None,
                        "latency_ms": None,
                        "scoring_class": "CORRECT_ABSTENTION" if is_s1 else "NOT_APPLICABLE_NO_GT_REF",
                        "step1_found_reference": False,
                    })
                continue

            # --- Reference-bearing cases ---
            for ref_key, gt in gt_by_key.items():
                eb = expected_by_ref.get(ref_key, {})
                expected_outcome = eb.get("expected_outcome", "UNKNOWN")
                intended_ids = eb.get("intended_candidate_ids", [])

                if is_s1:
                    matched_expr = match_for_ref.get(ref_key)
                    if matched_expr is None:
                        telemetry.append({
                            "case_id": case_id, "category": category, "cell": cell,
                            "ref_key": ref_key, "reference_expression": None,
                            "expected_outcome": expected_outcome,
                            "intended_candidate_ids": intended_ids,
                            "rar_invoked": False,
                            "candidate_ids_supplied": list(candidate_ids),
                            "signals_supplied": {},
                            "actual_outcome": None,
                            "actual_candidate_id": None,
                            "actual_ambiguous_ids": [],
                            "rar_failure_class": None,
                            "rule_used": None,
                            "latency_ms": None,
                            "scoring_class": "SILENT_STEP1_MISS",
                            "step1_found_reference": False,
                            "human_marked_span": gt.get("human_marked_span"),
                        })
                        continue
                    trace, query = run_reference_cell(
                        matched_expr, candidates, s1_extraction.turn_frame_negation_spans, True, gt
                    )
                    ref_expr_used = matched_expr
                else:
                    trace, query = run_reference_cell(None, candidates, None, False, gt)
                    ref_expr_used = query.reference_expression

                scoring_class = classify_reference_result(
                    expected_outcome, intended_ids,
                    trace.resolution.outcome.value, trace.resolution.candidate_id,
                    invoked=True,
                )

                telemetry.append({
                    "case_id": case_id, "category": category, "cell": cell,
                    "ref_key": ref_key, "reference_expression": ref_expr_used,
                    "expected_outcome": expected_outcome,
                    "intended_candidate_ids": intended_ids,
                    "rar_invoked": True,
                    "candidate_ids_supplied": list(candidate_ids),
                    "signals_supplied": {
                        "recency_hint": query.local_evidence.recency_hint,
                        "negation_spans": list(query.local_evidence.negation_spans),
                        "target_type_hint": query.local_evidence.target_type_hint,
                    },
                    "actual_outcome": trace.resolution.outcome.value,
                    "actual_candidate_id": trace.resolution.candidate_id,
                    "actual_ambiguous_ids": list(trace.resolution.ambiguous_candidate_ids),
                    "rar_failure_class": trace.failure_class.value if trace.failure_class else None,
                    "rule_used": trace.rule_used.value if trace.rule_used else None,
                    "latency_ms": trace.latency_ms,
                    "scoring_class": scoring_class,
                    "step1_found_reference": True if is_s1 else None,
                    "human_marked_span": gt.get("human_marked_span"),
                })

            # Record unattributed Step-1 finds (spurious finds not matching any gt ref) once per cell, S1 only
            if is_s1 and unattributed_found:
                for expr in unattributed_found:
                    telemetry.append({
                        "case_id": case_id, "category": category, "cell": cell,
                        "ref_key": None, "reference_expression": expr,
                        "expected_outcome": "UNATTRIBUTED_STEP1_FIND",
                        "intended_candidate_ids": [],
                        "rar_invoked": False,
                        "candidate_ids_supplied": list(candidate_ids),
                        "signals_supplied": {},
                        "actual_outcome": None,
                        "actual_candidate_id": None,
                        "actual_ambiguous_ids": [],
                        "rar_failure_class": None,
                        "rule_used": None,
                        "latency_ms": None,
                        "scoring_class": "UNATTRIBUTED_STEP1_FIND",
                        "step1_found_reference": True,
                    })

    # --- Post-run corpus integrity check ---
    post_hash = sha256_of(FIXTURE_PATH)

    output = {
        "schema": "m35.uriv1.rar_natural_boundary.telemetry.v1",
        "fixture_path": str(FIXTURE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "post_run_sha256": post_hash,
        "sensitivity_excluded_case_ids": sorted(SENSITIVITY_EXCLUDE_CASE_IDS),
        "records": telemetry,
    }

    TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TELEMETRY_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(telemetry)} telemetry records to {TELEMETRY_PATH}")
    print(f"Post-run SHA-256: {post_hash}")


if __name__ == "__main__":
    main()
