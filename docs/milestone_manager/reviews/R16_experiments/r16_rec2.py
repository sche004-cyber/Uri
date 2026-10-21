from common import *
import io, contextlib, json
def cli_run(home, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try: rc = cli.run(["--home", str(home), *args])
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue().strip().replace("\n"," ")[:300]
m = new(actor="impl:a"); m.create_milestone("MM-1","x"); m.create_milestone("MM-2","y")
home = m.home
# simulate failed anchor refresh: own anchor count 0
a = json.loads((home/"local/anchors.json").read_text()); print("anchors keys", list(a))
seg = home/"events/h1.jsonl"; raw = seg.read_bytes()
EventStore.write_anchors_orig = EventStore.write_anchors
m2 = new(actor="impl:a")
home2 = m2.home
EventStore.write_anchors = lambda self, segs: (_ for _ in ()).throw(OSError("sim"))
Manager(home2, actor="impl:a").create_milestone("MM-1","x")
EventStore.write_anchors = EventStore.write_anchors_orig
s2 = home2/"events/h1.jsonl"; b = s2.read_bytes(); s2.write_bytes(b[:-20])   # torn tail, unanchored
print("open before", [(c["type"],c["kind"]) for c in Manager(home2).projection()["conflicts"] if not c["resolved"]], Manager(home2).projection()["integrity_warnings"])
print("recover", cli_run(home2, "--actor","impl:a","recover"))
p = Manager(home2).projection(); print("open after", [(c["type"],c["kind"], c["event"]["hash"][:12]) for c in p["conflicts"] if not c["resolved"]], "verify", EventStore(home2).verify()["ok"], p["integrity_warnings"])
