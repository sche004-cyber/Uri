from common import *
import shutil
def t(label, f):
    try: f(); print(label, "ALLOWED")
    except (ValidationError, StoreError) as e: print(label, "refused", e.code)
def rv(m, c, rev, verdict, blk=0): m.record_review("MM-A", c, "subagent", rev, "SUBAGENT", verdict, blk, blk, "COMPLETED_WITH_RESULT", "x")
# NEGATIVE_REVIEW in any order
m = new(); m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1); rv(m,C1,"rev:y","ACCEPT"); rv(m,C1,"rev:z","REJECT",1)
t("ACCEPT then REJECT same commit -> accept:", lambda: m.set_status("MM-A","ACCEPTED","r"))
# candidate lock + commit-bound integration approval
m = new(); m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1); rv(m,C1,"rev:y","ACCEPT"); m.set_status("MM-A","ACCEPTED","r")
t("change candidate while ACCEPTED:", lambda: m.update_milestone("MM-A", candidate_commit=C2))
ap = m.request_approval("MM-A","INTEGRATION","ok?")[0]["data"]["id"]; m.resolve_approval(ap,"APPROVED","yes","chat")
m.set_status("MM-A","IN_PROGRESS","rework"); m.update_milestone("MM-A", candidate_commit=C2); rv(m,C2,"rev:y","ACCEPT"); m.set_status("MM-A","ACCEPTED","r")
m.record_integration("MM-A","main",C2)
t("INTEGRATED with approval bound to old commit:", lambda: m.set_status("MM-A","INTEGRATED","r"))
ap2 = m.request_approval("MM-A","INTEGRATION","ok2?")[0]["data"]["id"]; m.resolve_approval(ap2,"APPROVED","yes","chat")
t("INTEGRATED with new approval:", lambda: m.set_status("MM-A","INTEGRATED","r"))
# decisions never overwritten
m = new(); m.record_decision("T","D","2026-10-21","REPO-RECORD","s")
t("record LDEC-001 again:", lambda: m.record_decision("T2","D2","2026-10-21","REPO-RECORD","s", ident="LDEC-001"))
# duplicate ids across hosts
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); A=Manager(base/"A",actor="impl:a"); A.create_milestone("MM-0","x")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb"); B=Manager(base/"B",actor="impl:b")
A.record_decision("TA","DA","2026-10-21","REPO-RECORD","s"); B.record_decision("TB","DB","2026-10-21","REPO-RECORD","s")
shutil.copy(B.store.segment_path, A.store.events_dir/"hb.jsonl")
p = A.projection(); print("dup ids:", {k:v["title"] for k,v in p["decisions"].items()}, "conflicts", [(c["type"],c["entity"]) for c in p["conflicts"]], "dups", [d["as"] for d in p["duplicates"]])
# tamper: edit middle line
m = new(); [m.create_milestone(f"MM-{i}","x") for i in range(3)]
L = m.store.segment_path.read_bytes().split(b"\n"); L[1] = L[1].replace(b'"x"', b'"y"'); m.store.segment_path.write_bytes(b"\n".join(L))
p = m.projection(); print("tamper middle: errors", len(p["integrity_errors"]), p["integrity_errors"][:1]); t("  write after tamper:", lambda: m.create_milestone("MM-9","x"))
# truncation (anchored) detection
m = new(); [m.create_milestone(f"MM-{i}","x") for i in range(3)]
L = m.store.segment_path.read_bytes().split(b"\n")[:-1]; m.store.segment_path.write_bytes(b"\n".join(L[:-1])+b"\n")
print("truncate newest: verify", m.store.verify()["ok"]); t("  write after truncate:", lambda: m.create_milestone("MM-9","x"))
# crash atomicity: partial batch unapplied
m = new(); m.create_milestone("MM-A","A")
m.record_decision("T","D","2026-10-21","REPO-RECORD","s"); m.record_decision("T2","D2","2026-10-21","REPO-RECORD","s", supersedes="LDEC-001")
L = m.store.segment_path.read_bytes().split(b"\n")[:-1]; m.store.segment_path.write_bytes(b"\n".join(L[:-1])+b"\n")
p = m.projection(); print("partial batch: LDEC-002 applied?", "LDEC-002" in p["decisions"], "LDEC-001 status", p["decisions"]["LDEC-001"].get("status"))
