from common import *
import io, json, hashlib
sd = Path("D:/uri-dev/lifecycle/LIFECYCLE-REVIEWER-TIERS-r11/state")
def h(): return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sd.iterdir() if p.is_file()}
m=new(); m.create_milestone("MM-1","x", objective="o"*3000)
if (sd/"state.json").is_file():
    b=h(); m.link_lifecycle("MM-1", sd); snap=m.sync_lifecycle("MM-1", sd)
    print("lifecycle", snap["stage"], snap["chain_ok"], snap["events"], snap["candidate"], "unchanged", h()==b)
else: print("no real lifecycle dir")
def cli_(*a):
    o=io.StringIO(); rc=cli.run(["--home",str(m.home),"--actor","impl:a","--no-emoji",*a],out=o); return rc,o.getvalue()
for s in ["sk-ant-"+"a"*30, "ghp_"+"b"*36, "password: Hunter2xyz9", "https://u:pw12@host/x"]:
    print("secret", cli_("milestone-update","MM-1","--next-action",s)[1].replace("\n"," ")[:90])
for i in range(40): m.record_handoff("MM-1","s"*1900, done="d"*3000, next_action="n"*3000)
for i in range(30): m.record_review("MM-1",C1,"subagent","r%d"%i,"SUBAGENT","REJECT",1,1,"COMPLETED_WITH_RESULT","z"*1990)
for i in range(30): m.request_approval("MM-1","OTHER","q"*3990)
for mx in (6000, 500, 100):
    rc,s=cli_("resume","MM-1","--no-tasks","--max-chars",str(mx)); print("resume", mx, len(s.rstrip("\n")), rc)
rc,s=cli_("status","--json","--no-tasks"); j=json.loads(s); print("schema", j["schema"], sorted(j), sorted(j["milestones"][0]), sorted(j["ledger"]))
rc,s=cli_("resume","MM-1","--no-tasks","--max-chars","10"); print("resume 10 ->", repr(s[:120]))
