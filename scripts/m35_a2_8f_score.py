"""M35 URIv1 -- A2.8F Scoring / Aggregation.

Reads docs/plans/M35_URIV1_A2_8F_TELEMETRY.json and computes per-detector
per-cell tables, target-18 cluster recovery, whole-corpus regression check
(D1R vs corrected D1 baseline), false-positive/boundary summaries, and the
five-case candidate-metadata tracking set (NB-J-02, NB-J-04, NB-D-04,
NB-D-07, NB-H-01).
"""

from __future__ import annotations

import json
import collections
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_PATH = REPO_ROOT / "docs" / "plans" / "M35_URIV1_A2_8F_TELEMETRY.json"
AGG_PATH = REPO_ROOT / "docs" / "plans" / "M35_URIV1_A2_8F_AGGREGATES.json"

TARGET_18 = {
    "T1": [("NB-A-01", "r1"), ("NB-A-03", "r1"), ("NB-A-04", "r1"), ("NB-A-05", "r1")],
    "T3": [("NB-C-03", "r1"), ("NB-F-02", "r1"), ("NB-G-03", "r1"), ("NB-J-03", "r1"), ("NB-L-11", "r2")],
    "T4": [("NB-G-04", "r2"), ("NB-J-01", "r1"), ("NB-L-04", "r1"), ("NB-L-08", "r3")],
    "T5-simple": [("NB-L-11", "r1")],
    "T6": [("NB-G-01", "r1")],
    "T7": [("NB-F-03", "r1"), ("NB-L-10", "r1"), ("NB-L-10", "r2")],
}
ALL_TARGET_18 = [k for cluster in TARGET_18.values() for k in cluster]

FULL_27_RESIDUAL = ALL_TARGET_18 + [
    ("NB-B-03", "r1"),  # T8
    ("NB-B-05", "r2"), ("NB-G-04", "r1"), ("NB-I-02", "r2"), ("NB-I-06", "r2"),
    ("NB-L-01", "r2"), ("NB-L-02", "r2"), ("NB-L-04", "r2"),  # T2
    ("NB-H-02", "r1"),  # T5-compound
]

METADATA_TRACK_SET = [("NB-J-02", "r1"), ("NB-J-04", "r1"), ("NB-D-04", "r1"), ("NB-D-07", "r1"), ("NB-H-01", "r1")]

WRONG_BINDING_CLASSES = {"INCORRECT_CONFIDENT_BINDING", "DETECTOR_FALSE_POSITIVE_BINDING"}
SAFE_CLASSES = {"CORRECT_ABSTENTION", "CORRECT_ABSTENTION_FAMILY_MISMATCH"}


def load():
    return json.load(open(TELEMETRY_PATH, encoding="utf-8"))


def cell_table(recs, cell):
    rows = [r for r in recs if r["cell"] == cell and r["scoring_class"] != "UNATTRIBUTED_DETECTOR_FIND"]
    gt_rows = [r for r in rows if r["expected_outcome"] != "NO_REFERENCE"]
    k_rows = [r for r in rows if r["expected_outcome"] == "NO_REFERENCE"]
    counts = collections.Counter(r["scoring_class"] for r in gt_rows)
    invented = sum(
        1 for r in rows
        if r.get("actual_outcome") == "RESOLVED"
        and r.get("actual_candidate_id") not in r.get("candidate_ids_supplied", [])
    )
    denom = len(gt_rows)
    silent = counts.get("SILENT_DETECTION_MISS", 0)
    return {
        "cell": cell, "gt_rows": denom, "k_rows": len(k_rows),
        "scoring_class_counts": dict(counts),
        "k_scoring_class_counts": dict(collections.Counter(r["scoring_class"] for r in k_rows)),
        "correct_resolution": counts.get("CORRECT_RESOLUTION", 0),
        "incorrect_confident_binding": counts.get("INCORRECT_CONFIDENT_BINDING", 0),
        "silent_detection_miss": silent,
        "missed_resolvable_case": counts.get("MISSED_RESOLVABLE_CASE", 0),
        "correct_abstention_total": sum(counts.get(c, 0) for c in SAFE_CLASSES),
        "invented_candidate": invented,
        "detection_recall": round((denom - silent) / denom, 4) if denom else None,
        "resolution_coverage": round(counts.get("CORRECT_RESOLUTION", 0) / denom, 4) if denom else None,
    }


def target_cluster_recovery(recs, detector, c_axis="C1"):
    cell = f"{detector}x{c_axis}"
    rows = {(r["case_id"], r["ref_key"]): r for r in recs if r["cell"] == cell and r["ref_key"] is not None}
    out = {}
    for cluster, keys in TARGET_18.items():
        detected = 0
        resolved = 0
        detail = []
        for k in keys:
            r = rows.get(k)
            sc = r["scoring_class"] if r else "NOT_PRESENT"
            was_detected = sc != "SILENT_DETECTION_MISS"
            was_resolved = sc == "CORRECT_RESOLUTION"
            detected += int(was_detected)
            resolved += int(was_resolved)
            detail.append({"case_ref": f"{k[0]}:{k[1]}", "scoring_class": sc})
        out[cluster] = {"total": len(keys), "detected": detected, "resolved": resolved, "detail": detail}
    return out


