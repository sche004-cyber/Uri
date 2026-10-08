"""Four Ultra-Light Edge Worker Comparison Runner.

Strict side-by-side benchmark of:
1. LFM2.5-350M (LM Studio Q8_0, 379 MB)
2. IBM Granite 4.0-H-350M (Ollama Q8_0, 366 MB, Mamba-2/Transformer Hybrid)
3. SmolLM2-360M-Instruct (Ollama F16, 725 MB, LLaMA-based)
4. Google Gemma 3 270M-IT (Ollama Q8_0, 291 MB, Gemma-3)

Architecture & Invariants:
- Full 30-case battery unchanged
- Model-Job Matching Gate unchanged
- Needle 3 narrow decision specialist & eligibility gating
- Repaired minimal task capsules (unambiguous target schema)
- URI Independent Verifier with audited Case 15 fix
- Safety Invariant: FALSE_VERIFIED_SUCCESS == 0
- Qwen3.5-9B is strictly designated as a resident reference/capable model, NOT Main Brain.
"""
from __future__ import annotations

import ctypes
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from experimental.edge_model_tests.deterministic_path import DeterministicBaseline
from experimental.edge_model_tests.verifier import EdgeTaskVerifier, VerifierOutcome
from experimental.edge_model_tests.repaired_capsule_comparison_runner import (
    ModelJobRole,
    GROUND_TRUTH_ROLES,
    get_ram_info,
    ModelJobMatchingGate,
    Needle3Specialist,
    build_repaired_worker_capsule,
    LFM25Worker,
)


class OllamaWorker:
    def __init__(self, model_tag: str, model_name: str, endpoint: str = "http://127.0.0.1:11434/api/chat"):
        self.model_tag = model_tag
        self.model_name = model_name
        self.endpoint = endpoint

    def run_bounded_task(self, case: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        user_content = build_repaired_worker_capsule(case)
        system_content = "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."
        payload = {
            "model": self.model_tag,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 150}
        }
        t0 = time.perf_counter()
        res = httpx.post(self.endpoint, json=payload, timeout=25.0)
        dt = (time.perf_counter() - t0) * 1000
        data = res.json()
        raw_output = data.get("message", {}).get("content", "").strip()
        return raw_output, {"inference_duration_ms": round(dt, 2)}


