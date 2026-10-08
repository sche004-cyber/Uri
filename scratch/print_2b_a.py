import json

with open('scripts/m35_a2_8c_resolution_results.json') as f:
    recs = json.load(f)

m_recs = [r for r in recs if r['model_name'] == 'qwen3.5-2b' and r['mode'] == 'MODE_A_DIRECT']
print("--- QWEN 2B MODE A DIRECT ---")
for r in m_recs:
    status = 'PASS' if r['scores'].get('final_task_path_success') else 'FAIL'
    fail = r.get('failure_attribution') or ''
    chosen = r['raw_response'].get('selected_capability')
    print(f"  {r['case_id']:<10} | {r['category']:<22} | chosen: {str(chosen):<26} | {status} {fail}")
