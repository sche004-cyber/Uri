from common import *
import hashlib
P = Path("D:/uri-dev/uri-p0-audit")
h = lambda: {f: hashlib.sha256((P/f).read_bytes()).hexdigest()[:16] for f in ("decisions.md","developmental.md")}
before = h(); print("hashes before", before)
m = new()
r1 = importers.import_decisions(m, P/"decisions.md", "8e1d6324"); r2 = importers.import_register(m, P/"developmental.md", "8e1d6324")
print("dec", {k:v for k,v in r1.items() if k not in ("source",)}); print("reg", {k:v for k,v in r2.items() if k not in ("source",)})
for f in ("decisions.md","developmental.md"):
    for i,l in enumerate((P/f).read_text(encoding="utf-8").splitlines(),1):
        x = model.find_secret(l)
        if x: print("HIT", f, i, x)
r3 = importers.import_decisions(m, P/"decisions.md", "8e1d6324"); r4 = importers.import_register(m, P/"developmental.md", "8e1d6324")
print("reimport dec", {k:r3.get(k) for k in ("recorded","revised","unchanged","collisions","skipped_secret","written")})
print("reimport reg", {k:r4.get(k) for k in ("recorded","revised","unchanged","collisions","skipped_secret","written")})
p = m.projection(); print("verify", m.store.verify()["ok"], "events", p.get("events"), "warn", p["integrity_warnings"], "errs", p["integrity_errors"])
print("hashes after", h(), "unchanged", h()==before)