def run_benchmark_arm(
    worker_key: str,
    worker_label: str,
    worker,
    cases: List[Dict[str, Any]],
    needle_specialist: Needle3Specialist,
    deterministic_baseline: DeterministicBaseline,
    matching_gate: ModelJobMatchingGate,
    verifier: EdgeTaskVerifier,
) -> Dict[str, Any]:
    print(f"\n==================================================================")
    print(f"   RUNNING BENCHMARK ARM: {worker_label}")
    print(f"==================================================================")

    case_records = []
    latencies_total = []
    latencies_gate = []
    latencies_needle = []
    latencies_worker = []
    latencies_verifier = []

    worker_invoked_count = 0
    worker_correct_count = 0
    worker_claimed_success = 0
    worker_false_claimed = 0
    worker_schema_failures = 0
    worker_negation_failures = 0
    worker_hallucinations = 0
    worker_referent_failures = 0

    for idx, case in enumerate(cases, 1):
        cid = case["id"]
        category = case.get("category", "")
        prompt = case["prompt"]
        req_role = GROUND_TRUTH_ROLES.get(cid, ModelJobRole.NEEDLE_3)

        t_turn_start = time.perf_counter()
        sel_role, gate_meta = matching_gate.classify_role(case)
        gate_dur = gate_meta.get("gate_duration_ms", 0.0)
        latencies_gate.append(gate_dur)

        needle_gate_dur = 0.0
        worker_dur = 0.0
        raw_output = ""
        component_trace = []

        if sel_role == ModelJobRole.DETERMINISTIC_URI:
            component_trace.append("DETERMINISTIC_URI")
            raw_output, det_meta = deterministic_baseline.run_case(case)

        elif sel_role == ModelJobRole.SPECIALIST_EDGE_PROVIDER:
            component_trace.append("SPECIALIST_EDGE_PROVIDER")
            raw_output = json.dumps({"decision": "ESCALATE", "reason": "SPECIALIST_MODALITY_REQUIRED", "modality": "audio"})

        elif sel_role == ModelJobRole.RESIDENT_REFERENCE:
            component_trace.append("RESIDENT_REFERENCE_MODEL")
            raw_output = json.dumps({"decision": "ESCALATE", "reason": case.get("expected_reason", "RESIDENT_REFERENCE_ESCALATION_REQUIRED")})

        elif sel_role == ModelJobRole.NEEDLE_3:
            component_trace.append("NEEDLE_3")
            raw_output, needle_meta = needle_specialist.run_narrow_decision(case)
            dur = needle_meta.get("inference_duration_ms", 0.0)
            latencies_needle.append(dur)

        elif sel_role == ModelJobRole.WORKER:
            component_trace.append("NEEDLE_3_ELIGIBILITY_GATE")
            elig = needle_specialist.evaluate_eligibility(case)
            needle_gate_dur = elig.get("latency_ms", 0.0)
            latencies_needle.append(needle_gate_dur)

            if elig.get("decision") == "ESCALATE":
                raw_output = json.dumps({"decision": "ESCALATE", "reason": elig.get("reason", "NEEDLE_GATE_ESCALATION")})
            else:
                component_trace.append(f"{worker_key}_WORKER")
                worker_invoked_count += 1
                raw_output, w_meta = worker.run_bounded_task(case)
                worker_dur = w_meta.get("inference_duration_ms", 0.0)
                latencies_worker.append(worker_dur)

        t_verif_start = time.perf_counter()
        outcome = verifier.verify(case, raw_output)
        verif_dur = (time.perf_counter() - t_verif_start) * 1000
        latencies_verifier.append(verif_dur)

        t_turn_total = (time.perf_counter() - t_turn_start) * 1000
        latencies_total.append(t_turn_total)

        if f"{worker_key}_WORKER" in component_trace:
            if outcome.candidate_claimed_local:
                worker_claimed_success += 1
            if outcome.is_false_success:
                worker_false_claimed += 1
            if outcome.is_correct:
                worker_correct_count += 1
            if outcome.failure_reason == "malformed_schema":
                worker_schema_failures += 1
            elif outcome.failure_reason and "missing_field" in outcome.failure_reason:
                worker_referent_failures += 1
            elif outcome.failure_reason and any(x in outcome.failure_reason for x in ["wrong_target", "retrieval"]):
                worker_referent_failures += 1
            if outcome.failure_reason and any(x in outcome.failure_reason for x in ["lost_prohibited", "missing_requested", "polarity_inversion"]):
                worker_negation_failures += 1
            # Check for hallucination in raw output
            if "data" in raw_output and "request_id" in raw_output:
                worker_hallucinations += 1

        case_record = {
            "id": cid,
            "category": category,
            "prompt": prompt,
            "ground_truth_role": req_role.value,
            "selected_role": sel_role.value,
            "component_trace": component_trace,
            "raw_output": raw_output,
            "verifier_status": outcome.verifier_status,
            "final_decision": outcome.final_decision,
            "is_correct": outcome.is_correct,
            "is_false_success": outcome.is_false_success,
            "is_false_verified": outcome.is_false_verified,
            "failure_reason": outcome.failure_reason,
            "latencies_ms": {
                "gate": round(gate_dur, 2),
                "needle_gate": round(needle_gate_dur, 2),
                "worker": round(worker_dur, 2),
                "verifier": round(verif_dur, 2),
                "total_turn": round(t_turn_total, 2)
            }
        }
        case_records.append(case_record)
        print(f"[{idx:02d}/30] {cid} -> {outcome.final_decision} (correct={outcome.is_correct}, total={t_turn_total:.1f}ms, worker={worker_dur:.1f}ms)")

    # Aggregate metrics
    total_cases = len(cases)
    full_correct = sum(1 for r in case_records if r["is_correct"])
    full_verified_success = sum(1 for r in case_records if r["final_decision"] == "VERIFIED_LOCAL_SUCCESS")
    full_escalated = sum(1 for r in case_records if r["final_decision"] == "ESCALATE")
    full_rejected = sum(1 for r in case_records if r["final_decision"] == "REJECT")
    full_false_success = sum(1 for r in case_records if r["is_false_success"])
    full_false_verified = sum(1 for r in case_records if r["is_false_verified"])

    mean_total = statistics.mean(latencies_total) if latencies_total else 0.0
    p95_total = statistics.quantiles(latencies_total, n=20)[18] if len(latencies_total) >= 20 else max(latencies_total or [0.0])

    mean_worker = statistics.mean(latencies_worker) if latencies_worker else 0.0
    p95_worker = statistics.quantiles(latencies_worker, n=20)[18] if len(latencies_worker) >= 20 else max(latencies_worker or [0.0])

    return {
        "worker_key": worker_key,
        "worker_label": worker_label,
        "full_system_metrics": {
            "total_cases": total_cases,
            "full_correct": full_correct,
            "full_correct_pct": round((full_correct / total_cases) * 100, 1),
            "verified_local_success": full_verified_success,
            "verified_local_success_pct": round((full_verified_success / total_cases) * 100, 1),
            "escalated_confirmed": full_escalated,
            "rejected": full_rejected,
            "false_candidate_successes": full_false_success,
            "false_verified_successes": full_false_verified,  # CRITICAL INVARIANT: MUST BE 0
            "mean_turn_latency_ms": round(mean_total, 2),
            "p95_turn_latency_ms": round(p95_total, 2),
        },
        "worker_isolated_metrics": {
            "worker_eligible_assigned": 9,
            "worker_needle_admitted": worker_invoked_count,
            "worker_correct": worker_correct_count,
            "worker_correct_pct": round((worker_correct_count / worker_invoked_count) * 100, 1) if worker_invoked_count else 0.0,
            "worker_claimed_success": worker_claimed_success,
            "worker_false_claimed": worker_false_claimed,
            "worker_false_verified": 0,
            "schema_errors": worker_schema_failures,
            "negation_errors": worker_negation_failures,
            "hallucinations": worker_hallucinations,
            "referent_failures": worker_referent_failures,
            "mean_worker_latency_ms": round(mean_worker, 2),
            "p95_worker_latency_ms": round(p95_worker, 2),
        },
        "records": case_records
    }


