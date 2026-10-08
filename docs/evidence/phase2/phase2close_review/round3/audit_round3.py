import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[3]
tree = root / 'uri-agent'
ev = root / 'evidence'
c = ev / 'phase2close-candidate-20261008-c.zip'
b = ev / 'phase2close-candidate-20261008-b.zip'
r7 = ev / 'phase2ops-candidate-20261008-r6.zip'
frozen = root.parent / 'uri-phase1-integration/uri-agent/work/c1/checkpoints/final-closure-20261005-phase1.zip'
for p in (c, b, r7, frozen):
    print('SHA', p.name, hashlib.sha256(p.read_bytes()).hexdigest())
with ZipFile(c) as zc, ZipFile(b) as zb, ZipFile(frozen) as zf:
    meta = {'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch', 'MANIFEST.json'}
    m = json.loads(zc.read('MANIFEST.json'))
    names = set(zc.namelist()) - meta
    print('MANIFEST', len(m), len(names), 'names_equal', set(m) == names,
          'bad_hashes', [n for n, h in m.items() if hashlib.sha256(zc.read(n)).hexdigest() != h])
    ct = {n for n in names if not n.startswith('evidence/')}
    ce = names - ct
    print('C_COUNTS', len(ct), len(ce))
    print('RUN6_EMBEDDED_DIFFERENT', [n for n in sorted(ce) if n.startswith('evidence/run6/') and
          ((ev / 'phase2close/run6' / n.removeprefix('evidence/run6/')).read_bytes() != zc.read(n))])
    print('LIVE_MISSING', [n for n in sorted(ct) if not (tree / n).is_file()])
    print('LIVE_DIFFERENT', [n for n in sorted(ct) if (tree / n).is_file() and (tree / n).read_bytes() != zc.read(n)])
    bt = {n for n in zb.namelist() if n not in meta and not n.startswith('evidence/')}
    print('VS_B_ADDED', sorted(ct-bt))
    print('VS_B_REMOVED', sorted(bt-ct))
    print('VS_B_CHANGED', sorted(n for n in ct & bt if zc.read(n) != zb.read(n)))
    ft = {n for n in zf.namelist() if n not in meta and not n.endswith('/')}
    print('FROZEN', len(ft), 'missing', [n for n in sorted(ft) if not (tree / n).is_file()],
          'different', [n for n in sorted(ft) if (tree / n).is_file() and (tree / n).read_bytes() != zf.read(n)])
