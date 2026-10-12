import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[3]
tree = root / 'uri-agent'
ev = root / 'evidence'
b = ev / 'phase2close-candidate-20261008-b.zip'
a = ev / 'phase2close-candidate-20261008-a.zip'
r7 = ev / 'phase2ops-candidate-20261008-r6.zip'
frozen = root.parent / 'uri-phase1-integration/uri-agent/work/c1/checkpoints/final-closure-20261005-phase1.zip'
for p in (b, a, r7, frozen):
    print('SHA', p.name, hashlib.sha256(p.read_bytes()).hexdigest())
with ZipFile(b) as zb, ZipFile(a) as za, ZipFile(r7) as zr, ZipFile(frozen) as zf:
    meta = {'GIT_HEAD.txt', 'GIT_STATUS.txt', 'GIT_DIFF.patch', 'MANIFEST.json'}
    m = json.loads(zb.read('MANIFEST.json'))
    names = set(zb.namelist()) - meta
    print('MANIFEST', len(m), len(names), 'names_equal', set(m) == names,
          'bad_hashes', [n for n, h in m.items() if hashlib.sha256(zb.read(n)).hexdigest() != h])
    bt = {n for n in names if not n.startswith('evidence/')}
    be = names - bt
    print('B_COUNTS', len(bt), len(be))
    print('RUN5_EMBEDDED_DIFFERENT', [n for n in sorted(be) if n.startswith('evidence/run5/') and
          ((ev / 'phase2close/run5' / n.removeprefix('evidence/run5/')).read_bytes() != zb.read(n))])
    print('LIVE_MISSING', [n for n in sorted(bt) if not (tree / n).is_file()])
    print('LIVE_DIFFERENT', [n for n in sorted(bt) if (tree / n).is_file() and (tree / n).read_bytes() != zb.read(n)])
    at = {n for n in za.namelist() if n not in meta and not n.startswith('evidence/')}
    print('VS_A_ADDED', sorted(bt-at))
    print('VS_A_REMOVED', sorted(at-bt))
    print('VS_A_CHANGED', sorted(n for n in bt & at if zb.read(n) != za.read(n)))
    rt = {n for n in zr.namelist() if n not in meta and not n.startswith('evidence/')}
    print('VS_R7_ADDED', sorted(bt-rt))
    print('VS_R7_REMOVED', sorted(rt-bt))
    print('VS_R7_CHANGED', sorted(n for n in bt & rt if zb.read(n) != zr.read(n)))
    ft = {n for n in zf.namelist() if n not in meta and not n.endswith('/')}
    print('FROZEN', len(ft), 'missing', [n for n in sorted(ft) if not (tree / n).is_file()],
          'different', [n for n in sorted(ft) if (tree / n).is_file() and (tree / n).read_bytes() != zf.read(n)])
