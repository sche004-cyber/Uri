import hashlib
import importlib.util
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = HERE.parents[2]
TREE = TOP / 'uri-agent'
EV = TOP / 'evidence'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inspect_archive(tag):
    p = EV / f'phase2oq-candidate-20261008-{tag}.zip'
    with zipfile.ZipFile(p) as z:
        m = json.loads(z.read('MANIFEST.json'))
        entries = {n for n in z.namelist() if n not in ('MANIFEST.json', 'GIT_DIFF.patch','GIT_HEAD.txt','GIT_STATUS.txt')}
        bad = [n for n, h in m.items() if n not in entries or sha(z.read(n)) != h]
        tree = {n: h for n, h in m.items() if not n.startswith('evidence/')}
        live_bad = [n for n, h in tree.items() if not (TREE / n).is_file() or sha((TREE / n).read_bytes()) != h]
        return p, m, {'hash': sha(p.read_bytes()), 'entries': len(entries), 'manifest': len(m),
                      'missing_or_extra': sorted(entries ^ set(m)), 'payload_bad': bad,
                      'tree_files': len(tree), 'evidence_files': len(m)-len(tree), 'live_bad': live_bad}

d, dm, di = inspect_archive('d')
c, cm, ci = inspect_archive('c')
spec = importlib.util.spec_from_file_location('chain', TREE / 'scripts/phase2close_chain.py')
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)
base = json.loads((EV/'phase2oq/phase1_outcome_baseline.json').read_text())
def xml_stats(p):
    cases = list(ET.parse(p).getroot().iter('testcase'))
    ids = [x.get('classname','')+'::'+x.get('name','') for x in cases]
    return {'cases':len(cases), 'unique':len(set(ids)), 'collisions':[(k,v) for k,v in Counter(ids).items() if v>1][:10],
            'outcomes':dict(Counter(chain.junit_outcomes(p).values()))}

real_xml = EV/'phase2oq/chain7/phase1_full.xml'
baseline_xml = EV/'phase2oq/outcome_baseline/phase1_baseline.xml'
base_log = EV/'phase2ops_r6/phase1_full.log'
actual_log = EV/'phase2oq/chain7/phase1_full.log'
with zipfile.ZipFile(EV/'phase2close-candidate-20261008-f.zip') as z:
    src = z.read('scripts/phase2d_regression.py')
    ini = z.read('scripts/phase2d_pytest.ini')
current_src = (TREE/'scripts/phase2d_regression.py').read_bytes()
scope = chain.phase1_scope_check(TREE, EV/'phase2close-candidate-20261008-f.zip')
now = chain.junit_outcomes(real_xml)
ok, details = chain.outcome_identity(now, base['outcomes'])
probes = {}
for label, edit in {
    'missing': lambda x:x.pop(next(iter(x))),
    'added': lambda x:x.update({'review_probe::new':'passed'}),
    'lost_pass': lambda x:x.update({next(k for k,v in x.items() if v=='passed'):'skipped'}),
    'new_failure': lambda x:x.update({next(k for k,v in x.items() if v=='passed'):'failed'}),
    'new_skip': lambda x:x.update({next(k for k,v in x.items() if v=='passed'):'skipped'}),
}.items():
    x=base['outcomes'].copy(); edit(x)
    probes[label]=chain.outcome_identity(x,base['outcomes'])[0]
x=base['outcomes'].copy(); p=next(k for k,v in x.items() if v=='passed'); s=next(k for k,v in x.items() if v=='skipped'); x[p],x[s]='skipped','passed'
probes['pass_skip_swap']=chain.outcome_identity(x,base['outcomes'])[0]

result = {'subject':di,'previous':ci,
    'change_added':sorted(set(dm)-set(cm)), 'change_removed':sorted(set(cm)-set(dm)),
    'change_modified':sorted(k for k in dm.keys()&cm.keys() if dm[k]!=cm[k]),
    'baseline_runner_hash_match':base['runner_sha256']==sha(src),
    'baseline_argv_match':base['argv']==chain.runner_argv(src.decode())+[chain.OQ_EXTRA_IGNORE,'-rfEsp','--junitxml',r'..\evidence\phase2oq\outcome_baseline\phase1_baseline.xml'],
    'current_argv_match':chain.runner_argv(current_src.decode())==chain.runner_argv(src.decode())+[chain.OQ_EXTRA_IGNORE],
    'ini_match':(TREE/'scripts/phase2d_pytest.ini').read_bytes()==ini,
    'scope':scope, 'baseline_xml':xml_stats(baseline_xml),'chain_xml':xml_stats(real_xml),
    'baseline_json_matches_xml':base['outcomes']==chain.junit_outcomes(baseline_xml),
    'chain_identity':{'ok':ok,**details}, 'failed_ids_match_accepted':chain.failed_ids(actual_log)==chain.failed_ids(base_log),
    'baseline_anchor_recomputed':{'same_failures':chain.failed_ids(EV/'phase2oq/outcome_baseline/phase1_baseline.log')==chain.failed_ids(base_log),
        'skip_now':{'|'.join(k):v for k,v in chain.skip_multiset(EV/'phase2oq/outcome_baseline/phase1_baseline.log').items()},
        'skip_accepted':{'|'.join(k):v for k,v in chain.skip_multiset(base_log).items()}}, 'probes':probes}

frozen=Path(r'C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip')
if frozen.exists():
    with zipfile.ZipFile(frozen) as z:
        names=[n for n in z.namelist() if not n.endswith('/') and n not in ('MANIFEST.json','GIT_HEAD.txt','GIT_STATUS.txt','GIT_DIFF.patch') and not n.startswith('evidence/')]
        result['frozen']={'hash':sha(frozen.read_bytes()),'entries':len(names),
           'live_bad':[n for n in names if not (TREE/n).is_file() or (TREE/n).read_bytes()!=z.read(n)]}
for p in (EV/'phase2close-candidate-20261008-f.zip', EV/'phase2close-candidate-20261008-r7.zip'):
    if p.exists(): result[p.name+'_sha256']=sha(p.read_bytes())
result['head']=subprocess.run(['git','-C',str(TREE),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
# The parser maps testcase records to a dict; determine whether duplicate IDs are rejected.
sample=HERE/'collision_probe.xml'
sample.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="p"/>'
                  '<testcase classname="b" name="q"><skipped/></testcase></testsuite></testsuites>')
result['collision_probe']={'xml':xml_stats(sample),'gate_accepts_extra_same_id':chain.outcome_identity(chain.junit_outcomes(sample),{'a::p':'passed','b::q':'skipped'})[0]}
conflict_sample=HERE/'conflict_probe.xml'
conflict_sample.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="p"><skipped/></testcase>'
                           '<testcase classname="a" name="p"/></testsuite></testsuites>')
result['conflict_reset_probe']={'xml':xml_stats(conflict_sample),'gate_accepts':chain.outcome_identity(chain.junit_outcomes(conflict_sample),{'a::p':'passed'})[0]}
(HERE/'reviewer_results.json').write_text(json.dumps(result,indent=2,default=str))
print(json.dumps({k:v for k,v in result.items() if k not in ('change_added','change_modified','baseline_anchor_recomputed','scope')},indent=2,default=str))
print('added',len(result['change_added']),result['change_added'])
print('modified',result['change_modified'])
print('scope',json.dumps(scope))
