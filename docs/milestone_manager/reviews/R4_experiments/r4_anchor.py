from common import *
import io
def trunc(m, k=1):
    lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
    m.store.segment_path.write_bytes(b"\n".join(lines[:-k])+b"\n")
def setup():
    m = new(); m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1)
    m.record_review("MM-A", C1, "subagent", "rev:x", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "bad")
    return m
def tryre(m, ack=False):
    try: i = m.store.reanchor("impl:a","routine", acknowledge_loss=ack); return ("OK", i["lost"], i["unknown_previous"])
    except StoreError as e: return ("REFUSED", e.code)
def after(m, label):
    p = m.projection(); v = m.store.verify()
    al = [c for c in p["conflicts"] if c["type"]=="ANCHOR_LOSS" and not c["resolved"]]
    ind = views.indicator(p, p["milestones"]["MM-A"])["color"]
    m.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    try: m.set_status("MM-A","ACCEPTED","r"); acc="ACCEPTED ALLOWED"
    except ValidationError as e: acc = e.code
    print(f"  {label}: verify ok={v['ok']} ANCHOR_LOSS open={len(al)} indicator={ind} accept={acc}")
# (b) plain truncation
m = setup(); trunc(m); print("(b) truncation, verify:", m.store.verify()["ok"])
print("  reanchor no-ack:", tryre(m)); print("  reanchor ack:", tryre(m, True)); after(m, "after ack")
m2 = setup(); trunc(m2); tryre(m2, True)
o=io.StringIO(); rc=cli.run(["--home",str(m2.home),"--actor","impl:z","resolve-conflict","LEDGER","--note","checked git"],out=o); print("  resolve-conflict LEDGER rc", rc)
after(m2, "after resolve")
# (c) own anchor entry removed + truncation
m = setup(); a = m.store.read_anchors(); trunc(m); a.pop("h1"); m.store.anchors_path.write_text(json.dumps(a))
print("(c) entry removed: verify", m.store.verify()["ok"], "| reanchor no-ack:", tryre(m)); after(m, "after")
# (c2) anchors {} + truncation
m = setup(); trunc(m); m.store.anchors_path.write_text("{}")
print("(c2) anchors {}: verify", m.store.verify()["ok"], "| reanchor no-ack:", tryre(m)); after(m, "after")
# (d) own entry count 0 + truncation
m = setup(); a = m.store.read_anchors(); trunc(m); a["h1"]={"count":0,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
print("(d) own count=0: verify", m.store.verify()["ok"], m.store.verify()["errors"]); after(m, "after")
# (d2) own entry rewritten to truncated count/head (deliberate edit)
m = setup(); trunc(m); segs=m.store.read_all(); m.store.write_anchors_force(segs)
print("(d2) anchors rewritten to match: verify", m.store.verify()["ok"])
# (e) anchors file deleted
m = setup(); trunc(m); m.store.anchors_path.unlink()
print("(e) anchors deleted: verify", m.store.verify()["ok"], "| reanchor no-ack:", tryre(m), "| ack:", tryre(m, True))
