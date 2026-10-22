from common import *
src = Path("D:/uri-dev/uri-p0-audit/decisions.md"); dev = Path("D:/uri-dev/uri-p0-audit/developmental.md")
import hashlib; h0 = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (src, dev)}
m = new()
a = importers.import_register(m, dev, "8e1d6324"); print("dev first: rec", a["recorded"], "secret", a["skipped_secret"], "bad", a.get("skipped_bad_id"), "coll", len(a.get("collisions", [])))
d = importers.import_decisions(m, src, "8e1d6324"); print("dec first: rec", d["recorded"], "secret", d["skipped_secret"], "coll", len(d["collisions"]), "sup", d["supersessions"])
b = importers.import_register(m, dev, "8e1d6324"); e = importers.import_decisions(m, src, "8e1d6324")
print("re-import dev: rec", b["recorded"], "rev", b["revised"], "unch", b["unchanged"], "| dec: rec", e["recorded"], "rev", e["revised"], "unch", e["unchanged"], "coll", len(e["collisions"]))
p = m.projection(); print("integrity", p["integrity_errors"], p["integrity_warnings"], "verify", m.store.verify()["ok"])
print("sources unchanged:", all(hashlib.sha256(p_.read_bytes()).hexdigest() == h for p_, h in h0.items()))
