"""FB4 e10: core guarantees re-confirmation (service API + CLI in a temp ledger)."""
import sys, os, json, tempfile, subprocess, io, shutil
src = sys.argv[1]; sys.path.insert(0, src)
from pathlib import Path
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore, StoreError, read_segment
from scripts.dev_workflow.milestones.model import ValidationError
from scripts.dev_workflow.milestones import views, cli
C1, C2 = "1"*40, "2"*40
def new(actor="impl:a"):
    home = Path(tempfile.mkdtemp(prefix="core_", dir=os.environ["TEMP"])) / "ledger"
    EventStore.init(home, "h1"); return Manager(home, actor=actor, session="s1")
def code(fn):
    try: fn(); return "OK"
    except (ValidationError, StoreError) as e: return e.code
def seg(m): return (Path(m.home)/"events"/"h1.jsonl").read_bytes()
R = []
def chk(name, cond, detail=""): R.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name, detail)
def ready_m():
    m = new(); m.create_milestone("MM-A", "A"); m.set_status("MM-A", "IN_PROGRESS", "s")
    m.update_milestone("MM-A", candidate_commit=C1)
    m.record_review("MM-A", C1, "subagent", "rev:1", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok"); return m
# guards
m = new(); m.create_milestone("MM-A", "A"); m.set_status("MM-A", "IN_PROGRESS", "s"); m.update_milestone("MM-A", candidate_commit=C1)
chk("ACCEPTED refused w/o review", code(lambda: m.set_status("MM-A", "ACCEPTED", "x")) == "NO_INDEPENDENT_ACCEPT")
m.record_review("MM-A", C1, "subagent", "impl:a", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "self")
chk("self-review refused", code(lambda: m.set_status("MM-A", "ACCEPTED", "x")) == "NO_INDEPENDENT_ACCEPT")
m.record_review("MM-A", C1, "subagent", "rev:p", "SUBAGENT", "ACCEPT", 0, 0, "PENDING", "pending")
chk("PENDING review refused", code(lambda: m.set_status("MM-A", "ACCEPTED", "x")) == "NO_INDEPENDENT_ACCEPT")
m = ready_m(); chk("independent ACCEPT allows ACCEPTED", code(lambda: m.set_status("MM-A", "ACCEPTED", "ok")) == "OK")
chk("INTEGRATED needs approval", code(lambda: m.set_status("MM-A", "INTEGRATED", "x")) == "NO_OWNER_INTEGRATION_APPROVAL")
chk("CANDIDATE_LOCKED", code(lambda: m.update_milestone("MM-A", candidate_commit=C2)) == "CANDIDATE_LOCKED")
v = m.projection()["versions"]["MM-A"]
chk("stale expect-version CONFLICT, nothing written", (lambda b: code(lambda: m.update_milestone("MM-A", expect_version=v-1, title="z")) == "CONFLICT" and seg(m) == b)(seg(m)))
# D1-01 independence invalidation
m.record_implementer("MM-A", "rev:1"); p = m.projection(); ind = views.indicator(p, p["milestones"]["MM-A"])
chk("D1-01 reviewer->implementer turns indicator RED", ind["color"] == "RED", ind.get("issue", "")[:90])
m.create_milestone("MM-B", "B", depends_on=["MM-A"]); p = m.projection()
chk("D1-01 dependent not ready", "MM-B" not in views.ready(p))
# R2-02 negative review invalidates ready
m = ready_m(); m.set_status("MM-A", "ACCEPTED", "ok"); m.create_milestone("MM-B", "B", depends_on=["MM-A"])
chk("ready when prerequisite ACCEPTED", "MM-B" in views.ready(m.projection()))
m.record_review("MM-A", C1, "subagent", "rev:2", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "no")
p = m.projection(); chk("R2-02 later REJECT removes ready", "MM-B" not in views.ready(p) and views.indicator(p, p["milestones"]["MM-A"])["color"] == "RED")
# decisions never overwritten
m = new(); m.record_decision("T", "original text", "2026-10-22", "OTHER", "src")
m.record_decision("T2", "new text", "2026-10-22", "OTHER", "src"); m.supersede_decision("LDEC-001", "LDEC-002", note="n")
m.correct_decision("LDEC-001", "correction", "OTHER", "src"); d = m.projection()["decisions"]
d1 = next(x for k, x in d.items() if "LDEC-001" in k)
chk("decision original text kept + links both ways", d1.get("decision") == "original text" and d1["superseded_by"] and d1["corrections"], str(list(d1))[:80])
before = seg(m)
chk("decision id reuse refused", code(lambda: m.record_decision("T", "overwrite", "2026-10-22", "OTHER", "src", ident="LDEC-001")) != "OK" and seg(m) == before)
# tamper
for attack in ("edit", "delete", "reorder"):
    m = new(); m.create_milestone("MM-A", "A"); m.record_handoff("MM-A", "one"); m.record_handoff("MM-A", "two")
    f = Path(m.home)/"events"/"h1.jsonl"; lines = f.read_bytes().splitlines(keepends=True)
    if attack == "edit": lines[1] = lines[1].replace(b'"one"', b'"0ne"')
    elif attack == "delete": del lines[1]
    else: lines[1], lines[2] = lines[2], lines[1]
    f.write_bytes(b"".join(lines)); rep = m.store.verify()
    chk(f"tamper {attack} detected", not rep["ok"] and rep["errors"], rep["errors"][:1])
    chk(f"tamper {attack}: writes refused", code(lambda: m.record_handoff("MM-A", "x")) == "CHAIN_BROKEN")
# torn tail + recover
m = new(); m.create_milestone("MM-A", "A"); f = Path(m.home)/"events"/"h1.jsonl"; good = f.read_bytes()
f.write_bytes(good + b'{"v":1,"seg":"h1","seq":2,"ts":"20')
rep = m.store.verify(); chk("torn tail reported", rep["torn"] and not rep["ok"])
chk("write refused on torn tail", code(lambda: m.record_handoff("MM-A", "x")) in ("TORN_TAIL", "CHAIN_BROKEN"))
r = m.store.recover("impl:a"); chk("recover quarantines, keeps events", r["recovered"] and f.read_bytes().startswith(good) and (Path(m.home)/r["quarantine"]).exists())
chk("after recover verify ok", m.store.verify()["ok"])
# no cache: projection from log; status --json schema
m = new(); m.create_milestone("MM-A", "A")
caches = [p for p in Path(m.home).rglob("*") if p.is_file() and "cache" in p.name.lower() or p.suffix in (".pickle", ".db", ".sqlite")]
chk("no cache files", not caches, [str(c) for c in caches])
buf = io.StringIO(); rc = cli.run(["--home", str(m.home), "status", "--json"], out=buf); j = json.loads(buf.getvalue())
chk("status --json schema", rc == 0 and j.get("schema") == "uri-mm-status/1" and isinstance(j.get("milestones"), list), j.get("schema"))
print("SUMMARY", sum(ok for _, ok in R), "/", len(R))
