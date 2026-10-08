import json

data = json.load(open('scripts/narrow_qualification_results.json'))

print("=== SCHEMA A (Goal/Intent) ===")
for x in data['schema_a']:
    print(f"{x['id']}: '{x['text']}' -> goal='{x['goal']}' family='{x['intent_family']}' (decl={x['declined']})")

print("\n=== SCHEMA B (Operations/Negation) ===")
for x in data['schema_b']:
    print(f"{x['id']}: '{x['text']}' -> req={x['requested_operations']} proh={x['prohibited_operations']} (decl={x['declined']})")

print("\n=== SCHEMA C (References/Temporal) ===")
for x in data['schema_c']:
    print(f"{x['id']}: '{x['text']}' -> refs={x['references']} trefs={x['temporal_references']} (decl={x['declined']})")

print("\n=== SCHEMA D (Constraints/Preferences) ===")
for x in data['schema_d']:
    print(f"{x['id']}: '{x['text']}' -> const={x['constraints']} prefs={x['output_preferences']} (decl={x['declined']})")
