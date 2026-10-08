"""Live qualification probe for Batch A2.1: Needle 3 Narrow-Schema Experiment.

Runs all 18 prompts across Schemas A, B, C, and D against the live Needle 3
generation-3 model via NeedleBridgeTransport.
Records full raw output, function calls, no-calls, confidences, latencies,
and normalized results to a JSON file.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from uri_v1.turn.needle_narrow import (
    NeedleNarrowSemanticExtractor,
    SCHEMA_A_TOOL_NAME,
    SCHEMA_B_TOOL_NAME,
    SCHEMA_C_TOOL_NAME,
    SCHEMA_D_TOOL_NAME,
)
from uri_v1.turn.needle_merge import merge_narrow_results

REQUIRED_CASES = [
    ("R1", "Convert this to PDF."),
    ("R2", "Bring that file up."),
    ("R3", "Do the same thing for them."),
    ("R4", "Don't send it. Just draft the email."),
    ("R5", "Find the previous approval, compare it with this one and draft a revised order."),
    (
        "R6",
        "The committee has already changed its view twice and the latest letter doesn't "
        "seem to match what was decided earlier. I need something I can put up tomorrow.",
    ),
    (
        "R7",
        "Compare only the 2025 and 2026 decisions, do not use anything before 2025, "
        "and keep the result under one page.",
    ),
    ("R8", "Draft a short formal email in Indian English to the Chief Warden."),
    ("R9", "Do not summarize this; compare the exact figures in a table."),
    ("R10", "What was approved yesterday?"),
]

STRESS_CASES = [
    ("S1", "Hello"),
    ("S2", "Thanks"),
    ("S3", "Open calculator."),
    ("S4", "Don't open it yet."),
    ("S5", "Send it to him after they approve it."),
    ("S6", "Compare the attached PDF with this spreadsheet."),
    ("S7", "Make something I can submit tomorrow."),
    ("S8", "No, I meant the earlier one."),
]


def run_probe():
    repo_root = Path(__file__).parent.parent
    venv_python = default_venv_python()
    bridge_script = repo_root / "uri_v1" / "turn" / "needle_bridge_runtime.py"

    print(f"Using Needle Python: {venv_python}")
    print(f"Using Bridge Script: {bridge_script}")

    transport = NeedleBridgeTransport(venv_python, bridge_script)
    extractor = NeedleNarrowSemanticExtractor(transport)

    transport.load()
    print("Bridge ready:", transport.runtime_info)

    all_cases = REQUIRED_CASES + STRESS_CASES
    results = {
        "runtime_info": transport.runtime_info,
        "schema_a": [],
        "schema_b": [],
        "schema_c": [],
        "schema_d": [],
        "merged": [],
    }

    # Run Schema A
    print("\n--- Running Schema A (Goal/Intent) ---")
    for pid, text in all_cases:
        res = extractor.extract_goal(text)
        item = {
            "id": pid,
            "text": text,
            "ok": res.ok,
            "goal": res.goal,
            "intent_family": res.intent_family.value if res.intent_family else None,
            "declined": res.declined,
            "call_count": res.call_count,
            "raw_confidence": res.raw_confidence,
            "latency_ms": res.latency_ms,
            "error_reason": res.error.reason.value if res.error else None,
            "error_detail": str(res.error) if res.error else None,
            "raw_wire": res.raw_wire,
        }
        results["schema_a"].append(item)
        print(f"[{pid}] ok={res.ok} declined={res.declined} calls={res.call_count} lat={res.latency_ms:.1f}ms goal='{res.goal}' intent={res.intent_family.value if res.intent_family else None}")

    # Run Schema B
    print("\n--- Running Schema B (Operations/Negation) ---")
    for pid, text in all_cases:
        res = extractor.extract_operations(text)
        item = {
            "id": pid,
            "text": text,
            "ok": res.ok,
            "requested_operations": list(res.requested_operations),
            "prohibited_operations": list(res.prohibited_operations),
            "declined": res.declined,
            "call_count": res.call_count,
            "raw_confidence": res.raw_confidence,
            "latency_ms": res.latency_ms,
            "error_reason": res.error.reason.value if res.error else None,
            "error_detail": str(res.error) if res.error else None,
            "raw_wire": res.raw_wire,
        }
        results["schema_b"].append(item)
        print(f"[{pid}] ok={res.ok} declined={res.declined} calls={res.call_count} lat={res.latency_ms:.1f}ms req={res.requested_operations} proh={res.prohibited_operations}")

    # Run Schema C
    print("\n--- Running Schema C (References/Temporal) ---")
    for pid, text in all_cases:
        res = extractor.extract_references(text)
        item = {
            "id": pid,
            "text": text,
            "ok": res.ok,
            "references": list(res.references),
            "temporal_references": list(res.temporal_references),
            "declined": res.declined,
            "call_count": res.call_count,
            "raw_confidence": res.raw_confidence,
            "latency_ms": res.latency_ms,
            "error_reason": res.error.reason.value if res.error else None,
            "error_detail": str(res.error) if res.error else None,
            "raw_wire": res.raw_wire,
        }
        results["schema_c"].append(item)
        print(f"[{pid}] ok={res.ok} declined={res.declined} calls={res.call_count} lat={res.latency_ms:.1f}ms refs={res.references} trefs={res.temporal_references}")

    # Run Schema D
    print("\n--- Running Schema D (Constraints/Preferences) ---")
    for pid, text in all_cases:
        res = extractor.extract_constraints(text)
        c_dict = {
            "included_items": list(res.constraints.included_items),
            "excluded_items": list(res.constraints.excluded_items),
            "length_limit": res.constraints.length_limit,
            "language_constraints": res.constraints.language_constraints,
        }
        p_dict = {
            "artifact_type": res.output_preferences.artifact_type,
            "tone": res.output_preferences.tone,
            "audience": res.output_preferences.audience,
            "language": res.output_preferences.language,
            "language_variant": res.output_preferences.language_variant,
            "length": res.output_preferences.length,
            "structure": res.output_preferences.structure,
        }
        item = {
            "id": pid,
            "text": text,
            "ok": res.ok,
            "constraints": c_dict,
            "output_preferences": p_dict,
            "declined": res.declined,
            "call_count": res.call_count,
            "raw_confidence": res.raw_confidence,
            "latency_ms": res.latency_ms,
            "error_reason": res.error.reason.value if res.error else None,
            "error_detail": str(res.error) if res.error else None,
            "raw_wire": res.raw_wire,
        }
        results["schema_d"].append(item)
        print(f"[{pid}] ok={res.ok} declined={res.declined} calls={res.call_count} lat={res.latency_ms:.1f}ms const={c_dict['included_items']}/{c_dict['excluded_items']} prefs={p_dict['artifact_type']}/{p_dict['tone']}/{p_dict['structure']}")

    # Run Deterministic Merge on the results
    print("\n--- Running Deterministic Merge ---")
    for i, (pid, text) in enumerate(all_cases):
        ga = results["schema_a"][i]
        gb = results["schema_b"][i]
        gc = results["schema_c"][i]
        gd = results["schema_d"][i]

        from uri_v1.turn.needle_narrow import (
            NarrowGoalResult,
            NarrowOperationsResult,
            NarrowReferencesResult,
            NarrowConstraintsResult,
        )
        from uri_v1.turn.contracts import IntentFamily, ConstraintScope, OutputPreferences

        goal_obj = NarrowGoalResult(
            goal=ga["goal"] or "",
            intent_family=IntentFamily(ga["intent_family"]) if ga["intent_family"] else IntentFamily.UNSPECIFIED,
            raw_confidence=ga["raw_confidence"],
            latency_ms=ga["latency_ms"],
            declined=ga["declined"],
        )
        ops_obj = NarrowOperationsResult(
            requested_operations=tuple(gb["requested_operations"]),
            prohibited_operations=tuple(gb["prohibited_operations"]),
            raw_confidence=gb["raw_confidence"],
            latency_ms=gb["latency_ms"],
            declined=gb["declined"],
        )
        refs_obj = NarrowReferencesResult(
            references=tuple(gc["references"]),
            temporal_references=tuple(gc["temporal_references"]),
            raw_confidence=gc["raw_confidence"],
            latency_ms=gc["latency_ms"],
            declined=gc["declined"],
        )
        const_obj = NarrowConstraintsResult(
            constraints=ConstraintScope(
                included_items=tuple(gd["constraints"]["included_items"]),
                excluded_items=tuple(gd["constraints"]["excluded_items"]),
                length_limit=gd["constraints"]["length_limit"],
                language_constraints=gd["constraints"]["language_constraints"],
            ),
            output_preferences=OutputPreferences(
                artifact_type=gd["output_preferences"]["artifact_type"],
                tone=gd["output_preferences"]["tone"],
                audience=gd["output_preferences"]["audience"],
                language=gd["output_preferences"]["language"],
                language_variant=gd["output_preferences"]["language_variant"],
                length=gd["output_preferences"]["length"],
                structure=gd["output_preferences"]["structure"],
            ),
            raw_confidence=gd["raw_confidence"],
            latency_ms=gd["latency_ms"],
            declined=gd["declined"],
        )

        try:
            merged = merge_narrow_results(goal_obj, ops_obj, refs_obj, const_obj, DecodeInput.from_text(text))
            merged_item = {
                "id": pid,
                "text": text,
                "merge_ok": True,
                "goal": merged.goal.description,
                "intent_family": merged.goal.intent_family.value,
                "operations_count": len(merged.operations),
                "references_count": len(merged.references),
                "temporal_count": len(merged.temporal_references),
                "dependencies_count": len(merged.dependencies),
                "confidence_overall": merged.confidence.overall.value,
                "total_sequential_latency_ms": (
                    (ga["latency_ms"] or 0)
                    + (gb["latency_ms"] or 0)
                    + (gc["latency_ms"] or 0)
                    + (gd["latency_ms"] or 0)
                ),
            }
        except Exception as exc:
            merged_item = {
                "id": pid,
                "text": text,
                "merge_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        results["merged"].append(merged_item)
        print(f"[{pid}] merge_ok={merged_item['merge_ok']} total_seq_lat={merged_item.get('total_sequential_latency_ms', 0):.1f}ms")

    extractor.close()

    out_path = repo_root / "scripts" / "narrow_qualification_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved full results to {out_path}")


if __name__ == "__main__":
    run_probe()
