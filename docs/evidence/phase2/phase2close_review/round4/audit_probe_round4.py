import hashlib
import importlib.util
import json
import re
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[3]
tree = root / 'uri-agent'
ev = root / 'evidence'
out = tree / 'work' / 'c1' / 'round4-review'
out.mkdir(parents=True, exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for name in ('phase2close-candidate-20261008-d.zip', 'phase2close-candidate-20261008-c.zip',
             'phase2ops-candidate-20261008-r6.zip'):
    print('SHA', name, sha(ev / name))
frozen = root.parent / 'uri-phase1-integration/uri-agent/work/c1/checkpoints/final-closure-20261005-phase1.zip'
print('SHA frozen', sha(frozen))
with ZipFile(ev / 'phase2close-candidate-20261008-d.zip') as zd, ZipFile(ev / 'phase2close-candidate-20261008-c.zip') as zc, ZipFile(frozen) as zf:
    meta = {'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch', 'MANIFEST.json'}
    names = set(zd.namelist()) - meta
    manifest = json.loads(zd.read('MANIFEST.json'))
    ct = {n for n in names if not n.startswith('evidence/')}
    ce = names - ct
    print('MANIFEST', len(manifest), len(names), set(manifest) == names,
          'bad', [n for n, h in manifest.items() if hashlib.sha256(zd.read(n)).hexdigest() != h])
    print('COUNTS', len(ct), len(ce))
    print('LIVE missing', sorted(n for n in ct if not (tree / n).is_file()))
    print('LIVE different', sorted(n for n in ct if (tree / n).is_file() and (tree / n).read_bytes() != zd.read(n)))
    print('RUN7 different', sorted(n for n in ce if (ev / 'phase2close/run7' / n.removeprefix('evidence/run7/')).read_bytes() != zd.read(n)))
    cc = {n for n in zc.namelist() if n not in meta and not n.startswith('evidence/')}
    print('VS_C added', sorted(ct-cc))
    print('VS_C removed', sorted(cc-ct))
    print('VS_C changed', sorted(n for n in ct & cc if zd.read(n) != zc.read(n)))
    ft = {n for n in zf.namelist() if n not in meta and not n.endswith('/')}
    print('FROZEN', len(ft), 'missing', sorted(n for n in ft if not (tree / n).is_file()),
          'different', sorted(n for n in ft if (tree / n).is_file() and (tree / n).read_bytes() != zf.read(n)))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

pl = load('pl_round4', tree / 'scripts/phase2close_powerloss_harness.py')
t = load('pl_test_round4', tree / 'tests/phase2close/test_powerloss_harness.py')

def pair(label):
    d = out / label
    return t._series(d / 'full'), t._series(d / 'control', n=4, sync='NORMAL', lose_at=(2,))

def check(label, fn=None):
    f, c = pair(label)
    if fn:
        fn(f, c)
    result = pl.assess(f, c)
    print('PROBE', label, result['verdict'], result['reasons'], 'qualified', result['qualified'])

def edit_json(path, fn):
    obj = json.loads(path.read_text(encoding='utf-8'))
    path.write_text(json.dumps(fn(obj)), encoding='utf-8')

def edit_raw(d, fn):
    p = d / 'acks.jsonl'
    ms = [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
    p.write_text(''.join(json.dumps(m) + '\n' for m in fn(ms)), encoding='utf-8')

check('coherent')
check('round3_summary', lambda f,c: edit_json(f/'summary.json', lambda s: {**s, 'failed': 200, 'verdict': 'SERIES_FAIL', 'synchronous': ['NORMAL']}))
check('round3_simulated', lambda f,c: edit_json(f/'summary.json', lambda s: {**s, 'power_method': {'simulated': 'local process kill'}}))
check('round3_lost_identity', lambda f,c: edit_json(c/'iterations.json', lambda rs: [{**r, 'lost': [{**x, 'task_id': 'fake'} for x in r['lost']]} for r in rs]))
check('round3_final_ready', lambda f,c: edit_raw(f, lambda ms: ms[:-1]))
check('round3_previous_boot', lambda f,c: edit_raw(f, lambda ms: [{**m, 'previous_boot': 999} if m.get('type') == 'report' and m.get('boot') == 2 else m for m in ms]))
check('bad_integrity', lambda f,c: edit_raw(f, lambda ms: [{**m, 'report': {**m['report'], 'integrity': 'corrupt'}} if m.get('type') == 'report' and m.get('boot') == 2 else m for m in ms]))
check('orphan_attempt', lambda f,c: edit_raw(f, lambda ms: [{**m, 'report': {**m['report'], 'orphan_attempts': [{'attempt_id': 1}]}} if m.get('type') == 'report' and m.get('boot') == 2 else m for m in ms]))
check('still_in_flight', lambda f,c: edit_raw(f, lambda ms: [{**m, 'report': {**m['report'], 'still_in_flight': ['task']}} if m.get('type') == 'report' and m.get('boot') == 2 else m for m in ms]))
check('false_power_commands', lambda f,c: edit_json(f/'summary.json', lambda s: {**s, 'power_method': {'power_off': 'echo hello', 'power_on': 'echo world'}}))

def consistent_bad_report(f, c, field, value, row_field, row_value):
    edit_raw(f, lambda ms: [{**m, 'report': {**m['report'], field: value}} if m.get('type') == 'report' and m.get('boot') == 2 else m for m in ms])
    edit_json(f/'iterations.json', lambda rs: [{**r, row_field: row_value} if r['iteration'] == 1 else r for r in rs])

check('coherent_files_corrupt_integrity', lambda f,c: consistent_bad_report(f,c,'integrity','corrupt','integrity','corrupt'))
check('coherent_files_orphan', lambda f,c: consistent_bad_report(f,c,'orphan_attempts',[{'attempt_id': 1}], 'orphans',1))
check('coherent_files_running', lambda f,c: consistent_bad_report(f,c,'still_in_flight',['task'], 'still_in_flight',['task']))

round2_dir = out / 'round2_pair'
round2_full = t._series(round2_dir / 'full', lose_at=tuple(range(1,201)))
round2_control = t._series(round2_dir / 'control', n=0, sync='NORMAL')
edit_json(round2_full/'summary.json', lambda s: {**s, 'verdict': 'SERIES_ALL_PASS', 'passed': 200, 'failed': 0})
edit_json(round2_control/'summary.json', lambda s: {**s, 'lost_acknowledged_steps': 1})
r2 = pl.assess(round2_full, round2_control)
print('PROBE round2_contradictory_pair', r2['verdict'], r2['reasons'], 'qualified', r2['qualified'])
for name in ('test_assess_accepts_only_coherent_raw_evidence_and_never_qualifies',
             'test_assess_rejects_the_round2_contradictory_summaries',
             'test_assess_rejects_the_round3_probes',
             'test_assess_refuses_every_tampered_or_weak_series'):
    getattr(t, name)(out / name)
    print('DIRECT_TEST', name, 'PASS')

chain = json.loads((ev / 'phase2close/run7/chain_summary.json').read_text(encoding='utf-8'))
print('CHAIN gates', list(chain['gates']), 'ALL_PASS', chain['ALL_PASS'])
for gate, name in (('phase2', 'phase2_all.log'), ('authority', 'phase1_authority.log'), ('phase1-full', 'phase1_full.log')):
    data = (ev / 'phase2close/run7' / name).read_text(encoding='utf-8', errors='replace')
    print('LOG', gate, 'head', data.splitlines()[0], 'tail', data.splitlines()[-2:])
base = (ev / 'phase2ops_r6/phase1_full.log').read_text(encoding='utf-8', errors='replace')
now = (ev / 'phase2close/run7/phase1_full.log').read_text(encoding='utf-8', errors='replace')
ids = lambda s: sorted(set(re.findall(r'^FAILED (\S+)', s, re.M)))
print('FAILED IDS', len(ids(now)), ids(now) == ids(base), ids(now))
for n in range(1, 11):
    d = json.loads((ev / f'phase2close/run7/ui_bridge_live_{n}.json').read_text(encoding='utf-8'))
    print('BRIDGE', n, d.get('exit'))
print('REFUSALS bytes', (ev / 'phase2close/run7/refusals.txt').stat().st_size)
