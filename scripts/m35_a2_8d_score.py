"""M35 URIv1 -- A2.8D Scoring / Aggregation.

Reads docs/plans/M35_URIV1_A2_8D_TELEMETRY.json (produced by
m35_a2_8d_run.py) and computes per-detector-per-cell measurement tables,
detection recall/precision, the six-way D1/D2 overlap breakdown, and the
residual-failure cross-check against A2.8C's six known genuine RAR
limitation cases. Read-only with respect to telemetry -- no re-execution.
"""

from __future__ import annotations

import json
import collections
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_PATH = REPO_ROOT / "docs" / "plans" / "M35_URIV1_A2_8D_TELEMETRY.json"
AGG_PATH = REPO_ROOT / "docs" / "plans" / "M35_URIV1_A2_8D_AGGREGATES.json"

KNOWN_RAR_LIMITATION_CASES = {
    ("NB-D-01", "r1"), ("NB-D-02", "r1"), ("NB-H-06", "r1"),
    ("NB-J-02", "r1"), ("NB-J-04", "r1"), ("NB-L-09", "r2"),
}
KNOWN_HARNESS_ARTIFACT_CASES = {("NB-C-04", "r1"), ("NB-C-05", "r1")}

SAFE_CLASSES = {"CORRECT_ABSTENTION", "CORRECT_ABSTENTION_FAMILY_MISMATCH"}
WRONG_BINDING_CLASSES = {"INCORRECT_CONFIDENT_BINDING", "DETECTOR_FALSE_POSITIVE_BINDING"}


def load():
    return json.load(open(TELEMETRY_PATH, encoding="utf-8"))


def cell_table(recs, cell):
    rows = [r for r in recs if r["cell"] == cell and r["scoring_class"] != "UNATTRIBUTED_DETECTOR_FIND"]
    gt_rows = [r for r in rows if r["expected_outcome"] not in ("NO_REFERENCE",)]
    k_rows = [r for r in rows if r["expected_outcome"] == "NO_REFERENCE"]
    counts = collections.Counter(r["scoring_class"] for r in gt_rows)
    invented = sum(
        1 for r in rows
        if r.get("actual_outcome") == "RESOLVED"
        and r.get("actual_candidate_id") not in r.get("candidate_ids_supplied", [])
    )
    correct = counts.get("CORRECT_RESOLUTION", 0)
    wrong = counts.get("INCORRECT_CONFIDENT_BINDING", 0)
    silent = counts.get("SILENT_DETECTION_MISS", 0)
    denom = len(gt_rows)
    return {
        "cell": cell,
        "gt_rows": denom,
        "k_rows": len(k_rows),
        "scoring_class_counts": dict(counts),
        "k_scoring_class_counts": dict(collections.Counter(r["scoring_class"] for r in k_rows)),
        "correct_resolution": correct,
        "incorrect_confident_binding": wrong,
        "silent_detection_miss": silent,
        "missed_resolvable_case": counts.get("MISSED_RESOLVABLE_CASE", 0),
        "correct_abstention_total": sum(counts.get(c, 0) for c in SAFE_CLASSES),
        "invented_candidate": invented,
        "resolution_coverage": round(correct / denom, 4) if denom else None,
        "detection_recall": round((denom - silent) / denom, 4) if denom else None,
    }


def detection_precision(recs, detector, c_axis="C1"):
    """Of all spans the detector produced in this cell (attributed + unattributed),
    what fraction were attributed to a real ground-truth reference?"""
    cell = f"{detector}x{c_axis}"
    rows = [r for r in recs if r["cell"] == cell and r.get("detected_span")]
    attributed = [r for r in rows if r["scoring_class"] not in ("UNATTRIBUTED_DETECTOR_FIND", "DETECTOR_FALSE_POSITIVE_BINDING", "DETECTOR_FALSE_POSITIVE_SAFE_ABSTENTION")]
    false_positive_like = [r for r in rows if r["scoring_class"] in ("UNATTRIBUTED_DETECTOR_FIND", "DETECTOR_FALSE_POSITIVE_BINDING", "DETECTOR_FALSE_POSITIVE_SAFE_ABSTENTION")]
    total = len(rows)
    return {
        "detector": detector, "c_axis": c_axis,
        "total_spans_produced": total,
        "attributed_to_real_reference": len(attributed),
        "false_positive_or_unattributed": len(false_positive_like),
        "precision": round(len(attributed) / total, 4) if total else None,
    }


