"""Live Empirical Qualification Probe for Batch A2.3:

TurnFrame + Compact Active Context + Adaptive Needle.

Executes comprehensive evaluation:
  1. Variant A (Baseline): 18 baseline prompts without active context.
  2. Variant B (Active Context): 6 conversational turns with active session artifacts/entities.
  3. Variant C (ID Selection vs Free-Text): Comparison on candidate action/ref extraction.
  4. Variant D (Reset vs Stale Reuse): Measuring dialogue context bleed across sequential turns.

Saves full metrics and per-turn breakdown to scripts/scaffolded_needle_results.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.contracts import (
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
)
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from uri_v1.turn.needle_scaffolded import ScaffoldedNeedleDecoder, ScaffoldedNeedleResult
from uri_v1.turn.needle_semantic_views import (
    SCHEMA_SELECT_OPERATIONS_FREETEXT,
    SCHEMA_SELECT_REFERENCES_FREETEXT,
    SYSTEM_SELECT_OPERATIONS_FREETEXT,
    SYSTEM_SELECT_REFERENCES_FREETEXT,
)

# ---------------------------------------------------------------------------
# Test Suites
# ---------------------------------------------------------------------------

BASELINE_CASES = [
    {
        "id": "P1",
        "text": "Convert report.pdf to text format",
        "expected_goal_keywords": ["convert", "text"],
        "expected_intent": "modify",
        "expected_requested_ops": ["convert"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P2",
        "text": "Draft an email to Prof. Rao about the meeting tomorrow, but do not send it",
        "expected_goal_keywords": ["draft", "email"],
        "expected_intent": "create",
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": ["send"],
        "expected_references": ["it"],
        "has_negation": True,
    },
    {
        "id": "P3",
        "text": "Summarize the attached PDF and highlight key findings",
        "expected_goal_keywords": ["summarize", "findings"],
        "expected_intent": "analyze",
        "expected_requested_ops": ["summarize"],
        "expected_prohibited_ops": [],
        "expected_references": ["attached PDF"],
        "has_negation": False,
    },
    {
        "id": "P4",
        "text": "Compare the quarterly figures in 2025 vs 2026",
        "expected_goal_keywords": ["compare", "figures"],
        "expected_intent": "compare",
        "expected_requested_ops": ["compare"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P5",
        "text": "Find all files modified yesterday in the project folder",
        "expected_goal_keywords": ["find", "files"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["find"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P6",
        "text": "Schedule a sync with the team for next Tuesday at 10 AM",
        "expected_goal_keywords": ["schedule", "sync"],
        "expected_intent": "create",
        "expected_requested_ops": ["schedule"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P7",
        "text": "Rewrite this paragraph to make it more professional",
        "expected_goal_keywords": ["rewrite", "paragraph"],
        "expected_intent": "modify",
        "expected_requested_ops": ["rewrite"],
        "expected_prohibited_ops": [],
        "expected_references": ["this", "it"],
        "has_negation": False,
    },
    {
        "id": "P8",
        "text": "Don't submit the form yet; first check for errors",
        "expected_goal_keywords": ["check", "errors"],
        "expected_intent": "analyze",
        "expected_requested_ops": ["check"],
        "expected_prohibited_ops": ["submit"],
        "expected_references": [],
        "has_negation": True,
    },
    {
        "id": "P9",
        "text": "Explain how the authentication middleware works",
        "expected_goal_keywords": ["explain", "middleware"],
        "expected_intent": "analyze",
        "expected_requested_ops": ["explain"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P10",
        "text": "Translate the welcome message to Spanish and French",
        "expected_goal_keywords": ["translate", "message"],
        "expected_intent": "modify",
        "expected_requested_ops": ["translate"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P11",
        "text": "Archive all logs older than 30 days",
        "expected_goal_keywords": ["archive", "logs"],
        "expected_intent": "execute",
        "expected_requested_ops": ["archive"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P12",
        "text": "Send the weekly status update to the engineering lead",
        "expected_goal_keywords": ["send", "status"],
        "expected_intent": "communicate",
        "expected_requested_ops": ["send"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P13",
        "text": "Generate a bar chart showing monthly revenue",
        "expected_goal_keywords": ["generate", "chart"],
        "expected_intent": "create",
        "expected_requested_ops": ["generate"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P14",
        "text": "Please don't delete the backup files, just move them",
        "expected_goal_keywords": ["move", "files"],
        "expected_intent": "modify",
        "expected_requested_ops": ["move"],
        "expected_prohibited_ops": ["delete"],
        "expected_references": ["them"],
        "has_negation": True,
    },
    {
        "id": "P15",
        "text": "Review this code for potential security vulnerabilities",
        "expected_goal_keywords": ["review", "code"],
        "expected_intent": "analyze",
        "expected_requested_ops": ["review"],
        "expected_prohibited_ops": [],
        "expected_references": ["this"],
        "has_negation": False,
    },
    {
        "id": "P16",
        "text": "Create a markdown table comparing product features",
        "expected_goal_keywords": ["create", "table"],
        "expected_intent": "create",
        "expected_requested_ops": ["create"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P17",
        "text": "Shorten the introduction section to under 200 words",
        "expected_goal_keywords": ["shorten", "introduction"],
        "expected_intent": "modify",
        "expected_requested_ops": ["shorten"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "P18",
        "text": "Do not reply to this email under any circumstances",
        "expected_goal_keywords": ["not reply"],
        "expected_intent": "communicate",
        "expected_requested_ops": [],
        "expected_prohibited_ops": ["reply"],
        "expected_references": ["this"],
        "has_negation": True,
    },
]

CONTEXT_CASES = [
    {
        "id": "C1",
        "text": "Send the invoice we discussed earlier to finance",
        "context": ActiveContext(
            active_artifacts=(ArtifactDescriptor(id="x1", name="invoice_august.pdf", artifact_type="document"),),
            active_topic="August Invoicing",
        ),
        "expected_target": "invoice_august.pdf",
        "expected_requested_ops": ["send"],
    },
    {
        "id": "C2",
        "text": "Update the hostel allocation order with the new roll numbers",
        "context": ActiveContext(
            active_artifacts=(ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),),
            active_topic="Hostel Allocation",
        ),
        "expected_target": "Hostel_Order_21Sep.docx",
        "expected_requested_ops": ["update"],
    },
    {
        "id": "C3",
        "text": "Revise it to sound more formal and add Dean's approval note",
        "context": ActiveContext(
            active_artifacts=(ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),),
            active_entities=(EntityDescriptor(id="e1", name="Dean", category="person"),),
            prior_semantic_operation="draft",
        ),
        "expected_target": "Hostel_Order_21Sep.docx",
        "expected_requested_ops": ["revise"],
    },
    {
        "id": "C4",
        "text": "Can you check if there are any conflicts in the schedule we drafted?",
        "context": ActiveContext(
            active_artifacts=(ArtifactDescriptor(id="x1", name="Orientation_Schedule.xlsx", artifact_type="spreadsheet"),),
            prior_semantic_operation="draft",
        ),
        "expected_target": "Orientation_Schedule.xlsx",
        "expected_requested_ops": ["check"],
    },
    {
        "id": "C5",
        "text": "Don't send the revised letter yet; wait for Prof. Rao's confirmation",
        "context": ActiveContext(
            active_artifacts=(ArtifactDescriptor(id="x1", name="Revised_Hostel_Letter.docx", artifact_type="document"),),
            active_entities=(EntityDescriptor(id="e1", name="Prof. Rao", category="person"),),
        ),
        "expected_target": "Revised_Hostel_Letter.docx",
        "expected_prohibited_ops": ["send"],
    },
    {
        "id": "C6",
        "text": "Export that table to CSV and share it with the team",
        "context": ActiveContext(
            active_artifacts=(ArtifactDescriptor(id="x1", name="Hostel_Fee_Summary.xlsx", artifact_type="spreadsheet"),),
            active_topic="Hostel Fee Summary",
        ),
        "expected_target": "Hostel_Fee_Summary.xlsx",
        "expected_requested_ops": ["export", "share"],
    },
]


def run_probe() -> Dict[str, Any]:
    print("=" * 70)
    print("M35 — URIv1 Parallel Architecture")
    print("Batch A2.3 — Scaffolded Needle Qualification Probe")
    print("=" * 70)

    repo_root = Path(__file__).resolve().parent.parent
    venv_python = default_venv_python()
    bridge_script = repo_root / "uri_v1" / "turn" / "needle_bridge_runtime.py"

    if not venv_python.is_file():
        raise RuntimeError(f"Needle virtualenv python not found at: {venv_python}")
    if not bridge_script.is_file():
        raise RuntimeError(f"Needle bridge script not found at: {bridge_script}")

    transport = NeedleBridgeTransport(venv_python, bridge_script)
    transport.load()
    decoder = ScaffoldedNeedleDecoder(transport=transport)

    results: Dict[str, Any] = {
        "metadata": {
            "model": "base-needle-3-generation-3",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "architecture": "TurnFrame + ActiveContext + Scaffolded Needle",
        },
        "variant_a_baseline": [],
        "variant_b_active_context": [],
        "variant_c_id_vs_freetext": [],
        "variant_d_reset_vs_stale": [],
        "summary_metrics": {},
    }

    # -----------------------------------------------------------------------
    # Variant A: Baseline 18 Prompts
    # -----------------------------------------------------------------------
    print("\nRunning Variant A: 18 Baseline Prompts (without active context)...")
    va_results = []
    for item in BASELINE_CASES:
        pid = item["id"]
        text = item["text"]
        started = time.perf_counter()
        res = decoder.decode_with_result(text, reset_state=True)
        elapsed = (time.perf_counter() - started) * 1000.0

        dr = res.decoded_request
        record = {
            "id": pid,
            "text": text,
            "ok": res.error is None and dr is not None,
            "error": str(res.error) if res.error else None,
            "total_latency_ms": res.total_latency_ms,
            "called_views": list(res.called_views),
            "skipped_views": list(res.skipped_views),
            "view_latencies_ms": res.view_latencies_ms,
            "contradictions": list(res.contradictions),
            "unknown_ids": list(res.unknown_ids),
        }
        if dr:
            record["goal"] = dr.goal.description
            record["intent_family"] = dr.goal.intent_family.value
            record["requested_ops"] = [op.name for op in dr.operations if op.status == OperationStatus.REQUESTED]
            record["prohibited_ops"] = [op.name for op in dr.operations if op.status == OperationStatus.PROHIBITED]
            record["references_count"] = len(dr.references)
            record["unresolved_refs"] = [r.expression for r in dr.references if not r.is_resolved]
            record["overall_confidence"] = dr.confidence.overall.value
        va_results.append(record)
        status_char = "OK" if record["ok"] else "ERR"
        print(f"  [{pid}] {status_char} ({res.total_latency_ms:.1f}ms, views={res.called_views}) - {text[:50]}...")

    results["variant_a_baseline"] = va_results

    # -----------------------------------------------------------------------
    # Variant B: 6 Active Context Prompts
    # -----------------------------------------------------------------------
    print("\nRunning Variant B: 6 Active Context Prompts...")
    vb_results = []
    for item in CONTEXT_CASES:
        cid = item["id"]
        text = item["text"]
        ctx = item["context"]
        res = decoder.decode_with_result(text, active_context=ctx, reset_state=True)
        dr = res.decoded_request
        record = {
            "id": cid,
            "text": text,
            "ok": res.error is None and dr is not None,
            "error": str(res.error) if res.error else None,
            "total_latency_ms": res.total_latency_ms,
            "called_views": list(res.called_views),
            "skipped_views": list(res.skipped_views),
            "view_latencies_ms": res.view_latencies_ms,
            "contradictions": list(res.contradictions),
            "unknown_ids": list(res.unknown_ids),
        }
        if dr:
            record["goal"] = dr.goal.description
            record["intent_family"] = dr.goal.intent_family.value
            record["requested_ops"] = [op.name for op in dr.operations if op.status == OperationStatus.REQUESTED]
            record["prohibited_ops"] = [op.name for op in dr.operations if op.status == OperationStatus.PROHIBITED]
            record["references"] = [{"expr": r.expression, "resolved": r.is_resolved, "hint": r.referent_hint} for r in dr.references]
        vb_results.append(record)
        status_char = "OK" if record["ok"] else "ERR"
        print(f"  [{cid}] {status_char} ({res.total_latency_ms:.1f}ms, views={res.called_views}) - {text[:50]}...")

    results["variant_b_active_context"] = vb_results

    # -----------------------------------------------------------------------
    # Variant C: ID Selection vs Free-Text Comparison
    # -----------------------------------------------------------------------
    print("\nRunning Variant C: Candidate-ID vs Free-Text Extraction...")
    vc_subset = ["P2", "P8", "P14", "C3", "C5"]
    vc_results = []
    all_dict = {x["id"]: x for x in (BASELINE_CASES + CONTEXT_CASES)}
    for sid in vc_subset:
        case = all_dict[sid]
        text = case["text"]
        # Candidate ID result
        ctx = case.get("context")
        res_id = decoder.decode_with_result(text, active_context=ctx, reset_state=True)

        # Free text call for operations
        transport.reset()
        t_start = time.perf_counter()
        resp_ft_ops = transport.decode(
            f"Extract requested and prohibited operations from: {text}",
            system=SYSTEM_SELECT_OPERATIONS_FREETEXT,
            schema=SCHEMA_SELECT_OPERATIONS_FREETEXT,
            max_new_tokens=150,
        )
        ft_ops_latency = (time.perf_counter() - t_start) * 1000.0

        vc_results.append({
            "id": sid,
            "text": text,
            "id_selection": {
                "ok": res_id.ok if hasattr(res_id, "ok") else (res_id.error is None),
                "contradictions": list(res_id.contradictions),
                "unknown_ids": list(res_id.unknown_ids),
                "raw_operations_call": res_id.raw_responses.get("operations", {}).get("function_calls", []),
            },
            "free_text": {
                "latency_ms": ft_ops_latency,
                "raw_call": resp_ft_ops.get("function_calls", []),
                "reasoning": resp_ft_ops.get("reasoning"),
            },
        })
        print(f"  [{sid}] Comparison collected.")

    results["variant_c_id_vs_freetext"] = vc_results

    # -----------------------------------------------------------------------
    # Variant D: Reset vs Stale Reuse (Bleed Test)
    # -----------------------------------------------------------------------
    print("\nRunning Variant D: Per-turn Reset vs Stale Reuse...")
    bleed_sequence = [
        "Draft an email to Prof. Rao about the meeting tomorrow, but do not send it",
        "Convert report.pdf to text format",
        "Don't submit the form yet; first check for errors",
        "Archive all logs older than 30 days",
        "Please don't delete the backup files, just move them",
    ]

    # Run 1: With Reset between turns
    reset_run = []
    for idx, prompt in enumerate(bleed_sequence):
        r = decoder.decode_with_result(prompt, reset_state=True)
        dr = r.decoded_request
        reset_run.append({
            "step": idx + 1,
            "prompt": prompt,
            "goal": dr.goal.description if dr else None,
            "ops": [op.name for op in dr.operations] if dr else [],
            "prohibited": list(dr.constraints.prohibited_actions) if dr else [],
        })

    # Run 2: Without Reset (Stale reuse across all turns)
    transport.reset()  # initial clean start
    stale_run = []
    for idx, prompt in enumerate(bleed_sequence):
        r = decoder.decode_with_result(prompt, reset_state=False)
        dr = r.decoded_request
        stale_run.append({
            "step": idx + 1,
            "prompt": prompt,
            "goal": dr.goal.description if dr else None,
            "ops": [op.name for op in dr.operations] if dr else [],
            "prohibited": list(dr.constraints.prohibited_actions) if dr else [],
        })

    results["variant_d_reset_vs_stale"] = {
        "reset_run": reset_run,
        "stale_run": stale_run,
    }
    print("  Reset vs Stale comparison completed.")

    # -----------------------------------------------------------------------
    # Summary Metrics Calculation
    # -----------------------------------------------------------------------
    all_runs = va_results + vb_results
    total_turns = len(all_runs)
    successful_turns = sum(1 for x in all_runs if x["ok"])
    contradiction_turns = sum(1 for x in all_runs if len(x["contradictions"]) > 0)
    unknown_id_turns = sum(1 for x in all_runs if len(x["unknown_ids"]) > 0)

    latencies = [x["total_latency_ms"] for x in all_runs]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    # View call frequencies
    view_counts = {"goal": 0, "operations": 0, "references": 0, "output_scope": 0}
    for x in all_runs:
        for v in x["called_views"]:
            if v in view_counts:
                view_counts[v] += 1

    results["summary_metrics"] = {
        "total_turns": total_turns,
        "successful_turns": successful_turns,
        "success_rate": successful_turns / total_turns if total_turns else 0.0,
        "contradiction_turns": contradiction_turns,
        "contradiction_rate": contradiction_turns / total_turns if total_turns else 0.0,
        "unknown_id_turns": unknown_id_turns,
        "unknown_id_rate": unknown_id_turns / total_turns if total_turns else 0.0,
        "average_latency_ms": avg_latency,
        "min_latency_ms": min(latencies) if latencies else 0.0,
        "max_latency_ms": max(latencies) if latencies else 0.0,
        "view_call_frequencies": view_counts,
        "average_calls_per_turn": sum(view_counts.values()) / total_turns if total_turns else 0.0,
    }

    # Save to json file
    output_path = repo_root / "scripts" / "scaffolded_needle_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")

    transport.close()
    return results


if __name__ == "__main__":
    run_probe()
