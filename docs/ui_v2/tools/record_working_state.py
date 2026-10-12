from pathlib import Path
import json,hashlib,subprocess,shutil,argparse
r=Path(__file__).resolve().parents[3]
def git(*a):return subprocess.check_output(['git','-C',str(r),*a],text=True).strip()
changed=git('diff','--name-only').splitlines()+git('ls-files','--others','--exclude-standard').splitlines()
for name in changed:
    p=r/name
    if p.is_file() and p.suffix=='.dart':
        p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
parser=argparse.ArgumentParser()
parser.add_argument('--regression', default='regression.jsonl')
args=parser.parse_args()
events=[json.loads(x) for x in (r/'docs/ui_v2'/args.regression).read_text(encoding='utf-8-sig').splitlines() if x.startswith('{')]
tests=[x for x in events if x['type']=='testDone' and not x.get('hidden')]
state={'baseline':'1b5423bc15fd7e5da9161c862cf839925da9f2eb','branch':git('branch','--show-current'),'candidate_committed':True, 'candidate_commit':'See git HEAD and external lifecycle receipt; local snapshot only',
 'flutter_tests':{'passed':sum(x['result']=='success' and not x.get('skipped') for x in tests),'skipped':sum(bool(x.get('skipped')) for x in tests),'success':next(x['success'] for x in reversed(events) if x['type']=='done')},
 'native_orbit_animation':'IMPLEMENTED candidate: existing paced clock, 180s orbit; proximity/focus/chat/reduced-motion pause; native behavior NOT VERIFIED',
 'chat_design':'OWNER APPROVED 2026-10-13: Detached chat, reference evidence/reference/companion-approved.jpg',
 'wake_phrase':'UNSUPPORTED by inspected accepted voice baseline',
 'independent_review':'Fresh exact-commit lifecycle review pending; unavailable reviewer must not imply acceptance', 'integration':'NONE','deployment':'NONE',
 'test_log':args.regression,
 'artwork':'Background-removed derivative, faded unframed steel engraving at bottom right',
 'visual_reference_comparison':'dashboard-review.html; see VISUAL_QUALIFICATION.md for scope and discrepancies',
 'files':{x:hashlib.sha256((r/x).read_bytes()).hexdigest() for x in changed if (r/x).is_file() and x.startswith('uri_ui/')}}
out=r/'docs/ui_v2/WORKING_STATE.json';out.write_text(json.dumps(state,indent=2),encoding='utf-8')
dst=r/'docs/ui_v2/evidence/concepts';dst.mkdir(parents=True,exist_ok=True)
src=Path('C:/Users/cheta/.codex/generated_images/01a1305a-4e45-76d0-a524-d644140bedee')
for name,file in [('input-pill','exec-5dee2c65-889d-4bff-877c-5be1acf6a7d5.png'),('reply-ribbon','exec-30ef684d-b41e-4be3-bb49-5115757e068e.png'),('detached-chat','exec-0258e970-3cd4-40c5-aba8-80f42f8064af.png')]:
    shutil.copyfile(src/file,dst/(name+'.png'))
print(json.dumps({k:v for k,v in state.items() if k!='files'},indent=2))
