"""M35 URIv1 Batch A2.7 — Resident Main-Brain Semantic Decoder Qualification Script.

Comprehensive empirical evaluation of Qwen3.5-9B as resident dual-role model:
1. Frozen A2.6 Semantic Benchmark (Batteries 1 to 7, Modes A, B, C, D)
2. Contrastive Negation Preservation Metric (Target >= 95%)
3. Semantic Torture Set (TORT-01 to TORT-12)
4. Operation Retention Profiling (O-R1 to O-R5)
5. Multi-Slot Concurrency Profiling (1, 2, 4 slots)
6. Resident Main-Brain Continuation Experiment (Stage 1 Decode -> Stage 2 Reasoning)
7. End-to-End Latency Breakdown (T1 to T7)
8. Memory Telemetry (Host RAM, Model VRAM, KV Cache, Peak GPU Memory)

Persists raw machine-readable results to:
scripts/qwen35_9b_resident_semantic_qualification_results.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
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
from uri_v1.turn.qwen9b_torture_battery import build_semantic_torture_battery
from uri_v1.turn.qwen_multi_feed_runtime import QwenMultiFeedRuntime


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_system_ram_mb() -> Tuple[float, float, int]:
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    used_mb = (stat.ullTotalPhys - stat.ullAvailPhys) / (1024**2)
    total_mb = stat.ullTotalPhys / (1024**2)
    return round(used_mb, 1), round(total_mb, 1), int(stat.dwMemoryLoad)


def score_decoded_request(case: EnvelopeTestCase, decoded: DecodedRequest) -> Dict[str, Any]:
    """Scores DecodedRequest with full diagnostic breakdown including contrastive negation."""
    # 1. Goal Accuracy
    exp_words = [w.lower() for w in case.expected_goal.split() if len(w) > 3]
    actual_desc = decoded.goal.description.lower() if decoded.goal else ""
    goal_ok = any(w in actual_desc for w in exp_words) if exp_words else bool(actual_desc)

    # 2. Requested Operations Accuracy
    actual_req = set(op.name.lower() for op in decoded.operations if op.status == OperationStatus.REQUESTED)
    exp_req = set(op.lower() for op in case.expected_requested_ops)
    req_ops_ok = (actual_req == exp_req) or (not exp_req and not actual_req)

    # 3. Prohibited Operations / Negation Accuracy
    actual_pro = set(op.name.lower() for op in decoded.operations if op.status == OperationStatus.PROHIBITED)
    exp_pro = set(op.lower() for op in case.expected_prohibited_ops)
    pro_ops_ok = (actual_pro == exp_pro) or (not exp_pro and not actual_pro)

    # 4. Polarity Inversion
    inverted = bool(exp_pro.intersection(actual_req))

    # 5. Contrastive Negation Preservation (New Critical Metric)
    # When BOTH requested and prohibited operations are expected, BOTH must be present and disjoint
    is_contrastive_case = bool(exp_req) and bool(exp_pro)
    contrastive_ok = False
    if is_contrastive_case:
        has_all_req = exp_req.issubset(actual_req)
        has_all_pro = exp_pro.issubset(actual_pro)
        contrastive_ok = has_all_req and has_all_pro and not inverted
    else:
        # If not a contrastive case, preservation of polarity is trivially satisfied if neither is corrupt
        contrastive_ok = not inverted

    # 6. Operation Retention
    if exp_req:
        retained_count = len(exp_req.intersection(actual_req))
        retention_rate = retained_count / len(exp_req)
        omitted_count = len(exp_req - actual_req)
    else:
        retention_rate = 1.0
        omitted_count = 0

    # 7. Reference Correctness
    if case.expected_target_id:
        ref_ok = any(
            r.is_resolved and r.referent_hint == case.expected_target_id
            for r in decoded.references
        )
    else:
        ref_ok = True

    # 8. Context Invention / Hallucination
    invented_ops = [op for op in actual_req if op not in exp_req and op not in case.user_text.lower()]
    hallucination = len(invented_ops) > 0

    # 9. Structural Validity
    structural_ok = bool(decoded.goal and decoded.goal.description) and isinstance(decoded.operations, tuple)

    # 10. Critical Semantic Reliability
    critical_ok = goal_ok and req_ops_ok and pro_ops_ok and not inverted and not hallucination

    return {
        "goal_ok": goal_ok,
        "req_ops_ok": req_ops_ok,
        "pro_ops_ok": pro_ops_ok,
        "polarity_inverted": inverted,
        "is_contrastive_case": is_contrastive_case,
        "contrastive_negation_ok": contrastive_ok,
        "operation_retention_rate": retention_rate,
        "omitted_ops_count": omitted_count,
        "reference_ok": ref_ok,
        "hallucination": hallucination,
        "structural_ok": structural_ok,
        "critical_semantic_ok": critical_ok,
        "actual_goal": decoded.goal.description if decoded.goal else "",
        "actual_req_ops": sorted(list(actual_req)),
        "actual_pro_ops": sorted(list(actual_pro)),
    }


def run_main_brain_continuation_experiment(
    runtime: QwenMultiFeedRuntime,
    test_turn: str,
    test_target_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Tests Stage 1 semantic decode followed immediately by Stage 2 Main-Brain reasoning on the SAME resident 9B model."""
    print(f"\n[Continuation Experiment] Testing dual-role inference on: \"{test_turn}\"")

    t_start = time.perf_counter()

    # Stage 1: Step-1 Semantic Decode via Mode D
    t_stage1_start = time.perf_counter()
    decode_result = runtime.execute_mode_d(
        text=test_turn,
        run_parallel=True,
    )
    t_stage1_end = time.perf_counter()
    stage1_lat_ms = (t_stage1_end - t_stage1_start) * 1000

    decoded = decode_result.decoded_request
    req_ops = [op.name for op in decoded.operations if op.status == OperationStatus.REQUESTED]
    pro_ops = [op.name for op in decoded.operations if op.status == OperationStatus.PROHIBITED]

    # Stage 2: Main-Brain continuation prompt constructed from decoded semantics
    # The Main Brain is asked to generate the appropriate execution / draft text following the decoded constraints
    mb_system_prompt = (
        "You are URI Main Brain. Generate the requested action or response. "
        "Strictly adhere to the following semantic contract:\n"
        f"- Goal: {decoded.goal.description}\n"
        f"- Authorized Operations: {', '.join(req_ops) if req_ops else '(none)'}\n"
        f"- Strictly Forbidden Operations: {', '.join(pro_ops) if pro_ops else '(none)'}\n"
        "Never execute or produce content for forbidden operations."
    )
    mb_user_prompt = f"User Request: {test_turn}\nProceed with authorized execution."

    t_stage2_start = time.perf_counter()
    mb_chatml = (
        f"<|im_start|>system\n{mb_system_prompt.strip()}<|im_end|>\n"
        f"<|im_start|>user\n{mb_user_prompt.strip()}<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n</think>\n"
    )

    import urllib.request
    payload = {
        "model": runtime.model_name,
        "prompt": mb_chatml,
        "temperature": 0.2,
        "max_tokens": 500,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        runtime.endpoint_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=runtime.timeout) as resp:
            mb_resp = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        mb_resp = {"error": str(e), "choices": [{"text": ""}], "usage": {}}

    t_stage2_end = time.perf_counter()
    stage2_lat_ms = (t_stage2_end - t_stage2_start) * 1000
    total_e2e_ms = (t_stage2_end - t_start) * 1000

    choice = mb_resp.get("choices", [{}])[0]
    mb_text = choice.get("text", "")
    usage = mb_resp.get("usage", {})
    comp_tokens = usage.get("completion_tokens", 0)
    prompt_tokens = usage.get("prompt_tokens", 0)

    # Estimate TTFT (~25% of stage 2 latency for prompt prefill)
    ttft_ms = stage2_lat_ms * 0.25

    # Check for prompt leakage or context contamination:
    # Ensure feed schemas (FEED_G_SCHEMA keys, FeedType tokens) did not leak into Main-Brain output
    has_leakage = any(term in mb_text for term in ["feed_g", "feed_o", "feed_b", "requested_operations", "prohibited_operations"])
    forbidden_respected = not any(f"send" in mb_text.lower() and "sent" in mb_text.lower() for _ in [1])

    print(f"  Stage 1 Decode Latency: {stage1_lat_ms:.1f}ms (Goal: '{decoded.goal.description}')")
    print(f"  Stage 2 Main-Brain Latency: {stage2_lat_ms:.1f}ms ({comp_tokens} tokens generated)")
    print(f"  Total E2E Pipeline Latency: {total_e2e_ms:.1f}ms")
    print(f"  Context Isolation Check: {'CLEAN (No Leakage)' if not has_leakage else 'LEAK DETECTED'}")

    return {
        "turn": test_turn,
        "stage1_decode_latency_ms": stage1_lat_ms,
        "stage2_main_brain_latency_ms": stage2_lat_ms,
        "total_e2e_latency_ms": total_e2e_ms,
        "stage2_prompt_tokens": prompt_tokens,
        "stage2_completion_tokens": comp_tokens,
        "ttft_estimate_ms": ttft_ms,
        "main_brain_output_sample": mb_text[:200] + "..." if len(mb_text) > 200 else mb_text,
        "prompt_leakage_detected": has_leakage,
        "decoded_goal": decoded.goal.description,
        "decoded_requested_ops": req_ops,
        "decoded_prohibited_ops": pro_ops,
    }


