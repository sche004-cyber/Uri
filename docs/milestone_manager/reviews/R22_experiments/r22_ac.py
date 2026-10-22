from common import *
import subprocess
base=Path(tempfile.mkdtemp())
def g(*a): return subprocess.run(["git","-C",str(base),*a],capture_output=True,text=True).stdout
g("init","-q"); g("config","user.name","t"); g("config","user.email","t@t")
(base/"README").write_text("x"); g("add","README"); g("commit","-qm","init")
EventStore.init(base/"ledger","h1",autocommit=True); m=Manager(base/"ledger",actor="impl:a")
m.create_milestone("MM-1","x")
(base/"wip.txt").write_text("user's unfinished staged work"); g("add","wip.txt")
m.create_milestone("MM-2","y")
print(g("log","--stat","--oneline","-3"))
print("status:", g("status","--porcelain"))
