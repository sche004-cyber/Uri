import sys; sys.argv=[sys.argv[0], "none"]
exec(open("r13_new2.py").read().split("which = sys.argv[1]")[0])
for label, mk in (("pending", mk_pending), ("adopt", mk_adopt)):
    home = mk()
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
oa = EventStore.append_many; n = [0]
def am(self, *a, **k):
    n[0] += 1
    if n[0] == 2: os._exit(9)
    return oa(self, *a, **k)
EventStore.append_many = am
Manager(r"{home}", actor="impl:c").create_milestone("MM-C","C")
'''
    print(label, "child rc", subprocess.run([sys.executable, "-c", child]).returncode)
    m = Manager(home, actor="impl:c"); p = m.projection()
    print(label, " after crash: open", openc(home), "MM-C", "MM-C" in p["milestones"], "marker", (home/"local/pending_loss.json").exists(), "warn", [w[:70] for w in p["integrity_warnings"]], "errs", p["integrity_errors"])
    rc, out = cli_run(home, "--actor", "impl:c", "milestone-add", "MM-D", "--title", "D"); print(label, " write2", rc, out[:300])
    rc, out = cli_run(home, "--actor", "impl:c", "milestone-add", "MM-E", "--title", "E"); print(label, " write3", rc, out[:120])
    evs = sorted([e for s in EventStore(home).read_all() for e in s.valid_events], key=lambda e:(e["ts"],e["seg"],e["seq"]))
    print(label, " hc kinds", [(e["kind"]) for e in evs if e["seg"]=="hc"], "open", openc(home))
    hc = [e for e in evs if e["seg"]=="hc"]; print(label, " ts monotone", all(hc[i]["ts"]<hc[i+1]["ts"] for i in range(len(hc)-1)), "max other ts < first hc", max(e["ts"] for e in evs if e["seg"]!="hc") < hc[0]["ts"])
    rc, out = cli_run(home, "verify"); print(label, " verify", rc, out[:150])
