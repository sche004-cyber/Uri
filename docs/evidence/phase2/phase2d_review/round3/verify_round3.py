import hashlib
import json
import pathlib
import zipfile

base = pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a')
tree = base / 'uri-agent'
ev = base / 'evidence'
subject = ev / 'phase2d-candidate-20261007-r2.zip'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for name in ('phase2d-candidate-20261007.zip', 'phase2d-candidate-20261007-r1.zip',
             'phase2d-candidate-20261007-r2.zip', 'phase2c-candidate-20261007.zip'):
    print('sha', name, sha(ev / name))
with zipfile.ZipFile(subject) as z:
    manifest = json.loads(z.read('MANIFEST.json'))
    archive_bad, live_bad = [], []
    for rel, digest in manifest.items():
        if hashlib.sha256(z.read(rel)).hexdigest() != digest:
            archive_bad.append(rel)
        path = (base if rel.startswith('evidence/') else tree) / rel
        if not path.is_file() or sha(path) != digest:
            live_bad.append(rel)
    print('candidate', len(manifest), 'tree', sum(not x.startswith('evidence/') for x in manifest),
          'external', sum(x.startswith('evidence/') for x in manifest), 'archive_bad', archive_bad,
          'live_bad', live_bad, 'extras', sorted(set(z.namelist()) - set(manifest) -
          {'MANIFEST.json', 'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch'}))
for label, path in [('phase1', pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip')),
                    ('phase2c', ev / 'phase2c-candidate-20261007.zip')]:
    print(label, 'sha', sha(path))
    with zipfile.ZipFile(path) as z:
        same, changed, missing = 0, [], []
        for rel in z.namelist():
            if rel.endswith('/') or rel in {'MANIFEST.json', 'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch'} or rel.startswith('evidence/'):
                continue
            current = tree / rel
            if not current.is_file():
                missing.append(rel)
            elif sha(current) == hashlib.sha256(z.read(rel)).hexdigest():
                same += 1
            else:
                changed.append(rel)
        print(label, 'same', same, 'changed', changed, 'missing', missing)
