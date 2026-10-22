from common import *
import io, collections
import scripts.dev_workflow.milestones.store as S
w = Path(tempfile.mkdtemp()); reg = w/"r.md"
rows = "".join(f"| CAP-{i} | c{i} | RED |\n" for i in range(1, 15))
reg.write_text("# Reg X\n\n## B. Capabilities\n\n| ID | Capability | Status |\n|---|---|---|\n" + rows, encoding="utf-8")
def openal(m): return [(c["type"]) for c in m.projection()["conflicts"] if not c["resolved"]]
def setup():
    m = new(); init_anchors = m.store.anchors_path.read_bytes()
    importers.import_register(m, reg)
    m.store.anchors_path.write_bytes(init_anchors)   # first anchor refresh failed
    return m
m = setup(); full = m.store.segment_path.read_bytes(); lines = full.split(b"\n")[:-1]
print("batch lines", len(lines), "records applied", len(m.projection()["records"]))
print("line1 prefix:", lines[1][:120])
def trial(k, off):
    m = setup(); m.store.segment_path.write_bytes(b"\n".join(lines[:k]) + b"\n" + lines[k][:off])
    seg = read_segment(m.store.segment_path)
    proof = S._torn_continues_batch(seg)
    o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o)
    out = o.getvalue()
    try: j = json.loads(out)
    except Exception: j = {}
    return proof, rc, ("LOSS_NOT_ACKNOWLEDGED" in out), bool(j.get("anchor_problems")), m
for k in (1, 5, 11, 12):
    if k >= len(lines): continue
    res = collections.Counter(); first = {}
    L = len(lines[k])
    for off in range(1, L):
        proof, rc, refused, noted, _ = trial(k, off)
        key = (proof, rc, refused, noted); res[key] += 1; first.setdefault(key, (off, lines[k][max(0,off-25):off]))
    print(f"line {k} len {L}:")
    for key, n in res.items(): print("   proof=%s rc=%s refused=%s ANCHOR_LOSS_noted=%s : %d offsets; e.g." % (*key, n), first[key])
# applied-then-truncated, cut deep in line 1 -> what does the ledger show afterwards?
proof, rc, refused, noted, m = trial(1, 200)
p = m.projection(); print("deep cut l1: proof", proof, "rc", rc, "records now", len(p["records"]), "open conflicts", openal(m), "errors", p["integrity_errors"], "warn", p["integrity_warnings"])
m.create_milestone("MM-Z","z"); p = m.projection(); print("  after next write: records", len(p["records"]), "open", openal(m), "verify", m.store.verify()["ok"])
