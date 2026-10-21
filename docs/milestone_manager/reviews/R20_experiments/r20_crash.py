from common import *
m=new(); m.create_milestone("MM-1","a"); m.create_milestone("MM-2","b"); m.create_milestone("MM-3","c")
seg=m.store.segment_path; raw=seg.read_bytes()
seg.write_bytes(raw+b'{"seq": 99, "partial')   # torn tail
p=m.projection(); print("torn: events",p["events"],"errs",p["integrity_errors"],"warn",p["integrity_warnings"][:1])
try: m.create_milestone("MM-4","d"); print("write over torn ALLOWED")
except Exception as e: print("write over torn:", type(e).__name__, str(e)[:120])
print("recover", {k:v for k,v in m.store.recover("impl:a","s",False).items() if k!="quarantine"})
p=m.projection(); print("after recover events", p["events"], "milestones", sorted(p["milestones"]), "errs", p["integrity_errors"])
# lose two complete anchored events
lines=seg.read_bytes().splitlines(keepends=True); seg.write_bytes(b"".join(lines[:-2]))
p=m.projection(); print("truncated: errs", p["integrity_errors"][:1])
try: print("recover no-ack", m.store.recover("impl:a","s",False))
except Exception as e: print("recover no-ack refused:", type(e).__name__, str(e)[:120])
try: r=m.store.recover("impl:a","s",True); print("recover ack ok")
except Exception as e: print("recover ack:", type(e).__name__, str(e)[:160])
p=m.projection(); print("errs", p["integrity_errors"][:1], "conflicts", [(r["id"],r["type"],r["detail"]) for r in views.conflict_rows(p)])
print("status:", [l for l in views.status_lines(p,False) if "ledger" in l.lower()][:1])
try: m.resolve_conflict("LEDGER","x",["deadbeefdead.000000"])
except ValidationError as e: print("bad id:", e.code)
cid=views.conflict_rows(p)[0]["id"]
try: m.resolve_conflict("LEDGER","x",[cid.split(".")[0]+".000000"])
except ValidationError as e: print("wrong check:", e.code)
m.resolve_conflict("LEDGER","loss reviewed",[cid]); print("open after", views.conflict_rows(m.projection()), "verify", m.store.verify()["ok"])
