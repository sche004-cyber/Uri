import sys, tempfile, json, datetime, os
T="C:/Users/cheta/AppData/Local/Temp/r6rev_b148t_ld"
sys.path.insert(0, T+"/src")
os.environ["TEMP"]=os.environ["TMP"]=T
tempfile.tempdir=T
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore, StoreError, read_segment
from scripts.dev_workflow.milestones.model import ValidationError
from scripts.dev_workflow.milestones import views, importers, cli, model
from pathlib import Path
C1="1"*40; C2="2"*40
def new(host="h1", actor="impl:a"):
    home = Path(tempfile.mkdtemp(prefix="mmrev_"))/"ledger"
    EventStore.init(home, host)
    return Manager(home, actor=actor, session="s1")
