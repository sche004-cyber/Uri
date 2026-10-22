import sys
which=sys.argv[1]
T="C:/Users/cheta/AppData/Local/Temp/r23_0nhyl83y"
sys.path.insert(0, T+("/old" if which=="old" else "/src"))
import os, tempfile, subprocess
from pathlib import Path
os.environ["TEMP"]=os.environ["TMP"]=T+"/tmp"; tempfile.tempdir=T+"/tmp"; sys.dont_write_bytecode=True
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
import scripts.dev_workflow.milestones.store as _S; print(_S.__file__)
def g(repo,*a): return subprocess.run(["git","-C",str(repo),*a],capture_output=True,text=True,encoding="utf-8")
for tag,sub,cfg in (("nonascii","lédger",None),("diff.relative","ledger",("diff.relative","true"))):
    repo=Path(tempfile.mkdtemp(prefix="acrepo_"))/"repo"; repo.mkdir(); g(repo,"init","-q"); g(repo,"config","user.name","t"); g(repo,"config","user.email","t@t")
    if cfg: g(repo,"config",*cfg)
    home=repo/sub; EventStore.init(home,"h1",autocommit=True); m=Manager(home,actor="impl:a"); m.create_milestone("MM-A","A")
    print(which,tag,m.last_autocommit, g(repo,"log","--format=%s").stdout.strip().splitlines()[:2])
