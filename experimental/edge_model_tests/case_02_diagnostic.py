"""Diagnostic script for CASE_02 intent extraction bias vs capability test.

Evaluates LFM2.5-350M (LM Studio) and Qwen3.5-0.8B (Ollama) on CASE_02 across 5 schema/presentation variants:
- Variant 1 (Current order): "intent": "EXTRACT"|"CALCULATE" (generic instruction)
- Variant 2 (Reversed order): "intent": "CALCULATE"|"EXTRACT" (generic instruction)
- Variant 3 (Current order + Neutral Definitions): "intent": "EXTRACT"|"CALCULATE" with explicit definitions
- Variant 4 (Reversed order + Neutral Definitions): "intent": "CALCULATE"|"EXTRACT" with explicit definitions
- Variant 5 (Neutral List + Definitions): "intent": string with allowed list and definitions

Tests for:
- Positional / enum ordering bias
- Semantic comprehension under neutral definition presentation
- Consistency across 3 deterministic repeats (temp=0.0)

Terminology note:
Qwen3.5-9B is a resident reference/capable model, not the Main Brain.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experimental.edge_model_tests.verifier import EdgeTaskVerifier

CASE_02 = {
    "id": "CASE_02_INTENT",
    "category": "intent_extraction",
    "prompt": "Calculate total revenue for Q3 from revenue.csv",
    "eligible_intents": ["EXTRACT", "CALCULATE", "COMMUNICATE", "REWRITE", "ESCALATE"],
    "expected_decision": "LOCAL",
    "expected_intent": "CALCULATE",
    "expected_target": "revenue.csv",
    "prohibitions": [],
    "tags": ["intent", "bounded"]
}

VARIANTS = {
    "variant_1_current_order": {
        "name": "Variant 1 (Current Order: EXTRACT | CALCULATE)",
        "schema": '{"decision": "LOCAL", "intent": "EXTRACT"|"CALCULATE", "target": "<filename>"}',
        "inst": "Extract the exact intent and target filename."
    },
    "variant_2_reversed_order": {
        "name": "Variant 2 (Reversed Order: CALCULATE | EXTRACT)",
        "schema": '{"decision": "LOCAL", "intent": "CALCULATE"|"EXTRACT", "target": "<filename>"}',
        "inst": "Extract the exact intent and target filename."
    },
    "variant_3_definitions_current_order": {
        "name": "Variant 3 (Definitions + Current Order: EXTRACT | CALCULATE)",
        "schema": '{"decision": "LOCAL", "intent": "EXTRACT"|"CALCULATE", "target": "<filename>"}',
        "inst": (
            "Identify the exact intent and target filename.\n"
            "Definitions:\n"
            "- EXTRACT: read/select an existing value without deriving a new result\n"
            "- CALCULATE: derive a new numeric result from provided data"
        )
    },
    "variant_4_definitions_reversed_order": {
        "name": "Variant 4 (Definitions + Reversed Order: CALCULATE | EXTRACT)",
        "schema": '{"decision": "LOCAL", "intent": "CALCULATE"|"EXTRACT", "target": "<filename>"}',
        "inst": (
            "Identify the exact intent and target filename.\n"
            "Definitions:\n"
            "- EXTRACT: read/select an existing value without deriving a new result\n"
            "- CALCULATE: derive a new numeric result from provided data"
        )
    },
    "variant_5_neutral_list_definitions": {
        "name": "Variant 5 (Neutral List + Definitions: string schema)",
        "schema": '{"decision": "LOCAL", "intent": string, "target": "<filename>"}',
        "inst": (
            "Identify the target filename and select the exact intent from options: ['CALCULATE', 'EXTRACT'].\n"
            "Definitions:\n"
            "- EXTRACT: read/select an existing value without deriving a new result\n"
            "- CALCULATE: derive a new numeric result from provided data"
        )
    }
}

REPEATS = 3


def query_lfm(user_content: str) -> Tuple[str, float]:
    system_content = "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."
    payload = {
        "model": "lfm2.5-350m",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.0,
        "max_tokens": 150
    }
    t0 = time.perf_counter()
    res = httpx.post("http://127.0.0.1:1234/v1/chat/completions", json=payload, timeout=20.0)
    dur = (time.perf_counter() - t0) * 1000
    data = res.json()
    choices = data.get("choices", [])
    raw_output = choices[0]["message"]["content"].strip() if choices else ""
    return raw_output, round(dur, 2)


def query_qwen(user_content: str) -> Tuple[str, float]:
    system_content = "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."
    full_prompt = (
        f"<|im_start|>system\n{system_content}\n<|im_end|>\n"
        f"<|im_start|>user\n{user_content}\n<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n</think>\n"
    )
    payload = {
        "model": "qwen3.5:0.8b",
        "prompt": full_prompt,
        "format": "json",
        "raw": True,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 150
        }
    }
    t0 = time.perf_counter()
    res = httpx.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=20.0)
    dur = (time.perf_counter() - t0) * 1000
    data = res.json()
    raw_output = data.get("response", "").strip()
    return raw_output, round(dur, 2)


def parse_intent(raw: str) -> str:
    clean = raw.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    try:
        data = json.loads(clean.strip())
        val = data.get("intent", "UNKNOWN")
        return str(val).upper()
    except Exception:
        return "PARSE_ERROR"


def run_diagnostic():
    print("=" * 70)
    print("FOCUSED DIAGNOSTIC: CASE_02 INTENT EXTRACTION BIAS VS CAPABILITY")
    print(f"Task: '{CASE_02['prompt']}'")
    print(f"Expected Intent: '{CASE_02['expected_intent']}' | Target: '{CASE_02['expected_target']}'")
    print("=" * 70)

    verifier = EdgeTaskVerifier()
    results: Dict[str, Any] = {
        "metadata": {
            "task": CASE_02["prompt"],
            "expected_intent": CASE_02["expected_intent"],
            "expected_target": CASE_02["expected_target"],
            "repeats": REPEATS,
            "terminology_note": "Qwen3.5-9B is a resident reference/capable model, not the Main Brain."
        },
        "workers": {
            "lfm25_350m": {},
            "qwen35_08b": {}
        }
    }

    workers = [
        ("lfm25_350m", "LFM2.5-350M (LM Studio Q8_0)", query_lfm),
        ("qwen35_08b", "Qwen3.5-0.8B (Ollama Q8_0)", query_qwen)
    ]

    for worker_key, worker_name, query_fn in workers:
        print(f"\n--- Testing Worker: {worker_name} ---")
        worker_summary = {}

        for vkey, vdef in VARIANTS.items():
            print(f"\n  [{vdef['name']}]")
            user_content = f"Task: {CASE_02['prompt']}\nInstruction: {vdef['inst']}\nSchema: {vdef['schema']}\nReturn ONLY valid JSON."

            runs = []
            latencies = []
            intents = []
            verifier_outcomes = []

            for r in range(1, REPEATS + 1):
                raw_out, dur = query_fn(user_content)
                outcome = verifier.verify(CASE_02, raw_out)
                intent = parse_intent(raw_out)

                runs.append({
                    "run": r,
                    "raw_output": raw_out,
                    "extracted_intent": intent,
                    "verifier_status": outcome.verifier_status,
                    "final_decision": outcome.final_decision,
                    "is_correct": outcome.is_correct,
                    "failure_reason": outcome.failure_reason,
                    "latency_ms": dur
                })
                latencies.append(dur)
                intents.append(intent)
                verifier_outcomes.append(outcome.final_decision)

            mean_lat = round(statistics.mean(latencies), 1)
            p95_lat = round(max(latencies), 1)
            consistent_intent = intents[0] if all(i == intents[0] for i in intents) else "INCONSISTENT"
            all_correct = all(run["is_correct"] for run in runs)

            print(f"    Intent: {consistent_intent:10s} | Verifier: {verifier_outcomes[0]:22s} | Mean Latency: {mean_lat}ms")

            worker_summary[vkey] = {
                "variant_name": vdef["name"],
                "schema_used": vdef["schema"],
                "instruction_used": vdef["inst"],
                "consistent_intent": consistent_intent,
                "is_correct": all_correct,
                "mean_latency_ms": mean_lat,
                "p95_latency_ms": p95_lat,
                "runs": runs
            }

        results["workers"][worker_key] = worker_summary

    # Save artifact
    out_path = ROOT / "experimental" / "edge_model_tests" / "case_02_diagnostic_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved diagnostic raw results to: {out_path}")

    return results


if __name__ == "__main__":
    run_diagnostic()
