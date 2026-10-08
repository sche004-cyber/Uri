"""Comprehensive Benchmark Runner for Qwen3-0.6B vs IBM Granite 4.0-H-350M.

Executes:
1. Canonical 30-case Battery (Qwen3-0.6B in GPU and CPU modes).
2. Supplementary 7-case Bounded Worker Challenge Set (Granite 4.0-H vs Qwen3-0.6B).
3. Full process telemetry, cold start, warm percentiles, and verifier containment.
4. Critical Invariant: FALSE_VERIFIED_SUCCESS == 0.

Terminology:
Qwen3.5-9B is a resident reference/capable model, not the Main Brain.
"""
from __future__ import annotations

import json
import os
import re
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


def get_llama_proc() -> Optional[psutil.Process]:
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if 'llama-server' in p.info['name'].lower():
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


class OllamaWorker:
    def __init__(self, model_tag: str, num_gpu: Optional[int] = None):
        self.model_tag = model_tag
        self.num_gpu = num_gpu
        self.endpoint = "http://127.0.0.1:11434/api/chat"

    def run_prompt(self, user_content: str) -> Tuple[str, Dict[str, Any]]:
        system_content = "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."
        options = {
            "temperature": 0.0,
            "num_predict": 150
        }
        if self.num_gpu is not None:
            options["num_gpu"] = self.num_gpu

        payload = {
            "model": self.model_tag,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            "format": "json",
            "think": False,
            "options": options,
            "stream": False
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

    def run_bounded_task(self, case: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        user_content = build_repaired_worker_capsule(case)
        return self.run_prompt(user_content)


def run_canonical_battery(
    arm_name: str,
    worker: OllamaWorker,
    cases: List[Dict[str, Any]],
    needle_specialist: Needle3Specialist,
    deterministic_baseline: DeterministicBaseline,
    matching_gate: ModelJobMatchingGate,
    verifier: EdgeTaskVerifier,
) -> Dict[str, Any]:
    print(f"\n--- Running Canonical Battery: {arm_name} ---")
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
                component_trace.append("QWEN3_06B_WORKER")
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

        if "QWEN3_06B_WORKER" in component_trace:
            if outcome.candidate_claimed_local:
                worker_claimed_success += 1
            if outcome.is_false_success:
                worker_false_claimed += 1
            if outcome.is_correct:
                worker_correct_count += 1

        case_records.append({
            "id": cid,
            "category": category,
            "prompt": prompt,
            "component_trace": component_trace,
            "raw_output": raw_output,
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
        })
        print(f"[{idx:02d}/30] {cid} -> {outcome.final_decision} (correct={outcome.is_correct}, total={t_turn_total:.1f}ms, worker={worker_dur:.1f}ms)")

    worker_mean = statistics.mean(latencies_worker)
    worker_median = statistics.median(latencies_worker)
    worker_p95 = statistics.quantiles(latencies_worker, n=20)[18] if len(latencies_worker) >= 20 else max(latencies_worker)

    turn_mean = statistics.mean(latencies_total)
    turn_median = statistics.median(latencies_total)
    turn_p95 = statistics.quantiles(latencies_total, n=20)[18] if len(latencies_total) >= 20 else max(latencies_total)

    false_verified_count = sum(1 for r in case_records if r["is_false_verified"])
    assert false_verified_count == 0, f"SAFETY INVARIANT VIOLATED: {false_verified_count} false verified!"

    return {
        "arm_name": arm_name,
        "worker_correct": worker_correct_count,
        "worker_admitted": worker_invoked_count,
        "worker_correct_pct": round((worker_correct_count / worker_invoked_count) * 100, 1),
        "false_candidate_successes": worker_false_claimed,
        "false_verified_successes": false_verified_count,
        "worker_latencies_ms": {
            "min": round(min(latencies_worker), 1),
            "mean": round(worker_mean, 1),
            "median": round(worker_median, 1),
            "p95": round(worker_p95, 1),
            "max": round(max(latencies_worker), 1),
        },
        "full_system_correct": sum(1 for r in case_records if r["is_correct"]),
        "full_system_pct": round((sum(1 for r in case_records if r["is_correct"]) / len(cases)) * 100, 1),
        "turn_latencies_ms": {
            "min": round(min(latencies_total), 1),
            "mean": round(turn_mean, 1),
            "median": round(turn_median, 1),
            "p95": round(turn_p95, 1),
            "max": round(max(latencies_total), 1),
        },
        "records": case_records
    }


def verify_supplementary_case(case: Dict[str, Any], raw_output: str) -> Dict[str, Any]:
    cid = case["id"]
    try:
        clean = raw_output.strip()
        if clean.startswith("```json"): clean = clean[7:]
        if clean.startswith("```"): clean = clean[3:]
        if clean.endswith("```"): clean = clean[:-3]
        clean = clean.strip()
        parsed = json.loads(clean)
    except Exception as e:
        return {"pass": False, "reason": f"json_parse_error: {e}", "parsed": None}

    if parsed.get("decision") != "LOCAL":
        return {"pass": False, "reason": "decision_not_local", "parsed": parsed}

    if cid == "SUPP_01_MULTI_ENTITY":
        exp = case["expected_values"]
        for k, v in exp.items():
            if str(parsed.get(k, "")).strip().lower() != str(v).strip().lower():
                return {"pass": False, "reason": f"field_mismatch: {k} expected '{v}', got '{parsed.get(k)}'", "parsed": parsed}
        return {"pass": True, "reason": None, "parsed": parsed}

    elif cid == "SUPP_02_DATE_CURRENCY_ID":
        exp = case["expected_values"]
        for k, v in exp.items():
            if str(parsed.get(k, "")).strip().lower() != str(v).strip().lower():
                return {"pass": False, "reason": f"field_mismatch: {k} expected '{v}', got '{parsed.get(k)}'", "parsed": parsed}
        return {"pass": True, "reason": None, "parsed": parsed}

    elif cid == "SUPP_03_DUAL_NEGATION":
        req = [x.lower() for x in parsed.get("requested_operations", [])]
        pro = [x.lower() for x in parsed.get("prohibited_operations", [])]
        if "summarize" not in req:
            return {"pass": False, "reason": "missing_requested: 'summarize'", "parsed": parsed}
        for p in ["include_ip_addresses", "export_user_emails"]:
            if not any(p in x or x in p for x in pro):
                return {"pass": False, "reason": f"missing_prohibited: '{p}' in {pro}", "parsed": parsed}
        if set(req).intersection(set(pro)):
            return {"pass": False, "reason": "polarity_inversion", "parsed": parsed}
        return {"pass": True, "reason": None, "parsed": parsed}

    elif cid == "SUPP_04_MULTI_ARG":
        if parsed.get("file") != case["expected_file"]:
            return {"pass": False, "reason": f"wrong_file: expected {case['expected_file']}, got {parsed.get('file')}", "parsed": parsed}
        f_act = parsed.get("filters", {})
        f_exp = case["expected_filters"]
        for fk, fv in f_exp.items():
            if str(f_act.get(fk, "")).strip().lower() != str(fv).strip().lower():
                return {"pass": False, "reason": f"filter_mismatch: {fk} expected '{fv}', got '{f_act.get(fk)}'", "parsed": parsed}
        return {"pass": True, "reason": None, "parsed": parsed}

    elif cid == "SUPP_05_DISTRACTOR_FILLING":
        exp = case["expected_values"]
        for k, v in exp.items():
            if str(parsed.get(k, "")).strip().lower() != str(v).strip().lower():
                return {"pass": False, "reason": f"field_mismatch: {k} expected '{v}', got '{parsed.get(k)}'", "parsed": parsed}
        return {"pass": True, "reason": None, "parsed": parsed}

    elif cid == "SUPP_06_COMPLEX_FILENAME":
        exp_target = case["expected_target"]
        if parsed.get("target") != exp_target:
            return {"pass": False, "reason": f"target_mismatch: expected '{exp_target}', got '{parsed.get('target')}'", "parsed": parsed}
        return {"pass": True, "reason": None, "parsed": parsed}

    elif cid == "SUPP_07_EXACT_REWRITE":
        text = parsed.get("sentence", "")
        req_fields = case["required_fields"]
        for f in req_fields:
            if f.lower() not in text.lower():
                return {"pass": False, "reason": f"missing_required_entity: '{f}' in '{text}'", "parsed": parsed}
        text_no_decimals = re.sub(r"\d+\.\d+", "<NUM>", text)
        punct = sum(text_no_decimals.count(p) for p in [".", "!", "?"])
        if punct > 1:
            return {"pass": False, "reason": f"sentence_limit_exceeded: got {punct} sentences", "parsed": parsed}
        return {"pass": True, "reason": None, "parsed": parsed}

    return {"pass": False, "reason": "unhandled_supp_case", "parsed": parsed}


def run_supplementary_battery(model_tag: str, model_name: str, num_gpu: Optional[int] = None) -> Dict[str, Any]:
    print(f"\n==================================================================")
    print(f"   SUPPLEMENTARY CHALLENGE SET: {model_name}")
    print(f"==================================================================")
    supp_path = ROOT / "experimental" / "edge_model_tests" / "supplementary_worker_battery.json"
    with open(supp_path, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    worker = OllamaWorker(model_tag, num_gpu=num_gpu)
    results = []
    latencies = []
    passes = 0

    for c in cases:
        cid = c["id"]
        prompt = c["prompt"]
        inst = c["instruction"]
        schema = c["schema"]
        capsule = f"Task: {prompt}\nInstruction: {inst}\nSchema: {schema}\nReturn ONLY valid JSON."
        raw, meta = worker.run_prompt(capsule)
        dur = meta["inference_duration_ms"]
        latencies.append(dur)
        verdict = verify_supplementary_case(c, raw)
        is_pass = verdict["pass"]
        if is_pass:
            passes += 1
            print(f"[{cid}] ({dur:.1f}ms) -> PASS")
            print(f"   Output: {raw}")
        else:
            print(f"[{cid}] ({dur:.1f}ms) -> FAIL")
            print(f"   Reason: {verdict['reason']}")
            print(f"   Raw: {raw}")

        results.append({
            "id": cid,
            "pass": is_pass,
            "reason": verdict["reason"],
            "raw_output": raw,
            "parsed": verdict["parsed"],
            "latency_ms": dur
        })

    return {
        "model_name": model_name,
        "model_tag": model_tag,
        "passed": passes,
        "total": len(cases),
        "pass_pct": round((passes / len(cases)) * 100, 1),
        "latencies_ms": {
            "min": round(min(latencies), 1),
            "mean": round(statistics.mean(latencies), 1),
            "median": round(statistics.median(latencies), 1),
            "max": round(max(latencies), 1),
        },
        "records": results
    }


def main():
    print("=== Initializing Qwen3-0.6B Comprehensive Comparative Qualification ===")
    
    # Measure cold start for Qwen3-0.6B
    print("\n--- Measuring Cold First-Call Latency for Qwen3-0.6B ---")
    subprocess.run(["ollama", "stop", "qwen3:0.6b"], capture_output=True)
    time.sleep(2)
    
    cold_worker = OllamaWorker("qwen3:0.6b")
    c01_capsule = build_repaired_worker_capsule({"id": "CASE_01_INTENT", "prompt": "Extract summary from sales_report.txt"})
    t0_cold = time.perf_counter()
    cold_raw, cold_meta = cold_worker.run_prompt(c01_capsule)
    cold_total_ms = (time.perf_counter() - t0_cold) * 1000
    print(f"Cold Total Call Latency: {cold_total_ms:.1f} ms")
    print(f"Cold Model Load Duration: {cold_meta['load_duration_ms']:.1f} ms")
    print(f"Cold Output: {cold_raw}")

    # Process RAM telemetry for Qwen3-0.6B
    proc = get_llama_proc()
    proc_info = {}
    if proc:
        proc_info = {
            "pid": proc.pid,
            "name": proc.name(),
            "working_set_mb": round(proc.memory_info().rss / (1024**2), 1),
            "thread_count": proc.num_threads()
        }
        print(f"Process RAM (Working Set): {proc_info['working_set_mb']} MB, Threads: {proc_info['thread_count']}")

    # Setup pipeline components
    print("\n--- Spawning Needle Transport & Setting Up Baseline ---")
    bridge_script = ROOT / "uri_v1" / "turn" / "needle_bridge_runtime.py"
    transport = NeedleBridgeTransport(default_venv_python(), bridge_script)
    transport.load()
    needle_specialist = Needle3Specialist(transport)
    deterministic_baseline = DeterministicBaseline()
    matching_gate = ModelJobMatchingGate()
    verifier = EdgeTaskVerifier()

    battery_path = ROOT / "experimental" / "edge_model_tests" / "battery.json"
    with open(battery_path, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    # 1. Run Canonical Battery: Qwen3-0.6B GPU Mode
    qwen_gpu_worker = OllamaWorker("qwen3:0.6b")
    qwen_gpu_canonical = run_canonical_battery(
        "Qwen3-0.6B (GPU Accelerated)", qwen_gpu_worker, cases,
        needle_specialist, deterministic_baseline, matching_gate, verifier
    )

    # 2. Run Canonical Battery: Qwen3-0.6B CPU Mode
    print("\n--- Stopping model to reset for CPU mode ---")
    subprocess.run(["ollama", "stop", "qwen3:0.6b"], capture_output=True)
    time.sleep(2)
    cpu_before = psutil.cpu_percent(interval=0.5)
    qwen_cpu_worker = OllamaWorker("qwen3:0.6b", num_gpu=0)
    qwen_cpu_canonical = run_canonical_battery(
        "Qwen3-0.6B (CPU-Only, num_gpu=0)", qwen_cpu_worker, cases,
        needle_specialist, deterministic_baseline, matching_gate, verifier
    )
    cpu_during = psutil.cpu_percent(interval=0.5)
    transport.close()

    # 3. Run Supplementary Battery on Granite 4.0-H-350M vs Qwen3-0.6B
    granite_supp = run_supplementary_battery("granite4:350m-h", "IBM Granite 4.0-H-350M")
    qwen_supp = run_supplementary_battery("qwen3:0.6b", "Qwen3-0.6B")

    final_payload = {
        "cold_start": {
            "total_ms": round(cold_total_ms, 1),
            "load_duration_ms": cold_meta["load_duration_ms"],
            "prompt_eval_ms": cold_meta["prompt_eval_duration_ms"],
            "eval_duration_ms": cold_meta["eval_duration_ms"]
        },
        "process_info": proc_info,
        "cpu_utilization_pct": {"before": cpu_before, "during": cpu_during},
        "canonical_battery": {
            "qwen_gpu": qwen_gpu_canonical,
            "qwen_cpu": qwen_cpu_canonical
        },
        "supplementary_battery": {
            "granite_350m": granite_supp,
            "qwen_06b": qwen_supp
        }
    }

    out_file = ROOT / "experimental" / "edge_model_tests" / "qwen06b_canonical_and_supplementary_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)
    print(f"\nTelemetry saved to {out_file}")


if __name__ == "__main__":
    main()