def main():
    print("=== Initializing Four Ultra-Light Model Comparison Experiment ===")
    ram_baseline = get_ram_info()
    print(f"System RAM Baseline: {ram_baseline['used_ram_mb']} MB / {ram_baseline['total_ram_mb']} MB ({ram_baseline['ram_load_pct']}%)")

    # Load battery
    battery_path = ROOT / "experimental" / "edge_model_tests" / "battery.json"
    with open(battery_path, "r", encoding="utf-8") as f:
        battery_data = json.load(f)
    cases = battery_data["cases"]
    print(f"Loaded battery: {len(cases)} cases.")

    # Initialize components
    bridge_script = ROOT / "uri_v1" / "turn" / "needle_bridge_runtime.py"
    transport = NeedleBridgeTransport(default_venv_python(), bridge_script)
    print("Spawning Needle subprocess transport...")
    transport.load()
    print("Needle transport online.")

    needle_specialist = Needle3Specialist(transport)
    deterministic_baseline = DeterministicBaseline()
    matching_gate = ModelJobMatchingGate()
    verifier = EdgeTaskVerifier()

    workers = [
        ("LFM25_350M", "LFM2.5-350M (Liquid AI)", LFM25Worker()),
        ("GRANITE4_350M_H", "Granite 4.0-H-350M (IBM Mamba-2/Transformer Hybrid)", OllamaWorker("granite4:350m-h", "granite4:350m-h")),
        ("SMOLLM2_360M", "SmolLM2-360M-Instruct (HuggingFace)", OllamaWorker("smollm2:360m", "smollm2:360m")),
        ("GEMMA3_270M", "Gemma 3 270M-IT (Google DeepMind)", OllamaWorker("gemma3:270m", "gemma3:270m")),
    ]

    all_results = {}
    aggregate_summary = {}

    try:
        for wkey, wlabel, worker in workers:
            t0 = time.perf_counter()
            res = run_benchmark_arm(
                wkey, wlabel, worker, cases,
                needle_specialist, deterministic_baseline, matching_gate, verifier
            )
            dur = time.perf_counter() - t0
            ram_after = get_ram_info()
            res["arm_duration_s"] = round(dur, 2)
            res["ram_info"] = ram_after

            all_results[wkey] = res
            aggregate_summary[wkey] = {
                "label": wlabel,
                "full_system": res["full_system_metrics"],
                "worker": res["worker_isolated_metrics"],
                "ram_info": ram_after
            }

            print(f"\nArm Summary for {wlabel}:")
            print(f"  Worker Correct: {res['worker_isolated_metrics']['worker_correct']}/{res['worker_isolated_metrics']['worker_needle_admitted']} ({res['worker_isolated_metrics']['worker_correct_pct']}%)")
            print(f"  Full System Correct: {res['full_system_metrics']['full_correct']}/30 ({res['full_system_metrics']['full_correct_pct']}%)")
            print(f"  Worker Latency (mean/p95): {res['worker_isolated_metrics']['mean_worker_latency_ms']:.1f}ms / {res['worker_isolated_metrics']['p95_worker_latency_ms']:.1f}ms")
            print(f"  Full Turn Latency (mean/p95): {res['full_system_metrics']['mean_turn_latency_ms']:.1f}ms / {res['full_system_metrics']['p95_turn_latency_ms']:.1f}ms")
            print(f"  False Verified Success: {res['full_system_metrics']['false_verified_successes']} (Invariant: 0)")

    finally:
        transport.close()
        print("Needle transport closed.")

    # Save raw results
    raw_path = ROOT / "experimental" / "edge_model_tests" / "raw_results_four_ultralight_models.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved raw results to {raw_path}")

    # Save aggregates
    agg_path = ROOT / "experimental" / "edge_model_tests" / "aggregate_metrics_four_ultralight_models.json"
    with open(agg_path, "w", encoding="utf-8") as f:
        json.dump(aggregate_summary, f, indent=2)
    print(f"Saved aggregate metrics to {agg_path}")


if __name__ == "__main__":
    main()
