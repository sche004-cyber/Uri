"""Provision only a fresh C1 fixture; never install a task or change a shortcut."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uri_core.core.runtime_identity import provision,RuntimeIdentityError

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--state-root",required=True);p.add_argument("--port",type=int,default=8031)
    p.add_argument("--composition",choices=("c1-isolated-compatibility","c2-paired-core"),default="c1-isolated-compatibility")
    a=p.parse_args()
    try:
        manifest=provision(Path(__file__).resolve().parents[1],Path(a.state_root),Path(sys.executable),a.port,a.composition)
        print(json.dumps({"result":"PROVISIONED","manifest":str(manifest)}))
    except RuntimeIdentityError as exc:
        print(json.dumps({"result":"REFUSED","code":str(exc)}));sys.exit(1)
