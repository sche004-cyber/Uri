import sys, os, shutil, subprocess, traceback
src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
for lab, kind, data in [("unknown kind", "FOO_BAR", {"x": 1}), ("handoff no id", "HANDOFF_RECORDED", {"note": "x"}),
                        ("status-set no id", "MILESTONE_STATUS_SET", {"status": "DONE"}), ("data list", "MILESTONE_CREATED", [1])]:
    h = os.path.join(base, "mal"); shutil.rmtree(h, ignore_errors=True); EventStore.init(h, "h1")
    m = Manager(h, actor="a:1"); m.create_milestone("M1", "t")
    st = EventStore(h)
    with st.locked(): st.append_many([(kind, data, None)], actor="a:2")
    try:
        Manager(h, actor="a:1").projection(); r = "fold OK"
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]; r = f"fold {type(e).__name__} {e} at {os.path.basename(tb.filename)}:{tb.lineno}"
    v = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", h, "verify"], cwd=src, env=env, capture_output=True, text=True)
    print(lab, "|", r, "| cli verify rc", v.returncode, v.stdout.strip().replace("\n", " ")[:120])
