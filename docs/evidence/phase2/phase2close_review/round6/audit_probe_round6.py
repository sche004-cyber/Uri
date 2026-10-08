import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[3]
tree = root / 'uri-agent'
ev = root / 'evidence'
runtime = tree / 'work' / 'c1' / 'round6-review'
runtime.mkdir(parents=True, exist_ok=True)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

frozen = root.parent / 'uri-phase1-integration/uri-agent/work/c1/checkpoints/final-closure-20261005-phase1.zip'
for p in [ev / 'phase2close-candidate-20261008-f.zip', ev / 'phase2ops-candidate-20261008-r6.zip', frozen]:
    print('HASH', p.name, sha(p))
meta = {'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch', 'MANIFEST.json'}
with ZipFile(ev / 'phase2close-candidate-20261008-f.zip') as zf, ZipFile(ev / 'phase2close-candidate-20261008-e.zip') as ze, ZipFile(frozen) as zp:
    names = set(zf.namelist()) - meta
    man = json.loads(zf.read('MANIFEST.json'))
    ct = {n for n in names if not n.startswith('evidence/')}
    ce = names - ct
    old = {n for n in ze.namelist() if n not in meta and not n.startswith('evidence/')}
    frozen_names = {n for n in zp.namelist() if n not in meta and not n.endswith('/')}
    print('MANIFEST', len(man), len(names), set(man) == names, 'bad', [n for n in names if man.get(n) != hashlib.sha256(zf.read(n)).hexdigest()])
    print('COUNTS', len(ct), len(ce))
    print('LIVE_DIFFERENT', [n for n in ct if not (tree/n).is_file() or (tree/n).read_bytes() != zf.read(n)])
    print('RUN9_DIFFERENT', [n for n in ce if not (ev/'phase2close/run9'/n.removeprefix('evidence/run9/')).is_file() or (ev/'phase2close/run9'/n.removeprefix('evidence/run9/')).read_bytes() != zf.read(n)])
    print('VS_E_ADDED', sorted(ct-old), 'REMOVED', sorted(old-ct), 'CHANGED', sorted(n for n in ct & old if zf.read(n) != ze.read(n)))
    print('FROZEN', len(frozen_names), 'MISSING', [n for n in frozen_names if not (tree/n).is_file()], 'DIFFERENT', [n for n in frozen_names if (tree/n).is_file() and (tree/n).read_bytes() != zp.read(n)])

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

pl = load('pl6', tree/'scripts/phase2close_powerloss_harness.py')
t = load('t6', tree/'tests/phase2close/test_powerloss_harness.py')

def pair(name):
    d = runtime/name
    return t._series(d/'full'), t._series(d/'control', n=4, sync='NORMAL', lose_at=(2,))

def assess(name, mut=None):
    f,c = pair(name)
    if mut: mut(f,c)
    r = pl.assess(f,c)
    print('PROBE', name, r['verdict'], r['reasons'], r['qualified'])

def edit(path, fn):
    obj = json.loads(path.read_text(encoding='utf-8'))
    path.write_text(json.dumps(fn(obj)), encoding='utf-8')

def raw(path, fn):
    ms = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
    path.write_text(''.join(json.dumps(m)+'\n' for m in fn(ms)), encoding='utf-8')

assess('good')
assess('req_zero', lambda f,c: edit(f/'summary.json', lambda s: {**s, 'iterations_requested':0,'verdict':'SERIES_FAIL'}))
assess('req_201', lambda f,c: edit(f/'summary.json', lambda s: {**s, 'iterations_requested':201,'verdict':'SERIES_FAIL'}))
assess('ctl_req_5', lambda f,c: edit(c/'summary.json', lambda s: {**s, 'iterations_requested':5,'verdict':'SERIES_FAIL'}))
assess('echo_pair', lambda f,c: edit(f/'summary.json', lambda s: {**s,'power_method':{'power_off':'echo hello','power_on':'echo world'}}))
assess('echo_hard_off_text', lambda f,c: edit(f/'summary.json', lambda s: {**s,'power_method':{'power_off':'echo Stop-VM -Name URI-PL -TurnOff','power_on':'echo world'}}))
assess('raw_truncated', lambda f,c: raw(f/'acks.jsonl', lambda ms: ms[:-1]))
assess('extra_report', lambda f,c: raw(f/'acks.jsonl', lambda ms: ms+[{'type':'report','boot':202,'previous_boot':201,'synchronous':'FULL','report':{}}]))
assess('bad_previous_boot', lambda f,c: raw(f/'acks.jsonl', lambda ms: [{**m,'previous_boot':999} if m.get('type')=='report' and m.get('boot')==2 else m for m in ms]))
assess('wrong_loss', lambda f,c: edit(c/'iterations.json', lambda rs: [{**r,'lost':[{'task_id':'fake'}]} if r['lost'] else r for r in rs]))
assess('corrupt_integrity', lambda f,c: raw(f/'acks.jsonl', lambda ms: [{**m,'report':{**m['report'],'integrity':'corrupt'}} if m.get('type')=='report' and m.get('boot')==2 else m for m in ms]))
assess('orphan', lambda f,c: raw(f/'acks.jsonl', lambda ms: [{**m,'report':{**m['report'],'orphan_attempts':[{'attempt_id':1}]}} if m.get('type')=='report' and m.get('boot')==2 else m for m in ms]))
assess('running', lambda f,c: raw(f/'acks.jsonl', lambda ms: [{**m,'report':{**m['report'],'still_in_flight':['task']}} if m.get('type')=='report' and m.get('boot')==2 else m for m in ms]))

for name in ('test_assess_rejects_the_round2_contradictory_summaries','test_assess_rejects_the_round3_probes','test_assess_rejects_the_round4_probes','test_assess_rejects_the_round5_probes','test_each_recognised_hard_off_form_is_accepted'):
    getattr(t,name)(runtime/name)
    print('DIRECT_TEST',name,'PASS')
