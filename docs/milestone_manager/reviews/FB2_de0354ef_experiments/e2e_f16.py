import sys, os, subprocess, json, tempfile
src = sys.argv[1]; base = sys.argv[2]
sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore, StoreError
from scripts.dev_workflow.milestones.service import Manager
home = os.path.join(base, "e2e_ledger")
env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
def cli(*a):
    r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "--actor", "rev:fb2", *a],
                       cwd=src, env=env, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] 
print("init", cli("init", "--host-id", "h1"))
print("add", cli("milestone-add", "M1", "--title", "t"))
for v in ["db_password=hunter2", '{"password": "x1y2"}', "password=HUNTER_TWO", "password＝hunter2",
          "token: 128k context",
          "mysql -u root --password=hunter2", "**password**: hunter2", "password:\n  hunter2",
          "token=TOKEN_8F3A9C2B7D1E6F", "password_reset=NewPass2024!", "password_hint: hunter2",
          "Authorization: Basic dXNlcjpodW50ZXIy", "token: streaming enabled"]:
    print("CLI handoff", repr(v), cli("handoff", "M1", "--summary", v))
    print("CLI next-action", repr(v), cli("milestone-update", "M1", "--next-action", v))
print("CLI reanchor", cli("reanchor", "--reason", "mysql --password=hunter2"))
print("CLI recover", cli("recover", "--reason", "--api-key=abc123def456ghi"))
st = EventStore(home)
for data in [{"note": "--password=hunter2"}, {"x": {"password": {"hunter2": None}}}, {"password": {"hunter2": "x"}}]:
    try:
        with st.locked():
            st.append_many([("handoff.recorded", data, None)], actor="rev:fb2")
        print("store append_many ACCEPTED", data)
    except StoreError as e:
        print("store append_many refused", data, e.code)
    except Exception as e:
        print("store append_many other", data, type(e).__name__, e)
m = Manager(home, actor="rev:fb2", session="s")
for v in ["github_token=abc123def", "--token=abcdef123456"]:
    try:
        m.record_handoff("M1", v); print("svc ACCEPTED", v)
    except Exception as e:
        print("svc refused", v, getattr(e, "code", e))
print("verify", cli("verify"))
