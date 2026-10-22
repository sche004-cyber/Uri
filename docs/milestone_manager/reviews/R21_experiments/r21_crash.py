from common import *
import io, json
m=new(); m.create_milestone("MM-1","a")
m.record_decision("T","D","2026-10-22","OWNER-PROMPT","chat", ident="LDEC-001")
seg=m.store.segment_path; seg0=seg.read_bytes(); anc0=m.store.anchors_path.read_bytes()
m.record_decision("T2","D2","2026-10-22","OWNER-PROMPT","chat", ident="LDEC-002", supersedes="LDEC-001")
new_lines=seg.read_bytes()[len(seg0):].splitlines(keepends=True); print("batch lines", len(new_lines))
seg.write_bytes(seg0+new_lines[0]+new_lines[1][:40]); m.store.anchors_path.write_bytes(anc0)  # crash mid-batch
p=m.projection(); print("decisions", sorted(p["decisions"]), "LDEC-001", p["decisions"]["LDEC-001"]["status"], "errs", p["integrity_errors"], "warn", [w[:80] for w in p["integrity_warnings"]])
o=io.StringIO(); rc=cli.run(["--home",str(m.home),"--actor","impl:a","recover"],out=o); r=json.loads(o.getvalue()); print("recover rc", rc, {k:r[k] for k in r if k in ("recovered","bytes","abandoned_batches","anchor_problems")})
p=m.projection(); print("after: decisions", sorted(p["decisions"]), "warn", p["integrity_warnings"], "errs", p["integrity_errors"], "open conflicts", [(c["type"]) for c in views.open_conflicts(p)])
m.record_decision("T2","D2","2026-10-22","OWNER-PROMPT","chat", ident="LDEC-002", supersedes="LDEC-001"); p=m.projection(); print("retry ok", p["decisions"]["LDEC-001"]["status"], m.store.verify()["ok"])
# unanchored own segment + torn tail => ANCHOR_LOSS recorded by recover
m2=new(); a0=m2.store.anchors_path.read_bytes(); m2.create_milestone("MM-1","a"); m2.store.anchors_path.write_bytes(a0)
m2.store.segment_path.write_bytes(m2.store.segment_path.read_bytes()+b'{"partial')
r=m2.store.recover("impl:a","s",False); print("unanchored recover", r["recovered"], r["anchor_problems"][:1])
p=m2.projection(); rows=views.conflict_rows(p); print("conflicts", [(x["type"],x["recorded_by"],str(x["detail"])[:80]) for x in rows])
try: m2.update_milestone("MM-1", candidate_commit=C1); m2.record_review("MM-1",C1,"subagent","rev:z","SUBAGENT","ACCEPT",0,0,"COMPLETED_WITH_RESULT","ok"); m2.set_status("MM-1","ACCEPTED","x"); print("ACCEPTED while ANCHOR_LOSS open!")
except ValidationError as e: print("accept blocked:", e.code)
