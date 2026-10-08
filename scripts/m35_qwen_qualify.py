"""Live qualification probe for Batch A2.2: Qwen Step-1 Semantic Decoder.

Runs all 18 prompts across BOTH constrained (JSON schema) and unconstrained modes
against the local Qwen candidate (Qwen3.5-0.8B.Q8_0 via LM Studio).
Saves complete raw telemetry, token counts, reasoning content, and extractions to JSON.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.qwen_decoder import QwenLocalTransport, QwenSemanticDecoder

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

ALL_CASES = REQUIRED_CASES + STRESS_CASES


def run_qualification():
    repo_root = Path(__file__).parent.parent
    transport = QwenLocalTransport()
    decoder = QwenSemanticDecoder(transport, max_tokens=600)

    print("Connecting to local Qwen runtime at:", transport.endpoint_url)

    results = {
        "model_id": transport.model_id,
        "endpoint": transport.endpoint_url,
        "constrained_mode": [],
        "unconstrained_mode": [],
    }

    # 1. Constrained Mode
    print("\n=======================================================")
    print("  RUNNING MODE 1: CONSTRAINED (JSON SCHEMA)")
    print("=======================================================")
    for pid, text in ALL_CASES:
        res = decoder.decode_with_result(DecodeInput(raw_text=text), constrained=True)
        item = {
            "id": pid,
            "text": text,
            "ok": res.ok,
            "latency_ms": res.latency_ms,
            "prompt_tokens": res.prompt_tokens,
            "completion_tokens": res.completion_tokens,
            "reasoning_tokens": res.reasoning_tokens,
            "error_reason": res.error.reason.value if res.error else None,
            "error_detail": str(res.error) if res.error else None,
            "content": res.raw_content,
            "reasoning_content": res.reasoning_content,
            "wire": res.raw_wire,
        }
        if res.decoded_request:
            dr = res.decoded_request
            item["decoded"] = {
                "goal": dr.goal.description,
                "intent_family": dr.goal.intent_family.value,
                "requested_operations": [op.name for op in dr.operations if op.status.value == "requested"],
                "prohibited_operations": [op.name for op in dr.operations if op.status.value == "prohibited"],
                "references": [r.expression for r in dr.references],
                "temporal_references": [tr.expression for tr in dr.temporal_references],
                "constraints": {
                    "included": list(dr.constraints.included_items),
                    "excluded": list(dr.constraints.excluded_items),
                    "length_limit": dr.constraints.length_limit,
                    "language_constraints": dr.constraints.language_constraints,
                },
                "output_preferences": {
                    "artifact_type": dr.output_preferences.artifact_type,
                    "tone": dr.output_preferences.tone,
                    "audience": dr.output_preferences.audience,
                    "language": dr.output_preferences.language,
                    "language_variant": dr.output_preferences.language_variant,
                    "length": dr.output_preferences.length,
                    "structure": dr.output_preferences.structure,
                },
                "entities": [{"name": e.name, "category": e.category.value} for e in dr.entities],
                "ambiguities": [a.description for a in dr.ambiguities],
                "dependencies": [d.description for d in dr.dependencies],
            }
        results["constrained_mode"].append(item)
        print(f"[{pid}] ok={res.ok} lat={res.latency_ms:.1f}ms tokens(prompt={res.prompt_tokens}, cmpl={res.completion_tokens}, rzn={res.reasoning_tokens})")
        if res.decoded_request:
            d = item["decoded"]
            print(f"     goal='{d['goal']}' ({d['intent_family']}) req={d['requested_operations']} proh={d['prohibited_operations']} refs={d['references']} trefs={d['temporal_references']}")
        elif res.error:
            print(f"     ERROR: {res.error.reason.value}: {res.error}")

    # 2. Unconstrained Mode
    print("\n=======================================================")
    print("  RUNNING MODE 2: UNCONSTRAINED (RAW JSON COMPLETION)")
    print("=======================================================")
    for pid, text in ALL_CASES:
        res = decoder.decode_with_result(DecodeInput(raw_text=text), constrained=False)
        item = {
            "id": pid,
            "text": text,
            "ok": res.ok,
            "latency_ms": res.latency_ms,
            "prompt_tokens": res.prompt_tokens,
            "completion_tokens": res.completion_tokens,
            "reasoning_tokens": res.reasoning_tokens,
            "error_reason": res.error.reason.value if res.error else None,
            "error_detail": str(res.error) if res.error else None,
            "content": res.raw_content,
            "reasoning_content": res.reasoning_content,
            "wire": res.raw_wire,
        }
        if res.decoded_request:
            dr = res.decoded_request
            item["decoded"] = {
                "goal": dr.goal.description,
                "intent_family": dr.goal.intent_family.value,
                "requested_operations": [op.name for op in dr.operations if op.status.value == "requested"],
                "prohibited_operations": [op.name for op in dr.operations if op.status.value == "prohibited"],
                "references": [r.expression for r in dr.references],
                "temporal_references": [tr.expression for tr in dr.temporal_references],
                "constraints": {
                    "included": list(dr.constraints.included_items),
                    "excluded": list(dr.constraints.excluded_items),
                    "length_limit": dr.constraints.length_limit,
                    "language_constraints": dr.constraints.language_constraints,
                },
                "output_preferences": {
                    "artifact_type": dr.output_preferences.artifact_type,
                    "tone": dr.output_preferences.tone,
                    "audience": dr.output_preferences.audience,
                    "language": dr.output_preferences.language,
                    "language_variant": dr.output_preferences.language_variant,
                    "length": dr.output_preferences.length,
                    "structure": dr.output_preferences.structure,
                },
                "entities": [{"name": e.name, "category": e.category.value} for e in dr.entities],
                "ambiguities": [a.description for a in dr.ambiguities],
                "dependencies": [d.description for d in dr.dependencies],
            }
        results["unconstrained_mode"].append(item)
        print(f"[{pid}] ok={res.ok} lat={res.latency_ms:.1f}ms tokens(prompt={res.prompt_tokens}, cmpl={res.completion_tokens}, rzn={res.reasoning_tokens})")
        if res.decoded_request:
            d = item["decoded"]
            print(f"     goal='{d['goal']}' ({d['intent_family']}) req={d['requested_operations']} proh={d['prohibited_operations']} refs={d['references']} trefs={d['temporal_references']}")
        elif res.error:
            print(f"     ERROR: {res.error.reason.value}: {res.error}")

    out_file = repo_root / "scripts" / "qwen_qualification_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved full results to {out_file}")


if __name__ == "__main__":
    run_qualification()
