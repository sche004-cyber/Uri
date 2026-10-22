import sys, tempfile, json, datetime, os, io
T="C:/Users/cheta/AppData/Local/Temp/r23_0nhyl83y"
sys.dont_write_bytecode=True
sys.path.insert(0, T+"/src")
os.environ["TEMP"]=os.environ["TMP"]=T+"/tmp"
tempfile.tempdir=T+"/tmp"
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore, StoreError, read_segment
from scripts.dev_workflow.milestones.model import ValidationError
from scripts.dev_workflow.milestones import views, importers, cli, model
from pathlib import Path
C1="1"*40; C2="2"*40; C3="3"*40
def new(host="h1", actor="impl:a"):
    home = Path(tempfile.mkdtemp(prefix="mmrev_"))/"ledger"
    EventStore.init(home, host)
    return Manager(home, actor=actor, session="s1")
def runcli(*argv):
    buf=io.StringIO(); rc=cli.run(list(argv), out=buf); return rc, buf.getvalue()
def segbytes(home):
    return {p.name: p.read_bytes() for p in sorted((Path(home)/"events").glob("*.jsonl"))}
