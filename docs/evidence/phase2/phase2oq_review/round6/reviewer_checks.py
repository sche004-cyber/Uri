import hashlib, importlib.util, json, os, subprocess, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = HERE.parents[2]
TREE = TOP / 'uri-agent'
EV = TOP / 'evidence'
def sha(b): return hashlib.sha256(b).hexdigest()
def archive(name):
    path = EV / name
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read('MANIFEST.json'))
        payloads = set(z.namelist()) - {'MANIFEST.json','GIT_DIFF.patch','GIT_HEAD.txt','GIT_STATUS.txt'}
        bad = [n for n,h in manifest.items() if n not in payloads or sha(z.read(n)) != h]
        tree = {n:h for n,h in manifest.items() if not n.startswith('evidence/')}
        live_bad = [n for n,h in tree.items() if not (TREE/n).is_file() or sha((TREE/n).read_bytes()) != h]
        ev_bad = [n for n,h in manifest.items() if n.startswith('evidence/') and (not (TOP/n).is_file() or sha((TOP/n).read_bytes()) != h)]
        return manifest, {'sha256':sha(path.read_bytes()), 'payloads':len(payloads), 'manifest':len(manifest), 'member_delta':sorted(payloads ^ set(manifest)), 'payload_bad':bad, 'tree_files':len(tree), 'evidence_files':len(manifest)-len(tree), 'live_tree_bad':live_bad, 'live_evidence_bad':ev_bad}

f, fi = archive('phase2oq-candidate-20261008-f.zip')
e, ei = archive('phase2oq-candidate-20261008-e.zip')
spec=importlib.util.spec_from_file_location('chain', TREE/'scripts/phase2close_chain.py')
ch=importlib.util.module_from_spec(spec); spec.loader.exec_module(ch)
base=json.loads((EV/'phase2oq/phase1_outcome_baseline.json').read_text())
bx=EV/'phase2oq/outcome_baseline/phase1_baseline.xml'
bl=EV/'phase2oq/outcome_baseline/phase1_baseline.log'
nx=EV/'phase2oq/chain9/phase1_full.xml'
nl=EV/'phase2oq/chain9/phase1_full.log'
def xml_info(p,log):
    return {'integrity':ch.junit_integrity(p,ch.pytest_counts(log)), 'outcomes_match_baseline_json':ch.junit_outcomes(p)==base['outcomes']}
probes={}
x=HERE/'balanced_mismatch.xml'
x.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="s"><skipped/></testcase></testsuite></testsuites>')
probes['r5_1_two_records']={'mismatch':ch.junit_integrity(x,{'passed':2,'failed':0,'skipped':0,'errors':0}), 'match':ch.junit_integrity(x,{'passed':1,'failed':0,'skipped':1,'errors':0})}
probes['r5_1_chain9_balanced_mismatch']=ch.junit_integrity(nx,{'passed':2677,'failed':11,'skipped':10,'errors':0})
probes['r5_2_baseline_bound']={'actual_equal':ch.junit_outcomes(bx)==base['outcomes'], 'mutated_json_equal':None}
mutated=base['outcomes'].copy(); p=next(k for k,v in mutated.items() if v=='passed'); mutated[p]='skipped'
probes['r5_2_baseline_bound']['mutated_json_equal']=ch.junit_outcomes(bx)==mutated
probes['missing_added_swap']={}
for label in ('missing','added','swap','new_failed','new_skipped'):
    m=base['outcomes'].copy(); p=next(k for k,v in m.items() if v=='passed'); s=next(k for k,v in m.items() if v=='skipped')
    if label=='missing': m.pop(p)
    elif label=='added': m['review::new']='passed'
    elif label=='swap': m[p],m[s]=m[s],m[p]
    elif label=='new_failed': m[p]='failed'
    else: m[p]='skipped'
    probes['missing_added_swap'][label]=ch.outcome_identity(m,base['outcomes'])[0]
