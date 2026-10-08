"""Live Empirical Qualification Probe for Batch A2.4:

Semantic Decoder Harness Control Qualification: Qwen3-14B.

Executes comprehensive evaluation:
  1. Mode A (Raw Semantic Decode): 18 baseline prompts (R1..R10, S1..S8).
  2. Mode B (TurnFrame Assisted): 18 baseline prompts with pre-semantic surface cues.
  3. Mode C (Active Context Assisted): 6 conversational turns with active working memory.
  4. Repeatability Verification: 3 runs each of R1, R4, R3, R5 in Mode A.

Saves full raw telemetry, reasoning tokens, decoded requests, and accuracy metrics
to scripts/qwen14b_qualification_results.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import statistics
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
    ReferenceKind,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.qwen_decoder import QwenLocalTransport
from uri_v1.turn.qwen_semantic_decoder import (
    DecoderMode,
    Qwen14BDecodeResult,
    Qwen14BSemanticDecoder,
)

# ---------------------------------------------------------------------------
# 18 Standard Test Cases (R1..R10, S1..S8)
# ---------------------------------------------------------------------------

STANDARD_CASES: List[Dict[str, Any]] = [
    {
        "id": "R1",
        "text": "Convert this to PDF.",
        "expected_goal_keywords": ["convert", "pdf"],
        "expected_intent": "modify",
        "expected_requested_ops": ["convert"],
        "expected_prohibited_ops": [],
        "expected_references": ["this"],
        "has_negation": False,
    },
    {
        "id": "R2",
        "text": "Bring that file up.",
        "expected_goal_keywords": ["bring", "open", "file", "display"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["bring", "open", "display", "retrieve"],
        "expected_prohibited_ops": [],
        "expected_references": ["that file"],
        "has_negation": False,
    },
    {
        "id": "R3",
        "text": "Do the same thing for them.",
        "expected_goal_keywords": ["same", "thing", "repeat", "apply"],
        "expected_intent": "create",  # or modify/unspecified
        "expected_requested_ops": ["do", "repeat", "apply", "execute"],
        "expected_prohibited_ops": [],
        "expected_references": ["same thing", "them"],
        "has_negation": False,
    },
    {
        "id": "R4",
        "text": "Don't send it. Just draft the email.",
        "expected_goal_keywords": ["draft", "email"],
        "expected_intent": "create",
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": ["send"],
        "expected_references": ["it"],
        "has_negation": True,
    },
    {
        "id": "R5",
        "text": "Find the previous approval, compare it with this one and draft a revised order.",
        "expected_goal_keywords": ["compare", "draft", "order", "approval"],
        "expected_intent": "create",
        "expected_requested_ops": ["find", "compare", "draft"],
        "expected_prohibited_ops": [],
        "expected_references": ["previous approval", "it", "this one"],
        "has_negation": False,
    },
    {
        "id": "R6",
        "text": (
            "The committee has already changed its view twice and the latest letter doesn't "
            "seem to match what was decided earlier. I need something I can put up tomorrow."
        ),
        "expected_goal_keywords": ["letter", "put up", "prepare", "draft", "compare"],
        "expected_intent": "create",
        "expected_requested_ops": ["put up", "prepare", "draft", "create"],
        "expected_prohibited_ops": [],
        "expected_references": ["latest letter", "what was decided earlier", "something"],
        "has_negation": False,
    },
    {
        "id": "R7",
        "text": "Compare only the 2025 and 2026 decisions, do not use anything before 2025, and keep the result under one page.",
        "expected_goal_keywords": ["compare", "decisions"],
        "expected_intent": "compare",
        "expected_requested_ops": ["compare"],
        "expected_prohibited_ops": ["use anything before 2025", "use"],
        "expected_references": [],
        "has_negation": True,
    },
    {
        "id": "R8",
        "text": "Draft a short formal email in Indian English to the Chief Warden.",
        "expected_goal_keywords": ["draft", "email", "chief warden"],
        "expected_intent": "create",
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "R9",
        "text": "Do not summarize this; compare the exact figures in a table.",
        "expected_goal_keywords": ["compare", "figures", "table"],
        "expected_intent": "compare",
        "expected_requested_ops": ["compare"],
        "expected_prohibited_ops": ["summarize"],
        "expected_references": ["this"],
        "has_negation": True,
    },
    {
        "id": "R10",
        "text": "What was approved yesterday?",
        "expected_goal_keywords": ["approved", "yesterday", "what"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["retrieve", "find", "query", "check"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    # Stress Cases
    {
        "id": "S1",
        "text": "Hello",
        "expected_goal_keywords": ["hello", "greet", "greeting"],
        "expected_intent": "unspecified",
        "expected_requested_ops": [],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "S2",
        "text": "Thanks",
        "expected_goal_keywords": ["thanks", "thank", "acknowledge"],
        "expected_intent": "unspecified",
        "expected_requested_ops": [],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "S3",
        "text": "Open calculator.",
        "expected_goal_keywords": ["calculator", "open", "launch"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["open"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
    },
    {
        "id": "S4",
        "text": "Don't open it yet.",
        "expected_goal_keywords": ["do not open", "wait", "hold"],
        "expected_intent": "unspecified",
        "expected_requested_ops": [],
        "expected_prohibited_ops": ["open"],
        "expected_references": ["it"],
        "has_negation": True,
    },
    {
        "id": "S5",
        "text": "Send it to him after they approve it.",
        "expected_goal_keywords": ["send", "approve"],
        "expected_intent": "communicate",
        "expected_requested_ops": ["send"],
        "expected_prohibited_ops": [],
        "expected_references": ["it", "him", "they"],
        "has_negation": False,
    },
    {
        "id": "S6",
        "text": "Compare the attached PDF with this spreadsheet.",
        "expected_goal_keywords": ["compare", "pdf", "spreadsheet"],
        "expected_intent": "compare",
        "expected_requested_ops": ["compare"],
        "expected_prohibited_ops": [],
        "expected_references": ["attached PDF", "this spreadsheet"],
        "has_negation": False,
    },
    {
        "id": "S7",
        "text": "Make something I can submit tomorrow.",
        "expected_goal_keywords": ["make", "submit", "prepare", "create"],
        "expected_intent": "create",
        "expected_requested_ops": ["make", "create", "prepare"],
        "expected_prohibited_ops": [],
        "expected_references": ["something"],
        "has_negation": False,
    },
    {
        "id": "S8",
        "text": "No, I meant the earlier one.",
        "expected_goal_keywords": ["earlier", "correct", "select"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["select", "retrieve", "refer"],
        "expected_prohibited_ops": [],
        "expected_references": ["earlier one"],
        "has_negation": False,
    },
]

# ---------------------------------------------------------------------------
# Conversational Turns (C1..C6)
# ---------------------------------------------------------------------------

CONVERSATIONAL_TURNS: List[Dict[str, Any]] = [
    {
        "id": "C1",
        "text": "Bring that file up.",
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),
            )
        ),
        "target_ref": "that file",
        "expected_target_id": "x1",
        "expected_resolved_name": "Hostel_Order_21Sep.docx",
    },
    {
        "id": "C2",
        "text": "Do the same thing for them.",
        "context": ActiveContext(
            active_entities=(
                EntityDescriptor(id="e1", name="Prof. Rao", category="person"),
            ),
            prior_semantic_operation="generate_report",
        ),
        "target_ref": "them",
        "expected_target_id": "e1",
        "expected_resolved_name": "Prof. Rao",
    },
    {
        "id": "C3",
        "text": "Don't send it. Just draft the email.",
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x2", name="Dean_Notification.eml", artifact_type="email"),
            )
        ),
        "target_ref": "it",
        "expected_target_id": "x2",
        "expected_resolved_name": "Dean_Notification.eml",
        "has_negation": True,
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": ["send"],
    },
    {
        "id": "C4",
        "text": "Revise it to sound more formal and add Dean's approval note.",
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="e2", name="Dean Academics", category="role"),
            ),
        ),
        "target_ref": "it",
        "expected_target_id": "x1",
        "expected_resolved_name": "Hostel_Order_21Sep.docx",
    },
    {
        "id": "C5",
        "text": "Compare it with the earlier draft.",
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),
                ArtifactDescriptor(id="x3", name="Hostel_Order_15Aug_Draft.docx", artifact_type="document"),
            )
        ),
        "target_ref": "earlier draft",
        "expected_target_id": "x3",
        "expected_resolved_name": "Hostel_Order_15Aug_Draft.docx",
    },
    {
        "id": "C6",
        "text": "No, I meant the earlier one.",
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),
                ArtifactDescriptor(id="x3", name="Hostel_Order_15Aug_Draft.docx", artifact_type="document"),
            )
        ),
        "target_ref": "earlier one",
        "expected_target_id": "x3",
        "expected_resolved_name": "Hostel_Order_15Aug_Draft.docx",
    },
]


def _evaluate_result(case: Dict[str, Any], res: Qwen14BDecodeResult) -> Dict[str, Any]:
    eval_item: Dict[str, Any] = {
        "id": case["id"],
        "text": case["text"],
        "ok": res.ok,
        "mode": res.mode,
        "latency_ms": res.latency_ms,
        "prompt_tokens": res.prompt_tokens,
        "completion_tokens": res.completion_tokens,
        "reasoning_tokens": res.reasoning_tokens,
        "error": str(res.error) if res.error else None,
        "reasoning_content": res.reasoning_content,
        "raw_content": res.raw_content,
    }

    if not res.ok or res.decoded_request is None:
        eval_item["goal_correct"] = False
        eval_item["requested_ops_correct"] = False
        eval_item["prohibited_ops_correct"] = False
        eval_item["references_detected"] = False
        eval_item["context_invented"] = False
        return eval_item

    dr = res.decoded_request
    eval_item["decoded"] = {
        "goal": dr.goal.description,
        "intent_family": dr.goal.intent_family.value,
        "requested_operations": [op.name for op in dr.operations if op.status == OperationStatus.REQUESTED],
        "prohibited_operations": [op.name for op in dr.operations if op.status == OperationStatus.PROHIBITED],
        "references": [
            {
                "expression": r.expression,
                "is_resolved": r.is_resolved,
                "referent_hint": r.referent_hint,
            }
            for r in dr.references
        ],
        "temporal_references": [tr.expression for tr in dr.temporal_references],
        "constraints": {
            "included": list(dr.constraints.included_items),
            "excluded": list(dr.constraints.excluded_items),
            "prohibited_actions": list(dr.constraints.prohibited_actions),
        },
        "entities": [{"name": e.name, "category": e.category.value} for e in dr.entities],
    }

    # 1. Goal evaluation
    goal_str = dr.goal.description.lower()
    expected_kw = case.get("expected_goal_keywords") or []
    if not expected_kw:
        goal_correct = bool(goal_str.strip())
    else:
        goal_correct = any(kw.lower() in goal_str for kw in expected_kw)
    eval_item["goal_correct"] = goal_correct

    # 2. Operations evaluation
    req_ops = [op.name.lower() for op in dr.operations if op.status == OperationStatus.REQUESTED]
    proh_ops = [op.name.lower() for op in dr.operations if op.status == OperationStatus.PROHIBITED]

    exp_req = [x.lower() for x in case.get("expected_requested_ops", [])]
    if not exp_req:
        req_correct = True
    else:
        req_correct = any(any(er in ro for ro in req_ops) for er in exp_req)
    eval_item["requested_ops_correct"] = req_correct

    # 3. Negation / Prohibited operations evaluation
    exp_proh = [x.lower() for x in case.get("expected_prohibited_ops", [])]
    if case.get("has_negation", False):
        if not exp_proh:
            proh_correct = len(proh_ops) > 0
        else:
            proh_correct = any(any(ep in po for po in proh_ops) for ep in exp_proh)
            # Ensure none of the prohibited operations are marked requested
            for ep in exp_proh:
                if any(ep in ro for ro in req_ops):
                    proh_correct = False
    else:
        proh_correct = len(proh_ops) == 0
    eval_item["prohibited_ops_correct"] = proh_correct

    # 4. Reference detection evaluation
    exp_refs = [x.lower() for x in case.get("expected_references", [])]
    found_refs = [r.expression.lower() for r in dr.references]
    if not exp_refs:
        ref_correct = True
    else:
        ref_correct = any(any(er in fr for fr in found_refs) for er in exp_refs)
    eval_item["references_detected"] = ref_correct

    # 5. Context invention check: did it invent files/names not in prompt?
    raw_lower = case["text"].lower()
    invented = False
    for ent in dr.entities:
        if ent.name.lower() not in raw_lower:
            invented = True
    eval_item["context_invented"] = invented

    return eval_item


def main():
    print("=================================================================")
    print("  M35 BATCH A2.4 — QWEN3-14B HARNESS CONTROL EMPIRICAL PROBE")
    print("=================================================================")

    transport = QwenLocalTransport(model_id="qwen3-14b", timeout=120.0)
    decoder = Qwen14BSemanticDecoder(transport=transport, max_tokens=800)

    results: Dict[str, Any] = {
        "metadata": {
            "model_id": "qwen3-14b",
            "model_file": "Qwen3-14B-Q4_K_M.gguf",
            "architecture": "qwen3",
            "parameters": "14.77B",
            "quantization": "Q4_K_M",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "mode_a_raw": [],
        "mode_b_turn_frame": [],
        "mode_c_active_context": [],
        "repeatability": [],
    }

    # -----------------------------------------------------------------------
    # Part 1: Mode A (Raw) on 18 Standard Prompts
    # -----------------------------------------------------------------------
    print("\n--- Part 1: Mode A (Raw Semantic Decode: 18 Prompts) ---")
    for case in STANDARD_CASES:
        t0 = time.perf_counter()
        res = decoder.decode_with_result(case["text"], mode=DecoderMode.RAW)
        dt = time.perf_counter() - t0
        eval_item = _evaluate_result(case, res)
        results["mode_a_raw"].append(eval_item)
        print(
            f"[{case['id']}] Mode A: ok={res.ok} | Latency={res.latency_ms:.0f}ms "
            f"(Tokens: {res.prompt_tokens}p + {res.reasoning_tokens}r + {res.completion_tokens}c) | "
            f"Goal={eval_item['goal_correct']} Req={eval_item['requested_ops_correct']} "
            f"Proh={eval_item['prohibited_ops_correct']} Ref={eval_item['references_detected']}"
        )

    # -----------------------------------------------------------------------
    # Part 2: Mode B (TurnFrame Assisted) on 18 Standard Prompts
    # -----------------------------------------------------------------------
    print("\n--- Part 2: Mode B (TurnFrame Assisted: 18 Prompts) ---")
    for case in STANDARD_CASES:
        t0 = time.perf_counter()
        res = decoder.decode_with_result(case["text"], mode=DecoderMode.TURN_FRAME)
        dt = time.perf_counter() - t0
        eval_item = _evaluate_result(case, res)
        results["mode_b_turn_frame"].append(eval_item)
        print(
            f"[{case['id']}] Mode B: ok={res.ok} | Latency={res.latency_ms:.0f}ms "
            f"(Tokens: {res.prompt_tokens}p + {res.reasoning_tokens}r + {res.completion_tokens}c) | "
            f"Goal={eval_item['goal_correct']} Req={eval_item['requested_ops_correct']} "
            f"Proh={eval_item['prohibited_ops_correct']} Ref={eval_item['references_detected']}"
        )

    # -----------------------------------------------------------------------
    # Part 3: Mode C (Active Context Assisted) on C1..C6 Conversational Turns
    # -----------------------------------------------------------------------
    print("\n--- Part 3: Mode C (Active Context Assisted: 6 Turns) ---")
    for case in CONVERSATIONAL_TURNS:
        t0 = time.perf_counter()
        res = decoder.decode_with_result(
            case["text"],
            mode=DecoderMode.ACTIVE_CONTEXT,
            active_context=case["context"],
        )
        dt = time.perf_counter() - t0
        eval_item = _evaluate_result(case, res)

        # Check resolution of target reference
        dr = res.decoded_request
        resolved_correctly = False
        if dr is not None:
            for ref in dr.references:
                if case["target_ref"].lower() in ref.expression.lower() or ref.expression.lower() in case["target_ref"].lower():
                    if ref.is_resolved and (ref.referent_hint == case["expected_resolved_name"] or ref.referent_hint == case["expected_target_id"]):
                        resolved_correctly = True
        eval_item["target_ref"] = case["target_ref"]
        eval_item["expected_target_id"] = case["expected_target_id"]
        eval_item["resolved_correctly"] = resolved_correctly

        results["mode_c_active_context"].append(eval_item)
        print(
            f"[{case['id']}] Mode C: ok={res.ok} | Latency={res.latency_ms:.0f}ms | "
            f"TargetRef='{case['target_ref']}' Resolved={resolved_correctly}"
        )

    # -----------------------------------------------------------------------
    # Part 4: Repeatability Verification (3 runs each of R1, R4, R3, R5)
    # -----------------------------------------------------------------------
    print("\n--- Part 4: Repeatability Verification (3 runs each of R1, R4, R3, R5) ---")
    repeat_cases = [c for c in STANDARD_CASES if c["id"] in ("R1", "R4", "R3", "R5")]
    for rep_idx in range(1, 4):
        print(f"Repeatability Run {rep_idx}/3:")
        for case in repeat_cases:
            res = decoder.decode_with_result(case["text"], mode=DecoderMode.RAW)
            eval_item = _evaluate_result(case, res)
            eval_item["run_index"] = rep_idx
            results["repeatability"].append(eval_item)
            print(
                f"  [{case['id']} run {rep_idx}] Goal={eval_item['goal_correct']} "
                f"Req={eval_item['requested_ops_correct']} Proh={eval_item['prohibited_ops_correct']} "
                f"Latency={res.latency_ms:.0f}ms"
            )

    # -----------------------------------------------------------------------
    # Summary Statistics Calculation
    # -----------------------------------------------------------------------
    def calc_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(items)
        if total == 0:
            return {}
        ok_count = sum(1 for x in items if x["ok"])
        goal_count = sum(1 for x in items if x.get("goal_correct", False))
        req_count = sum(1 for x in items if x.get("requested_ops_correct", False))
        proh_count = sum(1 for x in items if x.get("prohibited_ops_correct", False))
        ref_count = sum(1 for x in items if x.get("references_detected", False))
        invented_count = sum(1 for x in items if x.get("context_invented", False))

        latencies = [x["latency_ms"] for x in items if x.get("latency_ms") is not None]
        reasoning_tokens = [x["reasoning_tokens"] for x in items if x.get("reasoning_tokens") is not None]
        completion_tokens = [x["completion_tokens"] for x in items if x.get("completion_tokens") is not None]

        return {
            "total": total,
            "ok_rate": ok_count / total,
            "goal_accuracy": goal_count / total,
            "requested_ops_accuracy": req_count / total,
            "prohibited_ops_accuracy": proh_count / total,
            "reference_detection_accuracy": ref_count / total,
            "context_invention_rate": invented_count / total,
            "latency": {
                "min_ms": round(min(latencies), 1) if latencies else 0,
                "median_ms": round(statistics.median(latencies), 1) if latencies else 0,
                "mean_ms": round(statistics.mean(latencies), 1) if latencies else 0,
                "max_ms": round(max(latencies), 1) if latencies else 0,
            },
            "reasoning_tokens": {
                "min": min(reasoning_tokens) if reasoning_tokens else 0,
                "median": statistics.median(reasoning_tokens) if reasoning_tokens else 0,
                "mean": round(statistics.mean(reasoning_tokens), 1) if reasoning_tokens else 0,
                "max": max(reasoning_tokens) if reasoning_tokens else 0,
            },
            "completion_tokens": {
                "min": min(completion_tokens) if completion_tokens else 0,
                "median": statistics.median(completion_tokens) if completion_tokens else 0,
                "mean": round(statistics.mean(completion_tokens), 1) if completion_tokens else 0,
                "max": max(completion_tokens) if completion_tokens else 0,
            },
        }

    results["summary"] = {
        "mode_a_raw": calc_stats(results["mode_a_raw"]),
        "mode_b_turn_frame": calc_stats(results["mode_b_turn_frame"]),
        "mode_c_active_context": {
            **calc_stats(results["mode_c_active_context"]),
            "target_resolution_rate": sum(1 for x in results["mode_c_active_context"] if x.get("resolved_correctly", False)) / len(results["mode_c_active_context"]),
        },
        "repeatability": calc_stats(results["repeatability"]),
    }

    # Save to JSON
    out_path = Path(__file__).resolve().parent / "qwen14b_qualification_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n=================================================================")
    print(f"  RESULTS SAVED TO {out_path}")
    print("=================================================================")
    print("Summary:")
    print("Mode A (Raw):", json.dumps(results["summary"]["mode_a_raw"], indent=2))
    print("Mode B (TurnFrame):", json.dumps(results["summary"]["mode_b_turn_frame"], indent=2))
    print("Mode C (ActiveContext):", json.dumps(results["summary"]["mode_c_active_context"], indent=2))


if __name__ == "__main__":
    main()
