import hashlib, json, pathlib, zipfile, subprocess

root=pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent')
ev=root.parent/'evidence'
review=ev/'phase2d_review'
paths=[('candidate',ev/'phase2d-candidate-20261007.zip'),('phase2c',ev/'phase2c-candidate-20261007.zip'),('phase1',pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip'))]
for name,path in paths:
    print(name,'sha256',hashlib.sha256(path.read_bytes()).hexdigest())
    with zipfile.ZipFile(path) as z:
        names=z.namelist(); print(name,'entries',len(names),'first',names[:8])
        if name=='candidate':
            m=json.loads(z.read('MANIFEST.json'))
            print('manifest type',type(m).__name__, 'sample',str(m)[:1200])
            (review/'candidate_manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
            entries=m.items() if isinstance(m,dict) else [(e.get('path') or e.get('name'),e.get('sha256')) for e in m]
            problems=[]
            for rel,expected in entries:
                data=z.read(rel)
                live=(root.parent/rel) if rel.startswith('evidence/') else (root/rel)
                if not live.exists(): problems.append((rel,'missing live')); continue
                h=hashlib.sha256(data).hexdigest()
                if expected and h!=expected:problems.append((rel,'manifest hash',h,expected))
                if live.read_bytes()!=data: problems.append((rel,'live mismatch'))
            print('candidate entries checked',len(entries),'problems',problems[:30], 'total',len(problems))
        if name=='phase1':
            problems=[]; checked=0
            for rel in names:
                if rel.endswith('/') or rel in ('GIT_HEAD.txt','GIT_STATUS.txt','GIT_DIFF.patch'):continue
                live=root/rel
                if not live.exists():problems.append((rel,'missing'));continue
                checked+=1
                if live.read_bytes()!=z.read(rel):problems.append((rel,'mismatch'))
            print('phase1 checked',checked,'problems',problems[:40],'total',len(problems))
