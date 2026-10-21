import sys; sys.argv=[sys.argv[0], "none"]
exec(open("r13_new2.py").read().split("which = sys.argv[1]")[0])
import subprocess
def crash_child(home, where):
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
from scripts.dev_workflow.milestones import service, store
where = "{where}"
if where == "autocommit":
    EventStore.autocommit = lambda self, label: os._exit(9)
elif where == "unlink":
    service.unlink_retry = lambda p: os._exit(9)
elif where == "kbint":
    def ac(self, label): raise KeyboardInterrupt()
    EventStore.autocommit = ac
rc = cli.run(["--home", r"{home}", "--actor", "impl:c", "milestone-add", "MM-Z", "--title", "Z"])
print("child rc", rc)
'''
    r = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] 
for label, mk in (("pending", mk_pending), ("adopt", mk_adopt)):
    for where in ("autocommit", "unlink", "kbint"):
        if where == "unlink" and label == "adopt": continue
        home = mk()
        crc, tail = crash_child(home, where)
        p = Manager(home, actor="x").projection()
        print(f"[{label}/{where}] crashed rc={crc} tail={tail} open={openc(home)} warn={[w[:50] for w in p['integrity_warnings']]}")
        rc, out = cli_run(home, "--actor", "impl:c", "resolve-conflict", "LEDGER", "--note", "routine")
        print(f"   resolve-conflict LEDGER rc={rc} {out[:160]}")
        print(f"   open after={openc(home)}")
        try: Manager(home, actor="impl:c").set_status("MM-A", "ACCEPTED", "go"); print("   ACCEPTED ALLOWED")
        except Exception as e: print("   ACCEPTED refused", getattr(e, "code", e))
# recover rerun
home = mk_pending()
print("recover1", cli_run(home, "--actor", "impl:c", "recover")[0])
print("recover2", cli_run(home, "--actor", "impl:c", "recover"))
