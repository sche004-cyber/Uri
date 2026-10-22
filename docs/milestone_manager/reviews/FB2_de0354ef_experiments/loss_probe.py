import sys, os, shutil, subprocess, json
src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.model import ValidationError
home = os.path.join(base, "loss_ledger"); shutil.rmtree(home, ignore_errors=True)
EventStore.init(home, "h1"); m = Manager(home, actor="impl:a", session="s")
m.create_milestone("M1", "t"); m.record_handoff("M1", "one"); m.record_handoff("M1", "two")
seg = os.path.join(home, "events", "h1.jsonl"); lines = open(seg, "rb").read().split(b"\n")
open(seg, "wb").write(b"\n".join(lines[:-2]) + b"\n")  # drop newest event
env = dict(os.environ, PYTHONPATH=src)
def W(label):
    try:
        Manager(home, actor="impl:a", session="s").record_handoff("M1", label); print(label, "write ACCEPTED")
    except Exception as e: print(label, "write refused", getattr(e, "code", type(e).__name__), str(e)[:260])
W("after-truncate")
def cli(*a):
    r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "--actor", "impl:a", *a], cwd=src, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()[:400].replace(chr(10), " ")
print("reanchor", cli("reanchor", "--reason", "lost newest event in probe", "--acknowledge-loss"))
W("after-reanchor")
print("conflicts", cli("conflicts"))
W("second-after-reanchor")
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "conflicts"], cwd=src, env=env, capture_output=True, text=True)
print("conflicts:", r.stdout.strip()[:300])
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "status", "--json"], cwd=src, env=env, capture_output=True, text=True)
print("status mentions conflict id:", "CF-" in r.stdout or "conflict" in r.stdout.lower())
