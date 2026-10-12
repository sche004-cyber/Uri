import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = HERE.parents[2]
TREE = TOP / 'uri-agent'
EV = TOP / 'evidence'

def sha(b): return hashlib.sha256(b).hexdigest()
def archive(path):
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read('MANIFEST.json'))
        payloads = set(z.namelist()) - {'MANIFEST.json','GIT_DIFF.patch','GIT_HEAD.txt','GIT_STATUS.txt'}
        bad = [n for n,h in manifest.items() if n not in payloads or sha(z.read(n)) != h]
        tree = {n:h for n,h in manifest.items() if not n.startswith('evidence/')}
        live_bad = [n for n,h in tree.items() if not (TREE/n).is_file() or sha((TREE/n).read_bytes()) != h]
        return manifest, {'sha256':sha(path.read_bytes()),'entries':len(payloads),'manifest':len(manifest),'member_delta':sorted(payloads ^ set(manifest)), 'payload_bad':bad,'tree_files':len(tree),'evidence_files':len(manifest)-len(tree),'live_bad':live_bad}

e, ei = archive(EV/'phase2oq-candidate-20261008-e.zip')
d, di = archive(EV/'phase2oq-candidate-20261008-d.zip')
spec=importlib.util.spec_from_file_location('chain', TREE/'scripts/phase2close_chain.py')
ch=importlib.util.module_from_spec(spec); spec.loader.exec_module(ch)
base=json.loads((EV/'phase2oq/phase1_outcome_baseline.json').read_text())
bx=EV/'phase2oq/outcome_baseline/phase1_baseline.xml'
bl=EV/'phase2oq/outcome_baseline/phase1_baseline.log'
nx=EV/'phase2oq/chain8/phase1_full.xml'
nl=EV/'phase2oq/chain8/phase1_full.log'

def xml_info(p, log):
    rec=ch.junit_records(p)
    return {'integrity':ch.junit_integrity(p,ch.pytest_counts(log)), 'outcomes_match_json':ch.junit_outcomes(p)==base['outcomes'], 'records':len(rec)}

probes={}
sample=HERE/'collision_probe.xml'
sample.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="p"/><testcase classname="b" name="q"><skipped/></testcase></testsuite></testsuites>')
probes['duplicate_same']={'records':ch.junit_records(sample),'outcomes':ch.junit_outcomes(sample),'integrity':ch.junit_integrity(sample,{'passed':2,'failed':0,'skipped':1,'errors':0}),'identity':ch.outcome_identity(ch.junit_outcomes(sample),{'a::p':'passed','b::q':'skipped'})[0]}
probes['count_mismatch']=ch.junit_integrity(sample,{'passed':1,'failed':0,'skipped':1,'errors':0})
balanced=HERE/'balanced_mismatch.xml'
balanced.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="b" name="q"><skipped/></testcase></testsuite></testsuites>')
probes['outcome_count_mismatch']={'integrity':ch.junit_integrity(balanced,{'passed':2,'failed':0,'skipped':0,'errors':0}), 'identity':ch.outcome_identity(ch.junit_outcomes(balanced),{'a::p':'passed','b::q':'skipped'})[0]}
probes['full_gate_changed_skip_count']={'junit_integrity':ch.junit_integrity(nx,{'passed':2677,'failed':11,'skipped':10,'errors':0}),'outcome_identity':ch.outcome_identity(ch.junit_outcomes(nx),base['outcomes'])[0], 'same_failure_ids':ch.failed_ids(nl)==ch.failed_ids(EV/'phase2ops_r6/phase1_full.log')}
probes['baseline_json_xml_binding']={'gate_checks_mapping_equality':False, 'stored_mapping_equals_xml_now':ch.junit_outcomes(bx)==base['outcomes']}
for label,mut in [('missing',lambda x:x.pop(next(iter(x)))),('added',lambda x:x.update({'review::new':'passed'})),('swapped',None)]:
    x=base['outcomes'].copy()
    if mut: mut(x)
    else:
        p=next(k for k,v in x.items() if v=='passed'); s=next(k for k,v in x.items() if v=='skipped'); x[p],x[s]=x[s],x[p]
    probes[label]=ch.outcome_identity(x,base['outcomes'])[0]
