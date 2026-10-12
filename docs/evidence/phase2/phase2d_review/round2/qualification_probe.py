"""Independent synthetic attacks; never reads real identity or credential files."""
import hashlib, json, pathlib, shutil, sys, time, uuid
sys.path.insert(0, r'C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from uri_supervisor_bridge.qualification import (RecordTrust, build_record, write_record, load_records,
    compose_client, record_digest, qualification_dir, evidence_dir, revalidate, QualificationError,
    check_launch_chain, npm_codex_launch_chain)

base = pathlib.Path(__file__).parent / 'probe_state'
base.mkdir(exist_ok=True)
fake = pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\tests\phase2b\helpers\fake_harness.py')
def setup(label, level='FIXTURE_ONLY', models=(None,), now=None, ttl_s=30*24*3600):
    root = base/label
    if root.exists(): shutil.rmtree(root)
    root.mkdir()
    signer = Ed25519PrivateKey.generate(); cid = str(uuid.uuid4()); trust = RecordTrust.from_private_key(cid, signer)
    ev = root/'input.json'
    ev.write_text(json.dumps({'fixture':True,'provider':'claude_code'}))
    rec = build_record(client_root=root,client_id=cid,signer=signer,provider='claude_code',
        level=level,spec_id='generic_ndjson' if level=='FIXTURE_ONLY' else 'claude_code',
        executable=sys.executable,executable_args=[str(fake)],version='0.0.1',models=list(models),
        evidence_path=ev,qualified_by='independent probe',now=now,ttl_s=ttl_s)
    write_record(root,rec)
    return root,rec,trust,signer
def status(root,trust,now=None):
    c=compose_client(root,trust=trust,allow_fixture=True,now=now)
    return c.report[0]['status'],c.report[0]['reason'],c
def show(label,fn):
    try: print(label,fn())
    except Exception as e: print(label,'EXCEPTION',type(e).__name__,str(e))

root,rec,trust,key=setup('edit')
show('baseline',lambda: status(root,trust)[:2])
edited=dict(rec,models=[None,'new-model']);edited['record_sha256']=record_digest(edited)
write_record(root,edited)
show('digest_recomputed',lambda: status(root,trust)[:2])
other=Ed25519PrivateKey.generate(); body=json.dumps({k:v for k,v in edited.items() if k not in ('record_sha256','signature')},sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
edited['signature']=other.sign(body).hex();write_record(root,edited)
show('other_key_signature',lambda: status(root,trust)[:2])

root,rec,trust,key=setup('copy')
dest=base/'copy_dest'; shutil.rmtree(dest,ignore_errors=True)
shutil.copytree(root,dest)
othertrust=RecordTrust.from_private_key(str(uuid.uuid4()),Ed25519PrivateKey.generate())
show('copied_client',lambda: status(dest,othertrust)[:2])
show('copied_no_anchor',lambda: status(dest,None)[:2])

root,rec,trust,key=setup('evidence')
ev=evidence_dir(root)/rec['evidence_file']; ev.write_text('{"fixture":true,"provider":"claude_code","tampered":true}')
show('evidence_edited',lambda: status(root,trust)[:2])
ev.unlink();show('evidence_missing',lambda: status(root,trust)[:2])

root,rec,trust,key=setup('expire',now=int(time.time())-61,ttl_s=60)
show('expired_load',lambda: status(root,trust)[:2])
show('before_expiry_load',lambda: status(root,trust,now=rec['expires_at']-1)[:2])
c=compose_client(root,trust=trust,allow_fixture=True,now=rec['expires_at']-1)
show('after_expiry_cached_selectable',lambda: c.registry.selectable('claude_code')['usable'])

root,rec,trust,key=setup('postcompose')
c=compose_client(root,trust=trust,allow_fixture=True)
(evidence_dir(root)/rec['evidence_file']).unlink()
show('deleted_evidence_cached_selectable',lambda:c.registry.selectable('claude_code')['usable'])

root,rec,trust,key=setup('model')
rec['models']=[None,'untested-model']; rec['record_sha256']=record_digest(rec)
body=json.dumps({k:v for k,v in rec.items() if k not in ('record_sha256','signature')},sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
rec['signature']=key.sign(body).hex(); write_record(root,rec)
show('extra_model_same_key',lambda: status(root,trust)[:2])

root,rec,trust,key=setup('missing_pin')
rec['level']='NATIVE_QUALIFIED';rec['spec_id']='claude_code';rec['executable']='C:/missing/launcher.cmd';rec['pinned_files']={}
rec['record_sha256']=record_digest(rec)
body=json.dumps({k:v for k,v in rec.items() if k not in ('record_sha256','signature')},sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
rec['signature']=key.sign(body).hex();write_record(root,rec)
show('missing_chain',lambda: status(root,trust)[:2])

chain=base/'chain'; shutil.rmtree(chain,ignore_errors=True);chain.mkdir()
payload=chain/'payload.exe'; payload.write_bytes(b'original')
pins={str(payload):hashlib.sha256(payload.read_bytes()).hexdigest()}
show('chain_baseline',lambda:check_launch_chain(pins,{},environ={'PATH':str(chain)}) or 'PASS')
payload.write_bytes(b'replaced')
show('chain_replaced',lambda:check_launch_chain(pins,{},environ={'PATH':str(chain)}) or 'PASS')
payload.write_bytes(b'original')
node=chain/'node.exe'; node.write_bytes(b'node-original')
pins[str(node)]=hashlib.sha256(node.read_bytes()).hexdigest()
show('chain_path_baseline',lambda:check_launch_chain(pins,{'node':str(node)},environ={'PATH':str(chain)}) or 'PASS')
redirect=base/'redirect';shutil.rmtree(redirect,ignore_errors=True);redirect.mkdir()
(redirect/'node.exe').write_bytes(b'other')
show('chain_path_redirect',lambda:check_launch_chain(pins,{'node':str(node)},environ={'PATH':str(redirect)}) or 'PASS')
real=shutil.which('codex')
if real and pathlib.Path(real).suffix.lower()=='.cmd':
    show('real_npm_chain',lambda: (lambda p,r:(len(p),list(r)))(*npm_codex_launch_chain(real)))

# Native-shaped record against the synthetic version-printing executable. This is not native provider qualification.
root=base/'native_auth';shutil.rmtree(root,ignore_errors=True);root.mkdir()
signer=Ed25519PrivateKey.generate();cid=str(uuid.uuid4());trust=RecordTrust.from_private_key(cid,signer)
ev=root/'native_evidence.json';ev.write_text(json.dumps({'provider':'codex_cli','ok':True,'version':'0.0.1',
    'model':'model-a','executable_sha256':hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest()}))
rec=build_record(client_root=root,client_id=cid,signer=signer,provider='codex_cli',level='NATIVE_QUALIFIED',
    spec_id='codex_cli',executable=sys.executable,executable_args=[str(fake)],version='0.0.1',
    models=['model-a','model-b'],evidence_path=ev,qualified_by='independent synthetic probe')
write_record(root,rec)
state={'auth':True};comp=compose_client(root,trust=trust,auth_probe=lambda _id:state['auth'])
show('native_evidence_one_model_record_two',lambda:(comp.report[0]['status'],comp.executors['codex_cli'].qualified_models))
show('auth_before_logout',lambda:comp.registry.selectable('codex_cli')['usable'])
state['auth']=False
show('auth_after_logout',lambda:comp.registry.selectable('codex_cli')['usable'])
