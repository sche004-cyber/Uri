"""M35 URIv1 Batch A2.5 Stage 4 — Comprehensive Live Qualification Script.

Executes all 7 diagnostic batteries against local LFM2.5-350M endpoint:
1. Context Envelope Battery (L0 to L7)
2. Noise Sensitivity Controlled Pairs (300 to 1500 tokens)
3. Semantic Complexity Ladder (C0 to C8)
4. Negation Ladder (N1 to N6)
5. Operation Retention Ladder (O-R1 to O-R5)
6. Progressive Feed Width Ladder (O0 to O5)
7. Multi-Mode Comparative Suite (Modes A, B, C, D)

Calculates:
- Precise accuracy metrics per dimension
- Sequential vs parallel latency
- Token consumption and TTFT
- Empirical breakpoints and operating boundaries
- Persists machine-readable results to scripts/lfm_stage4_qualification_results.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
)
from uri_v1.turn.lfm_adaptive_feeds import (
    FEED_B_SCHEMA,
    FEED_B_SYSTEM_PROMPT,
    FEED_C_SCHEMA,
    FEED_C_SYSTEM_PROMPT,
    FEED_G_SCHEMA,
    FEED_G_SYSTEM_PROMPT,
    FEED_O_SCHEMA,
    FEED_O_SYSTEM_PROMPT,
    FeedType,
    build_feed_b_prompt,
    build_feed_c_prompt,
    build_feed_g_prompt,
    build_feed_o_prompt,
    parse_feed_b_response,
    parse_feed_c_response,
    parse_feed_g_response,
    parse_feed_o_response,
)
from uri_v1.turn.lfm_envelope_battery import (
    EnvelopeTestCase,
    build_complexity_ladder_battery,
    build_context_envelope_battery,
    build_negation_ladder_battery,
    build_noise_sensitivity_battery,
    build_operation_retention_battery,
    build_progressive_feed_width_battery,
)
from uri_v1.turn.lfm_multi_feed_runtime import (
    FeedCallMetric,
    LFMMultiFeedRuntime,
    MultiFeedExecutionResult,
)


def score_decoded_request(case: EnvelopeTestCase, decoded: DecodedRequest) -> Dict[str, Any]:
    """Scores DecodedRequest against expected ground truth for an EnvelopeTestCase."""
    # 1. Goal Accuracy
    # Check if key concepts from expected goal are in description
    exp_words = [w.lower() for w in case.expected_goal.split() if len(w) > 3]
    actual_desc = decoded.goal.description.lower()
    goal_ok = any(w in actual_desc for w in exp_words) if exp_words else bool(actual_desc)

    # 2. Requested Operations Accuracy
    actual_req = set(op.name.lower() for op in decoded.operations if op.status == OperationStatus.REQUESTED)
    exp_req = set(op.lower() for op in case.expected_requested_ops)
    req_ops_ok = (actual_req == exp_req) or (not exp_req and not actual_req)

    # 3. Prohibited Operations / Negation Accuracy
    actual_pro = set(op.name.lower() for op in decoded.operations if op.status == OperationStatus.PROHIBITED)
    exp_pro = set(op.lower() for op in case.expected_prohibited_ops)
    pro_ops_ok = (actual_pro == exp_pro) or (not exp_pro and not actual_pro)

    # Check for polarity inversion (prohibited action accidentally put into requested)
    inverted = bool(exp_pro.intersection(actual_req))

    # 4. Operation Retention (for multiple ops)
    if exp_req:
        retained_count = len(exp_req.intersection(actual_req))
        retention_rate = retained_count / len(exp_req)
        omitted_count = len(exp_req - actual_req)
    else:
        retention_rate = 1.0
        omitted_count = 0

    # 5. Reference Correctness
    if case.expected_target_id:
        # Check if reference is resolved to expected target
        ref_ok = any(
            r.is_resolved and r.referent_hint == case.expected_target_id
            for r in decoded.references
        )
    else:
        ref_ok = True

    # 6. Context Invention / Hallucination
    # Any operation or reference invented out of thin air
    invented_ops = [op for op in actual_req if op not in exp_req and op not in case.user_text.lower()]
    hallucination = len(invented_ops) > 0

    # 7. Structural Validity
    structural_ok = bool(decoded.goal.description) and isinstance(decoded.operations, tuple)

    # 8. Overall Critical Semantic Reliability
    # Pass requires goal_ok, req_ops_ok, pro_ops_ok, and no inversion
    critical_ok = goal_ok and req_ops_ok and pro_ops_ok and not inverted and not hallucination

    return {
        "goal_ok": goal_ok,
        "req_ops_ok": req_ops_ok,
        "pro_ops_ok": pro_ops_ok,
        "polarity_inverted": inverted,
        "operation_retention_rate": retention_rate,
        "omitted_ops_count": omitted_count,
        "reference_ok": ref_ok,
        "hallucination": hallucination,
        "structural_ok": structural_ok,
        "critical_semantic_ok": critical_ok,
        "actual_goal": decoded.goal.description,
        "actual_req_ops": list(actual_req),
        "actual_pro_ops": list(actual_pro),
    }


def run_all_batteries(runtime: LFMMultiFeedRuntime) -> Dict[str, Any]:
    print("=" * 80)
    print("M35 URIv1 Batch A2.5 Stage 4 — Live Multi-Feed Operating Envelope Evaluation")
    print(f"Target Runtime: {runtime.endpoint_url} (Model: {runtime.model_name})")
    print("=" * 80)

    results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": runtime.model_name,
        "endpoint": runtime.endpoint_url,
        "batteries": {},
    }

    # -----------------------------------------------------------------------
    # Battery 1: Context Envelope Experiment (L0 to L7)
    # -----------------------------------------------------------------------
    print("\n[Battery 1/7] Running Context Envelope Battery (L0 to L7)...")
    b1_cases = build_context_envelope_battery()
    b1_records = []
    b1_breakpoint = None

    for case in b1_cases:
        res = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores = score_decoded_request(case, res.decoded_request)
        record = {
            "case_id": case.case_id,
            "approx_tokens": case.context_tokens_approx,
            "relevant_tokens": case.relevant_tokens_approx,
            "noise_tokens": case.noise_tokens_approx,
            "latency_ms": res.total_latency_ms,
            "rar_latency_ms": res.rar_latency_ms,
            "calls_made": res.calls_made,
            "scores": scores,
        }
        b1_records.append(record)
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id} ({case.context_tokens_approx} tokens): {status} | Goal: {scores['goal_ok']} | Req: {scores['req_ops_ok']} | Neg: {scores['pro_ops_ok']} | Lat: {res.total_latency_ms:.1f}ms")

        if scores["critical_semantic_ok"]:
            b1_breakpoint = case.case_id

    results["batteries"]["context_envelope"] = {
        "breakpoint_case": b1_breakpoint,
        "records": b1_records,
    }

    # -----------------------------------------------------------------------
    # Battery 2: Noise Sensitivity Controlled Pairs
    # -----------------------------------------------------------------------
    print("\n[Battery 2/7] Running Noise Sensitivity Controlled Pairs...")
    b2_cases = build_noise_sensitivity_battery()
    b2_records = []

    for case in b2_cases:
        res = runtime.execute_mode_d(text=case.user_text, run_parallel=True)
        scores = score_decoded_request(case, res.decoded_request)
        record = {
            "case_id": case.case_id,
            "useful_tokens": case.relevant_tokens_approx,
            "noise_tokens": case.noise_tokens_approx,
            "total_tokens": case.context_tokens_approx,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        }
        b2_records.append(record)
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id} (Noise: {case.noise_tokens_approx} tok): {status} | Lat: {res.total_latency_ms:.1f}ms")

    results["batteries"]["noise_sensitivity"] = b2_records

    # -----------------------------------------------------------------------
    # Battery 3: Semantic Complexity Ladder (C0 to C8)
    # -----------------------------------------------------------------------
    print("\n[Battery 3/7] Running Semantic Complexity Ladder (C0 to C8)...")
    b3_cases = build_complexity_ladder_battery()
    b3_records = []
    b3_breakpoint = None

    for case in b3_cases:
        res = runtime.execute_mode_d(text=case.user_text, run_parallel=True)
        scores = score_decoded_request(case, res.decoded_request)
        record = {
            "case_id": case.case_id,
            "description": case.description,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        }
        b3_records.append(record)
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id}: {status} | Req: {scores['req_ops_ok']} | Neg: {scores['pro_ops_ok']} | Lat: {res.total_latency_ms:.1f}ms | {case.description}")
        if scores["critical_semantic_ok"] and b3_breakpoint is None:
            b3_breakpoint = case.case_id

    results["batteries"]["complexity_ladder"] = {
        "breakpoint_case": b3_breakpoint,
        "records": b3_records,
    }

    # -----------------------------------------------------------------------
    # Battery 4: Negation Ladder (N1 to N6)
    # -----------------------------------------------------------------------
    print("\n[Battery 4/7] Running Negation Ladder (N1 to N6)...")
    b4_cases = build_negation_ladder_battery()
    b4_records = []

    for case in b4_cases:
        res = runtime.execute_mode_d(text=case.user_text, run_parallel=True)
        scores = score_decoded_request(case, res.decoded_request)
        record = {
            "case_id": case.case_id,
            "text": case.user_text,
            "expected_pro": list(case.expected_prohibited_ops),
            "expected_req": list(case.expected_requested_ops),
            "actual_pro": scores["actual_pro_ops"],
            "actual_req": scores["actual_req_ops"],
            "scores": scores,
            "latency_ms": res.total_latency_ms,
        }
        b4_records.append(record)
        status = "PASS" if scores["pro_ops_ok"] and not scores["polarity_inverted"] else "FAIL"
        print(f"  {case.case_id} ('{case.user_text}'): {status} | Pro: {scores['actual_pro_ops']} | Req: {scores['actual_req_ops']}")

    results["batteries"]["negation_ladder"] = b4_records

    # -----------------------------------------------------------------------
    # Battery 5: Operation Retention Ladder (O-R1 to O-R5)
    # -----------------------------------------------------------------------
    print("\n[Battery 5/7] Running Operation Retention Ladder (O-R1 to O-R5)...")
    b5_cases = build_operation_retention_battery()
    b5_records = []

    for case in b5_cases:
        res = runtime.execute_mode_d(text=case.user_text, run_parallel=True)
        scores = score_decoded_request(case, res.decoded_request)
        record = {
            "case_id": case.case_id,
            "expected_ops_count": len(case.expected_requested_ops),
            "actual_ops_count": len(scores["actual_req_ops"]),
            "retention_rate": scores["operation_retention_rate"],
            "omitted_count": scores["omitted_ops_count"],
            "scores": scores,
            "latency_ms": res.total_latency_ms,
        }
        b5_records.append(record)
        print(f"  {case.case_id} ({len(case.expected_requested_ops)} ops): Retention: {scores['operation_retention_rate']*100:.1f}% | Retained: {scores['actual_req_ops']}")

    results["batteries"]["operation_retention"] = b5_records

    # -----------------------------------------------------------------------
    # Battery 6: Progressive Feed Width Ladder (O0 to O5)
    # -----------------------------------------------------------------------
    print("\n[Battery 6/7] Running Progressive Feed Width Ladder (O0 to O5)...")
    b6_cases = build_progressive_feed_width_battery()
    b6_records = []

    for case in b6_cases:
        clause = case.user_text
        if case.case_id == "WIDTH-O0":
            p = build_feed_o_prompt(clause)
        elif case.case_id == "WIDTH-O1":
            p = build_feed_o_prompt(clause, candidate_actions=["review", "send"])
        elif case.case_id == "WIDTH-O2":
            p = build_feed_o_prompt(clause, candidate_actions=["review", "send"], rar_anchors=["doc_draft_order_2026"])
        elif case.case_id == "WIDTH-O3":
            p = build_feed_o_prompt(clause, candidate_actions=["review", "send"], rar_anchors=["doc_draft_order_2026"], active_context_labels=["Draft Order 2026.docx"])
        elif case.case_id == "WIDTH-O4":
            p = build_feed_o_prompt(clause, candidate_actions=["review", "send"], extra_metadata="Modified: 2026-09-21, Size: 45KB, Author: Warden")
        else:
            p = build_feed_o_prompt(clause, candidate_actions=["review", "send"], distractors=["Audit Event Log 001", "Meeting Memo 2025"])

        parsed_json, metric = runtime._call_feed_endpoint(FEED_O_SYSTEM_PROMPT, p, FEED_O_SCHEMA, "feed_o")
        feed_o = parse_feed_o_response(parsed_json)
        req_ok = set(feed_o.requested_operations) == set(case.expected_requested_ops)
        pro_ok = set(feed_o.prohibited_operations) == set(case.expected_prohibited_ops)

        record = {
            "case_id": case.case_id,
            "prompt_tokens": metric.prompt_tokens,
            "completion_tokens": metric.completion_tokens,
            "latency_ms": metric.latency_ms,
            "req_ok": req_ok,
            "pro_ok": pro_ok,
            "extracted_req": list(feed_o.requested_operations),
            "extracted_pro": list(feed_o.prohibited_operations),
        }
        b6_records.append(record)
        status = "PASS" if req_ok and pro_ok else "FAIL"
        print(f"  {case.case_id} ({metric.prompt_tokens} tokens): {status} | Req: {list(feed_o.requested_operations)} | Pro: {list(feed_o.prohibited_operations)} | Lat: {metric.latency_ms:.1f}ms")

    results["batteries"]["feed_width"] = b6_records

    # -----------------------------------------------------------------------
    # Battery 7: Multi-Mode Comparative Suite (Modes A, B, C, D)
    # -----------------------------------------------------------------------
    print("\n[Battery 7/7] Running Multi-Mode Comparative Suite (Modes A, B, C, D)...")
    test_cases = [
        EnvelopeTestCase(
            case_id="COMP-01",
            category="Mode_Comparison",
            user_text="Draft the memo and summarize it.",
            expected_goal="Draft and summarize memo",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("draft", "summarize"),
            expected_prohibited_ops=(),
        ),
        EnvelopeTestCase(
            case_id="COMP-02",
            category="Mode_Comparison",
            user_text="Review the draft order but do not send it.",
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            expected_reference_expression="the draft order",
            expected_target_id="doc_draft_order_2026",
            candidate_pool=b1_cases[2].candidate_pool,
        ),
        EnvelopeTestCase(
            case_id="COMP-03",
            category="Mode_Comparison",
            user_text="Don't send the previous version before Friday; revise the draft.",
            expected_goal="Revise draft without sending previous version before Friday",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("revise",),
            expected_prohibited_ops=("send",),
            expected_reference_expression="the previous version",
            expected_target_id="doc_prior_order_2025",
            candidate_pool=b1_cases[4].candidate_pool,
        ),
    ]

    mode_comparison: Dict[str, List[Dict[str, Any]]] = {"Mode A": [], "Mode B": [], "Mode D_seq": [], "Mode D_par": []}

    for case in test_cases:
        # Mode A: Raw Broad
        res_a = runtime.execute_mode_a(case.user_text)
        sc_a = score_decoded_request(case, res_a.decoded_request)
        mode_comparison["Mode A"].append({"case_id": case.case_id, "latency_ms": res_a.total_latency_ms, "critical_ok": sc_a["critical_semantic_ok"], "tokens": res_a.total_tokens})

        # Mode B: Serial RAR -> Broad
        res_b = runtime.execute_mode_b(case.user_text, referring_expression=case.expected_reference_expression, candidate_pool=case.candidate_pool)
        sc_b = score_decoded_request(case, res_b.decoded_request)
        mode_comparison["Mode B"].append({"case_id": case.case_id, "latency_ms": res_b.total_latency_ms, "critical_ok": sc_b["critical_semantic_ok"], "tokens": res_b.total_tokens})

        # Mode D: Adaptive Multi-Feed (Sequential)
        res_d_seq = runtime.execute_mode_d(case.user_text, referring_expression=case.expected_reference_expression, candidate_pool=case.candidate_pool, run_parallel=False)
        sc_d_seq = score_decoded_request(case, res_d_seq.decoded_request)
        mode_comparison["Mode D_seq"].append({"case_id": case.case_id, "latency_ms": res_d_seq.sequential_latency_ms, "critical_ok": sc_d_seq["critical_semantic_ok"], "tokens": res_d_seq.total_tokens, "calls": res_d_seq.calls_made})

        # Mode D: Adaptive Multi-Feed (Parallel)
        res_d_par = runtime.execute_mode_d(case.user_text, referring_expression=case.expected_reference_expression, candidate_pool=case.candidate_pool, run_parallel=True)
        sc_d_par = score_decoded_request(case, res_d_par.decoded_request)
        mode_comparison["Mode D_par"].append({"case_id": case.case_id, "latency_ms": res_d_par.parallel_latency_ms, "critical_ok": sc_d_par["critical_semantic_ok"], "tokens": res_d_par.total_tokens, "calls": res_d_par.calls_made})

        print(f"  {case.case_id}: Mode A: {sc_a['critical_semantic_ok']} ({res_a.total_latency_ms:.1f}ms) | Mode B: {sc_b['critical_semantic_ok']} ({res_b.total_latency_ms:.1f}ms) | Mode D_seq: {sc_d_seq['critical_semantic_ok']} ({res_d_seq.sequential_latency_ms:.1f}ms) | Mode D_par: {sc_d_par['critical_semantic_ok']} ({res_d_par.parallel_latency_ms:.1f}ms)")

    results["batteries"]["mode_comparison"] = mode_comparison

    # Save to JSON
    out_path = os.path.join(os.path.dirname(__file__), "lfm_stage4_qualification_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Machine-readable qualification results persisted to: {out_path}")

    return results


if __name__ == "__main__":
    runtime = LFMMultiFeedRuntime()
    run_all_batteries(runtime)