def overlap_breakdown(recs, c_axis="C1"):
    """D1 vs D2 six-way breakdown for gt-bearing references, at one C axis."""
    d1 = {(r["case_id"], r["ref_key"]): r for r in recs if r["cell"] == f"D1x{c_axis}" and r["ref_key"] is not None}
    d2 = {(r["case_id"], r["ref_key"]): r for r in recs if r["cell"] == f"D2x{c_axis}" and r["ref_key"] is not None}
    keys = sorted(set(d1) & set(d2))
    buckets = collections.Counter()
    detail = []
    for k in keys:
        d1_detected = d1[k]["scoring_class"] != "SILENT_DETECTION_MISS"
        d2_detected = d2[k]["scoring_class"] != "SILENT_DETECTION_MISS"
        d1_correct = d1[k]["scoring_class"] == "CORRECT_RESOLUTION"
        d2_correct = d2[k]["scoring_class"] == "CORRECT_RESOLUTION"
        if d1_correct and d2_correct:
            b = "both_correct"
        elif d1_correct and not d2_correct:
            b = "only_d1_correct"
        elif d2_correct and not d1_correct:
            b = "only_d2_correct"
        elif d1_detected and d2_detected:
            b = "both_detect_rar_fails_or_abstains"
        elif d1_detected and not d2_detected:
            b = "only_d1_detects"
        elif d2_detected and not d1_detected:
            b = "only_d2_detects"
        else:
            b = "neither_detects"
        buckets[b] += 1
        detail.append({"case_id": k[0], "ref_key": k[1], "bucket": b})
    return {"c_axis": c_axis, "paired_count": len(keys), "buckets": dict(buckets), "detail": detail}


def residual_rar_limitation_visibility(recs, detector, c_axis):
    """Confirms the 6 known RAR limitation cases remain individually visible
    (not silently masked) in this detector's telemetry."""
    cell = f"{detector}x{c_axis}"
    out = {}
    for case_id, ref_key in KNOWN_RAR_LIMITATION_CASES:
        rows = [r for r in recs if r["cell"] == cell and r["case_id"] == case_id and r["ref_key"] == ref_key]
        out[f"{case_id}:{ref_key}"] = rows[0]["scoring_class"] if rows else "NOT_PRESENT_IN_CELL"
    return out


def main():
    data = load()
    recs = data["records"]

    result = {
        "schema": "m35.uriv1.a2_8d.aggregates.v1",
        "pre_run_sha256": data["pre_run_sha256"],
        "post_run_sha256": data["post_run_sha256"],
        "d2_availability": data["d2_availability"],
        "d2_batch_elapsed_s": data["d2_batch_elapsed_s"],
        "cells": {},
        "precision": {},
        "overlap": {},
        "residual_rar_limitation_visibility": {},
        "boundary_violations_total": sum(1 for r in recs if r.get("boundary_violation")),
    }

    for det in ("D0", "D1", "D2"):
        for c in ("C1", "C2", "C3"):
            cell = f"{det}x{c}"
            result["cells"][cell] = cell_table(recs, cell)
        result["precision"][det] = detection_precision(recs, det, "C1")
        result["residual_rar_limitation_visibility"][det] = residual_rar_limitation_visibility(recs, det, "C1")

    result["overlap"]["C1"] = overlap_breakdown(recs, "C1")
    result["overlap"]["C2"] = overlap_breakdown(recs, "C2")

    with open(AGG_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result["cells"], indent=2))
    print(json.dumps(result["precision"], indent=2))
    print("boundary_violations_total:", result["boundary_violations_total"])
    print("Wrote", AGG_PATH)


if __name__ == "__main__":
    main()
