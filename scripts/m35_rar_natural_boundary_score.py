"""M35 URIv1 -- RAR Natural-Boundary Scoring / Aggregation.

Reads the telemetry JSON produced by m35_rar_natural_boundary_run.py and
computes: per-cell measurement tables, safety metrics, stage attribution,
C1<->C2 and S1<->S2 paired analyses, failure-class distribution, and the
four-case sensitivity view. Writes a single aggregates JSON. Read-only with
respect to telemetry; performs no re-execution of RAR/TurnFrame.
"""

from __future__ import annotations

import json
import collections
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_PATH = REPO_ROOT / "docs" / "plans" / "M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json"
AGG_PATH = REPO_ROOT / "docs" / "plans" / "M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json"
SENSITIVITY_EXCLUDE = {"NB-C-06", "NB-C-07", "NB-I-06", "NB-I-07"}

SAFE_ABSTENTION_CLASSES = {"CORRECT_ABSTENTION", "CORRECT_ABSTENTION_FAMILY_MISMATCH", "K_FALSE_POSITIVE_SAFE_ABSTENTION"}
WRONG_BINDING_CLASSES = {"INCORRECT_CONFIDENT_BINDING", "K_FALSE_POSITIVE_BINDING"}


def load_telemetry():
    with open(TELEMETRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def stage_attribution(rec: dict) -> str:
    sc = rec["scoring_class"]
    cell = rec["cell"]
    if sc == "SILENT_STEP1_MISS":
        return "STEP1_EXTRACTION_FAILURE"
    if sc in ("MISSED_RESOLVABLE_CASE",):
        if cell.endswith("C3"):
            return "CANDIDATE_CONTEXT_FAILURE"
        return "RAR_RESOLUTION_FAILURE"
    if sc in WRONG_BINDING_CLASSES:
        return "RAR_RESOLUTION_FAILURE"
    if sc == "CORRECT_RESOLUTION":
        return "SUCCESS"
    if sc in SAFE_ABSTENTION_CLASSES:
        return "SUCCESS_SAFE_ABSTENTION" if sc != "CORRECT_ABSTENTION_FAMILY_MISMATCH" else "SUCCESS_SAFE_ABSTENTION_SOFT"
    return "NOT_APPLICABLE"


def cell_table(records, cell, excluded_case_ids=frozenset()):
    rows = [r for r in records if r["cell"] == cell and r["case_id"] not in excluded_case_ids]
    ref_rows = [r for r in rows if r["ref_key"] is not None or r["scoring_class"] not in ("UNATTRIBUTED_STEP1_FIND",)]
    total_applicable = len([r for r in rows if r["scoring_class"] != "UNATTRIBUTED_STEP1_FIND"])
    counts = collections.Counter(r["scoring_class"] for r in rows if r["scoring_class"] != "UNATTRIBUTED_STEP1_FIND")
    invented = sum(1 for r in rows if r["actual_outcome"] == "RESOLVED" and r["actual_candidate_id"] not in r["candidate_ids_supplied"])
    wrong_binding = sum(counts.get(c, 0) for c in WRONG_BINDING_CLASSES)
    safe_abstain = sum(counts.get(c, 0) for c in SAFE_ABSTENTION_CLASSES)
    correct_resolution = counts.get("CORRECT_RESOLUTION", 0)
    not_applicable = counts.get("NOT_APPLICABLE_NO_GT_REF", 0)
    # Rate denominators exclude NOT_APPLICABLE_NO_GT_REF (K-category rows with no
    # ground-truth reference to resolve under the oracle S2 condition -- these can
    # never be RESOLVED/AMBIGUOUS/UNKNOWN and including them in the denominator
    # mechanically deflates every rate). This was a scoring defect in the original
    # v1 aggregation (fixed independently during A2.8D pre-planning verification).
    rate_denominator = total_applicable - not_applicable
    return {
        "cell": cell,
        "total_rows": total_applicable,
        "rate_denominator": rate_denominator,
        "scoring_class_counts": dict(counts),
        "correct_resolution": correct_resolution,
        "correct_ambiguity": counts.get("CORRECT_ABSTENTION", 0),  # subset already counted in safe_abstain; reported separately per spec
        "correct_unknown_or_abstention_total": safe_abstain,
        "no_reference_correct": counts.get("CORRECT_ABSTENTION", 0) if cell.startswith("S1") else None,
        "incorrect_confident_binding": wrong_binding,
        "invented_candidate": invented,
        "missed_resolvable_case": counts.get("MISSED_RESOLVABLE_CASE", 0),
        "silent_step1_miss": counts.get("SILENT_STEP1_MISS", 0),
        "not_applicable_no_gt_ref": not_applicable,
        "resolution_coverage": round(correct_resolution / rate_denominator, 4) if rate_denominator else None,
        "safe_abstention_rate": round(safe_abstain / rate_denominator, 4) if rate_denominator else None,
        "wrong_binding_rate": round(wrong_binding / rate_denominator, 4) if rate_denominator else None,
    }


def failure_class_distribution(records, cell, excluded_case_ids=frozenset()):
    rows = [r for r in records if r["cell"] == cell and r["case_id"] not in excluded_case_ids and r["rar_failure_class"]]
    return dict(collections.Counter(r["rar_failure_class"] for r in rows))


def stage_attribution_distribution(records, cell, excluded_case_ids=frozenset()):
    rows = [r for r in records if r["cell"] == cell and r["case_id"] not in excluded_case_ids]
    return dict(collections.Counter(stage_attribution(r) for r in rows if r["scoring_class"] != "UNATTRIBUTED_STEP1_FIND"))


def paired_c1_c2(records, s_axis, excluded_case_ids=frozenset()):
    """Pairs S{s}xC1 vs S{s}xC2 by (case_id, ref_key)."""
    c1 = {(r["case_id"], r["ref_key"]): r for r in records if r["cell"] == f"{s_axis}xC1" and r["case_id"] not in excluded_case_ids and r["ref_key"] is not None}
    c2 = {(r["case_id"], r["ref_key"]): r for r in records if r["cell"] == f"{s_axis}xC2" and r["case_id"] not in excluded_case_ids and r["ref_key"] is not None}
    common_keys = sorted(set(c1) & set(c2))
    buckets = collections.Counter()
    flips_to_wrong_binding = []
    flips_to_safe_abstention = []
    for k in common_keys:
        a, b = c1[k]["scoring_class"], c2[k]["scoring_class"]
        a_ok = a in ("CORRECT_RESOLUTION",)
        b_ok = b in ("CORRECT_RESOLUTION",)
        if a_ok and b_ok:
            buckets["correct_in_both"] += 1
        elif a_ok and not b_ok:
            buckets["correct_c1_fails_c2"] += 1
            if b in WRONG_BINDING_CLASSES:
                flips_to_wrong_binding.append(k)
            elif b in SAFE_ABSTENTION_CLASSES or b == "MISSED_RESOLVABLE_CASE":
                flips_to_safe_abstention.append(k)
        elif (not a_ok) and b_ok:
            buckets["fails_c1_correct_c2"] += 1
        else:
            buckets["fails_in_both"] += 1
    return {
        "s_axis": s_axis,
        "paired_reference_count": len(common_keys),
        "buckets": dict(buckets),
        "distractor_induced_wrong_binding_count": len(flips_to_wrong_binding),
        "distractor_induced_wrong_binding_examples": [f"{k[0]}:{k[1]}" for k in flips_to_wrong_binding],
        "distractor_induced_safe_abstention_count": len(flips_to_safe_abstention),
        "distractor_induced_safe_abstention_examples": [f"{k[0]}:{k[1]}" for k in flips_to_safe_abstention[:10]],
    }


def paired_s1_s2(records, c_axis, excluded_case_ids=frozenset()):
    """Pairs S1x{c} vs S2x{c} by (case_id, ref_key), S1-invoked rows only meaningful."""
    s1 = {(r["case_id"], r["ref_key"]): r for r in records if r["cell"] == f"S1x{c_axis}" and r["case_id"] not in excluded_case_ids and r["ref_key"] is not None}
    s2 = {(r["case_id"], r["ref_key"]): r for r in records if r["cell"] == f"S2x{c_axis}" and r["case_id"] not in excluded_case_ids and r["ref_key"] is not None}
    common_keys = sorted(set(s1) & set(s2))
    buckets = collections.Counter()
    s1_fails_s2_succeeds_examples = []
    for k in common_keys:
        a, b = s1[k]["scoring_class"], s2[k]["scoring_class"]
        a_ok = a == "CORRECT_RESOLUTION"
        b_ok = b == "CORRECT_RESOLUTION"
        if a_ok and b_ok:
            buckets["s1_succeeds_s2_succeeds"] += 1
        elif (not a_ok) and b_ok:
            buckets["s1_fails_s2_succeeds"] += 1
            s1_fails_s2_succeeds_examples.append(f"{k[0]}:{k[1]} (S1={a})")
        elif a_ok and not b_ok:
            buckets["s1_succeeds_s2_fails"] += 1
        else:
            buckets["s1_fails_s2_fails"] += 1
    return {
        "c_axis": c_axis,
        "paired_reference_count": len(common_keys),
        "buckets": dict(buckets),
        "s1_fails_s2_succeeds_examples": s1_fails_s2_succeeds_examples,
    }


def main():
    data = load_telemetry()
    records = data["records"]

    result = {
        "schema": "m35.uriv1.rar_natural_boundary.aggregates.v1",
        "post_run_sha256": data["post_run_sha256"],
        "cells": {},
        "failure_class_distribution": {},
        "stage_attribution": {},
        "paired_c1_c2": {},
        "paired_s1_s2": {},
        "sensitivity": {"excluded_case_ids": sorted(SENSITIVITY_EXCLUDE), "cells": {}, "paired_c1_c2": {}, "paired_s1_s2": {}},
    }

    for cell in ("S1xC1", "S1xC2", "S1xC3", "S2xC1", "S2xC2"):
        result["cells"][cell] = cell_table(records, cell)
        result["failure_class_distribution"][cell] = failure_class_distribution(records, cell)
        result["stage_attribution"][cell] = stage_attribution_distribution(records, cell)
        result["sensitivity"]["cells"][cell] = cell_table(records, cell, excluded_case_ids=SENSITIVITY_EXCLUDE)

    for s_axis in ("S1", "S2"):
        result["paired_c1_c2"][s_axis] = paired_c1_c2(records, s_axis)
        result["sensitivity"]["paired_c1_c2"][s_axis] = paired_c1_c2(records, s_axis, excluded_case_ids=SENSITIVITY_EXCLUDE)

    for c_axis in ("C1", "C2"):
        result["paired_s1_s2"][c_axis] = paired_s1_s2(records, c_axis)
        result["sensitivity"]["paired_s1_s2"][c_axis] = paired_s1_s2(records, c_axis, excluded_case_ids=SENSITIVITY_EXCLUDE)

    # Global safety metrics (across all invoked rows, all cells)
    invoked = [r for r in records if r["rar_invoked"]]
    total_invented = sum(1 for r in invoked if r["actual_outcome"] == "RESOLVED" and r["actual_candidate_id"] not in r["candidate_ids_supplied"])
    total_wrong_binding = sum(1 for r in invoked if r["scoring_class"] in WRONG_BINDING_CLASSES)
    result["global_safety"] = {
        "total_invoked_rows": len(invoked),
        "total_invented_candidate": total_invented,
        "total_incorrect_confident_binding": total_wrong_binding,
    }

    # K-category (no-reference) false-positive summary
    k_rows = [r for r in records if r["expected_outcome"] == "NO_REFERENCE"]
    result["no_reference_false_positive_summary"] = {
        "total_k_rows_all_cells": len(k_rows),
        "step1_found_something_rows": len([r for r in k_rows if r.get("step1_found_reference")]),
        "k_false_positive_binding": len([r for r in k_rows if r["scoring_class"] == "K_FALSE_POSITIVE_BINDING"]),
        "k_false_positive_safe_abstention": len([r for r in k_rows if r["scoring_class"] == "K_FALSE_POSITIVE_SAFE_ABSTENTION"]),
    }

    with open(AGG_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result["cells"], indent=2))
    print("Wrote aggregates to", AGG_PATH)


if __name__ == "__main__":
    main()
