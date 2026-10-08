"""Independent, synthetic client. No real identity, credential, or provider calls."""
import hashlib
import json
import pathlib
import shutil
import sys
import uuid

ROOT = pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent')
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from uri_supervisor_bridge.qualification import (RecordTrust, build_record, compose_client,
    evidence_dir, qualification_dir, write_record)
from uri_core.core.runtime_identity import FixtureGuard
from types import SimpleNamespace

state = HERE / 'probe_state'
state.mkdir(exist_ok=True)
fake = ROOT / 'tests/phase2b/helpers/fake_harness.py'

def make(label, *, native=False, models=(None,), evidence_models=None, now=None):
    root = state / label
    if root.exists(): shutil.rmtree(root)
    root.mkdir()
    key = Ed25519PrivateKey.generate()
    trust = RecordTrust.from_private_key(str(uuid.uuid4()), key)
    ev = root / 'input.json'
    data = {'provider': 'codex_cli', 'ok': True, 'version': '0.0.1', 'model': 'model-a',
            'executable_sha256': hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest()} if native else {'provider':'claude_code','fixture':True}
    if evidence_models is not None: data['models'] = evidence_models
    ev.write_text(json.dumps(data))
    rec = build_record(client_root=root, client_id=trust.client_id, signer=key,
        provider='codex_cli' if native else 'claude_code', level='NATIVE_QUALIFIED' if native else 'FIXTURE_ONLY',
        spec_id='codex_cli' if native else 'generic_ndjson', executable=sys.executable,
        executable_args=[str(fake)], version='0.0.1', models=list(models), evidence_path=ev,
        qualified_by='independent round3 synthetic probe', now=now)
    path = write_record(root, rec)
    return root, rec, trust, path

clock = {'t':1001}
root, rec, trust, path = make('expiry', now=1000)
comp = compose_client(root, trust=trust, allow_fixture=True, clock=lambda: clock['t'])
print('expiry_initial', comp.qualified(), comp.executors['claude_code'].revalidate())
clock['t'] = rec['expires_at']
print('expiry_after', comp.executors['claude_code'].revalidate(), next(x for x in comp.registry.discover() if x['harness_id']=='claude_code')['usable'])

for label, mutation in [('delete_evidence','evidence'),('delete_record','record'),('swap_record','swap')]:
    root, rec, trust, path = make(label)
    comp = compose_client(root, trust=trust, allow_fixture=True)
    if mutation == 'evidence': (evidence_dir(root)/rec['evidence_file']).unlink()
    elif mutation == 'record': path.unlink()
    else:
        (root/'input2.json').write_text(json.dumps({'provider':'claude_code','fixture':True,'note':'new run'}))
        key = Ed25519PrivateKey.generate()
        # Mutation of the record bytes suffices to exercise the same-record pin; no real signer is used.
        path.write_text(path.read_text().replace('independent round3 synthetic probe','other run'))
    print(label, comp.executors['claude_code'].revalidate(), next(x for x in comp.registry.discover() if x['harness_id']=='claude_code')['usable'])

root, rec, trust, path = make('extra_models', native=True, models=('model-a','model-b'))
comp = compose_client(root, trust=trust, auth_probe=lambda _:True)
print('native_extra_models', comp.report[0]['status'], comp.report[0]['reason'])

root, rec, trust, path = make('bad_fixture_evidence', evidence_models=42)
try:
    comp = compose_client(root, trust=trust, allow_fixture=True)
    print('bad_fixture_evidence', comp.report[0]['status'], comp.report[0]['reason'])
except Exception as exc:
    print('bad_fixture_evidence_exception', type(exc).__name__, str(exc))

class Phase2FixtureGuard(FixtureGuard):
    _NULL = pathlib.Path(__import__('os').devnull).resolve()
    def check_path(self, value, write=False):
        import os
        if not isinstance(value, int) and value is not None and pathlib.Path(os.fsdecode(value)).resolve() == self._NULL:
            return
        return super().check_path(value, write)

guard = Phase2FixtureGuard(SimpleNamespace(data={'state_root':str(state/'guard_client'),'source_root':str(ROOT)}))
for name, value in [('null', __import__('os').devnull), ('external', str(state.parent/'external.txt'))]:
    try:
        guard.check_path(value, write=True)
        print('guard', name, 'allowed')
    except Exception as exc:
        print('guard', name, type(exc).__name__, str(exc))
