import json

data = json.load(open('scripts/narrow_qualification_results.json'))

print("=== SCHEMA B: Required Prompts ===")
for x in data['schema_b'][:10]:
    print(f"{x['id']}: '{x['text']}' -> req={x['requested_operations']} proh={x['prohibited_operations']} (decl={x['declined']})")

print("\n=== SCHEMA B: Stress Prompts ===")
for x in data['schema_b'][10:]:
    print(f"{x['id']}: '{x['text']}' -> req={x['requested_operations']} proh={x['prohibited_operations']} (decl={x['declined']})")
