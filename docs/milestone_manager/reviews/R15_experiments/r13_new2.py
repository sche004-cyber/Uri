from common import *
import subprocess, shutil, sys, io, contextlib
def mk_pending():
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); ma = Manager(base/"A",actor="impl:a"); ma.create_milestone("MM-A","A")
    ma.update_milestone("MM-A", candidate_commit=C1)
    ma.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    EventStore.init_host(home, "hb"); mb = Manager(home, actor="impl:b"); mb.create_milestone("MM-B","B"); mb.create_milestone("MM-B2","B2")
    seg = home/"events/hb.jsonl"; lines = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(lines[:1]) + b"\n")
    (home/"local/host.json").unlink()
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
ow = EventStore._write_local
def wl(home, hid):
    r = ow(home, hid); os._exit(9)
EventStore._write_local = staticmethod(wl)
EventStore.init_host(r"{home}", "hc", acknowledge_loss=True)
'''
    subprocess.run([sys.executable, "-c", child]); assert (home/"local/pending_loss.json").exists()
    return home
def mk_adopt():
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); ma = Manager(base/"A",actor="impl:a"); ma.create_milestone("MM-A","A")
    ma.update_milestone("MM-A", candidate_commit=C1); ma.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
oa = EventStore.append_many
def am(self, *a, **k):
    r = oa(self, *a, **k); os._exit(9)
EventStore.append_many = am
EventStore.init_host(r"{home}", "hc")
'''
    subprocess.run([sys.executable, "-c", child]); return home
def openc(home): p = Manager(home, actor="x").projection(); return [(c["type"], c["kind"]) for c in p["conflicts"] if not c["resolved"]]
def cli_run(home, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: rc = cli.run(["--home", str(home), *args])
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue().strip().replace("\n"," ")[:400]

which = sys.argv[1]
for label, mk in (("pending", mk_pending), ("adopt", mk_adopt)):
    if which == "selfresolve":
        home = mk()
        st = Manager(home, actor="x").projection()
        print(label, "before: open", openc(home), "warn", [w[:60] for w in st["integrity_warnings"]])
        rc, out = cli_run(home, "--actor", "impl:c", "resolve-conflict", "LEDGER", "--note", "routine")
        print(label, " resolve rc", rc, out)
        print(label, " after: open", openc(home))
        try: Manager(home, actor="impl:c").set_status("MM-A", "ACCEPTED", "go"); print(label, " ACCEPTED ALLOWED")
        except Exception as e: print(label, " ACCEPTED refused", getattr(e, "code", e))
    elif which == "stale":
        home = mk(); m = Manager(home, actor="impl:c")
        n0 = sum(len(s.valid_events) for s in m.store.read_all())
        try: m.update_milestone("MM-A", expect_version=0, title="new"); print(label, "stale update allowed?!")
        except Exception as e: print(label, "stale refused", getattr(e,"code",e))
        n1 = sum(len(s.valid_events) for s in m.store.read_all()); print(label, " events before", n0, "after", n1, "new kinds", [e["kind"] for s in m.store.read_all() for e in s.valid_events][n0-n1:] if n1>n0 else [])
        rc, out = cli_run(home, "--actor", "impl:c", "milestone-update", "MM-A", "--expect-version", "0", "--title", "x")
        print(label, " cli stale (2nd)", rc, out)
    elif which == "dedupe":
        home = mk()
        sd = Path(tempfile.mkdtemp())
        m = Manager(home, actor="impl:c")
        rc, out = cli_run(home, "--actor", "impl:c", "dep-add", "MM-A", "MM-A")
        print(label, " self-dep", rc, out)
