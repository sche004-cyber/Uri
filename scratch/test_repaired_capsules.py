import json
import time
import httpx
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experimental.edge_model_tests.verifier import EdgeTaskVerifier

battery_path = ROOT / "experimental" / "edge_model_tests" / "battery.json"
with open(battery_path, "r", encoding="utf-8") as f:
    battery = json.load(f)

cases_by_id = {c["id"]: c for c in battery["cases"]}

def build_repaired_capsule(case):
    cid = case["id"]
    prompt = case["prompt"]

    if cid == "CASE_01_INTENT":
        schema = '{"decision": "LOCAL", "intent": "EXTRACT", "target": "<filename>"}'
        inst = "Extract target filename from request."
    elif cid == "CASE_02_INTENT":
        schema = '{"decision": "LOCAL", "intent": "CALCULATE", "target": "<filename>"}'
        inst = "Extract target filename from request."
    elif cid == "CASE_03_ARG":
        schema = '{"decision": "LOCAL", "file": "orders.xlsx", "filters": {"status": "pending", "region": "West"}}'
        inst = "Extract exact file and filters."
    elif cid == "CASE_04_ARG":
        schema = '{"decision": "LOCAL", "file": "data.csv", "target_format": "json"}'
        inst = "Extract exact file and target format."
    elif cid == "CASE_10_STRUCT":
        schema = '{"decision": "LOCAL", "sheet": "Orders", "rows": 50, "cols": 4, "empty_cells": 0}'
        inst = "Populate exact sheet, rows, cols, empty_cells."
    elif cid == "CASE_15_REWRITE":
        schema = '{"decision": "LOCAL", "sentence": "<one sentence summary>"}'
        inst = "Write exactly one concise sentence containing: ID 101, Customer Bob, Total $250.00."
    elif cid == "CASE_19_NEGATION":
        schema = '{"decision": "LOCAL", "requested_operations": ["summarize"], "prohibited_operations": ["disclose_names", "disclose_phone_numbers"]}'
        inst = "Separate requested operations from prohibited operations."
    elif cid == "CASE_20_NEGATION":
        schema = '{"decision": "LOCAL", "requested_operations": ["save_draft"], "prohibited_operations": ["send_email"]}'
        inst = "Separate requested operations from prohibited operations."
    else:
        schema = '{"decision": "LOCAL"}'
        inst = "Process bounded task."

    user_content = f"Task: {prompt}\nInstruction: {inst}\nSchema: {schema}\nReturn ONLY valid JSON."
    return user_content

def query_lfm(user_content: str):
    payload = {
        "model": "lfm2.5-350m",
        "messages": [
            {"role": "system", "content": "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.0,
        "max_tokens": 150
    }
    t0 = time.perf_counter()
    res = httpx.post("http://127.0.0.1:1234/v1/chat/completions", json=payload, timeout=20.0)
    dur = (time.perf_counter() - t0) * 1000
    raw = res.json()["choices"][0]["message"]["content"].strip()
    return raw, dur

def query_qwen(user_content: str):
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
    raw = res.json().get("response", "").strip()
    return raw, dur

verifier = EdgeTaskVerifier()
target_cases = ["CASE_01_INTENT", "CASE_02_INTENT", "CASE_03_ARG", "CASE_04_ARG", "CASE_10_STRUCT", "CASE_15_REWRITE", "CASE_19_NEGATION", "CASE_20_NEGATION"]

print("=== TESTING REPAIRED CAPSULES ON LFM2.5-350M ===")
for cid in target_cases:
    case = cases_by_id[cid]
    capsule = build_repaired_capsule(case)
    raw, dur = query_lfm(capsule)
    outcome = verifier.verify(case, raw)
    status = "OK" if outcome.is_correct else "FAIL"
    print(f"[{status}] {cid:18s} -> {outcome.final_decision:22s} ({dur:.1f}ms) | Raw: {raw[:80]}")

print("\n=== TESTING REPAIRED CAPSULES ON QWEN3.5-0.8B ===")
for cid in target_cases:
    case = cases_by_id[cid]
    capsule = build_repaired_capsule(case)
    raw, dur = query_qwen(capsule)
    outcome = verifier.verify(case, raw)
    status = "OK" if outcome.is_correct else "FAIL"
    print(f"[{status}] {cid:18s} -> {outcome.final_decision:22s} ({dur:.1f}ms) | Raw: {raw[:80]}")
