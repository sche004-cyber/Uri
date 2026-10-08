import json

data = json.load(open('scripts/qwen_qualification_results.json'))

for item in data['constrained_mode'][:6]:
    pid = item['id']
    text = item['text']
    ok = item['ok']
    if not ok:
        print(f"[{pid}] FAILED: {item['error_reason']}")
        continue
    d = item['decoded']
    print(f"[{pid}] '{text}'")
    print(f"  Goal: '{d['goal']}' ({d['intent_family']})")
    print(f"  Req: {d['requested_operations']} | Proh: {d['prohibited_operations']}")
    print(f"  Refs: {d['references']} | Trefs: {d['temporal_references']}")
    print(f"  Const: {d['constraints']} | Prefs: {d['output_preferences']}")
