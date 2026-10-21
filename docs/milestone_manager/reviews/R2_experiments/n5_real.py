from common import *
import re
P = Path("D:/uri-dev/uri-p0-audit")
m = new()
r1 = importers.import_decisions(m, P/"decisions.md", "8e1d6324"); r2 = importers.import_register(m, P/"developmental.md", "8e1d6324")
print({k:v for k,v in r1.items() if k!="source"}); print({k:v for k,v in r2.items() if k!="source"})
# line-level scan of both files with find_secret to look for false positives anywhere
for f in ("decisions.md","developmental.md"):
    for i,l in enumerate((P/f).read_text(encoding="utf-8").splitlines(),1):
        h = model.find_secret(l)
        if h: print("HIT", f, i, h, l[:140])
r3 = importers.import_decisions(m, P/"decisions.md", "8e1d6324"); r4 = importers.import_register(m, P/"developmental.md", "8e1d6324")
print("reimport", {k:r3[k] for k in ("recorded","revised","unchanged")}, {k:r4[k] for k in ("recorded","revised","unchanged") if k in r4})
print("verify", m.store.verify()["ok"], "events", m.projection()["events"], m.projection()["integrity_warnings"])
