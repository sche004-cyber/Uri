"""FB4 e1b: base dict with credential key and string value, fresh store per case; show stored line + verify + fold."""
import sys, os, tempfile
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import store as S, model as M, service as SV
cases = [{"password": "hunter2xyz"}, {"api_key": "Zq81mPx0aa"}, {"db_password": "Tr0ub4dor&3"},
         {"PASSWORD-RESET": 3}, {"M1": "password=hunter2"}, {"M1": {"secret": "abc"}}]
for base in cases:
    root = tempfile.mkdtemp(prefix="e1b_", dir=os.environ["TEMP"])
    home = os.path.join(root, "home")
    st = S.EventStore.init(home, host_id="h1")
    try:
        with st.locked():
            st.append_many([("NOTE", {"x": 1}, base)], actor="agent")
        line = open(st.segment_path, encoding="utf-8").read().strip().splitlines()[-1]
        v = st.verify()
        try:
            p = SV.Manager(home, actor="a").projection()
            fold = f"fold ok, integrity_errors={p['integrity_errors'][:1]}"
        except Exception as e:
            fold = f"fold raised {type(e).__name__}: {e}"
        print("STORED ", base, "| verify ok:", v["ok"], "|", fold, "| line has base:", '"base":' + line.split('"base":')[1][:50])
    except Exception as e:
        print("REFUSED", base, type(e).__name__, str(e)[:80])
