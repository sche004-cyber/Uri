import importlib.util
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[3]
tree = root / 'uri-agent'
work = tree / 'work' / 'c1' / 'round3-review'
work.mkdir(parents=True, exist_ok=True)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

pl = load('pl', tree / 'scripts/phase2close_powerloss_harness.py')
t = load('pl_tests', tree / 'tests/phase2close/test_powerloss_harness.py')
base = work / 'synthetic'
base.mkdir(exist_ok=True)
full = t._series(base / 'full')
ctl = t._series(base / 'control', n=4, sync='NORMAL', lose_at=(2,))

def result(label):
    x = pl.assess(full, ctl)
    print(label, json.dumps({'verdict': x['verdict'], 'reasons': x['reasons'], 'full': x['full'], 'control': x['control']}))

def edit(path, fn):
    old = path.read_text(encoding='utf-8')
    obj = json.loads(old)
    path.write_text(json.dumps(fn(obj)), encoding='utf-8')
    return old

result('coherent')
fsummary = full / 'summary.json'
original = edit(fsummary, lambda s: {**s, 'verdict': 'SERIES_FAIL', 'failed': 200, 'synchronous': ['NORMAL']})
result('summary_marks_failed_and_normal')
fsummary.write_text(original, encoding='utf-8')
original = edit(fsummary, lambda s: {**s, 'power_method': {'simulated': 'local process kill'}})
result('simulated_method_mislabeled_vm')
fsummary.write_text(original, encoding='utf-8')
crow = ctl / 'iterations.json'
original = edit(crow, lambda rows: [{**r, 'lost': [{'task_id': 'not-the-actual-lost-task'}]} if r['lost'] else r for r in rows])
result('false_lost_task_in_control_row')
crow.write_text(original, encoding='utf-8')
raw = full / 'acks.jsonl'
original = raw.read_text(encoding='utf-8')
raw.write_text(original[:-15], encoding='utf-8')
result('truncated_raw_record')
raw.write_text(original, encoding='utf-8')
lines = original.splitlines(keepends=True)
assert json.loads(lines[-1])['type'] == 'ready'
raw.write_text(''.join(lines[:-1]), encoding='utf-8')
result('truncated_at_final_ready_record')
raw.write_text(original, encoding='utf-8')
msgs = [json.loads(line) for line in lines]
for msg in msgs:
    if msg.get('type') == 'report' and msg.get('boot') == 2:
        msg['previous_boot'] = 999
        break
raw.write_text(''.join(json.dumps(m) + '\n' for m in msgs), encoding='utf-8')
result('wrong_previous_boot_in_raw_report')
raw.write_text(original, encoding='utf-8')
original = edit(full / 'summary.json', lambda s: {**s, 'passed': 0, 'failed': 200, 'lost_acknowledged_steps': 200, 'verdict': 'SERIES_ALL_PASS'})
ctl_original = (ctl / 'summary.json').read_text(encoding='utf-8')
(ctl / 'summary.json').write_text(json.dumps({'label': 'VM_SERIES', 'power_method': {'x': 1}, 'iterations_requested': 0, 'iterations_run': 0, 'passed': 0, 'failed': 0, 'lost_acknowledged_steps': 1, 'synchronous': ['NORMAL'], 'verdict': 'SERIES_ALL_PASS'}), encoding='utf-8')
(ctl / 'acks.jsonl').write_text('', encoding='utf-8')
(ctl / 'iterations.json').write_text('[]', encoding='utf-8')
result('round2_contradictory_pair_variant')

real = work / 'real-local-campaign'
real.mkdir(exist_ok=True)
off, on = pl.local_power(real, real / 'guest' / 'ledger.db', 'FULL')
summary = pl.campaign(real, 2, off, on, 1.5, 2.0, 60, 0, 'SIMULATED', power_method={'simulated': 'process kill'})
facts, reasons = pl.assess_series(real, 'FULL')
rows = json.loads((real / 'iterations.json').read_text(encoding='utf-8'))
print('real_local_campaign', json.dumps({'summary': {k: summary[k] for k in ('verdict', 'iterations_run', 'passed', 'failed')}, 'rows': [(r.get('boot'), r.get('verdict'), r.get('acked_tasks'), len(r.get('lost') or [])) for r in rows], 'replay': facts, 'assess_reasons': reasons}))
