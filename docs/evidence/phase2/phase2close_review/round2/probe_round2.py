import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[3] / 'uri-agent'
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'tests'))

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, root / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

acc = load('acc_probe', 'scripts/phase2close_acceptance.py')
pl = load('pl_probe', 'scripts/phase2close_powerloss_harness.py')
base = root / 'work/c1/round2-review-probe'
client = base / 'client'
(client / 'control').mkdir(parents=True, exist_ok=True)
(base / 'campaign.json').write_text(json.dumps({'base': str(base), 'client_root': str(client), 'gates': []}))
fake = {'CODEX_API_KEY': 'synthetic', 'codex_api_key': 'synthetic', 'CLAUDE_CODE_OAUTH_TOKEN': 'synthetic',
        'claude_code_oauth_token': 'synthetic', 'OPENAI_API_KEY': 'synthetic', 'ANTHROPIC_API_KEY': 'synthetic',
        'SOME_TOKEN': 'synthetic', 'OTHER_SECRET': 'synthetic', 'API_PASSWORD': 'synthetic',
        'CODEX_HOME': 'wrong-home', 'PATH': 'synthetic-path'}
env, removed = acc.probe_environment(client, fake)
print('ENV_REMOVED', removed)
print('ENV_RETAINED', sorted(env))
print('PINNED_CODEX_HOME', env.get('CODEX_HOME') == str(client / 'home/.codex'))
original = dict(os.environ)
os.environ['CODEX_API_KEY'] = 'synthetic-probe-only'
seen = {}
def direct_probe(provider, model, evidence):
    seen['direct_token'] = 'CODEX_API_KEY' in os.environ
    seen['home'] = os.environ.get('CODEX_HOME')
    return {'ok': True, 'status': 'OK', 'executable': 'codex', 'version': '0.0.0'}
acc._load_p2c = lambda: SimpleNamespace(direct_probe=direct_probe)
from uri_supervisor_bridge import qualification as q
prior_auth = q.native_auth_probe
def auth(provider, exe):
    seen['auth_token'] = 'CODEX_API_KEY' in os.environ
    return False
q.native_auth_probe = auth
try:
    rc = acc.qualify(SimpleNamespace(campaign=str(base), provider='codex_cli', model='synthetic'))
    print('QUALIFY_RC', rc, 'SEEN', seen, 'CALLER_RESTORED', os.environ.get('CODEX_API_KEY') == 'synthetic-probe-only')
    print('RECORD_EXISTS', (client / 'control/supervisor/qualification/codex_cli.json').exists())
finally:
    q.native_auth_probe = prior_auth
    os.environ.clear()
    os.environ.update(original)

full = {'label': 'VM_SERIES', 'synchronous': ['FULL'], 'power_method': {'power_off': 'Stop-VM'},
        'verdict': 'SERIES_ALL_PASS', 'iterations_requested': 200, 'iterations_run': 200,
        'passed': 0, 'failed': 200, 'lost_acknowledged_steps': 200}
control = {'label': 'VM_SERIES', 'synchronous': ['NORMAL'], 'power_method': {'power_off': 'Stop-VM'},
           'verdict': 'SERIES_ALL_PASS', 'iterations_run': 0, 'passed': 0, 'failed': 0,
           'lost_acknowledged_steps': 1}
print('ASSESS_INCONSISTENT', pl.assess(full, control))
