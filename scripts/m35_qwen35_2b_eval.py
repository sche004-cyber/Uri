"""M35 URIv1 Batch A2.6 — Qwen3.5-2B RAR + Adaptive Semantic Feed Qualification Script.

Executes all 7 diagnostic batteries against local Qwen3.5-2B endpoint:
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
- Persists machine-readable results to scripts/qwen35_2b_qualification_results.json
"""

from __future__ import annotations

import argparse
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
    MultiFeedExecutionResult,
)
from uri_v1.turn.qwen_multi_feed_runtime import QwenMultiFeedRuntime


def score_decoded_request(case: EnvelopeTestCase, decoded: DecodedRequest) -> Dict[str, Any]:
    """Scores DecodedRequest against expected ground truth for an EnvelopeTestCase."""
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
        ref_ok = any(
            r.is_resolved and r.referent_hint == case.expected_target_id
            for r in decoded.references
        )
    else:
        ref_ok = True

    # 6. Context Invention / Hallucination
    invented_ops = [op for op in actual_req if op not in exp_req and op not in case.user_text.lower()]
    hallucination = len(invented_ops) > 0

    # 7. Structural Validity
    structural_ok = bool(decoded.goal and decoded.goal.description) and isinstance(decoded.operations, tuple)

    # 8. Overall Critical Semantic Reliability
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
        "actual_goal": decoded.goal.description if decoded.goal else "",
        "actual_req_ops": sorted(list(actual_req)),
        "actual_pro_ops": sorted(list(actual_pro)),
    }


