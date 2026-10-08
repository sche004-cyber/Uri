"""Experimental runner for Edge Model lightweight qualification.

Executes battery across 3 arms:
- Arm A: Deterministic baseline
- Arm B: Qwen3.5-0.8B candidate
- Arm C: Qwen3.5-9B resident model
Runs all outputs through URI independent verification.
Computes comprehensive metrics and persists raw results.
"""
from __future__ import annotations

import ctypes
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experimental.edge_model_tests.deterministic_path import DeterministicBaseline
from experimental.edge_model_tests.edge_candidate import Qwen08BCandidate
from experimental.edge_model_tests.resident_candidate import Qwen9BResidentCandidate
from experimental.edge_model_tests.verifier import EdgeTaskVerifier, VerifierOutcome


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


def get_ram_info() -> Dict[str, float]:
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    used_mb = (stat.ullTotalPhys - stat.ullAvailPhys) / (1024**2)
    total_mb = stat.ullTotalPhys / (1024**2)
    return {
        "used_ram_mb": round(used_mb, 1),
        "total_ram_mb": round(total_mb, 1),
        "ram_load_pct": int(stat.dwMemoryLoad),
    }


def classify_failure(case: Dict[str, Any], raw_output: str, outcome: VerifierOutcome) -> str:
    if outcome.failure_reason:
        reason = outcome.failure_reason.lower()
        if "malformed" in reason or "json parse" in reason:
            return "malformed_schema"
        if "negation" in reason or "prohibition" in reason:
            return "lost_negation"
        if "capability" in reason:
            return "wrong_tool_or_capability"
        if "intent" in reason:
            return "semantic_misunderstanding"
        if "filter" in reason or "format" in reason or "field" in reason:
            return "argument_mismatch"
        if "attempted_task_that_should_escalate" in reason:
            return "attempted_task_that_should_escalate"
        if "refused_safe_local_task" in reason:
            return "refused_safe_local_task"
    if outcome.final_decision == "ESCALATE":
        exp_reason = case.get("expected_reason", "")
        if "MISSING_ARGUMENT" in exp_reason:
            return "missing_argument"
        if "AMBIGUOUS" in exp_reason:
            return "ambiguity"
        if "NO_QUALIFIED_CAPABILITY" in exp_reason:
            return "unsupported_operation"
        if "CROSS_SESSION" in exp_reason:
            return "insufficient_context"
        if "DESTRUCTIVE" in exp_reason or "ELEVATION" in exp_reason:
            return "prohibited_boundary_escalation"
        return "grounded_escalation"
    return "none"


