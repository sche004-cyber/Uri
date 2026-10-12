from pathlib import Path
for name in ['companion-review.html','CURRENT_UI_EVIDENCE.md','VISUAL_QUALIFICATION.md']:
 p=Path('docs/ui_v2')/name;s=p.read_text(encoding='utf-8').replace('evidence/accepted-companion/', 'evidence/delivery/').replace('regression_accepted_companion.jsonl','regression_delivery.jsonl').replace('analyze_accepted_companion.txt','analyze_final_framing.txt');p.write_text(s,encoding='utf-8')