dup=HERE/'duplicate.xml'; dup.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="p"/></testsuite></testsuites>')
probes['duplicate']=ch.junit_integrity(dup,{'passed':2,'failed':0,'skipped':0,'errors':0})
# Joint baseline/current outcome swap preserves every category count and failure ID.
import xml.etree.ElementTree as ET
tree=ET.parse(bx)
cases=list(tree.getroot().iter('testcase'))
pass_case=next(c for c in cases if not any(t.tag in ('failure','error','skipped') for t in c))
skip_case=next(c for c in cases if any(t.tag=='skipped' for t in c))
pass_id=pass_case.get('classname','')+'::'+pass_case.get('name','')
skip_id=skip_case.get('classname','')+'::'+skip_case.get('name','')
skip_child=next(c for c in skip_case if c.tag=='skipped')
skip_case.remove(skip_child); pass_case.append(skip_child)
tampered_xml=HERE/'joint_tamper.xml'; tree.write(tampered_xml,encoding='utf-8')
tampered_map=base['outcomes'].copy(); tampered_map[pass_id]='skipped'; tampered_map[skip_id]='passed'
probes['joint_baseline_tamper']={'changed_ids':[pass_id,skip_id], 'baseline_integrity':ch.junit_integrity(tampered_xml,ch.pytest_counts(bl))['ok'], 'current_integrity':ch.junit_integrity(tampered_xml,ch.pytest_counts(nl))['ok'], 'baseline_bound':ch.junit_outcomes(tampered_xml)==tampered_map, 'outcome_identity':ch.outcome_identity(ch.junit_outcomes(tampered_xml),tampered_map)[0], 'same_accepted_failure_ids':ch.failed_ids(nl)==ch.failed_ids(EV/'phase2ops_r6/phase1_full.log'), 'original_baseline_equal':tampered_map==base['outcomes']}
probes['phase1_exit_ignored']={'actual_exit':1, 'hypothetical_exit':3, 'predicate_same_for_both':True}
with zipfile.ZipFile(EV/'phase2close-candidate-20261008-f.zip') as z:
    accepted=z.read('scripts/phase2d_regression.py'); ini=z.read('scripts/phase2d_pytest.ini')
scope=ch.phase1_scope_check(TREE,EV/'phase2close-candidate-20261008-f.zip')
frozen=Path(r'C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip')
with zipfile.ZipFile(frozen) as z:
    fn=[n for n in z.namelist() if not n.endswith('/') and n not in ('MANIFEST.json','GIT_HEAD.txt','GIT_STATUS.txt','GIT_DIFF.patch') and not n.startswith('evidence/')]
    frozen_info={'hash':sha(frozen.read_bytes()), 'entries':len(fn), 'live_bad':[n for n in fn if not (TREE/n).is_file() or (TREE/n).read_bytes()!=z.read(n)]}
summary=json.loads((EV/'phase2oq/chain9/chain_summary.json').read_text())
result={'subject':fi,'previous':ei,'added':sorted(set(f)-set(e)),'removed':sorted(set(e)-set(f)),'changed':sorted(k for k in f.keys()&e.keys() if f[k]!=e[k]),'head':subprocess.run(['git','-C',str(TREE),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip(),'frozen':frozen_info,'closure_hash':sha((EV/'phase2close-candidate-20261008-f.zip').read_bytes()),'round7_hash':sha((EV/'phase2ops-candidate-20261008-r6.zip').read_bytes()),'baseline':xml_info(bx,bl),'chain_xml':xml_info(nx,nl),'chain_identity':ch.outcome_identity(ch.junit_outcomes(nx),base['outcomes']),'baseline_runner_hash':base['runner_sha256']==sha(accepted),'baseline_argv':base['argv'],'current_runner_argv_match':ch.runner_argv((TREE/'scripts/phase2d_regression.py').read_text())==ch.runner_argv(accepted.decode())+[ch.OQ_EXTRA_IGNORE],'ini_match':(TREE/'scripts/phase2d_pytest.ini').read_bytes()==ini,'scope':scope,'chain_gates':{k:{'PASS':v.get('PASS'),'exit':v.get('exit')} for k,v in summary['gates'].items()},'chain_all_pass':summary['ALL_PASS'],'probes':probes}
(HERE/'reviewer_results.json').write_text(json.dumps(result,indent=2,default=str))
print(json.dumps({k:v for k,v in result.items() if k not in ('added','scope','baseline_argv')},indent=2,default=str))
