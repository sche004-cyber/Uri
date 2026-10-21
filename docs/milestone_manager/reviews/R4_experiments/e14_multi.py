from common import *
m = new()
m.record_decision("Old","old","2026-10-21","OWNER-PROMPT","chat")
orig = m.store.append; n = {"c":0}
def append(*a, **k):
    n["c"] += 1
    if n["c"] == 2: raise OSError(28, "No space left on device (simulated)")
    return orig(*a, **k)
m.store.append = append
try: m.record_decision("New","new","2026-10-21","OWNER-PROMPT","chat", supersedes="DEC-001")
except OSError as e: print("command failed:", e)
m.store.append = orig
p = m.projection(); print({k:(v["status"],v["supersedes"]) for k,v in p["decisions"].items()})
try: m.record_decision("New","new","2026-10-21","OWNER-PROMPT","chat", ident="DEC-002", supersedes="DEC-001")
except ValidationError as e: print("retry refused:", e.code)
