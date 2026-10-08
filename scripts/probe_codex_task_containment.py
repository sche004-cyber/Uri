"""Harmless native sandbox qualification probe; never a provider/model task.

Touches only URI-owned marker files. Uses per-invocation CLI configuration,
never user config, credentials, project permissions or native provider sign-in.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / 'scratch' / 'codex_containment_probe'
    workspace = base / 'workspace'
    workspace.mkdir(parents=True, exist_ok=True)
    sentinel = base / 'protected.txt'
    if not sentinel.exists():
        sentinel.write_text('URI disposable protected marker', encoding='utf-8')
    probe = workspace / 'read_write_probe.py'
    probe.write_text('''import json
from pathlib import Path
p = Path.cwd()
results = {}
for name, operation in [
    ('inside_write', lambda: (p / 'inside_unelevated.txt').write_text('probe')),
    ('outside_read', lambda: (p.parent / 'protected.txt').read_text()),
    ('outside_write', lambda: (p.parent / 'outside_unelevated.txt').write_text('probe')),
]:
    try:
        operation()
        results[name] = 'allowed'
    except (PermissionError, OSError):
        results[name] = 'denied'
print(json.dumps(results))
''', encoding='utf-8')
    paths = {':root': 'deny', ':minimal': 'read', workspace.as_posix(): 'write',
             Path(sys.executable).parent.as_posix(): 'read'}
    profile = '{' + ','.join(json.dumps(k) + '=' + json.dumps(v) for k, v in paths.items()) + '}'
    command = [shutil.which('codex'), 'sandbox', '-C', str(workspace),
               '-P', 'uri_qualification', '-c', 'windows.sandbox="unelevated"',
               '-c', 'permissions.uri_qualification.filesystem=' + profile,
               '-c', 'permissions.uri_qualification.network.enabled=false',
               sys.executable, str(probe)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    evidence = {'mode': 'unelevated', 'exit_code': result.returncode,
                'stdout': result.stdout, 'stderr': result.stderr, 'profile': paths,
                'outside_write_exists': (base / 'outside_unelevated.txt').exists(),
                'provider_task': False, 'qualification_granted': False}
    destination = root / 'docs' / 'plans' / 'HARNESS_CONNECTIONS_CONSOLE_EVIDENCE' / 'codex_unelevated_probe.json'
    destination.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
