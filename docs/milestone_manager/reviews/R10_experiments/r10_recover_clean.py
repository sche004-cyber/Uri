from common import *
import io, shutil
def openc(m): return [c["type"] for c in m.projection()["conflicts"] if not c["resolved"]]
def rec(m):
    o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o); return rc, json.loads(o.getvalue()).get("anchor_problems")
# 1: anchored writes then power loss mid next write
m = new(); m.create_milestone("MM-A","A"); m.create_milestone("MM-B","B")
data = m.store.segment_path.read_bytes(); m.store.segment_path.write_bytes(data + b'{"v":1,"seg":"h1","se')
print("1 anchored then torn:", rec(m), "open", openc(m), "verify", m.store.verify()["ok"])
m.create_milestone("MM-C","C"); m.set_status("MM-A","IN_PROGRESS","x"); print("   later writes ok, open", openc(m))
# 2: init-host clone, first own write torn (own count 1 from HOST_REGISTERED)
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb")
mb = Manager(base/"B", actor="impl:b"); sp = mb.store.segment_path; sp.write_bytes(sp.read_bytes() + b'{"v":1,"seg"')
print("2 init-host then torn first cmd:", rec(mb), "open", openc(mb))
# 3: recover with no torn tail
print("3 recover clean:", cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=io.StringIO()), "open", openc(m))
