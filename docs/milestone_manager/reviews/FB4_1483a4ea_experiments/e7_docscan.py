"""FB4 e7: scan every docs/**/*.md line of the candidate tree with model.find_secret; report hit count and examples."""
import sys, pathlib, collections, re
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import model as M
root = pathlib.Path(sys.argv[1]) / "docs"
files = sorted(root.rglob("*.md"))
total = hits = 0; by = collections.Counter(); ex = []
idhits = []
for f in files:
    for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip(): continue
        total += 1
        r = M.find_secret(line)
        if r:
            hits += 1; by[r] += 1; ex.append((str(f.relative_to(root)), n, r, line.strip()[:160]))
            if re.search(r"\b[A-Z][A-Z0-9]*-(?:[A-Z0-9]+-)*(?:PASSWORD|TOKEN|SECRET|KEY)\b|\b(?:PASSWORD|TOKEN|SECRET)-[A-Z]", line):
                idhits.append(ex[-1])
print(f"files={len(files)} nonblank_lines={total} hits={hits} rate={hits/total:.4%}")
print(dict(by))
for e in ex: print("HIT", e)
print("ID-LIKE HITS", len(idhits))
for e in idhits: print("ID ", e)
