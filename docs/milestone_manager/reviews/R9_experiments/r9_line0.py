from common import *
import io, collections
def openc(m): return [c["type"] for c in m.projection()["conflicts"] if not c["resolved"]]
w = Path(tempfile.mkdtemp()); reg = w/"r.md"
rows = "".join(f"| CAP-{i} | c{i} | RED |\n" for i in range(1, 6))
reg.write_text("# Reg X\n\n## B. Capabilities\n\n| ID | Capability | Status |\n|---|---|---|\n" + rows, encoding="utf-8")
def setup(kind):
    m = new(); ia = m.store.anchors_path.read_bytes()
    if kind == "single": m.create_milestone("MM-A","A")
    else: importers.import_register(m, reg)
    m.store.anchors_path.write_bytes(ia)  # first anchor refresh failed (§17)
    return m
for kind in ("single", "batch"):
    m = setup(kind); line0 = m.store.segment_path.read_bytes().split(b"\n")[0]
    p = m.projection(); print(kind, "applied before cut: milestones", len(p.get("milestones",{})), "records", len(p.get("records",{})), "warn", p["integrity_warnings"][:1])
    res = collections.Counter(); ex = {}
    for off in list(range(1, len(line0), max(1, len(line0)//40))) + [len(line0)-1]:
        m = setup(kind); m.store.segment_path.write_bytes(line0[:off])
        o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o)
        p = m.projection(); key = (rc, tuple(openc(m)), len(p.get("milestones",{})) + len(p.get("records",{})), m.store.verify()["ok"])
        res[key] += 1; ex.setdefault(key, (off, o.getvalue().replace("\n"," ")[:220]))
    for k, n in res.items(): print("  rc=%s open_conflicts=%s entities_after=%s verify_ok=%s : %d offsets" % (*k, n), "e.g.", ex[k])
    # status/verify before recover on a cut file
    m = setup(kind); m.store.segment_path.write_bytes(line0[:len(line0)//2])
    o = io.StringIO(); rc = cli.run(["--home", str(m.home), "status"], out=o); print("  status before recover rc", rc, o.getvalue().replace("\n"," ")[:300])
