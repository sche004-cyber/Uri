import re
from uri_v1.turn.rar_stage4b_independent_fixtures import get_rar_stage4b_fixtures
from uri_v1.turn.turn_frame_builder import REFERENCE_PATTERNS

fixtures = get_rar_stage4b_fixtures()
ref_regexes = [re.compile(p, re.IGNORECASE) for p in REFERENCE_PATTERNS]

r0_cases = []
r1_cases = []
r2_cases = []
r3_cases = []

for fix in fixtures:
    turn = fix.turn_text.strip()
    ref = fix.query.reference_expression.strip()
    
    clean_turn = re.sub(r"^[.\s\"'?!]+|[.\s\"'?!]+$", "", turn)
    clean_ref = re.sub(r"^[.\s\"'?!]+|[.\s\"'?!]+$", "", ref)
    
    if clean_turn.lower() == clean_ref.lower():
        r0_cases.append(fix.id)
        continue
        
    matched_r1 = False
    for regex in ref_regexes:
        m = regex.fullmatch(ref)
        if m:
            matched_r1 = True
            break
            
    if not matched_r1:
        if re.fullmatch(r"[A-Za-z0-9]+-[A-Za-z0-9]+(-[A-Za-z0-9]+)*", ref):
            matched_r1 = True

    if matched_r1:
        r1_cases.append(fix.id)
    else:
        r2_cases.append(fix.id)

print(f"R0 (Whole turn is reference): {len(r0_cases)}")
print(f"R1 (Surface regex or bounded ID pattern): {len(r1_cases)}")
print(f"R2 (Semantic segmentation required): {len(r2_cases)}")
print(f"R3 (Cannot determine): {len(r3_cases)}")
print(f"Total: {len(r0_cases) + len(r1_cases) + len(r2_cases) + len(r3_cases)}")
print("R0 sample:", r0_cases[:5])
print("R1 sample:", r1_cases[:10])
print("R2 sample:", r2_cases[:10])