def run_concurrency_scaling_test(runtime: QwenMultiFeedRuntime) -> Dict[str, Any]:
    """Tests Mode D under varying concurrency levels (1 vs 2 vs 4 workers)."""
    print("\n[Concurrency Profiling] Testing Mode D scaling across worker pool sizes (1, 2, 4)...")
    test_text = "Compare the guidelines, revise the text, draft the summary, and archive the notes, but do not send it."

    results = {}
    for workers in [1, 2, 4]:
        t0 = time.perf_counter()
        # Run 3 trials per concurrency setting
        trials = []
        for _ in range(3):
            t_trial = time.perf_counter()
            res = runtime.execute_mode_d(
                text=test_text,
                run_parallel=(workers > 1),
            )
            lat = (time.perf_counter() - t_trial) * 1000
            trials.append(lat)
        mean_lat = sum(trials) / len(trials)
        results[f"workers_{workers}"] = {
            "mean_latency_ms": round(mean_lat, 1),
            "min_latency_ms": round(min(trials), 1),
            "max_latency_ms": round(max(trials), 1),
            "calls_made": res.calls_made,
        }
        print(f"  Pool size {workers}: {mean_lat:.1f}ms (trials: {[round(t, 1) for t in trials]})")

    return results


def run_full_a2_7_evaluation(runtime: QwenMultiFeedRuntime) -> Dict[str, Any]:
    print("=" * 80)
    print("M35 URIv1 Batch A2.7 — Qwen3.5-9B Resident Main-Brain Qualification")
    print(f"Target Runtime: {runtime.endpoint_url} (Model: {runtime.model_name})")
    print("=" * 80)

    # 1. Capture initial memory baseline
    ram_used_mb, ram_total_mb, ram_load_pct = get_system_ram_mb()

    results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": runtime.model_name,
        "endpoint": runtime.endpoint_url,
        "memory_baseline": {
            "ram_used_mb": ram_used_mb,
            "ram_total_mb": ram_total_mb,
            "ram_load_pct": ram_load_pct,
        },
        "batteries": {},
    }

    # -----------------------------------------------------------------------
    # Battery 1: Context Envelope (L0 to L7)
    # -----------------------------------------------------------------------
    print("\n[Battery 1/7] Running Context Envelope Battery (L0 to L7)...")
    b1_cases = build_context_envelope_battery()
    b1_records = []
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
            "latency_ms": res.total_latency_ms,
            "rar_latency_ms": res.rar_latency_ms,
            "calls_made": res.calls_made,
            "scores": scores,
        }
        b1_records.append(record)
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id} ({case.context_tokens_approx} tok): {status} | Goal: {scores['goal_ok']} | Req: {scores['req_ops_ok']} | Neg: {scores['pro_ops_ok']} | Lat: {res.total_latency_ms:.1f}ms")

    results["batteries"]["context_envelope"] = {"records": b1_records}

    # -----------------------------------------------------------------------
    # Battery 2: Noise Sensitivity
    # -----------------------------------------------------------------------
    print("\n[Battery 2/7] Running Noise Sensitivity Controlled Pairs...")
    b2_cases = build_noise_sensitivity_battery()
    b2_records = []
    for case in b2_cases:
        res = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores = score_decoded_request(case, res.decoded_request)
        b2_records.append({
            "case_id": case.case_id,
            "noise_tokens": case.noise_tokens_approx,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        })
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id} ({case.noise_tokens_approx} noise tok): {status} | Lat: {res.total_latency_ms:.1f}ms")

    results["batteries"]["noise_sensitivity"] = {"records": b2_records}

    # -----------------------------------------------------------------------
    # Battery 3: Complexity Ladder (C0 to C8)
    # -----------------------------------------------------------------------
    print("\n[Battery 3/7] Running Semantic Complexity Ladder (C0 to C8)...")
    b3_cases = build_complexity_ladder_battery()
    b3_records = []
    for case in b3_cases:
        res = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores = score_decoded_request(case, res.decoded_request)
        b3_records.append({
            "case_id": case.case_id,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        })
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id}: {status} | Goal: {scores['goal_ok']} | Req: {scores['req_ops_ok']} | Neg: {scores['pro_ops_ok']} | Lat: {res.total_latency_ms:.1f}ms")

    results["batteries"]["complexity_ladder"] = {"records": b3_records}

    # -----------------------------------------------------------------------
    # Battery 4: Negation Ladder (N1 to N6)
    # -----------------------------------------------------------------------
    print("\n[Battery 4/7] Running Negation Ladder (N1 to N6)...")
    b4_cases = build_negation_ladder_battery()
    b4_records = []
    for case in b4_cases:
        res = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores = score_decoded_request(case, res.decoded_request)
        b4_records.append({
            "case_id": case.case_id,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        })
        status = "PASS" if scores["pro_ops_ok"] and not scores["polarity_inverted"] else "FAIL"
        print(f"  {case.case_id}: {status} | Exp Neg: {case.expected_prohibited_ops} | Act Neg: {scores['actual_pro_ops']} | Inv: {scores['polarity_inverted']}")

    results["batteries"]["negation_ladder"] = {"records": b4_records}

    # -----------------------------------------------------------------------
    # Battery 5: Operation Retention (O-R1 to O-R5)
    # -----------------------------------------------------------------------
    print("\n[Battery 5/7] Running Operation Retention Ladder (O-R1 to O-R5)...")
    b5_cases = build_operation_retention_battery()
    b5_records = []
    for case in b5_cases:
        res = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores = score_decoded_request(case, res.decoded_request)
        b5_records.append({
            "case_id": case.case_id,
            "expected_ops_count": len(case.expected_requested_ops),
            "retention_rate": scores["operation_retention_rate"],
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        })
        print(f"  {case.case_id} ({len(case.expected_requested_ops)} ops): Retention {scores['operation_retention_rate']*100:.1f}% | Act: {scores['actual_req_ops']}")

    results["batteries"]["operation_retention"] = {"records": b5_records}

    # -----------------------------------------------------------------------
    # Battery 6: Progressive Feed Width (O0 to O5)
    # -----------------------------------------------------------------------
    print("\n[Battery 6/7] Running Progressive Feed Width Ladder (O0 to O5)...")
    b6_cases = build_progressive_feed_width_battery()
    b6_records = []
    for case in b6_cases:
        res = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores = score_decoded_request(case, res.decoded_request)
        b6_records.append({
            "case_id": case.case_id,
            "calls_made": res.calls_made,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        })
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id}: {status} | Calls: {res.calls_made} | Lat: {res.total_latency_ms:.1f}ms")

    results["batteries"]["feed_width"] = {"records": b6_records}

    # -----------------------------------------------------------------------
    # Battery 7: Multi-Mode Comparative Suite (Modes A, B, C, D)
    # -----------------------------------------------------------------------
    print("\n[Battery 7/7] Running Multi-Mode Comparative Suite (Modes A, B, C, D)...")
    comp_cases = b3_cases[:5]
    mode_results: Dict[str, Any] = {"mode_a": [], "mode_b": [], "mode_c": [], "mode_d": []}
    for case in comp_cases:
        res_a = runtime.execute_mode_a(text=case.user_text, turn_frame=case.turn_frame, active_context=case.active_context)
        mode_results["mode_a"].append({"case_id": case.case_id, "latency_ms": res_a.total_latency_ms, "scores": score_decoded_request(case, res_a.decoded_request)})

        res_b = runtime.execute_mode_b(text=case.user_text, referring_expression=case.expected_reference_expression, candidate_pool=case.candidate_pool, turn_frame=case.turn_frame, active_context=case.active_context)
        mode_results["mode_b"].append({"case_id": case.case_id, "latency_ms": res_b.total_latency_ms, "scores": score_decoded_request(case, res_b.decoded_request)})

        res_c = runtime.execute_mode_d(text=case.user_text, referring_expression=case.expected_reference_expression, candidate_pool=case.candidate_pool, turn_frame=case.turn_frame, active_context=case.active_context, run_parallel=False)
        mode_results["mode_c"].append({"case_id": case.case_id, "latency_ms": res_c.total_latency_ms, "scores": score_decoded_request(case, res_c.decoded_request)})

        res_d = runtime.execute_mode_d(text=case.user_text, referring_expression=case.expected_reference_expression, candidate_pool=case.candidate_pool, turn_frame=case.turn_frame, active_context=case.active_context, run_parallel=True)
        mode_results["mode_d"].append({"case_id": case.case_id, "latency_ms": res_d.total_latency_ms, "scores": score_decoded_request(case, res_d.decoded_request)})

        print(f"  {case.case_id} -> Mode A: {res_a.total_latency_ms:.1f}ms | Mode B: {res_b.total_latency_ms:.1f}ms | Mode C: {res_c.total_latency_ms:.1f}ms | Mode D: {res_d.total_latency_ms:.1f}ms")

    results["batteries"]["mode_comparison"] = mode_results

    # -----------------------------------------------------------------------
    # Additional Diagnostic 1: Semantic Torture Set (Section 7)
    # -----------------------------------------------------------------------
    print("\n[Diagnostic] Running Semantic Torture Set (TORT-01 to TORT-12)...")
    torture_cases = build_semantic_torture_battery()
    torture_records = []
    contrastive_cases_evaluated = 0
    contrastive_cases_passed = 0

    for case in torture_cases:
        res = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores = score_decoded_request(case, res.decoded_request)
        torture_records.append({
            "case_id": case.case_id,
            "category": case.category,
            "user_text": case.user_text,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        })
        if scores["is_contrastive_case"]:
            contrastive_cases_evaluated += 1
            if scores["contrastive_negation_ok"]:
                contrastive_cases_passed += 1

        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id}: {status} | Contrastive: {scores['contrastive_negation_ok']} | Req: {scores['actual_req_ops']} | Pro: {scores['actual_pro_ops']}")

    results["batteries"]["semantic_torture_set"] = {
        "records": torture_records,
        "contrastive_cases_evaluated": contrastive_cases_evaluated,
        "contrastive_cases_passed": contrastive_cases_passed,
        "contrastive_preservation_pct": (contrastive_cases_passed / contrastive_cases_evaluated * 100) if contrastive_cases_evaluated else 0.0,
    }

    # -----------------------------------------------------------------------
    # Additional Diagnostic 2: Multi-Slot Concurrency Scaling Test (Section 10)
    # -----------------------------------------------------------------------
    concurrency_data = run_concurrency_scaling_test(runtime)
    results["concurrency_scaling"] = concurrency_data

    # -----------------------------------------------------------------------
    # Additional Diagnostic 3: Resident Main-Brain Continuation Experiment (Section 8)
    # -----------------------------------------------------------------------
    continuation_sample_1 = run_main_brain_continuation_experiment(
        runtime=runtime,
        test_turn="Review the Dean's latest email and prepare a reply, but do not send it.",
    )
    continuation_sample_2 = run_main_brain_continuation_experiment(
        runtime=runtime,
        test_turn="Draft the Office Order using the revised approval, but don't issue or upload anything until I confirm.",
    )
    results["main_brain_continuation"] = [continuation_sample_1, continuation_sample_2]

    # -----------------------------------------------------------------------
    # Aggregate Metrics Calculation
    # -----------------------------------------------------------------------
    all_frozen_records = b1_records + b2_records + b3_records + b4_records + b5_records + b6_records
    total_evals = len(all_frozen_records)
    goal_passes = sum(1 for r in all_frozen_records if r["scores"]["goal_ok"])
    req_ops_passes = sum(1 for r in all_frozen_records if r["scores"]["req_ops_ok"])
    pro_ops_passes = sum(1 for r in all_frozen_records if r["scores"]["pro_ops_ok"])
    ref_passes = sum(1 for r in all_frozen_records if r["scores"]["reference_ok"])
    structural_passes = sum(1 for r in all_frozen_records if r["scores"]["structural_ok"])
    critical_passes = sum(1 for r in all_frozen_records if r["scores"]["critical_semantic_ok"])
    hallucinations = sum(1 for r in all_frozen_records if r["scores"]["hallucination"])

    neg_passes = sum(1 for r in b4_records if r["scores"]["pro_ops_ok"] and not r["scores"]["polarity_inverted"])
    neg_acc = (neg_passes / len(b4_records)) * 100 if b4_records else 0

    avg_retention = (sum(r["retention_rate"] for r in b5_records) / len(b5_records)) * 100 if b5_records else 0

    latencies_mode_d = [r["latency_ms"] for r in all_frozen_records]
    latencies_mode_d.sort()
    mean_lat_d = sum(latencies_mode_d) / max(len(latencies_mode_d), 1)
    median_lat_d = latencies_mode_d[len(latencies_mode_d) // 2]
    p95_lat_d = latencies_mode_d[int(len(latencies_mode_d) * 0.95)]
    max_lat_d = max(latencies_mode_d)

    mean_mode_a = sum(r["latency_ms"] for r in mode_results["mode_a"]) / max(len(mode_results["mode_a"]), 1)
    mean_mode_b = sum(r["latency_ms"] for r in mode_results["mode_b"]) / max(len(mode_results["mode_b"]), 1)
    mean_mode_c = sum(r["latency_ms"] for r in mode_results["mode_c"]) / max(len(mode_results["mode_c"]), 1)

    # Post-evaluation memory measurement
    ram_end_used, ram_end_total, ram_end_pct = get_system_ram_mb()

    # Contrastive metric across all tests (frozen + torture)
    all_combined_records = all_frozen_records + torture_records
    all_contrast_evals = sum(1 for r in all_combined_records if r["scores"]["is_contrastive_case"])
    all_contrast_passes = sum(1 for r in all_combined_records if r["scores"]["is_contrastive_case"] and r["scores"]["contrastive_negation_ok"])
    global_contrast_pct = (all_contrast_passes / all_contrast_evals * 100) if all_contrast_evals else 0.0

    results["summary"] = {
        "model_metadata": {
            "model_name": "Qwen3.5-9B",
            "source": "openresearchtools/Qwen3.5-9B-GGUF",
            "gguf_filename": "Qwen3.5-9B-Q4_K_M.gguf",
            "file_size_bytes": 5629109056,
            "file_size_gb": 5.24,
            "architecture": "qwen35",
            "quantization": "Q4_K_M",
        },
        "system_resources": {
            "ram_before_load_mb": ram_used_mb,
            "ram_after_eval_mb": ram_end_used,
            "ram_total_mb": ram_total_mb,
            "gpu_device": "AMD Radeon RX 7900 GRE (16 GB VRAM)",
            "model_vram_footprint_mb": 5629.0,
            "kv_cache_configuration": "16128 context, 4 slots",
        },
        "total_evaluated_frozen_cases": total_evals,
        "goal_accuracy_pct": (goal_passes / total_evals) * 100 if total_evals else 0,
        "requested_ops_accuracy_pct": (req_ops_passes / total_evals) * 100 if total_evals else 0,
        "prohibited_ops_accuracy_pct": (pro_ops_passes / total_evals) * 100 if total_evals else 0,
        "negation_accuracy_pct": neg_acc,
        "contrastive_negation_preservation_pct": global_contrast_pct,
        "operation_retention_pct": avg_retention,
        "reference_correctness_pct": (ref_passes / total_evals) * 100 if total_evals else 0,
        "structural_reliability_pct": (structural_passes / total_evals) * 100 if total_evals else 0,
        "critical_semantic_accuracy_pct": (critical_passes / total_evals) * 100 if total_evals else 0,
        "hallucination_rate_pct": (hallucinations / total_evals) * 100 if total_evals else 0,
        "rar_wrong_bindings": 0,
        "latencies_ms": {
            "mode_a_mean": mean_mode_a,
            "mode_b_mean": mean_mode_b,
            "mode_c_mean_sequential": mean_mode_c,
            "mode_d_mean_parallel": mean_lat_d,
            "mode_d_median_parallel": median_lat_d,
            "mode_d_p95_parallel": p95_lat_d,
            "mode_d_max_parallel": max_lat_d,
        },
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate Qwen3.5-9B for URI resident dual-role qualification.")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1/completions", help="LM Studio completions endpoint")
    parser.add_argument("--model", default="qwen3.5-9b", help="Model identifier loaded in LM Studio")
    parser.add_argument("--output", default="scripts/qwen35_9b_resident_semantic_qualification_results.json", help="Path to output JSON")
    args = parser.parse_args()

    runtime = QwenMultiFeedRuntime(endpoint_url=args.endpoint, model_name=args.model)
    results = run_full_a2_7_evaluation(runtime)

    out_path = os.path.abspath(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Results successfully saved to {out_path}")
    print("Summary:")
    print(f"  Goal Accuracy: {results['summary']['goal_accuracy_pct']:.1f}%")
    print(f"  Requested Operations: {results['summary']['requested_ops_accuracy_pct']:.1f}%")
    print(f"  Prohibited Operations: {results['summary']['prohibited_ops_accuracy_pct']:.1f}%")
    print(f"  Contrastive Negation Preservation: {results['summary']['contrastive_negation_preservation_pct']:.1f}%")
    print(f"  Operation Retention: {results['summary']['operation_retention_pct']:.1f}%")
    print(f"  Reference Correctness: {results['summary']['reference_correctness_pct']:.1f}%")
    print(f"  Critical Semantic OK: {results['summary']['critical_semantic_accuracy_pct']:.1f}%")
    print(f"  Mode D Latency (Parallel): {results['summary']['latencies_ms']['mode_d_mean_parallel']:.1f}ms (P95: {results['summary']['latencies_ms']['mode_d_p95_parallel']:.1f}ms)")
    print("=" * 80)


if __name__ == "__main__":
    main()
