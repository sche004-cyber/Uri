import hashlib, json, pathlib, zipfile

base = pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a')
tree = base / 'uri-agent'
evidence = base / 'evidence'
candidate = evidence / 'phase2d-candidate-20261007-r1.zip'
with zipfile.ZipFile(candidate) as z:
    manifest = json.loads(z.read('MANIFEST.json'))
    bad_archive, bad_live = [], []
    for rel, expected in manifest.items():
        archived = hashlib.sha256(z.read(rel)).hexdigest()
        if archived != expected: bad_archive.append(rel)
        live = (base / rel) if rel.startswith('evidence/') else (tree / rel)
        if not live.is_file() or hashlib.sha256(live.read_bytes()).hexdigest() != expected:
            bad_live.append(rel)
    extras = sorted(set(z.namelist()) - set(manifest) - {'MANIFEST.json', 'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch'})
print('candidate_entries', len(manifest), 'tree_entries', sum(not p.startswith('evidence/') for p in manifest), 'evidence_entries', sum(p.startswith('evidence/') for p in manifest), 'archive_bad', bad_archive, 'live_bad', bad_live, 'extras', extras)
for label, path in [('phase2c', evidence/'phase2c-candidate-20261007.zip'), ('phase1', pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip'))]:
    print(label, path.exists(), hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)
    if not path.exists(): continue
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        print(label, 'count', len(names), 'first', names[:4])
        same, changed, missing = 0, [], []
        for rel in names:
            if rel.endswith('/') or rel in ('MANIFEST.json', 'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch'): continue
            live = tree / rel
            if not live.is_file(): missing.append(rel)
            elif hashlib.sha256(live.read_bytes()).digest() == hashlib.sha256(z.read(rel)).digest(): same += 1
            else: changed.append(rel)
        print(label, 'same', same, 'changed', changed, 'missing', missing)
