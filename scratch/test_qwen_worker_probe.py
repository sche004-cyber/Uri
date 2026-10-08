import httpx
import json
import time

cases = [
    ("CASE_01_INTENT", "Extract summary from sales_report.txt", '{"decision": "LOCAL", "intent": "EXTRACT"|"CALCULATE", "target": "<filename>"}', "Extract the exact intent and target filename."),
    ("CASE_02_INTENT", "Calculate total revenue for Q3 from revenue.csv", '{"decision": "LOCAL", "intent": "EXTRACT"|"CALCULATE", "target": "<filename>"}', "Extract the exact intent and target filename."),
    ("CASE_03_ARG", "Filter orders.xlsx where status='pending' and region='West'", '{"decision": "LOCAL", "file": "orders.xlsx", "filters": {"status": "pending", "region": "West"}}', "Extract exact file and filters."),
    ("CASE_04_ARG", "Convert input file data.csv to target format json", '{"decision": "LOCAL", "file": "data.csv", "target_format": "json"}', "Extract exact file and target format."),
    ("CASE_10_STRUCT", "Format table inspection: sheet 'Orders', 50 rows, 4 columns, 0 empty cells", '{"decision": "LOCAL", "sheet": "Orders", "rows": 50, "cols": 4, "empty_cells": 0}', "Populate exact sheet, rows, cols, empty_cells."),
    ("CASE_15_REWRITE", "Format this invoice summary into exactly one sentence: ID 101, Customer Bob, Total $250.00", '{"decision": "LOCAL", "sentence": "<one sentence summary>"}', "Format this invoice summary into exactly one sentence containing: ID 101, Customer Bob, Total $250.00."),
    ("CASE_19_NEGATION", "Summarize customer_feedback.txt but do not disclose customer names or phone numbers", '{"decision": "LOCAL", "requested_operations": ["summarize"], "prohibited_operations": ["disclose_names", "disclose_phone_numbers"]}', "Separate requested operations from prohibited operations."),
    ("CASE_20_NEGATION", "Don't send the email to client yet, just save it as draft in drafts.txt", '{"decision": "LOCAL", "requested_operations": ["save_draft"], "prohibited_operations": ["send_email"]}', "Separate requested operations from prohibited operations.")
]

print("Testing Qwen3.5:0.8B on Ollama with identical capsules...")

for cid, prompt, schema, inst in cases:
    user_content = f"Task: {prompt}\nInstruction: {inst}\nSchema: {schema}\nReturn ONLY valid JSON."
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
    resp = data.get("response", "").strip()
    print(f"\n[{cid}] ({dur:.1f}ms):")
    print(" ", resp)
