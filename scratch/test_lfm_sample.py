import httpx
import json

def test_lfm(prompt, schema_hint):
    capsule = f"Task: {prompt}\nInstruction: Populate JSON with exact extracted values.\nSchema: {schema_hint}\nReturn ONLY valid JSON."
    res = httpx.post("http://127.0.0.1:1234/v1/chat/completions", json={
        "model": "lfm2.5-350m",
        "messages": [
            {"role": "system", "content": "You are a tiny semantic worker. Output valid JSON only matching the schema. No markdown, no prose."},
            {"role": "user", "content": capsule}
        ],
        "temperature": 0.0,
        "max_tokens": 120
    }, timeout=15.0)
    print("PROMPT:", prompt)
    print("RESPONSE:", repr(res.json()["choices"][0]["message"]["content"]))

test_lfm("Extract summary from sales_report.txt", '{"decision": "LOCAL", "intent": "EXTRACT", "target": "sales_report.txt"}')
test_lfm("Filter orders.xlsx where status='pending' and region='West'", '{"decision": "LOCAL", "file": "orders.xlsx", "filters": {"status": "pending", "region": "West"}}')
test_lfm("Format this invoice summary into exactly one sentence: ID 101, Customer Bob, Total $250.00", '{"decision": "LOCAL", "sentence": "..."}')
test_lfm("Scan directory for duplicate files, but DO NOT delete or rename any files", '{"decision": "LOCAL", "requested_operations": ["..."], "prohibited_operations": ["..."]}')
