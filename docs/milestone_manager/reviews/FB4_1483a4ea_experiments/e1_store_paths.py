"""FB4 e1: direct EventStore write paths (append_many base/kind/actor/session/ts, reanchor, recover)."""
import sys, os, json, tempfile
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import store as S, model as M
root = tempfile.mkdtemp(prefix="e1_", dir=os.environ["TEMP"])
st = S.EventStore.init(os.path.join(root, "home"), host_id="h1")
def tryit(label, **kw):
    args = dict(kind="NOTE", data={"x": 1}, base={}, actor="agent", session=None, ts=None)
    args.update(kw)
    try:
        with st.locked():
            evs = st.append_many([(args["kind"], args["data"], args["base"])], actor=args["actor"],
                                 session=args["session"], ts=args["ts"])
        raw = open(st.segment_path, encoding="utf-8").read()
        print(f"STORED  {label}: hunter2 in segment={'hunter2' in raw or 'Hunter2' in raw}")
    except Exception as e:
        print(f"REFUSED {label}: {type(e).__name__} {str(e)[:90]}")
tryit("base dict password->str", base={"password": "hunter2xyz"})
tryit("base dict api_key->str", base={"api_key": "hunter2xyz9"})
tryit("base key password=hunter2", base={"password=hunter2": 0})
tryit("base id PASSWORD-RESET", base={"PASSWORD-RESET": 3})
tryit("base value nested dict", base={"M1": {"password": "hunter2"}})
tryit("base value list", base={"M1": ["password", "hunter2"]})
tryit("kind assignment", kind="password=hunter2")
tryit("kind dict-like", kind='{"password": "hunter2"}')
tryit("actor", actor="password=hunter2")
tryit("session", session="password: hunter2")
tryit("ts", ts="password=hunter2")
tryit("data dict", data={"password": "hunter2"})
tryit("data key text", data={"password=hunter2": 1})
tryit("data nested list", data={"cfg": [{"db_password": "hunter2"}]})
tryit("data value dict leaf", data={"password": {"hunter2": None}})
tryit("data value under key 'value'", data={"secret": {"value": "hunter2"}})
tryit("data value json string", data={"note": '{"password": "hunter2"}'})
tryit("data flag", data={"cmd": "psql --password hunter2"})
tryit("data int pwd", data={"pin_password": 123456})
# reanchor / recover
for label, fn in [("reanchor reason", lambda: st.reanchor("agent", "password: hunter2")),
                  ("reanchor actor", lambda: st.reanchor("password=hunter2", "ok")),
                  ("reanchor session", lambda: st.reanchor("agent", "ok", session="token: hunter2abc")),
                  ("recover actor", lambda: st.recover("password=hunter2")),
                  ("recover session", lambda: st.recover("agent", session='{"password":"hunter2"}'))]:
    try:
        fn(); print("RAN    ", label)
    except Exception as e:
        print(f"REFUSED {label}: {type(e).__name__} {str(e)[:80]}")
