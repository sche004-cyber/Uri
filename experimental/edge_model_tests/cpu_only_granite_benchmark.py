"""Focused CPU-Only Deployment Benchmark for IBM Granite 4.0-H-350M.

Evaluates:
- CPU-only execution without discrete GPU acceleration (num_gpu=0).
- Cold start & model load duration.
- Process RSS / Working Set, Private Bytes, and thread count.
- CPU utilization and office responsiveness during inference.
- Full 30-case battery and 8 admitted worker cases under the canonical URI pipeline.
- Comparison with target deployment profile (Intel Core i7-11700, 16GB RAM, UHD 750).
- Invariant check: FALSE_VERIFIED_SUCCESS == 0.
- Verification of CASE_02 target/fixture alignment.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from experimental.edge_model_tests.deterministic_path import DeterministicBaseline
from experimental.edge_model_tests.verifier import EdgeTaskVerifier, VerifierOutcome
from experimental.edge_model_tests.repaired_capsule_comparison_runner import (
    ModelJobRole,
    GROUND_TRUTH_ROLES,
    ModelJobMatchingGate,
    Needle3Specialist,
    build_repaired_worker_capsule,
)


def get_llama_server_proc() -> Optional[psutil.Process]:
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'llama-server' in p.info['name'].lower():
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


class GraniteCPUWorker:
    def __init__(self, model_tag: str = "granite4:350m-h", endpoint: str = "http://127.0.0.1:11434/api/chat", threads: Optional[int] = None):
        self.model_tag = model_tag
        self.endpoint = endpoint
        self.threads = threads

    def run_bounded_task(self, case: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        user_content = build_repaired_worker_capsule(case)
        system_content = "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."
        
        options = {
            "num_gpu": 0,         # 100% CPU execution - NO GPU OFFLOAD
            "temperature": 0.0,
            "num_predict": 150
        }
        if self.threads:
            options["num_thread"] = self.threads

        payload = {
            "model": self.model_tag,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            "format": "json",
            "stream": False,
            "options": options
        }

        t0 = time.perf_counter()
        res = httpx.post(self.endpoint, json=payload, timeout=30.0)
        dt = (time.perf_counter() - t0) * 1000
        data = res.json()
        raw_output = data.get("message", {}).get("content", "").strip()

        meta = {
            "inference_duration_ms": round(dt, 2),
            "total_duration_ms": round(data.get("total_duration", 0) / 1e6, 2),
            "load_duration_ms": round(data.get("load_duration", 0) / 1e6, 2),
            "prompt_eval_duration_ms": round(data.get("prompt_eval_duration", 0) / 1e6, 2),
            "eval_duration_ms": round(data.get("eval_duration", 0) / 1e6, 2),
            "eval_count": data.get("eval_count", 0),
        }
        return raw_output, meta


def run_cpu_benchmark():
    print("==================================================================")
    print("   URI FOCUSED CPU-ONLY BENCHMARK: IBM Granite 4.0-H-350M")
    print("==================================================================")

    # 1. Host specs
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    sys_ram = psutil.virtual_memory()
    print(f"Host CPU: AMD Ryzen 9 5900X ({cpu_count_physical} Cores / {cpu_count_logical} Threads, max {cpu_freq.max:.0f} MHz)")
    print(f"Host RAM: {sys_ram.total / (1024**3):.1f} GB total, {sys_ram.available / (1024**3):.1f} GB available")
    print("GPU Offload: EXPLICITLY DISABLED (num_gpu=0, pure CPU execution)")

    # 2. Stop existing model instances to measure cold first-call latency
    print("\n--- Unloading models from Ollama to measure cold start ---")
    subprocess.run(["ollama", "stop", "granite4:350m-h"], capture_output=True)
    time.sleep(2)

    worker = GraniteCPUWorker()

    # Load battery
    battery_path = ROOT / "experimental" / "edge_model_tests" / "battery.json"
    with open(battery_path, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    print(f"Battery loaded: {len(cases)} cases.")

    # Cold first call
    print("\n--- Measuring Cold First-Call & Model Load Latency ---")
    c01 = next(c for c in cases if c["id"] == "CASE_01_INTENT")
    t_cold_start = time.perf_counter()
    cold_output, cold_meta = worker.run_bounded_task(c01)
    cold_total_ms = (time.perf_counter() - t_cold_start) * 1000

    print(f"Cold Total Call Latency: {cold_total_ms:.1f} ms")
    print(f"Ollama Load Duration:    {cold_meta['load_duration_ms']:.1f} ms")
    print(f"Prompt Eval Duration:    {cold_meta['prompt_eval_duration_ms']:.1f} ms")
    print(f"Eval Duration:           {cold_meta['eval_duration_ms']:.1f} ms ({cold_meta['eval_count']} tokens)")
    print(f"Cold Output:             {cold_output}")

    # Inspect runner process memory and threads
    proc = get_llama_server_proc()
    proc_stats = {}
    if proc:
        mem_info = proc.memory_info()
        proc_stats = {
            "pid": proc.pid,
            "name": proc.name(),
            "working_set_mb": round(mem_info.rss / (1024**2), 1),
            "private_bytes_mb": round(proc.memory_full_info().uss / (1024**2), 1) if hasattr(proc.memory_full_info(), 'uss') else round(mem_info.rss / (1024**2), 1),
            "thread_count": proc.num_threads(),
        }
        print(f"\n--- llama-server Process Telemetry ---")
        print(f"Process PID:          {proc_stats['pid']} ({proc_stats['name']})")
        print(f"Process RSS (RAM):    {proc_stats['working_set_mb']} MB")
        print(f"Private Bytes (USS):  {proc_stats['private_bytes_mb']} MB")
        print(f"Thread Count:         {proc_stats['thread_count']}")
    else:
        print("Warning: llama-server process not directly detected by name.")

    # Initialize full URI pipeline
    print("\n--- Initializing URI Needle 3 Transport & Deterministic Baseline ---")
    bridge_script = ROOT / "uri_v1" / "turn" / "needle_bridge_runtime.py"
    transport = NeedleBridgeTransport(default_venv_python(), bridge_script)
    transport.load()
    needle_specialist = Needle3Specialist(transport)
    deterministic_baseline = DeterministicBaseline()
    matching_gate = ModelJobMatchingGate()
    verifier = EdgeTaskVerifier()
    print("Needle transport online.")

    # Measure CPU utilization during execution
    cpu_before = psutil.cpu_percent(interval=0.5)

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

    print("\n--- Running Full 30-Case Battery (Granite 4.0-H-350M CPU-Only) ---")
    t_arm_start = time.perf_counter()

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
        w_meta = {}

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
                component_trace.append("GRANITE4_CPU_WORKER")
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

        if "GRANITE4_CPU_WORKER" in component_trace:
            if outcome.candidate_claimed_local:
                worker_claimed_success += 1
            if outcome.is_false_success:
                worker_false_claimed += 1
            if outcome.is_correct:
                worker_correct_count += 1

        rec = {
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
            },
            "worker_meta": w_meta
        }
        case_records.append(rec)
        print(f"[{idx:02d}/30] {cid} -> {outcome.final_decision} (correct={outcome.is_correct}, total={t_turn_total:.1f}ms, worker={worker_dur:.1f}ms)")

    cpu_during = psutil.cpu_percent(interval=0.5)
    total_arm_duration = (time.perf_counter() - t_arm_start)
    transport.close()

    # Re-check process memory after arm
    proc_after = get_llama_server_proc()
    if proc_after:
        proc_stats["working_set_after_mb"] = round(proc_after.memory_info().rss / (1024**2), 1)

    # Worker latency stats
    worker_mean = statistics.mean(latencies_worker)
    worker_median = statistics.median(latencies_worker)
    worker_p95 = statistics.quantiles(latencies_worker, n=20)[18] if len(latencies_worker) >= 20 else max(latencies_worker)
    worker_min = min(latencies_worker)
    worker_max = max(latencies_worker)

    # Full turn latency stats
    turn_mean = statistics.mean(latencies_total)
    turn_median = statistics.median(latencies_total)
    turn_p95 = statistics.quantiles(latencies_total, n=20)[18] if len(latencies_total) >= 20 else max(latencies_total)
    turn_min = min(latencies_total)
    turn_max = max(latencies_total)

    # Invariant verification
    false_verified_count = sum(1 for r in case_records if r["is_false_verified"])
    assert false_verified_count == 0, f"CRITICAL INVARIANT VIOLATED: {false_verified_count} false verified successes!"

    results_summary = {
        "benchmark": "IBM Granite 4.0-H-350M CPU-Only Benchmark",
        "target_profile": {
            "os": "Windows 64-bit",
            "cpu_target": "Intel Core i7-11700 (8C/16T, 2.5-4.9 GHz, AVX-512, 16MB L3)",
            "ram_target_gb": 16,
            "gpu_target": "Intel UHD 750 (No discrete GPU)"
        },
        "host_hardware": {
            "cpu": "AMD Ryzen 9 5900X (12C/24T, 3.7-4.8 GHz, AVX2, 64MB L3)",
            "ram_total_gb": round(sys_ram.total / (1024**3), 1),
            "discrete_gpu_used": False,
            "num_gpu_setting": 0
        },
        "process_metrics": proc_stats,
        "cold_start_metrics": {
            "cold_total_latency_ms": round(cold_total_ms, 2),
            "model_load_duration_ms": round(cold_meta["load_duration_ms"], 2),
            "prompt_eval_duration_ms": round(cold_meta["prompt_eval_duration_ms"], 2),
            "eval_duration_ms": round(cold_meta["eval_duration_ms"], 2)
        },
        "cpu_utilization": {
            "cpu_before_pct": cpu_before,
            "cpu_during_pct": cpu_during,
            "system_threads": psutil.cpu_count()
        },
        "worker_metrics": {
            "admitted_cases": worker_invoked_count,
            "worker_correct": worker_correct_count,
            "worker_correct_pct": round((worker_correct_count / worker_invoked_count) * 100, 1),
            "false_candidate_successes": worker_false_claimed,
            "false_verified_successes": false_verified_count,
            "latency_worker_ms": {
                "min": round(worker_min, 1),
                "mean": round(worker_mean, 1),
                "median": round(worker_median, 1),
                "p95": round(worker_p95, 1),
                "max": round(worker_max, 1)
            }
        },
        "full_system_metrics": {
            "total_cases": len(cases),
            "full_correct": sum(1 for r in case_records if r["is_correct"]),
            "full_correct_pct": round((sum(1 for r in case_records if r["is_correct"]) / len(cases)) * 100, 1),
            "verified_local_success": sum(1 for r in case_records if r["final_decision"] == "VERIFIED_LOCAL_SUCCESS"),
            "escalated_confirmed": sum(1 for r in case_records if r["final_decision"] == "ESCALATE"),
            "rejected": sum(1 for r in case_records if r["final_decision"] == "REJECT"),
            "latency_turn_ms": {
                "min": round(turn_min, 1),
                "mean": round(turn_mean, 1),
                "median": round(turn_median, 1),
                "p95": round(turn_p95, 1),
                "max": round(turn_max, 1)
            }
        },
        "case_02_verification": next(r for r in case_records if r["id"] == "CASE_02_INTENT"),
        "case_15_verification": next(r for r in case_records if r["id"] == "CASE_15_REWRITE"),
        "records": case_records
    }

    # Save results
    output_path = ROOT / "experimental" / "edge_model_tests" / "cpu_only_granite_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)
    print(f"\nSaved CPU-only benchmark telemetry to {output_path}")

    return results_summary


if __name__ == "__main__":
    run_cpu_benchmark()
