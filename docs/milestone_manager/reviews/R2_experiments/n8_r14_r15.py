from common import *
m2 = new(actor="impl:a"); m2.create_milestone("MM-B","B"); m2.update_milestone("MM-B", candidate_commit=C1)
m2.record_review("MM-B", C1, "session", " IMPL:A ", "SESSION", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "self")
try: m2.set_status("MM-B","ACCEPTED","self"); print("R14 self-review accepted")
except ValidationError as e: print("R14 refused", e.code)
# R1-15: simulate a crash after the first line of a 2-event batch hits disk
m = new(); m.record_decision("Old","old","2026-10-21","OWNER-PROMPT","chat")
orig = m.store.append_many
def partial(items, actor, session=None, ts=None):
    evs = orig(items, actor, session, ts)
    data = m.store.segment_path.read_bytes().split(b"\n")
    m.store.segment_path.write_bytes(b"\n".join(data[:-2]) + b"\n")  # drop the batch's last event
    raise OSError(5, "simulated crash")
m.store.append_many = partial
try: m.record_decision("New","new","2026-10-21","OWNER-PROMPT","chat", supersedes="DEC-001")
except OSError as e: print("crash:", e)
m.store.append_many = orig
p = m.projection(); print("after crash:", {k:(v["status"]) for k,v in p["decisions"].items()}, p["integrity_warnings"], p["integrity_errors"])
try:
    m.record_decision("New","new","2026-10-21","OWNER-PROMPT","chat", ident="DEC-002", supersedes="DEC-001")
    p = m.projection(); print("retry ok:", {k:(v["status"]) for k,v in p["decisions"].items()}, "warnings", p["integrity_warnings"])
except Exception as e: print("retry failed", type(e).__name__, e)
print("verify ok:", m.store.verify()["ok"])
