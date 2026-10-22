from common import *
import io
def trunc(m, k=1):
    lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
    m.store.segment_path.write_bytes(b"\n".join(lines[:-k]) + b"\n")
def al(m): return [(c["kind"], c["resolved"]) for c in m.projection()["conflicts"] if c["type"]=="ANCHOR_LOSS"]
# truncation + torn + recover --acknowledge-loss via CLI
m = new(); m.create_milestone("MM-A","A"); m.create_milestone("MM-B","B"); trunc(m)
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover", "--acknowledge-loss"], out=o)
print("CLI recover ack rc", rc, o.getvalue()[:300].replace("\n"," "))
p = m.projection(); print("  after: errors", p["integrity_errors"], "AL", al(m), "recoveries", len(p["recoveries"]))
# g-flow: failed first refresh -> adopt -> resolve -> accept works
m = new(); m.create_milestone("MM-A","A"); a=m.store.read_anchors(); a["h1"]={"count":0,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
m.update_milestone("MM-A", candidate_commit=C1); print("adopt AL", al(m))
r = Manager(m.home, actor="rev:z")
m.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
try: m.set_status("MM-A","ACCEPTED","r"); print("accepted with open AL?!")
except (ValidationError, StoreError) as e: print("accept before resolve:", e.code)
m.resolve_conflict("LEDGER", "reviewed: anchor refresh failed on first write, no loss"); 
m.set_status("MM-A","ACCEPTED","r"); print("accept after resolve OK; AL", al(m), "warnings", m.projection()["integrity_warnings"])
