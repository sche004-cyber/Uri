"""M35 URIv1 -- A2.8F Execution Runner.

Runs the frozen 79-case corpus through FOUR detector paths (D0 existing
TurnFrame / D1 corrected A2.8D baseline / D2 Needle-3 narrow / D1R the
A2.8F bounded deterministic generalization) crossed with the existing
C1/C2/C3 candidate-pool conditions, calling the real, unmodified
resolve_rar_deterministic_extended() exactly once per detected reference.

D1's own module (scripts/m35_a2_8d_detector_d1.py) and its own telemetry
file (docs/plans/M35_URIV1_A2_8D_TELEMETRY.json) are read/imported but
never modified or overwritten -- this script writes to a SEPARATE telemetry
file so D1's corrected-baseline evidence stays intact and independently
re-derivable.

Frozen boundary check (same as A2.8D): every detector-produced span/field
is scanned for accidental leakage of a live candidate_id before use; any
hit is recorded as boundary_violation=True and excluded from scoring.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from m35_rar_natural_boundary_harness import (  # noqa: E402
    FIXTURE_PATH,
    build_candidate_pool,
    load_fixture,
    sha256_of,
)
from m35_a2_8d_detector_d1 import detect_references as d1_detect  # noqa: E402
from m35_a2_8f_detector_d1r import detect_references as d1r_detect  # noqa: E402
from m35_a2_8d_detector_d2_needle import (  # noqa: E402
    check_availability as d2_check_availability,
    run_batch as d2_run_batch,
    to_d1_shaped_reference as d2_to_shaped,
)

from uri_v1.turn.contracts import AttachmentReference  # noqa: E402
from uri_v1.turn.turn_frame_builder import build_turn_frame  # noqa: E402
from uri_v1.turn.rar_contracts import RAREvidence, RARQuery  # noqa: E402
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended  # noqa: E402

TELEMETRY_PATH = REPO_ROOT / "docs" / "plans" / "M35_URIV1_A2_8F_TELEMETRY.json"
CELLS_C = ("C1", "C2", "C3")


def find_matching_found_expr(gt_span: Optional[str], found_exprs: Sequence[str], used: set) -> Optional[str]:
    """Bidirectional substring match -- the A2.8E-fixed version, applied
    identically here from the start (not re-broken)."""
    if not gt_span:
        return None
    gt_lower = gt_span.lower()
    for expr in found_exprs:
        if expr in used:
            continue
        expr_lower = expr.lower()
        if expr_lower in gt_lower or gt_lower in expr_lower:
            return expr
    return None


def boundary_violation(span: Optional[str], candidate_ids: Sequence[str], raw_text: str = "") -> bool:
    """A genuine boundary violation is the DETECTOR fabricating/injecting a
    live candidate_id the user never actually wrote -- not the detector
    faithfully reporting a span that happens to equal an ID because the
    USER typed that literal ID in their own turn (e.g. "use file <uuid>
    for this"). The T1 code/UUID mechanism is explicitly designed to
    extract exactly such user-typed literal IDs verbatim, so a check that
    treats "span contains a candidate_id substring" alone as disqualifying
    would flag legitimate verbatim extraction as a fabricated violation.
    The correct check: flag only when the candidate_id substring appears in
    the detector's span but does NOT appear verbatim in the raw user text
    -- i.e. the detector, not the user, is the source of that ID.
    """
    if not span:
        return False
    span_low = span.lower()
    raw_low = raw_text.lower()
    for cid in candidate_ids:
        cid_low = cid.lower()
        if cid_low in span_low or span_low == cid_low:
            if cid_low not in raw_low:
                return True  # genuine: detector introduced an ID the user never wrote
    return False


def build_query(reference_expression: str, candidates, recency_hint, negation_spans, target_type_hint=None) -> RARQuery:
    evidence = RAREvidence(
        recency_hint=recency_hint,
        negation_spans=tuple(negation_spans or ()),
        target_type_hint=target_type_hint,
    )
    return RARQuery(
        reference_expression=reference_expression,
        candidates=candidates,
        local_evidence=evidence,
        deterministic_anchor=None,
    )


def run_d0_case(raw_text: str, turn_attachments: Sequence[str]):
    attachments = tuple(AttachmentReference(identifier=a) for a in turn_attachments)
    tf = build_turn_frame(raw_text, attachments=attachments)
    refs = []
    for cr in tf.candidate_references:
        refs.append({
            "span": cr.expression,
            "recency_hint": "same" if cr.expression in ("same", "same thing") else None,
            "negation_spans": tf.negation_spans,
            "coarse_type": None,
        })
    return refs


def run_d1_case(raw_text: str):
    out = []
    for r in d1_detect(raw_text):
        out.append({"span": r.span, "recency_hint": r.recency_hint, "negation_spans": r.negation_spans,
                     "coarse_type": r.coarse_type, "mechanism": r.mechanism})
    return out


def run_d1r_case(raw_text: str):
    out = []
    for r in d1r_detect(raw_text):
        out.append({"span": r.span, "recency_hint": r.recency_hint, "negation_spans": r.negation_spans,
                     "coarse_type": r.coarse_type, "mechanism": r.mechanism})
    return out


def main() -> None:
    pre_hash = sha256_of(FIXTURE_PATH)
    data = load_fixture()
    library = data["candidate_library"]
    cases = data["cases"]

    d2_unavailable_reason = d2_check_availability()
    d2_results_by_case: Dict[str, dict] = {}
    d2_run_started = time.perf_counter()
    if d2_unavailable_reason is None:
        batch_payload = [{"case_id": c["case_id"], "text": c["raw_user_text"]} for c in cases]
        d2_results_by_case = d2_run_batch(batch_payload)
    d2_run_elapsed_s = time.perf_counter() - d2_run_started

    telemetry: List[dict] = []

    for case in cases:
        case_id = case["case_id"]
        category = case["category"]
        raw_text = case["raw_user_text"]
        turn_attachments = case["conversation_context"]["turn_attachments"]
        gt_refs = case["ground_truth_references"]
        gt_by_key = {r["ref_key"]: r for r in gt_refs}
        variants_by_cond = {v["candidate_condition"]: v for v in case["variants"]}

        d0_found = run_d0_case(raw_text, turn_attachments)
        d1_found = run_d1_case(raw_text)
        d1r_found = run_d1r_case(raw_text)

        d2_raw = d2_results_by_case.get(case_id)
        d2_shaped = None
        if d2_raw is not None and d2_raw.get("status") == "ok":
            d2_shaped = d2_to_shaped(d2_raw)
        d2_found = [d2_shaped] if d2_shaped else []

        detectors = {"D0": d0_found, "D1": d1_found, "D2": d2_found, "D1R": d1r_found}

        for detector_id, found_list in detectors.items():
            found_spans = [f["span"] for f in found_list]
            used_spans: set = set()
            match_for_ref: Dict[str, Optional[dict]] = {}
            for ref_key, gt in gt_by_key.items():
                m_expr = find_matching_found_expr(gt.get("human_marked_span"), found_spans, used_spans)
                if m_expr is not None:
                    used_spans.add(m_expr)
                    match_for_ref[ref_key] = next(f for f in found_list if f["span"] == m_expr)
                else:
                    match_for_ref[ref_key] = None
            unattributed = [f for f in found_list if f["span"] not in used_spans]

            for c_axis in CELLS_C:
                if c_axis == "C3":
                    candidate_ids: Sequence[str] = ()
                    variant = None
                else:
                    variant = variants_by_cond[c_axis]
                    candidate_ids = variant["available_candidates"]
                candidates = build_candidate_pool(candidate_ids, library, oracle_recency=False)
                expected_by_ref = {}
                if variant is not None:
                    for eb in variant["expected_by_reference"]:
                        expected_by_ref[eb["ref_key"]] = eb

                if not gt_refs:
                    if found_list:
                        for f in found_list:
                            bv = boundary_violation(f["span"], candidate_ids, raw_text)
                            if bv:
                                telemetry.append(_row(
                                    case_id, category, detector_id, c_axis, None, f["span"],
                                    "NO_REFERENCE", [], candidate_ids, f, None, boundary_violation=True,
                                ))
                                continue
                            q = build_query(f["span"], candidates, f["recency_hint"], f["negation_spans"], f.get("coarse_type"))
                            trace = resolve_rar_deterministic_extended(q)
                            telemetry.append(_row(
                                case_id, category, detector_id, c_axis, None, f["span"],
                                "NO_REFERENCE", [], candidate_ids, f, trace,
                            ))
                    else:
                        telemetry.append(_row(
                            case_id, category, detector_id, c_axis, None, None,
                            "NO_REFERENCE", [], candidate_ids, None, None,
                        ))
                    continue

                for ref_key, gt in gt_by_key.items():
                    eb = expected_by_ref.get(ref_key, {})
                    expected_outcome = eb.get("expected_outcome", "UNKNOWN")
                    intended_ids = eb.get("intended_candidate_ids", [])
                    f = match_for_ref.get(ref_key)

                    if f is None:
                        telemetry.append(_row(
                            case_id, category, detector_id, c_axis, ref_key, None,
                            expected_outcome, intended_ids, candidate_ids, None, None,
                            scoring_class_override="SILENT_DETECTION_MISS",
                        ))
                        continue

                    bv = boundary_violation(f["span"], candidate_ids, raw_text)
                    if bv:
                        telemetry.append(_row(
                            case_id, category, detector_id, c_axis, ref_key, f["span"],
                            expected_outcome, intended_ids, candidate_ids, f, None, boundary_violation=True,
                        ))
                        continue

                    q = build_query(f["span"], candidates, f["recency_hint"], f["negation_spans"], f.get("coarse_type"))
                    trace = resolve_rar_deterministic_extended(q)
                    telemetry.append(_row(
                        case_id, category, detector_id, c_axis, ref_key, f["span"],
                        expected_outcome, intended_ids, candidate_ids, f, trace,
                    ))

                for f in unattributed:
                    bv = boundary_violation(f["span"], candidate_ids, raw_text)
                    telemetry.append(_row(
                        case_id, category, detector_id, c_axis, None, f["span"],
                        "UNATTRIBUTED_DETECTOR_FIND", [], candidate_ids, f, None,
                        boundary_violation=bv, scoring_class_override="UNATTRIBUTED_DETECTOR_FIND",
                    ))

    post_hash = sha256_of(FIXTURE_PATH)

    output = {
        "schema": "m35.uriv1.a2_8f.telemetry.v1",
        "fixture_path": str(FIXTURE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "pre_run_sha256": pre_hash,
        "post_run_sha256": post_hash,
        "d2_availability": "AVAILABLE" if d2_unavailable_reason is None else d2_unavailable_reason,
        "d2_batch_elapsed_s": d2_run_elapsed_s,
        "d2_cases_with_result": len(d2_results_by_case),
        "records": telemetry,
    }
    TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TELEMETRY_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(telemetry)} telemetry records to {TELEMETRY_PATH}")
    print(f"Pre-run SHA-256:  {pre_hash}")
    print(f"Post-run SHA-256: {post_hash}")
    print(f"D2 availability: {output['d2_availability']}")


def _row(case_id, category, detector_id, c_axis, ref_key, span, expected_outcome,
         intended_ids, candidate_ids, found, trace, boundary_violation=False,
         scoring_class_override=None):
    row = {
        "case_id": case_id, "category": category, "detector": detector_id,
        "cell": f"{detector_id}x{c_axis}", "c_axis": c_axis, "ref_key": ref_key,
        "detected_span": span, "expected_outcome": expected_outcome,
        "intended_candidate_ids": intended_ids, "candidate_ids_supplied": list(candidate_ids),
        "signals_supplied": {
            "recency_hint": found.get("recency_hint") if found else None,
            "negation_spans": list(found.get("negation_spans") or ()) if found else [],
            "coarse_type": found.get("coarse_type") if found else None,
        } if found else {},
        "mechanism": found.get("mechanism") if found else None,
        "boundary_violation": boundary_violation,
    }
    if trace is not None:
        row.update({
            "rar_invoked": True,
            "actual_outcome": trace.resolution.outcome.value,
            "actual_candidate_id": trace.resolution.candidate_id,
            "actual_ambiguous_ids": list(trace.resolution.ambiguous_candidate_ids),
            "rar_failure_class": trace.failure_class.value if trace.failure_class else None,
            "rule_used": trace.rule_used.value if trace.rule_used else None,
            "latency_ms": trace.latency_ms,
        })
    else:
        row.update({
            "rar_invoked": False, "actual_outcome": None, "actual_candidate_id": None,
            "actual_ambiguous_ids": [], "rar_failure_class": None, "rule_used": None, "latency_ms": None,
        })

    if scoring_class_override:
        row["scoring_class"] = scoring_class_override
    elif boundary_violation:
        row["scoring_class"] = "BOUNDARY_VIOLATION"
    elif not row["rar_invoked"]:
        row["scoring_class"] = "SILENT_DETECTION_MISS"
    else:
        row["scoring_class"] = _classify(row)
    return row


def _classify(row: dict) -> str:
    expected = row["expected_outcome"]
    actual = row["actual_outcome"]
    intended = row["intended_candidate_ids"]
    cid = row["actual_candidate_id"]

    if expected == "NO_REFERENCE":
        return "DETECTOR_FALSE_POSITIVE_BINDING" if actual == "RESOLVED" else "DETECTOR_FALSE_POSITIVE_SAFE_ABSTENTION"
    if expected == "UNATTRIBUTED_DETECTOR_FIND":
        return "UNATTRIBUTED_DETECTOR_FIND"

    if actual == "RESOLVED":
        if expected == "RESOLVED" and cid in intended:
            return "CORRECT_RESOLUTION"
        return "INCORRECT_CONFIDENT_BINDING"
    if expected == "RESOLVED":
        return "MISSED_RESOLVABLE_CASE"
    if expected in ("AMBIGUOUS", "UNKNOWN"):
        return "CORRECT_ABSTENTION" if actual == expected else "CORRECT_ABSTENTION_FAMILY_MISMATCH"
    return "UNCLASSIFIED_OBSERVED_OUTCOME"


if __name__ == "__main__":
    main()
