from common import *
def trunc(m):
    lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
    m.store.segment_path.write_bytes(b"\n".join(lines[:-1])+b"\n")
# (a) anchors replaced by {} (valid JSON, empty) + truncation
m = new(); m.create_milestone("MM-A","A"); m.create_milestone("MM-B","B")
trunc(m); m.store.anchors_path.write_text("{}")
v = m.store.verify(); print("(a) {} anchors + truncation: verify ok", v["ok"], v["errors"])
m.create_milestone("MM-C","C"); print("    write accepted; anchors", m.store.read_anchors())
# (b) reanchor to hide deletion: visible where?
m = new(); m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1)
m.record_review("MM-A", C1, "subagent", "rev:x", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "bad")
trunc(m)  # delete the REJECT review
print("(b) verify before reanchor:", m.store.verify()["ok"])
info = m.store.reanchor("impl:a", "routine")
print("    reanchor info:", info["previous"], info["counts"])
v = m.store.verify(); p = m.projection()
print("    verify after:", v["ok"], v["errors"], "| projection keys mentioning anchors:", [k for k in p if "anchor" in k])
import io
for cmd in (["status","--no-tasks"],["verify"]):
    o=io.StringIO(); rc=cli.run(["--home",str(m.home),*cmd],out=o); s=o.getvalue()
    print("   ", cmd, "rc", rc, "mentions ANCHORS_RESET/reanchor:", ("ANCHORS_RESET" in s) or ("reanchor" in s.lower()))
m.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
m.set_status("MM-A","ACCEPTED","r"); print("    MM-A:", m.projection()["milestones"]["MM-A"]["status"])
# (c) remove one segment's anchor entry only
m = new(); m.create_milestone("MM-A","A"); m.create_milestone("MM-B","B")
a = m.store.read_anchors(); trunc(m); a.pop("h1"); a["zz"]={"count":0,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
print("(c) entry removed + truncation: verify ok", m.store.verify()["ok"])