malformed=HERE/'malformed.xml'; malformed.write_text('<testsuites><testcase')
try: ch.junit_integrity(malformed,{'passed':1,'failed':0,'skipped':0,'errors':0})
except Exception as exc: probes['malformed_exception']=type(exc).__name__

real=HERE/'collision_case'
for part in ('a.b','a/b'):
    p=real/part/'test_same.py'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('def test_same():\n    assert True\n')
rx=HERE/'real_collision.xml'
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
r=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--import-mode=importlib','--rootdir',str(real),'--junitxml',str(rx),str(real)],capture_output=True,text=True,cwd=real,env=env)
(HERE/'real_collision.log').write_text(r.stdout+'\nSTDERR\n'+r.stderr)
probes['real_collision']={'exit':r.returncode,'records':ch.junit_records(rx),'integrity':ch.junit_integrity(rx,{'passed':2,'failed':0,'skipped':0,'errors':0}),'identity':ch.outcome_identity(ch.junit_outcomes(rx),{'evidence.phase2oq_review.round5.collision_case.a.b.test_same::test_same':'passed'})[0]}

with zipfile.ZipFile(EV/'phase2close-candidate-20261008-f.zip') as z:
    accepted=z.read('scripts/phase2d_regression.py')
    ini=z.read('scripts/phase2d_pytest.ini')
scope=ch.phase1_scope_check(TREE,EV/'phase2close-candidate-20261008-f.zip')
frozen=Path(r'C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip')
with zipfile.ZipFile(frozen) as z:
    fn=[n for n in z.namelist() if not n.endswith('/') and n not in ('MANIFEST.json','GIT_HEAD.txt','GIT_STATUS.txt','GIT_DIFF.patch') and not n.startswith('evidence/')]
    frozen_info={'hash':sha(frozen.read_bytes()),'entries':len(fn),'live_bad':[n for n in fn if not (TREE/n).is_file() or (TREE/n).read_bytes()!=z.read(n)]}

summary=json.loads((EV/'phase2oq/chain8/chain_summary.json').read_text())
result={'subject':ei,'previous':di,'added':sorted(set(e)-set(d)),'removed':sorted(set(d)-set(e)),'changed':sorted(k for k in e.keys()&d.keys() if e[k]!=d[k]),'head':subprocess.run(['git','-C',str(TREE),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip(),'frozen':frozen_info,'closure_hash':sha((EV/'phase2close-candidate-20261008-f.zip').read_bytes()),'round7_hash':sha((EV/'phase2ops-candidate-20261008-r6.zip').read_bytes()),'baseline':xml_info(bx,bl),'chain_xml':xml_info(nx,nl),'chain_identity':ch.outcome_identity(ch.junit_outcomes(nx),base['outcomes']),'baseline_runner_hash':base['runner_sha256']==sha(accepted),'baseline_argv':base['argv'],'current_runner_argv_match':ch.runner_argv((TREE/'scripts/phase2d_regression.py').read_text())==ch.runner_argv(accepted.decode())+[ch.OQ_EXTRA_IGNORE],'ini_match':(TREE/'scripts/phase2d_pytest.ini').read_bytes()==ini,'scope':scope,'chain_gates':{k:{'PASS':v.get('PASS'),'exit':v.get('exit')} for k,v in summary['gates'].items()},'chain_all_pass':summary['ALL_PASS'],'probes':probes}
(HERE/'reviewer_results.json').write_text(json.dumps(result,indent=2,default=str))
print(json.dumps({k:v for k,v in result.items() if k not in ('added','scope','baseline_argv')},indent=2,default=str))
