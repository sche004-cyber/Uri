import os, sys, shutil, json
from pathlib import Path
from scripts.dev_workflow.milestones.store import EventStore, StoreError
from scripts.dev_workflow.milestones import model as M
D = Path(os.environ["MMFB"]) / "ex" / "home_store"
shutil.rmtree(D, ignore_errors=True)
s = EventStore.init(D, host_id="hosts")
def tryit(name, fn):
    try:
        r = fn(); print("ACCEPTED ", name)
    except (StoreError, M.ValidationError) as e:
        print("refused  ", name, e.code)
    except Exception as e:
        print("EXC      ", name, type(e).__name__, str(e)[:80])
with s.locked():
    tryit("data password", lambda: s.append("NOTE", {"password": "abc"}, "a"))
    tryit("base metadata (R2-01)", lambda: s.append("NOTE", {}, "a", base={"password=12345678": 0}))
    tryit("base nested value", lambda: s.append("NOTE", {}, "a", base={"x": {"token": "abcdef"}}))
    tryit("kind secret", lambda: s.append("password=abc", {}, "a"))
    tryit("actor secret", lambda: s.append("NOTE", {}, "token=abc"))
    tryit("session secret", lambda: s.append("NOTE", {}, "a", session="token=abc"))
    tryit("ts secret", lambda: s.append("NOTE", {}, "a", ts="password=abc"))
    tryit("append_many 2nd item", lambda: s.append_many([("NOTE", {}, None), ("NOTE", {"x": {"api_key": {"value": "abcd1234xyz9876"}}}, None)], "a"))
    tryit("R3-01 access_token", lambda: s.append("NOTE", {"access_token": "abc123def456ghi789jkl012mno345"}, "a"))
    tryit("R5-01 credentials/password slash", lambda: s.append("NOTE", {"credentials": {"password": {"value": "s3cret/abc123"}}}, "a"))
    tryit("R6-01 /s3cret99", lambda: s.append("NOTE", {"password": {"value": "/s3cret99"}}, "a"))
    tryit("R7-01 comma", lambda: s.append("NOTE", {"metadata": {"password": "abc,defghi9"}}, "a"))
    tryit("R8-01 dollar", lambda: s.append("NOTE", {"password": {"value": "$uperS3cret!"}}, "a"))
    tryit("D2-01 short", lambda: s.append("NOTE", {"password": {"value": "abc"}}, "a"))
    tryit("D2-01 1 char", lambda: s.append("NOTE", {"password": "a"}, "a"))
    tryit("D2-02 ref then pw", lambda: s.append("NOTE", {"note": "password: ${PASSWORD} hunter2"}, "a"))
    tryit("D2-02 dict ref then pw", lambda: s.append("NOTE", {"password": "${PASSWORD} hunter2"}, "a"))
    print("--- new bypass candidates")
    tryit("BYP db_password dict", lambda: s.append("NOTE", {"db_password": "BYPASS_A1x"}, "a"))
    tryit("BYP secret as dict key under password", lambda: s.append("NOTE", {"password": {"BYPASS_b2y": None}}, "a"))
    tryit("BYP secret as dict key bool", lambda: s.append("NOTE", {"password": {"BYPASS_c3z": True}}, "a"))
    tryit("BYP json text", lambda: s.append("NOTE", {"note": '{"password": "BYPASS_d4w"}'}, "a"))
    tryit("BYP free text DB_PASSWORD", lambda: s.append("NOTE", {"note": "DB_PASSWORD=BYPASS_e5v"}, "a"))
    tryit("BYP password key in base", lambda: s.append("NOTE", {}, "a", base={"db_password": "BYPASS_f6u"}))
    tryit("BYP bytes", lambda: s.append("NOTE", {"password": b"BYPASS_g7t"}, "a"))
raw = b"".join(p.read_bytes() for p in (D/"events").glob("*.jsonl"))
for tok in [b"12345678", b"abcdef", b"abcd1234", b"s3cret", b"defghi9", b"uperS3", b"hunter2", b"BYPASS_A1x", b"BYPASS_b2y", b"BYPASS_c3z", b"BYPASS_d4w", b"BYPASS_e5v", b"BYPASS_f6u", b"BYPASS_g7t"]:
    print("in segment" if tok in raw else "absent    ", tok)
