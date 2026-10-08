import json

data = json.load(open('scripts/narrow_qualification_results.json'))

print("=== SCHEMA A: Required Prompts ===")
for x in data['schema_a'][:10]:
    print(f"{x['id']}: '{x['text']}' -> goal='{x['goal']}' family='{x['intent_family']}' (decl={x['declined']})")

print("\n=== SCHEMA A: Stress Prompts ===")
for x in data['schema_a'][10:]:
    print(f"{x['id']}: '{x['text']}' -> goal='{x['goal']}' family='{x['intent_family']}' (decl={x['declined']})")