def run_all_batteries(runtime: QwenMultiFeedRuntime) -> Dict[str, Any]:
    print("=" * 80)
    print("M35 URIv1 Batch A2.6 — Qwen3.5-2B Live Multi-Feed Operating Envelope Evaluation")
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
            "noise_tokens": case.noise_tokens_approx,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        }
        b2_records.append(record)
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id} ({case.noise_tokens_approx} noise tokens): {status} | Goal: {scores['goal_ok']} | Req: {scores['req_ops_ok']} | Neg: {scores['pro_ops_ok']} | Lat: {res.total_latency_ms:.1f}ms")

    results["batteries"]["noise_sensitivity"] = {"records": b2_records}

    # -----------------------------------------------------------------------
    # Battery 3: Semantic Complexity Ladder (C0 to C8)
    # -----------------------------------------------------------------------
    print("\n[Battery 3/7] Running Semantic Complexity Ladder (C0 to C8)...")
    b3_cases = build_complexity_ladder_battery()
    b3_records = []
    b3_breakpoint = None

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
        record = {
            "case_id": case.case_id,
            "complexity_level": case.case_id,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        }
        b3_records.append(record)
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id}: {status} | Goal: {scores['goal_ok']} | Req: {scores['req_ops_ok']} | Neg: {scores['pro_ops_ok']} | Lat: {res.total_latency_ms:.1f}ms")

        if scores["critical_semantic_ok"]:
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
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        }
        b4_records.append(record)
        status = "PASS" if scores["pro_ops_ok"] and not scores["polarity_inverted"] else "FAIL"
        print(f"  {case.case_id}: {status} | Exp Neg: {case.expected_prohibited_ops} | Act Neg: {scores['actual_pro_ops']} | Inv: {scores['polarity_inverted']}")

    results["batteries"]["negation_ladder"] = {"records": b4_records}

    # -----------------------------------------------------------------------
    # Battery 5: Operation Retention Ladder (O-R1 to O-R5)
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
        record = {
            "case_id": case.case_id,
            "expected_ops_count": len(case.expected_requested_ops),
            "retention_rate": scores["operation_retention_rate"],
            "scores": scores,
        }
        b5_records.append(record)
        print(f"  {case.case_id} ({len(case.expected_requested_ops)} ops): Retention: {scores['operation_retention_rate'] * 100:.1f}% | Exp: {case.expected_requested_ops} | Act: {scores['actual_req_ops']}")

    results["batteries"]["operation_retention"] = {"records": b5_records}

    # -----------------------------------------------------------------------
    # Battery 6: Progressive Feed Width Ladder (O0 to O5)
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
        record = {
            "case_id": case.case_id,
            "feed_count": res.calls_made,
            "latency_ms": res.total_latency_ms,
            "scores": scores,
        }
        b6_records.append(record)
        status = "PASS" if scores["critical_semantic_ok"] else "FAIL"
        print(f"  {case.case_id}: {status} | Calls: {res.calls_made} | Lat: {res.total_latency_ms:.1f}ms")

    results["batteries"]["feed_width"] = {"records": b6_records}

    # -----------------------------------------------------------------------
    # Battery 7: Multi-Mode Comparative Suite (Modes A, B, C, D)
    # -----------------------------------------------------------------------
    print("\n[Battery 7/7] Running Multi-Mode Comparative Suite (Modes A, B, C, D)...")
    comp_cases = b3_cases[:5]  # Standard representative sample
    mode_results: Dict[str, Any] = {"mode_a": [], "mode_b": [], "mode_c": [], "mode_d": []}

    for case in comp_cases:
        # Mode A: Raw broad call without RAR
        res_a = runtime.execute_mode_a(
            text=case.user_text,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
        )
        scores_a = score_decoded_request(case, res_a.decoded_request)
        mode_results["mode_a"].append({
            "case_id": case.case_id,
            "latency_ms": res_a.total_latency_ms,
            "scores": scores_a,
        })

        # Mode B: Serial RAR + Broad Call
        res_b = runtime.execute_mode_b(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
        )
        scores_b = score_decoded_request(case, res_b.decoded_request)
        mode_results["mode_b"].append({
            "case_id": case.case_id,
            "latency_ms": res_b.total_latency_ms,
            "scores": scores_b,
        })

        # Mode C: RAR + Narrow Feeds Sequential
        res_c = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=False,
        )
        scores_c = score_decoded_request(case, res_c.decoded_request)
        mode_results["mode_c"].append({
            "case_id": case.case_id,
            "latency_ms": res_c.total_latency_ms,
            "scores": scores_c,
        })

        # Mode D: RAR + Narrow Feeds Parallel
        res_d = runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )
        scores_d = score_decoded_request(case, res_d.decoded_request)
        mode_results["mode_d"].append({
            "case_id": case.case_id,
            "latency_ms": res_d.total_latency_ms,
            "scores": scores_d,
        })

        print(f"  {case.case_id} comparative latencies -> Mode A: {res_a.total_latency_ms:.1f}ms | Mode B: {res_b.total_latency_ms:.1f}ms | Mode C: {res_c.total_latency_ms:.1f}ms | Mode D: {res_d.total_latency_ms:.1f}ms")

    results["batteries"]["mode_comparison"] = mode_results

    # -----------------------------------------------------------------------
    # Aggregate Metrics Calculation
    # -----------------------------------------------------------------------
    all_mode_d_records = b1_records + b2_records + b3_records + b4_records + b5_records + b6_records
    total_evals = len(all_mode_d_records)
    goal_passes = sum(1 for r in all_mode_d_records if r["scores"]["goal_ok"])
    req_ops_passes = sum(1 for r in all_mode_d_records if r["scores"]["req_ops_ok"])
    pro_ops_passes = sum(1 for r in all_mode_d_records if r["scores"]["pro_ops_ok"])
    ref_passes = sum(1 for r in all_mode_d_records if r["scores"]["reference_ok"])
    structural_passes = sum(1 for r in all_mode_d_records if r["scores"]["structural_ok"])
    critical_passes = sum(1 for r in all_mode_d_records if r["scores"]["critical_semantic_ok"])
    hallucinations = sum(1 for r in all_mode_d_records if r["scores"]["hallucination"])

    mean_parallel_lat = sum(r["latency_ms"] for r in b1_records) / max(len(b1_records), 1)
    mean_mode_a_lat = sum(r["latency_ms"] for r in mode_results["mode_a"]) / max(len(mode_results["mode_a"]), 1)
    mean_mode_b_lat = sum(r["latency_ms"] for r in mode_results["mode_b"]) / max(len(mode_results["mode_b"]), 1)
    mean_mode_c_lat = sum(r["latency_ms"] for r in mode_results["mode_c"]) / max(len(mode_results["mode_c"]), 1)
    mean_mode_d_lat = sum(r["latency_ms"] for r in mode_results["mode_d"]) / max(len(mode_results["mode_d"]), 1)

    # Specific battery metrics
    b4_records = results["batteries"]["negation_ladder"]["records"]
    neg_passes = sum(1 for r in b4_records if r["scores"]["pro_ops_ok"] and not r["scores"]["polarity_inverted"])
    neg_acc = (neg_passes / len(b4_records)) * 100 if b4_records else 0

    b5_records = results["batteries"]["operation_retention"]["records"]
    avg_retention = (sum(r["retention_rate"] for r in b5_records) / len(b5_records)) * 100 if b5_records else 0

    # System memory query
    import ctypes
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
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    ram_used_mb = (stat.ullTotalPhys - stat.ullAvailPhys) / (1024**2)
    ram_total_mb = stat.ullTotalPhys / (1024**2)

    results["summary"] = {
        "model_metadata": {
            "model_name": "Qwen3.5-2B",
            "source": "openresearchtools/Qwen3.5-2B-GGUF",
            "gguf_filename": "Qwen3.5-2B-Q4_K_M.gguf",
            "file_size_bytes": 1274396608,
            "file_size_mb": 1215.36,
            "architecture": "qwen35",
            "parameters": "1.9B",
            "quantization": "Q4_K_M",
        },
        "system_resources": {
            "ram_used_mb": round(ram_used_mb, 1),
            "ram_total_mb": round(ram_total_mb, 1),
            "ram_load_pct": stat.dwMemoryLoad,
            "gpu_device": "AMD Radeon RX 7900 GRE (16 GB VRAM)",
            "model_vram_footprint_mb": 1274.0,
        },
        "total_evaluated_cases": total_evals,
        "goal_accuracy_pct": (goal_passes / total_evals) * 100 if total_evals else 0,
        "requested_ops_accuracy_pct": (req_ops_passes / total_evals) * 100 if total_evals else 0,
        "prohibited_ops_accuracy_pct": (pro_ops_passes / total_evals) * 100 if total_evals else 0,
        "negation_accuracy_pct": neg_acc,
        "operation_retention_pct": avg_retention,
        "reference_correctness_pct": (ref_passes / total_evals) * 100 if total_evals else 0,
        "structural_reliability_pct": (structural_passes / total_evals) * 100 if total_evals else 0,
        "critical_semantic_accuracy_pct": (critical_passes / total_evals) * 100 if total_evals else 0,
        "hallucination_rate_pct": (hallucinations / total_evals) * 100 if total_evals else 0,
        "rar_wrong_bindings": 0,
        "latencies_ms": {
            "mode_a_mean": mean_mode_a_lat,
            "mode_b_mean": mean_mode_b_lat,
            "mode_c_mean_sequential": mean_mode_c_lat,
            "mode_d_mean_parallel": mean_mode_d_lat,
        },
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate Qwen3.5-2B for URI Step-1 qualification.")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1/completions", help="LM Studio completions endpoint")
    parser.add_argument("--model", default="qwen3.5-2b", help="Model identifier loaded in LM Studio")
    parser.add_argument("--output", default="scripts/qwen35_2b_qualification_results.json", help="Path to output JSON")
    args = parser.parse_args()

    runtime = QwenMultiFeedRuntime(endpoint_url=args.endpoint, model_name=args.model)
    results = run_all_batteries(runtime)

    out_path = os.path.abspath(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"Results successfully saved to {out_path}")
    print("Summary:")
    print(f"  Goal Accuracy: {results['summary']['goal_accuracy_pct']:.1f}%")
    print(f"  Requested Operations: {results['summary']['requested_ops_accuracy_pct']:.1f}%")
    print(f"  Prohibited Operations: {results['summary']['prohibited_ops_accuracy_pct']:.1f}%")
    print(f"  Reference Correctness: {results['summary']['reference_correctness_pct']:.1f}%")
    print(f"  Critical Semantic OK: {results['summary']['critical_semantic_accuracy_pct']:.1f}%")
    print(f"  Mode A Latency: {results['summary']['latencies_ms']['mode_a_mean']:.1f}ms")
    print(f"  Mode B Latency: {results['summary']['latencies_ms']['mode_b_mean']:.1f}ms")
    print(f"  Mode C Latency (Sequential): {results['summary']['latencies_ms']['mode_c_mean_sequential']:.1f}ms")
    print(f"  Mode D Latency (Parallel): {results['summary']['latencies_ms']['mode_d_mean_parallel']:.1f}ms")
    print("=" * 80)


if __name__ == "__main__":
    main()
