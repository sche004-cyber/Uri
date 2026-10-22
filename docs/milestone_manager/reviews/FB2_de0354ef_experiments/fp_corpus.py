import sys, glob, os, collections
src = sys.argv[1]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.model import find_secret
files = glob.glob(os.path.join(src, "docs", "**", "*.md"), recursive=True) + glob.glob(os.path.join(sys.argv[2], "*.md"))
n = 0; hits = []
for f in files:
    for i, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
        n += 1
        h = find_secret(line)
        if h: hits.append((os.path.relpath(f, src) if f.startswith(src) else os.path.basename(f), i, h, line.strip()[:150]))
print("files", len(files), "lines", n, "hits", len(hits))
for h in hits: print(h)
