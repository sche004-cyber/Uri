from common import *
import io, shutil, datetime as dt
import scripts.dev_workflow.milestones.store as S
import scripts.dev_workflow.milestones.service as SV

def trunc(m, k=1):
    lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
    m.store.segment_path.write_bytes(b"\n".join(lines[:-k]) + b"\n")

def setup():
    m = new(); m.create_milestone("MM-A", "A"); m.update_milestone("MM-A", candidate_commit=C1)
    m.record_review("MM-A", C1, "subagent", "rev:x", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "bad")
    return m

def try_accept(m, label):
    try:
        m.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
        m.set_status("MM-A", "ACCEPTED", "r"); acc = "ACCEPTED ALLOWED"
    except (ValidationError, StoreError) as e:
        acc = "refused " + e.code
    p = m.projection(); v = m.store.verify()
    al = [c for c in p["conflicts"] if c["type"] == "ANCHOR_LOSS" and not c["resolved"]]
    print(f"  {label}: accept={acc} | verify ok={v['ok']} errors={len(v['errors'])} warnings={p['integrity_warnings']} "
          f"ANCHOR_LOSS open={len(al)} | REJECT review present={'RV-1' in p['reviews']}")

print("A. own count 0 + truncation of the REJECT review, then ordinary writes (no reanchor):")
m = setup(); a = m.store.read_anchors(); trunc(m); a["h1"] = {"count": 0, "head": "0" * 64}
m.store.anchors_path.write_text(json.dumps(a))
try_accept(m, "after plain writes")

print("M1. anchors file deleted + truncation of REJECT + torn byte, then `recover` (no acknowledgement):")
m = setup(); trunc(m); m.store.anchors_path.unlink()
print("  before recover: verify ok", m.store.verify()["ok"], m.store.verify()["errors"][:1])
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o); print("  recover rc", rc, o.getvalue().strip()[:200])
try_accept(m, "after recover")

print("M2. own anchor entry removed + truncation + torn byte, then `recover`:")
m = setup(); a = m.store.read_anchors(); trunc(m); a.pop("h1"); m.store.anchors_path.write_text(json.dumps(a))
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
print("  recover:", m.store.recover("impl:a").get("recovered"))
try_accept(m, "after recover")

print("M3. anchors file deleted (no truncation) + torn byte -> recover clears 'unknown history' error?")
m = setup(); m.store.anchors_path.unlink()
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
m.store.recover("impl:a"); p = m.projection(); print("  integrity errors after recover:", p["integrity_errors"],
      "ANCHOR_LOSS:", [c for c in p["conflicts"] if c["type"] == "ANCHOR_LOSS"])

print("G. legitimate flows and reanchor without acknowledgement:")
m = new(); print("  fresh init reanchor:", m.store.reanchor("impl:a", "r")["unknown_previous"])
m = new(); m.create_milestone("MM-A", "A"); print("  after normal write reanchor:", m.store.reanchor("impl:a", "r")["unknown_previous"])
base = Path(tempfile.mkdtemp()); EventStore.init(base / "A", "ha"); A = Manager(base / "A", actor="impl:a"); A.create_milestone("MM-A", "A")
shutil.copytree(base / "A", base / "B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base / "B", "hb")
B = Manager(base / "B", actor="impl:b")
try: print("  init-host clone reanchor:", B.store.reanchor("impl:b", "r")["unknown_previous"])
except StoreError as e: print("  init-host clone reanchor REFUSED", e.code)
m = new(); m.create_milestone("MM-A", "A")
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
m.store.recover("impl:a")
try: print("  after recover reanchor:", m.store.reanchor("impl:a", "r")["unknown_previous"])
except StoreError as e: print("  after recover reanchor REFUSED", e.code)

print("B. Lamport floor across day boundary / fixed clock:")
fixed = "2026-10-21T23:59:59.999998Z"
S.utc_now = lambda: fixed; SV.store_now = lambda: fixed
m = new()
for i in range(4): m.create_milestone(f"MM-{i}", "t")
ts = [e["ts"] for e in m.store.read_all()[0].events]; print("  ts:", ts, "strictly increasing:", all(a < b for a, b in zip(ts, ts[1:])))

print("C. reanchor / recover on a host whose clock is 1 h behind (floor applied?):")
real_now = lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
S.utc_now = real_now; SV.store_now = real_now
base = Path(tempfile.mkdtemp()); EventStore.init(base / "B", "b"); B = Manager(base / "B", actor="impl:b")
EventStore.init(base / "A", "a"); A = Manager(base / "A", actor="impl:a")
A.create_milestone("MM-A", "A"); B.create_milestone("MM-B", "B")
shutil.copy(B.store.segment_path, A.store.events_dir / "b.jsonl")
A.store.write_anchors(A.store.read_all())
behind = lambda: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
S.utc_now = behind; SV.store_now = behind
info = A.store.reanchor("impl:a", "routine")
evs = A.store.read_all()
newest_b = [e["ts"] for s in evs if s.name == "b" for e in s.events][-1]
reset_ts = [e["ts"] for s in evs if s.name == "a" for e in s.events if e["kind"] == "ANCHORS_RESET"][0]
print("  ANCHORS_RESET ts", reset_ts, "> newest seen b event", newest_b, ":", reset_ts > newest_b)
S.utc_now = real_now; SV.store_now = real_now

print("D. conflict index after an in-place resolve on the same projection object:")
from scripts.dev_workflow.milestones import model as Mo
base = Path(tempfile.mkdtemp()); EventStore.init(base / "A", "ha"); A = Manager(base / "A", actor="impl:a")
A.create_milestone("MM-A", "A")
shutil.copytree(base / "A", base / "B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base / "B", "hb")
B = Manager(base / "B", actor="impl:b")
A.update_milestone("MM-A", title="x"); B.update_milestone("MM-A", title="y")
shutil.copy(B.store.segment_path, A.store.events_dir / "hb.jsonl")
p = A.projection(); before = len(views.open_conflicts(p, "MM-A"))
ev = A.resolve_conflict("MM-A", "checked")[0]
Mo.apply(p, ev)
print("  open conflicts on MM-A before", before, "| after applying CONFLICT_RESOLVED to same p:",
      len(views.open_conflicts(p, "MM-A")), "| fresh projection:", len(views.open_conflicts(A.projection(), "MM-A")),
      "| indicator on stale p:", views.indicator(p, p["milestones"]["MM-A"])["color"])

print("E. register heading with a UTF-8 BOM:")
src = Path("D:/uri-dev/uri-p0-audit/decisions.md")
w = Path(tempfile.mkdtemp()); bom = w / "decisions.md"; bom.write_bytes(b"\xef\xbb\xbf" + src.read_bytes())
m = new(); importers.import_decisions(m, src)
try:
    r = importers.import_decisions(m, bom); print("  BOM copy: unchanged", r["unchanged"], "collisions", len(r["collisions"]))
except ValidationError as e: print("  BOM copy refused:", e.code)

print("F. anchors with a non-integer count, CLI status/verify:")
m = new(); m.create_milestone("MM-A", "A"); a = m.store.read_anchors(); a["h1"]["count"] = "1"
m.store.anchors_path.write_text(json.dumps(a))
for cmd in (["status"], ["verify"]):
    o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--no-tasks", *cmd] if cmd == ["status"] else ["--home", str(m.home), *cmd], out=o)
    print("  ", cmd, "rc", rc, o.getvalue().strip()[:160])
