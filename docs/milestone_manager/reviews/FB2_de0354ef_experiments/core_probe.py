import sys, os, json, shutil, subprocess
src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.model import ValidationError
home = os.path.join(base, "core_ledger"); shutil.rmtree(home, ignore_errors=True)
EventStore.init(home, "h1")
m = Manager(home, actor="impl:a", session="s")
C1 = "a" * 40; C2 = "b" * 40
def tryit(label, fn):
    try:
        r = fn(); print("OK     ", label)
        return r
    except ValidationError as e: print("REFUSED", label, e.code)
    except Exception as e: print("ERR    ", label, type(e).__name__, str(e)[:120])
m.create_milestone("M1", "t")
tryit("ACCEPTED without candidate", lambda: m.set_status("M1", "ACCEPTED", "r"))
m.update_milestone("M1", candidate_commit=C1)
tryit("ACCEPTED without review", lambda: m.set_status("M1", "ACCEPTED", "r"))
m.record_review("M1", C1, "subagent", "impl:a", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "self")
tryit("ACCEPTED with implementer self-review", lambda: m.set_status("M1", "ACCEPTED", "r"))
m.record_review("M1", C2, "subagent", "rev:x", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "other commit")
tryit("ACCEPTED with review on other commit", lambda: m.set_status("M1", "ACCEPTED", "r"))
m.record_review("M1", C1, "subagent", "rev:x", "SUBAGENT", "ACCEPT", 0, 0, "PENDING", "pending")
tryit("ACCEPTED with PENDING review", lambda: m.set_status("M1", "ACCEPTED", "r"))
m.record_review("M1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
tryit("ACCEPTED with independent completed review", lambda: m.set_status("M1", "ACCEPTED", "r"))
tryit("candidate change while ACCEPTED (expect CANDIDATE_LOCKED)", lambda: m.update_milestone("M1", candidate_commit=C2))
tryit("INTEGRATED without owner approval", lambda: m.set_status("M1", "INTEGRATED", "r"))
aid = None
m.request_approval("M1", "INTEGRATION", "integrate?")
p = m.projection(); aid = [a for a in p["approvals"]][0]
m.resolve_approval(aid, "APPROVED", owner_words="yes integrate", source="chat")
tryit("INTEGRATED with approval but no integration record", lambda: m.set_status("M1", "INTEGRATED", "r"))
# decisions never overwritten
d = m.record_decision("T", "original text", "2026-10-22", "REPO-RECORD", "src")
p = m.projection(); did = list(p["decisions"])[0]
tryit("decision-correct", lambda: m.correct_decision(did, "corrected text", "REPO-RECORD", "src"))
p = m.projection(); dec = p["decisions"][did]
print("original decision text still present:", "original text" in json.dumps(dec), "| correction present:", "corrected text" in json.dumps(p["decisions"]))
# record-then-refuse for secrets: nothing written
before = os.path.getsize(os.path.join(home, "events", "h1.jsonl"))
tryit("secret refused", lambda: m.record_handoff("M1", "password=hunter2"))
print("segment unchanged after refusal:", before == os.path.getsize(os.path.join(home, "events", "h1.jsonl")))
# tamper detection
seg = os.path.join(home, "events", "h1.jsonl")
raw = open(seg, "rb").read(); lines = raw.split(b"\n")
t = lines[1].replace(b'"t"', b'"T"', 1) if b'"t"' in lines[1] else lines[1][:-3] + b"xx" + lines[1][-1:]
lines[1] = t; open(seg, "wb").write(b"\n".join(lines))
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "verify"], cwd=src,
                   env=dict(os.environ, PYTHONPATH=src), capture_output=True, text=True)
print("verify after tamper rc=", r.returncode, (r.stdout+r.stderr).strip().replace("\n"," ")[:200])
tryit("write after tamper", lambda: Manager(home, actor="impl:a", session="s").record_handoff("M1", "x"))
open(seg, "wb").write(raw)
# torn tail + recover
open(seg, "ab").write(b'{"partial":')
tryit("write with torn tail", lambda: Manager(home, actor="impl:a", session="s").record_handoff("M1", "x"))
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "--actor", "impl:a", "recover"], cwd=src,
                   env=dict(os.environ, PYTHONPATH=src), capture_output=True, text=True)
print("recover rc=", r.returncode, (r.stdout+r.stderr).strip().replace("\n"," ")[:160])
tryit("write after recover", lambda: Manager(home, actor="impl:a", session="s").record_handoff("M1", "after recover"))
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "status", "--json"], cwd=src,
                   env=dict(os.environ, PYTHONPATH=src), capture_output=True, text=True)
j = json.loads(r.stdout); print("status --json keys:", sorted(j)[:12], "schema:", j.get("schema") or j.get("schema_version"))
print("cache files:", [f for f in os.listdir(home) if "cache" in f.lower() or "proj" in f.lower()])
