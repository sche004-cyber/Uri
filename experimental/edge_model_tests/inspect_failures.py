import json
from pathlib import Path

raw_file = Path("experimental/edge_model_tests/raw_results.json")
data = json.loads(raw_file.read_text(encoding="utf-8"))

print("=== QWEN3.5-0.8B FAILURE DETAILS ===")
for r in data["detailed_results"]["qwen35_08b"]:
    if not r["is_correct"]:
        print(f"Case: {r['case_id']} ({r['category']})")
        print(f"  Expected: {r['expected_decision']} | Final: {r['final_decision']}")
        print(f"  Failure Reason: {r['failure_reason']}")
        print(f"  Classification: {r['failure_classification']}")
        print(f"  Output: {r['candidate_output']}")
        print("-" * 50)
