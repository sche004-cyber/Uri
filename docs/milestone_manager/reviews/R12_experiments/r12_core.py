from common import *
import shutil, os
def tryit(label, f):
    try: r = f(); print(f"{label}: OK")
    except Exception as e: print(f"{label}: refused {getattr(e,'code',type(e).__name__)}")
m = new(actor="impl:a")
m.create_milestone("MM-1", "one"); m.update_milestone("MM-1", candidate_commit=C1)
tryit("ACCEPTED without review", lambda: m.set_status("MM-1","ACCEPTED","r"))
m.record_review("MM-1", C1, "subagent", "impl:a", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "self")
tryit("ACCEPTED with self review", lambda: m.set_status("MM-1","ACCEPTED","r"))
m.record_review("MM-1", C1, "subagent", "rev:x", "SUBAGENT", "ACCEPT", 0, 0, "PENDING", "pending")
tryit("ACCEPTED with PENDING review", lambda: m.set_status("MM-1","ACCEPTED","r"))
m.record_review("MM-1", C1, "subagent", "rev:z", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "neg")
m.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "pos")
tryit("ACCEPTED with REJECT on same commit (expect NEGATIVE_REVIEW)", lambda: m.set_status("MM-1","ACCEPTED","r"))
m.update_milestone("MM-1", candidate_commit=C2)
m.record_review("MM-1", C2, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "pos")
tryit("ACCEPTED on new candidate", lambda: m.set_status("MM-1","ACCEPTED","r"))
tryit("candidate change after ACCEPTED (expect CANDIDATE_LOCKED)", lambda: m.update_milestone("MM-1", candidate_commit="3"*40))
# integration approval bound to commit
a = m.request_approval("MM-1", "INTEGRATION", "integrate?")
aid = a[0]["data"]["id"]
m.resolve_approval(aid, "APPROVED", owner_words="yes integrate", source="chat 2026-10-22")
m.record_integration("MM-1", "master", C2)
tryit("INTEGRATED with bound approval", lambda: m.set_status("MM-1","INTEGRATED","r"))
m2 = m; m2.create_milestone("MM-2","two"); m2.update_milestone("MM-2", candidate_commit=C1)
a2 = m2.request_approval("MM-2","INTEGRATION","q")[0]["data"]["id"]; m2.resolve_approval(a2,"APPROVED",owner_words="ok",source="chat")
m2.record_review("MM-2", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "pos"); m2.set_status("MM-2","ACCEPTED","r")
m2.set_status("MM-2","IN_PROGRESS","repair"); m2.update_milestone("MM-2", candidate_commit=C2)
m2.record_review("MM-2", C2, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "pos"); m2.set_status("MM-2","ACCEPTED","r"); m2.record_integration("MM-2","master",C2)
tryit("INTEGRATED with approval bound to OLD candidate (expect NO_OWNER_INTEGRATION_APPROVAL)", lambda: m2.set_status("MM-2","INTEGRATED","r"))
# decisions
d1 = m.record_decision("T1","original text","2026-10-22","OWNER_STATED" if "OWNER_STATED" in model.EVIDENCE_CLASSES else sorted(model.EVIDENCE_CLASSES)[0],"chat")[0]["data"]["id"]
d2 = m.record_decision("T2","new text","2026-10-22",sorted(model.EVIDENCE_CLASSES)[0],"chat")[0]["data"]["id"]
m.supersede_decision(d1, d2); m.correct_decision(d1, "fix", sorted(model.EVIDENCE_CLASSES)[0], "chat")
p = m.projection(); dd = p["decisions"][d1]
print("decision original kept:", dd.get("decision") == "original text", "superseded_by", [s["by"] for s in dd["superseded_by"]], "corrections", len(dd.get("corrections", [])))
print("files in home:", sorted(str(x.relative_to(m.home)) for x in m.home.rglob("*") if x.is_file()))
print("verify", m.store.verify()["ok"])
# tamper detection
seg = m.store.segment_path; raw = seg.read_bytes(); lines = raw.split(b"\n")
seg.write_bytes(raw.replace(b"original text", b"originaX text", 1)); print("edit ->", EventStore(m.home).verify()["errors"][:1])
seg.write_bytes(b"\n".join(lines[:-2]) + b"\n"); print("delete last ->", EventStore(m.home).verify()["errors"][:1])
seg.write_bytes(raw); print("restored ->", EventStore(m.home).verify()["ok"])
# duplicate ids across hosts (offline), merge by copying segments
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-0","base")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb")
ma, mb = Manager(base/"A",actor="impl:a"), Manager(base/"B",actor="impl:b")
ma.create_milestone("MM-X","from A"); mb.create_milestone("MM-X","from B")
ma.record_decision("DA","a","2026-10-22",sorted(model.EVIDENCE_CLASSES)[0],"x", ident="LDEC-900"); mb.record_decision("DB","b","2026-10-22",sorted(model.EVIDENCE_CLASSES)[0],"x", ident="LDEC-900")
shutil.copy(base/"B/events/hb.jsonl", base/"A/events/hb.jsonl")
p = Manager(base/"A").projection()
print("dup milestones:", sorted(k for k in p["milestones"] if k.startswith("MM-X")), "dup decisions:", sorted(k for k in p["decisions"] if k.startswith("LDEC-900")), "conflicts:", sorted({c["type"] for c in p["conflicts"] if not c["resolved"]}), "errs", p["integrity_errors"])
