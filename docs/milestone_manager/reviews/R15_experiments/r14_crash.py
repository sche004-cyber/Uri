import sys; sys.argv=[sys.argv[0], "none"]
exec(open("r13_new2.py").read().split("which = sys.argv[1]")[0])
P0 = Path("D:/uri-dev/uri-p0-audit/developmental.md")
home = Path(tempfile.mkdtemp())/"L"; EventStore.init(home, "h1"); Manager(home, actor="impl:a").create_milestone("MM-1", "x")
child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
Manager._refresh_after = lambda self, segs, written: os._exit(9)
importers.import_register(Manager(r"{home}", actor="impl:a"), Path(r"{P0}"), "8e1d6324")
'''
print("child rc", subprocess.run([sys.executable, "-c", child]).returncode)
seg = home/"events/h1.jsonl"; raw = seg.read_bytes(); lines = raw.split(b"\n")
print("lines", len(lines)); seg.write_bytes(b"\n".join(lines[:40]) + b"\n" + lines[40][:30])
p = Manager(home, actor="x").projection()
print("applied records", len(p.get("records", {})), "milestones", list(p["milestones"]), "warn", [w[:90] for w in p["integrity_warnings"]], "errs", p["integrity_errors"])
rc, out = cli_run(home, "--actor", "impl:a", "recover"); print("recover", rc, out[:300])
print("open", openc(home))
rc, out = cli_run(home, "--actor", "impl:a", "milestone-add", "MM-2", "--title", "y"); print("next write", rc, out[:200])
p = Manager(home, actor="x").projection(); print("final warn", p["integrity_warnings"], "errs", p["integrity_errors"], "verify", EventStore(home).verify()["ok"])
