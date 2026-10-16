from pathlib import Path
import hashlib,json,subprocess
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
r=Path('.').resolve(); d=r/'docs/ui_v2'; base='1b5423bc15fd7e5da9161c862cf839925da9f2eb'
# Read-only comparison of the final PNG, never edits either image.
refpath=d/'evidence/reference/companion-approved.jpg'; cap=d/'evidence/delivery/companion-listening.png'
ref=Image.open(refpath).convert('RGB').resize((440,680),Image.Resampling.LANCZOS)
actual=Image.open(cap).convert('RGBA'); bg=Image.new('RGBA',actual.size,'#72726f'); bg.alpha_composite(actual); actual=bg.convert('RGB')
def score(x,y):
 a,b=[np.asarray(z,dtype=np.float64)@np.array([.2126,.7152,.0722]) for z in [x,y]]
 blur=lambda z:gaussian_filter(z,1.5,truncate=3.333333333)
 ma,mb=blur(a),blur(b);va,vb=blur(a*a)-ma*ma,blur(b*b)-mb*mb;cov=blur(a*b)-ma*mb
 z=((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225))
 return float(z[5:-5,5:-5].mean())
regions={'solar':(105,85,335,315),'chat_button':(25,165,110,240),'dashboard_button':(330,165,415,240),'voice_button':(175,310,265,400),'waveform':(135,382,305,468),'detached_chat':(70,445,370,670)}
scores={k:score(ref.crop(v),actual.crop(v)) for k,v in regions.items()};avg=sum(scores.values())/len(scores)
report={'method':'Six equal-weight local luminance SSIM regions; approved reference resampled in memory to 440x680; RGBA composited in memory over comparison gray #72726f','regions':{k:{'bounds':regions[k],'ssim':v} for k,v in scores.items()},'mean_ssim':avg,'screenshot_checkpoint':.8,'meets_screenshot_checkpoint':avg>=.8,'reference_sha256':hashlib.sha256(refpath.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(cap.read_bytes()).hexdigest(),'limitations':['Not a literal design-accuracy percentage or acceptance','Actual procedural texture/phase differs from generated reference','Readable labels/buttons/panel are physically larger than scaled reference','Background/reference JPEG and simulated audio level differ','Native compositor/runtime/device effects not verified']}
(d/'evidence/delivery/companion_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Exact candidate delta check, distinct from the old historical checkpoint.
import sys; sys.path.insert(0,str(r))
from scripts.ws_frozen_check import PROTECTED
changed=subprocess.check_output(['git','diff','--name-only',base],text=True).splitlines()+subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
hits=[p for p in changed if p.startswith(PROTECTED) or p in PROTECTED]
(d/'frozen_candidate_delta.json').write_text(json.dumps({'baseline':base,'new_protected_changes':hits,'ok':not hits},indent=2),encoding='utf-8')
# Design provenance records originals, not credentials/private chats.
paths=['evidence/reference/companion-approved.jpg','evidence/reference/owner-current.jpg','evidence/reference/ivory-1440.png','evidence/reference/white-1440.png','evidence/reference/ash-1440.png','evidence/portrait/original.png','evidence/portrait/EDIT_PROMPT.md']
items=[{'path':x,'sha256':hashlib.sha256((d/x).read_bytes()).hexdigest()} for x in paths if (d/x).is_file()]
(d/'DESIGN_SOURCE_INVENTORY.json').write_text(json.dumps({'accepted_base':base,'companion_approval_date':'2026-10-13','dashboard_layout':'Concept C / Solar / conduits','themes':['Ivory Foundry','Snow Archive','Ash & Limestone'],'references':items,'portrait_source':'https://chatgpt.com/s/m_6acd26337fc8819181de65cc4bb5d338','historical_figma':'https://www.figma.com/design/7y6g4JEBB9h5xWIYKVwand','figma_edit_or_new_file':'NOT VERIFIED / not claimed','current_capture':'evidence/delivery','independent_acceptance':False,'integration':'none','deployment':'none'},indent=2),encoding='utf-8')
p=d/'VISUAL_QUALIFICATION.md';s=p.read_text(encoding='utf-8');s+=f'\n## Final Companion screenshot checkpoint\n\nThe six-region luminance SSIM comparison is **{avg:.3f}** at 440x680, with the approved reference resampled and the transparent PNG composited over the comparison-page gray only in memory. It '+('meets' if avg>=.8 else 'does not meet')+' the 0.80 screenshot checkpoint. See `evidence/delivery/companion_comparison.json` for all regions, bounds and exact hashes. This must not be presented as a literal accuracy percentage. Larger readable controls/chat and actual Solar texture/phase remain explicit differences; no image has been altered to inflate this score.\n';p.write_text(s,encoding='utf-8')
p=d/'dashboard-review.html';s=p.read_text(encoding='utf-8').replace('evidence/engraving-final/', 'evidence/delivery/');p.write_text(s,encoding='utf-8')
(d/'UX_AUDIT_AND_DESIGN_PLAN.md').write_text('''# UX audit and implemented direction

The approved Companion reference resolves the prior chat-option choice. The design uses one existing Companion, floating contextual Chat/Dashboard/Voice actions, an audio-level display below the orbit and a compact detached conversation. Actual renderer reuse takes precedence over reproducing the generated sun texture. The three approved palettes remain independent from identity; no logo, neon/teal scheme or fake replacement Orb was added.

State truth remains the primary constraint: unavailable voice is omitted, opening controls does not listen, a reply is not task completion, and Review remains explicit. Auth/bootstrap are real gates. The fixture preview is labelled simulated and cannot demonstrate successful authentication or production work.

Dashboard preserves six readable destinations and brass conduits; the bottom-right engraving is unframed and fades into the canvas. Navigation, settings, task/draft and context continuity remain reachable. Larger readable controls/chat and original renderer texture are documented visual discrepancies, not silently labelled exact reference matches.

Completed: separate Companion catalog/theme selection, gallery isolation, approved detached chat, compact contextual controls, paused orbit motion, truthful voice states, themed login/bootstrap and dashboard. Available tests and native engine captures are recorded separately from runtime/desktop qualification.

Remaining: exhaustive legacy control/unreachable-route audit, native/device/runtime qualification, rendering-cost measurement, reference discrepancy disposition and fresh exact-commit independent audit. Office and experimental Harness/Console candidates remain separate. Figma edit capability/new editable file was not established. No new runtime API or authority is proposed.

See the bounded inventory, coverage matrix, theme specification, interaction/performance specification and future qualification proposal. This candidate is reviewable in isolation and is not integrated/deployed.
''',encoding='utf-8')
(d/'tools/README.md').write_text('''# Evidence tools

Supported read-only preview: `serve_options.py` binds only 127.0.0.1:8137 and serves this documentation; it never starts URI services. `record_working_state.py --regression <log>` normalizes changed Dart line endings and records file hashes/results. `compare_owner_reference.py` preserves the historical dashboard metric.

Other scripts here preserve one-use editing/capture/report history. They are not idempotent migration commands and must not be blindly rerun. Product entry points are documented in HANDOFF.md. No tool in this folder grants integration/deployment authority.
''',encoding='utf-8')
print(json.dumps({'companion_ssim':avg,'regions':scores,'frozen_delta':hits},indent=2))
