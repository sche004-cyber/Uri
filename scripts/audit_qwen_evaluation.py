import json

data = json.load(open('scripts/qwen_qualification_results.json'))

print("=================================================================")
print("  EVALUATION DIMENSIONS AUDIT: CONSTRAINED MODE")
print("=================================================================")

for item in data['constrained_mode']:
    pid = item['id']
    text = item['text']
    ok = item['ok']
    if not ok:
        print(f"[{pid}] FAILED: {item['error_reason']} - {item['error_detail']}")
        continue

    d = item['decoded']
    print(f"\n[{pid}] Prompt: '{text}'")
    print(f"  Goal: '{d['goal']}' | Intent: '{d['intent_family']}'")
    print(f"  Req Ops: {d['requested_operations']}")
    print(f"  Proh Ops: {d['prohibited_operations']}")
    print(f"  Refs: {d['references']}")
    print(f"  Temporal: {d['temporal_references']}")
    print(f"  Constraints: {d['constraints']}")
    print(f"  Output Prefs: {d['output_preferences']}")
    print(f"  Ambiguities: {d['ambiguities']}")
    print(f"  Tokens: prompt={item['prompt_tokens']}, total_cmpl={item['completion_tokens']}, reasoning={item['reasoning_tokens']}, content_tokens={item['completion_tokens']-item['reasoning_tokens']}")
    print(f"  Latency: {item['latency_ms']:.1f}ms")
