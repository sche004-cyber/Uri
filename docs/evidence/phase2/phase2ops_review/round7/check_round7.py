import asyncio
import hashlib
import json
import pathlib
import re
import sys
import zipfile

tree = pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent')
ev = tree.parent / 'evidence'
new = ev / 'phase2ops-candidate-20261008-r6.zip'
old = ev / 'phase2ops-candidate-20261007-r5.zip'
sha = lambda b: hashlib.sha256(b).hexdigest()

with zipfile.ZipFile(new) as z, zipfile.ZipFile(old) as oz:
    print('new_zip', sha(new.read_bytes()), 'old_zip', sha(old.read_bytes()))
    print('members', len(z.namelist()), len(oz.namelist()))
    print('first', z.namelist()[:8])
    manifests = [n for n in z.namelist() if n.endswith('MANIFEST.json')]
    print('manifest_names', manifests)
    print('manifest_head', z.read(manifests[0])[:300])
    manifest = json.loads(z.read('MANIFEST.json'))
    bad_archive = [n for n, h in manifest.items() if n not in z.namelist() or sha(z.read(n)) != h]
    bad_live = [n for n, h in manifest.items() if n.startswith('evidence/') is False and
                (not (tree/n).is_file() or sha((tree/n).read_bytes()) != h)]
    bad_evidence = [n for n, h in manifest.items() if n.startswith('evidence/') and
                    (not (ev/n.removeprefix('evidence/')).is_file() or sha((ev/n.removeprefix('evidence/')).read_bytes()) != h)]
    print('manifest_counts', len(manifest), 'archive_bad', bad_archive, 'tree_bad', bad_live, 'evidence_bad', bad_evidence)
    changed = []
    for n in sorted(set(z.namelist()) | set(oz.namelist())):
        if n in ('MANIFEST.json', 'GIT_STATUS.txt'):
            continue
        a = z.read(n) if n in z.namelist() else None
        b = oz.read(n) if n in oz.namelist() else None
        if a != b:
            changed.append(n)
    print('changed_members', json.dumps(changed))

checkpoint = pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip')
print('phase1_checkpoint', checkpoint.exists(), sha(checkpoint.read_bytes()) if checkpoint.exists() else None)
if checkpoint.exists():
    with zipfile.ZipFile(checkpoint) as z:
        items = [n for n in z.namelist() if not n.startswith('GIT_')]
        bad = [n for n in items if not (tree/n).is_file() or (tree/n).read_bytes() != z.read(n)]
        print('phase1_files', len(items), 'mismatches', bad)

sys.path.insert(0, str(tree))
from uri_supervisor_bridge.refusal_log import RefusalLog, KNOWN_CODES, in_scope, refusal_line, route_shape

print('known_count', len(KNOWN_CODES))
found = set()
for f in ('uri_core/app/client_routes.py', 'uri_core/core/client_service.py', 'uri_core/core/client_pairing.py',
          'uri_core/core/client_execution_control.py', 'uri_core/core/client_state_ports.py',
          'uri_core/core/paired_coordinator.py'):
    s = (tree/f).read_text(encoding='utf-8')
    found |= set(re.findall(r'(?:ClientControlError|PairingError|ExecutionControlError|StatePortError)\("([A-Z][A-Z0-9_]+)"', s))
    found |= set(re.findall(r'detail="([A-Z][A-Z0-9_]+)"', s))
    found |= set(re.findall(r'content=\{"detail": "([A-Z][A-Z0-9_]+)"', s))
print('source_codes', len(found), 'missing', sorted(found-set(KNOWN_CODES)), 'extra', sorted(set(KNOWN_CODES)-found))
for detail in ('SESSION_SCOPE', 'SK_LIVE_SECRET_TOKEN', 'BEARER_ABC', 'SESSION_SCOPE_EXTRA'):
    print('detail', detail, refusal_line('BEARERX', '/client/v1/turns/sk-private/approval?token=x', 403, json.dumps({'detail': detail}).encode()))
print('bad_status', refusal_line('POST', '/client/v1/session', '9999', b'{}'))
for path in ('/client/v1', '/client/v1/turns', '/client/v1evil/x', '/client/v10/x'):
    print('scope', path, in_scope(path), route_shape(path))

async def probe(path, status, body_chunks):
    logged, sent = [], []
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': status, 'headers': []})
        for i, chunk in enumerate(body_chunks):
            await send({'type': 'http.response.body', 'body': chunk, 'more_body': i < len(body_chunks)-1})
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(m):
        sent.append(m)
    await RefusalLog(app, sink=logged.append)({'type': 'http', 'method': 'POST', 'path': path}, receive, send)
    return logged, len(sent)

print('asgi_in', asyncio.run(probe('/client/v1/session', 403, [b'{"detail":"SESSION_SCOPE"}'])))
print('asgi_out', asyncio.run(probe('/client/v1evil/x', 403, [b'{"detail":"SESSION_SCOPE"}'])))
print('asgi_ok', asyncio.run(probe('/client/v1/session', 200, [b'{"detail":"SESSION_SCOPE"}'])))
print('asgi_long', asyncio.run(probe('/client/v1/session', 403, [b'x'*5000, b'y'*5000])))

for i in range(1, 11):
    p = ev/'phase2ops_r6'/f'ui_bridge_live_{i}.json'
    d = json.loads(p.read_text(encoding='utf-8'))
    rec = d['execution_records']
    tuples = sorted((r.get('state'), r.get('code'), r.get('operation_owner') == r.get('execution_id')) for r in rec)
    stdout = (ev/'phase2ops_r6'/f'ui_bridge_stdout_{i}.txt').read_text(encoding='utf-8')
    print('live', i, 'exit', d.get('exit'), 'stdout_pass', 'All tests passed!' in stdout,
          'records', tuples)
native = json.loads((ev/'phase2ops_r6'/'codex_cli_lifecycle_000547.json').read_text(encoding='utf-8'))
print('native', native.get('direct_probe'), native.get('live_auth_status_probe'),
      native.get('qualification_decision'), [(r.get('name'),r.get('state'),r.get('code')) for r in native.get('runs',[])])
