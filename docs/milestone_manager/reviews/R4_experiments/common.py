import sys, tempfile, json, datetime
sys.path.insert(0, "C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/7930d870-1417-469b-b31b-e46354e768c5/scratchpad/src")
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
