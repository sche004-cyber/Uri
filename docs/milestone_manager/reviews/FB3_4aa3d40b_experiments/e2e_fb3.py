import sys, os, subprocess, json, shutil
src, base = sys.argv[1], sys.argv[2]
sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore, StoreError
home = os.path.join(base, "e2e_fb3"); shutil.rmtree(home, ignore_errors=True)
env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
def cli(*a):
    r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "--actor", "rev:fb3", *a],
                       cwd=src, env=env, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:]
print("init", cli("init", "--host-id", "h1"))
print("add", cli("milestone-add", "M1", "--title", "t"))
vals = ["API key: 9f8e7d6c5b4a3f2e1d0c", "| DB password | hunter2 |", "| password | correct horse battery staple |",
        "__password__: hunter2", "password: |\n  none\n  hunter2", "PGPASSWORD=hunter2"]
for v in vals:
    print("CLI handoff", repr(v), cli("handoff", "M1", "--summary", v))
    print("CLI next-action", repr(v), cli("milestone-update", "M1", "--next-action", v))
st = EventStore(home)
for data in [{"note": "Secret key: 9f8e7d6c5b4a3f2e"}]:
    try:
        with st.locked():
            st.append_many([("HANDOFF_RECORDED", data, None)], actor="rev:fb3")
        print("store append_many ACCEPTED", data)
    except StoreError as e:
        print("store append_many refused", data, e.code)
blob = open(st.segment_path, encoding="utf-8").read()
for needle in ["9f8e7d6c5b4a3f2e1d0c", "DB password | hunter2", "correct horse battery staple", "__password__: hunter2", "PGPASSWORD=hunter2", "Secret key: 9f8e"]:
    print("in segment:", needle, needle in blob)
print("verify", cli("verify"))
