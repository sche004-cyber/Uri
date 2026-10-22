from common import *
import io, re, json, shutil
RX=re.compile(r"[0-9a-f]{12}\.[0-9a-f]{6}")
def cli_(home,*a):
    o=io.StringIO(); rc=cli.run(["--home",str(home),"--actor","impl:a","--no-emoji",*a],out=o); return rc,o.getvalue()
m=new(); m.create_milestone("MM-1","a"); home=m.home
m.store.anchors_path.unlink()
for c in [("status","--no-tasks"),("reanchor","--reason","r"),("reanchor","--reason","r","--acknowledge-loss"),("status","--no-tasks"),("show","MM-1"),("log",),("verify",),("conflicts",)]:
    rc,s=cli_(home,*c); print(" ".join(c)[:40].ljust(40), rc, sorted(set(RX.findall(s))))
m2=new(); a0=m2.store.anchors_path.read_bytes(); m2.create_milestone("MM-1","a"); m2.store.anchors_path.write_bytes(a0)
m2.store.segment_path.write_bytes(m2.store.segment_path.read_bytes()+b'{"x')
for c in [("recover",),("status","--no-tasks"),("resume","MM-1","--no-tasks"),("milestone-add","MM-2","--title","t"),("conflicts",)]:
    rc,s=cli_(m2.home,*c); print(" ".join(c)[:40].ljust(40), rc, sorted(set(RX.findall(s))))
# init-host ack loss
base=Path(tempfile.mkdtemp()); A=base/"A"; EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x")
B=base/"B"; shutil.copytree(A,B); (B/"local"/"host.json").unlink()
(B/"local"/"anchors.json").write_text(json.dumps({"ha":{"count":5,"head":"a"*64}}))
for c in [("init-host","--host-id","hb"),("init-host","--host-id","hb","--acknowledge-loss"),("status","--no-tasks"),("conflicts",)]:
    rc,s=cli_(B,*c); print(" ".join(c)[:40].ljust(40), rc, sorted(set(RX.findall(s))))
