import json

with open('scripts/m35_a2_8c_resolution_results.json') as f:
    recs = json.load(f)

for m in ['qwen3.5-2b', 'qwen3.5-9b', 'lfm2.5-350m']:
    print(f"\n==================== {m} ====================")
    for mode in ['MODE_A_DIRECT', 'MODE_B_STRUCTURED']:
        m_recs = [r for r in recs if r['model_name'] == m and r['mode'] == mode]
        print(f"\n--- {mode} ---")
        for r in m_recs:
            status = 'PASS' if r['scores'].get('final_task_path_success') else 'FAIL'
            fail = r.get('failure_attribution') or ''
            chosen = r['raw_response'].get('matched_capability') or r['raw_response'].get('selected_capability')
            print(f"  {r['case_id']:<10} | {r['category']:<22} | chosen: {str(chosen):<26} | {status} {fail}")