def run_arm(arm_name: str, candidate, cases: List[Dict[str, Any]], verifier: EdgeTaskVerifier) -> Dict[str, Any]:
    print(f"\n--- Running Arm: {arm_name} ({len(cases)} cases) ---")
    case_results = []
    latencies = []
    inference_latencies = []
    verification_latencies = []
    prompt_tokens_list = []
    eval_tokens_list = []

    for idx, case in enumerate(cases, 1):
        cid = case["id"]
        t_case_start = time.perf_counter()

        # 1. Candidate inference
        raw_output, cand_metrics = candidate.run_case(case)
        t_inference_done = time.perf_counter()

        # 2. URI verification
        t_verify_start = time.perf_counter()
        outcome = verifier.verify(case, raw_output)
        t_verify_done = time.perf_counter()

        # 3. Timing breakdown
        total_latency_ms = (t_verify_done - t_case_start) * 1000
        inf_ms = cand_metrics.get("inference_duration_ms", (t_inference_done - t_case_start) * 1000)
        verify_ms = (t_verify_done - t_verify_start) * 1000
        harness_overhead_ms = max(0.0, total_latency_ms - inf_ms - verify_ms)

        latencies.append(total_latency_ms)
        inference_latencies.append(inf_ms)
        verification_latencies.append(verify_ms)
        prompt_tokens_list.append(cand_metrics.get("prompt_tokens", 0))
        eval_tokens_list.append(cand_metrics.get("eval_tokens", 0))

        fail_cat = classify_failure(case, raw_output, outcome)

        record = {
            "case_id": cid,
            "category": case.get("category"),
            "expected_decision": case.get("expected_decision"),
            "candidate_output": raw_output,
            "candidate_claimed_local": outcome.candidate_claimed_local,
            "verifier_status": outcome.verifier_status,
            "final_decision": outcome.final_decision,
            "is_correct": outcome.is_correct,
            "is_false_success": outcome.is_false_success,
            "is_false_verified": outcome.is_false_verified,
            "failure_reason": outcome.failure_reason,
            "failure_classification": fail_cat,
            "metrics": {
                "total_latency_ms": round(total_latency_ms, 1),
                "inference_latency_ms": round(inf_ms, 1),
                "verification_latency_ms": round(verify_ms, 2),
                "harness_overhead_ms": round(harness_overhead_ms, 2),
                "prompt_tokens": cand_metrics.get("prompt_tokens", 0),
                "eval_tokens": cand_metrics.get("eval_tokens", 0),
            }
        }
        case_results.append(record)
        print(f"[{idx:02d}/30] {cid:22s} | Exp: {case.get('expected_decision'):8s} | Claimed: {'LOCAL' if outcome.candidate_claimed_local else 'ESC':5s} | Verifier: {outcome.verifier_status:20s} | Final: {outcome.final_decision:22s} | Corr: {str(outcome.is_correct):5s} | {inf_ms:6.1f}ms")

    # Aggregate calculations
    total_cases = len(case_results)
    correct_cases = sum(1 for r in case_results if r["is_correct"])
    verified_local_successes = sum(1 for r in case_results if r["final_decision"] == "VERIFIED_LOCAL_SUCCESS")
    candidate_claimed_successes = sum(1 for r in case_results if r["candidate_claimed_local"])
    false_candidate_successes = sum(1 for r in case_results if r["is_false_success"])
    false_verified_successes = sum(1 for r in case_results if r["is_false_verified"])
    correct_escalations = sum(1 for r in case_results if r["final_decision"] == "ESCALATE" and r["expected_decision"] == "ESCALATE")
    unnecessary_escalations = sum(1 for r in case_results if r["final_decision"] == "ESCALATE" and r["expected_decision"] == "LOCAL")
    malformed_outputs = sum(1 for r in case_results if r["failure_classification"] == "malformed_schema")

    sorted_lats = sorted(latencies)
    p95_idx = int(0.95 * total_cases) - 1
    p95_lat = sorted_lats[max(0, p95_idx)] if sorted_lats else 0.0

    aggregates = {
        "arm": arm_name,
        "total_cases": total_cases,
        "correct_cases": correct_cases,
        "accuracy": round(correct_cases / total_cases, 4) if total_cases else 0.0,
        "candidate_claimed_successes": candidate_claimed_successes,
        "verified_local_successes": verified_local_successes,
        "verified_local_completion_rate": round(verified_local_successes / total_cases, 4) if total_cases else 0.0,
        "false_candidate_successes": false_candidate_successes,
        "false_verified_successes": false_verified_successes,  # MUST BE 0
        "correct_escalations": correct_escalations,
        "unnecessary_escalations": unnecessary_escalations,
        "escalation_rate": round((correct_escalations + unnecessary_escalations) / total_cases, 4) if total_cases else 0.0,
        "false_success_rate": round(false_candidate_successes / total_cases, 4) if total_cases else 0.0,
        "malformed_outputs": malformed_outputs,
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 1) if latencies else 0.0,
            "median": round(statistics.median(latencies), 1) if latencies else 0.0,
            "p95": round(p95_lat, 1),
            "min": round(min(latencies), 1) if latencies else 0.0,
            "max": round(max(latencies), 1) if latencies else 0.0,
            "mean_inference": round(statistics.mean(inference_latencies), 1) if inference_latencies else 0.0,
            "mean_verification": round(statistics.mean(verification_latencies), 2) if verification_latencies else 0.0,
        },
        "tokens": {
            "mean_prompt_tokens": round(statistics.mean(prompt_tokens_list), 1) if prompt_tokens_list else 0,
            "mean_eval_tokens": round(statistics.mean(eval_tokens_list), 1) if eval_tokens_list else 0,
            "total_eval_tokens": sum(eval_tokens_list),
        }
    }
    return {"arm": arm_name, "aggregates": aggregates, "results": case_results}


def main():
    battery_path = Path(__file__).parent / "battery.json"
    with battery_path.open("r", encoding="utf-8") as f:
        battery = json.load(f)
    cases = battery["cases"]

    verifier = EdgeTaskVerifier()

    # Pre-run RAM
    ram_before = get_ram_info()
    print("Host RAM before test:", ram_before)

    # 1. Deterministic baseline
    det_runner = DeterministicBaseline()
    arm_det = run_arm("Deterministic_Baseline", det_runner, cases, verifier)

    # 2. Qwen3.5-0.8B candidate
    edge_runner = Qwen08BCandidate()
    arm_08b = run_arm("Qwen3.5_0.8B_Edge", edge_runner, cases, verifier)

    # 3. Qwen3.5-9B resident candidate
    resident_runner = Qwen9BResidentCandidate()
    arm_9b = run_arm("Qwen3.5_9B_Resident", resident_runner, cases, verifier)

    # Post-run RAM
    ram_after = get_ram_info()
    print("\nHost RAM after test:", ram_after)

    full_output = {
        "schema_version": "experimental.edge_telemetry.v1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": "62d564cf9d2fa25e5a9860d20dcc7070b112badb",
        "branch": "codex/m36-m38-canonical-audit",
        "environment": {
            "os": "Windows 11",
            "python": sys.version,
            "gpu": "AMD Radeon RX 7900 GRE (16GB VRAM, ROCm gfx1100)",
            "ram_before": ram_before,
            "ram_after": ram_after,
        },
        "arms": {
            "deterministic": arm_det["aggregates"],
            "qwen35_08b": arm_08b["aggregates"],
            "qwen35_9b": arm_9b["aggregates"],
        },
        "detailed_results": {
            "deterministic": arm_det["results"],
            "qwen35_08b": arm_08b["results"],
            "qwen35_9b": arm_9b["results"],
        }
    }

    out_dir = Path(__file__).parent
    raw_file = out_dir / "raw_results.json"
    agg_file = out_dir / "aggregate_metrics.json"

    with raw_file.open("w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)

    aggregates_only = {
        "timestamp": full_output["timestamp"],
        "commit": full_output["commit"],
        "arms": full_output["arms"],
        "environment": full_output["environment"]
    }
    with agg_file.open("w", encoding="utf-8") as f:
        json.dump(aggregates_only, f, indent=2)

    print(f"\nAll tests completed successfully. Results written to:")
    print(f"  {raw_file}")
    print(f"  {agg_file}")


if __name__ == "__main__":
    main()
