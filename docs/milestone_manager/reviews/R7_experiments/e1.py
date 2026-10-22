from common import *
import io
w = Path(tempfile.mkdtemp()); reg = w/"r.md"
reg.write_text("# Reg X\n\n## B. Capabilities\n\n| ID | Capability | Status |\n|---|---|---|\n| CAP-1 | a | RED |\n| CAP-2 | b | RED |\n| CAP-3 | c | RED |\n", encoding="utf-8")
def openal(m): return [(c["type"],c["kind"]) for c in m.projection()["conflicts"] if not c["resolved"]]
for torn_bytes in (b'{"x', None):
    m = new(); init_anchors = m.store.anchors_path.read_bytes()
    importers.import_register(m, reg)           # first command: complete multi-event batch, APPLIED
    m.store.anchors_path.write_bytes(init_anchors)  # process killed before anchor refresh (count 0) -- realistic (h5)
    p = m.projection(); print("applied records before:", sorted(p["records"]), "events", len(m.store.read_all()[0].events))
    lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
    cut = lines[0] + b"\n" + (torn_bytes or b"")   # later loss: complete lines 2..n deleted
    m.store.segment_path.write_bytes(cut)
    p = m.projection(); print(" after cut: records", sorted(p["records"]), "errors", p["integrity_errors"], "warn", len(p["integrity_warnings"]))
    if torn_bytes:
        o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o)
        print(" recover (NO ack) rc", rc, json.loads(o.getvalue()).get("anchor_problems"), "abandoned", json.loads(o.getvalue()).get("abandoned_batches"))
    m.create_milestone("MM-Z","z")
    p = m.projection(); print(" after next write: records", sorted(p["records"]), "open conflicts", openal(m), "errors", p["integrity_errors"], "warn", p["integrity_warnings"], "verify", m.store.verify()["ok"])
