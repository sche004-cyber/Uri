import sys; sys.argv=[sys.argv[0], "none"]
exec(open("r13_new2.py").read().split("which = sys.argv[1]")[0])
home = Path(tempfile.mkdtemp())/"L"; EventStore.init(home, "h1")
child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
EventStore.write_anchors = lambda self, segs: os._exit(9)
Manager(r"{home}", actor="impl:a").create_milestone("MM-A","A")
'''
print("child rc", subprocess.run([sys.executable, "-c", child]).returncode)
# make a torn tail too (power loss mid next write)
seg = home/"events/h1.jsonl"; seg.write_bytes(seg.read_bytes() + b'{"partial":')
print("status warn", [w[:70] for w in Manager(home, actor="x").projection()["integrity_warnings"]])
rc, out = cli_run(home, "--actor", "impl:a", "recover"); print("recover rc", rc, out)
print("open", openc(home), "torn left:", seg.read_bytes().endswith(b'{"partial":'))