def regression_check(recs, c_axis="C1"):
    """D1R vs D1 (corrected baseline), paired by (case_id, ref_key).
    A regression = D1 correctly resolved, D1R does not."""
    d1 = {(r["case_id"], r["ref_key"]): r for r in recs if r["cell"] == f"D1x{c_axis}" and r["ref_key"] is not None}
    d1r = {(r["case_id"], r["ref_key"]): r for r in recs if r["cell"] == f"D1Rx{c_axis}" and r["ref_key"] is not None}
    keys = sorted(set(d1) & set(d1r))
    regressions = []
    new_wrong_bindings = []
    gains = []
    for k in keys:
        a, b = d1[k]["scoring_class"], d1r[k]["scoring_class"]
        if a == "CORRECT_RESOLUTION" and b != "CORRECT_RESOLUTION":
            regressions.append({"case_ref": f"{k[0]}:{k[1]}", "d1": a, "d1r": b})
        if a not in WRONG_BINDING_CLASSES and b in WRONG_BINDING_CLASSES:
            new_wrong_bindings.append({"case_ref": f"{k[0]}:{k[1]}", "d1": a, "d1r": b})
        if a != "CORRECT_RESOLUTION" and b == "CORRECT_RESOLUTION":
            gains.append({"case_ref": f"{k[0]}:{k[1]}", "d1": a, "d1r": b})
    return {
        "paired_count": len(keys),
        "regressions_count": len(regressions), "regressions": regressions,
        "new_wrong_bindings_count": len(new_wrong_bindings), "new_wrong_bindings": new_wrong_bindings,
        "gains_count": len(gains), "gains": gains,
    }


def metadata_tracking(recs, detector, c_axis="C1"):
    cell = f"{detector}x{c_axis}"
    rows = {(r["case_id"], r["ref_key"]): r for r in recs if r["cell"] == cell}
    out = {}
    for k in METADATA_TRACK_SET:
        r = rows.get(k)
        out[f"{k[0]}:{k[1]}"] = {
            "scoring_class": r["scoring_class"] if r else "NOT_PRESENT",
            "recency_hint_supplied": r["signals_supplied"].get("recency_hint") if r and r.get("signals_supplied") else None,
        } if r else {"scoring_class": "NOT_PRESENT"}
    return out


def full_residual_check(recs, c_axis="C1"):
    """Of the full 27-case residual, which are now detected/resolved under D1R."""
    cell = f"D1Rx{c_axis}"
    rows = {(r["case_id"], r["ref_key"]): r for r in recs if r["cell"] == cell and r["ref_key"] is not None}
    out = []
    for k in FULL_27_RESIDUAL:
        r = rows.get(k)
        out.append({"case_ref": f"{k[0]}:{k[1]}", "scoring_class": r["scoring_class"] if r else "NOT_PRESENT"})
    return out


def false_positive_summary(recs, detector, c_axis="C1"):
    cell = f"{detector}x{c_axis}"
    rows = [r for r in recs if r["cell"] == cell]
    k_rows = [r for r in rows if r["expected_outcome"] == "NO_REFERENCE"]
    unattributed = [r for r in rows if r["scoring_class"] == "UNATTRIBUTED_DETECTOR_FIND"]
    return {
        "k_false_positive_binding": sum(1 for r in k_rows if r["scoring_class"] == "DETECTOR_FALSE_POSITIVE_BINDING"),
        "k_false_positive_safe_abstention": sum(1 for r in k_rows if r["scoring_class"] == "DETECTOR_FALSE_POSITIVE_SAFE_ABSTENTION"),
        "k_silent_correct": sum(1 for r in k_rows if r["scoring_class"] == "SILENT_DETECTION_MISS"),
        "unattributed_detector_finds": len(unattributed),
    }


def main():
    data = load()
    recs = data["records"]

    result = {
        "schema": "m35.uriv1.a2_8f.aggregates.v1",
        "pre_run_sha256": data["pre_run_sha256"],
        "post_run_sha256": data["post_run_sha256"],
        "d2_availability": data["d2_availability"],
        "cells": {}, "target_18_recovery": {}, "regression_check": {},
        "metadata_tracking": {}, "full_residual_check_D1R": {},
        "false_positive_summary": {}, "boundary_violations_total": sum(1 for r in recs if r.get("boundary_violation")),
        "invented_candidate_total": sum(
            1 for r in recs if r.get("actual_outcome") == "RESOLVED"
            and r.get("actual_candidate_id") not in r.get("candidate_ids_supplied", [])
        ),
    }

    for det in ("D0", "D1", "D2", "D1R"):
        for c in ("C1", "C2", "C3"):
            result["cells"][f"{det}x{c}"] = cell_table(recs, f"{det}x{c}")
        result["false_positive_summary"][det] = false_positive_summary(recs, det, "C1")

    result["target_18_recovery"]["D1"] = target_cluster_recovery(recs, "D1", "C1")
    result["target_18_recovery"]["D1R"] = target_cluster_recovery(recs, "D1R", "C1")
    result["regression_check"]["C1"] = regression_check(recs, "C1")
    result["regression_check"]["C2"] = regression_check(recs, "C2")
    result["metadata_tracking"]["D1"] = metadata_tracking(recs, "D1", "C1")
    result["metadata_tracking"]["D1R"] = metadata_tracking(recs, "D1R", "C1")
    result["full_residual_check_D1R"]["C1"] = full_residual_check(recs, "C1")

    with open(AGG_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("boundary_violations_total:", result["boundary_violations_total"])
    print("invented_candidate_total:", result["invented_candidate_total"])
    print(json.dumps(result["cells"], indent=2))
    print(json.dumps(result["target_18_recovery"], indent=2))
    print(json.dumps(result["regression_check"], indent=2))
    print("Wrote", AGG_PATH)


if __name__ == "__main__":
    main()
