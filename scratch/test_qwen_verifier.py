import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import json

from experimental.edge_model_tests.verifier import EdgeTaskVerifier

battery_path = ROOT / "experimental" / "edge_model_tests" / "battery.json"
with open(battery_path, "r", encoding="utf-8") as f:
    battery = json.load(f)

cases_by_id = {c["id"]: c for c in battery["cases"]}
verifier = EdgeTaskVerifier()

qwen_outputs = {
    "CASE_01_INTENT": '{\n  "decision": "LOCAL",\n  "intent": "EXTRACT",\n  "target": "sales_report.txt"\n}',
    "CASE_02_INTENT": '{\n  "decision": "LOCAL",\n  "intent": "EXTRACT",\n  "target": "revenue.csv"\n}',
    "CASE_03_ARG": '{\n  "decision": "LOCAL",\n  "file": "orders.xlsx",\n  "filters": {\n    "status": "pending",\n    "region": "West"\n  }\n}',
    "CASE_04_ARG": '{\n  "decision": "LOCAL",\n  "file": "data.csv",\n  "target_format": "json"\n}',
    "CASE_10_STRUCT": '{\n  "decision": "LOCAL",\n  "sheet": "Orders",\n  "rows": 50,\n  "cols": 4,\n  "empty_cells": 0\n}',
    "CASE_15_REWRITE": '{\n  "decision": "LOCAL",\n  "sentence": "ID 101 is for Customer Bob with a total of $250.00."\n}',
    "CASE_19_NEGATION": '{\n  "decision": "LOCAL",\n  "requested_operations": [\n    "summarize"\n  ],\n  "prohibited_operations": [\n    "disclose_names",\n    "disclose_phone_numbers"\n  ]\n}',
    "CASE_20_NEGATION": '{\n  "decision": "LOCAL",\n  "requested_operations": [\n    "save_draft"\n  ],\n  "prohibited_operations": [\n    "send_email"\n  ]\n}'
}

for cid, out in qwen_outputs.items():
    case = cases_by_id[cid]
    res = verifier.verify(case, out)
    print(f"[{cid}] Verifier Status: {res.verifier_status} | Final: {res.final_decision} | Correct: {res.is_correct} | Reason: {res.failure_reason}")
