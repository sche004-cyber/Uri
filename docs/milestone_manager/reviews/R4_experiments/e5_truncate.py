from common import *
m = new()
m.create_milestone("MM-A","A")
m.create_decision = None
m.record_decision("D","decide","2026-10-21","OWNER-PROMPT","chat")
m.supersede_decision  # noop
lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
m.store.segment_path.write_bytes(b"\n".join(lines[:-1])+b"\n")  # delete the last event (the decision)
r = m.store.verify(); print("verify ok after deleting newest event:", r["ok"], r["errors"])
p = m.projection(); print("decisions now:", list(p["decisions"]), "integrity_errors:", p.get("integrity_errors"))
m.create_milestone("MM-B","B"); print("write accepted; verify:", m.store.verify()["ok"])
