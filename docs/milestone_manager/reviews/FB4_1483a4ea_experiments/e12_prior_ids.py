"""FB4 e12: re-run the reproduction of every prior secret-refusal id against the detector + store preflight."""
import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import model as M, store as S
def refused(v):
    try: S.check_free_text(data=v); return False
    except S.StoreError as e: return e.code == "SECRET"
must = {
 "R2-01 base key text": None,
 "R3-01": {"access_token": "abc123def456ghi789jkl012mno345"},
 "R4-01": {"api_key": {"value": "abcd1234xyz9876"}},
 "R5-01": {"credentials": {"password": {"value": "s3cret/abc123"}}},
 "R6-01": {"password": {"value": "/s3cret99"}},
 "R7-01": {"metadata": {"password": "abc,defghi9"}},
 "R8-01": {"password": {"value": "$uperS3cret!"}},
 "D2-01": {"password": {"value": "abc"}},
 "D2-02": "password: ${PASSWORD} hunter2",
 "FB-01a": "db_password=hunter2x", "FB-01b": "DB_PASSWORD=hunter2x", "FB-01c": "github_token: abcdef123456",
 "FB-01d": "myPassword=hunter2x", "FB-02": '{"password": "x"}', "FB-03": {"password": {"hunter2": None}},
 "FB-03b": {"password": {"hunter2": True}}, "FB-03c": {"password": {"hunter2": {}}},
 "FB-04a": "password: HUNTER_TWO", "FB-04b": "secret=1234567", "FB-04c": "password＝hunter2", "FB-04d": "pass​word=hunter2",
 "FB2-01a": "--password=hunter2", "FB2-01b": "--password hunter2",
 "FB2-02a": "**password**: hunter2", "FB2-02b": "password:\n  hunter2", "FB2-02c": "| password | hunter2 |", "FB2-02d": '{"db password": "hunter2"}',
 "FB2-03a": "password: SUPER_SECRET_99", "FB2-03b": "api_key: PROD_API_KEY_7Q2W9E4R", "FB2-03c": "token: TOKEN_8F3A9B",
 "FB2-04a": "password_reset: hunter2", "FB2-04b": "password_hint: hunter2", "FB2-04c": "password_file: hunter2",
 "FB2-05a": "Authorization: Basic dXNlcjpwYXNz", "FB2-05b": "passcode: 4711x", "FB2-05c": "session_key=abc123",
 "FB2-06a": "token: 1234567", "FB2-06b": "password: abc;def", "FB2-06c": "password: abc|def", "FB2-06d": "password: xXx.X",
 "FB2-06e": {"password": {"hunter2": "required"}},
 "FB3-01": "API key: hunter2x", "FB3-02a": "| DB password | hunter2 |", "FB3-02b": "| 'password' | hunter2 |", "FB3-02c": "| password | hunter two |",
 "FB3-03a": "__password__: hunter2", "FB3-03b": "~~password~~: hunter2",
 "FB3-04": "password: |\n  ok\n  hunter2\n", "FB3-06a": "PGPASSWORD=hunter2", "FB3-06b": "accesstoken: hunter2",
}
for k, v in must.items():
    if v is None:
        try:
            S.check_free_text(base=["password=12345678", 0]); print("MISS", k)
        except S.StoreError: print("ok  ", k)
        continue
    print(("ok  " if refused(v) else "MISS") + " " + k + " " + repr(v)[:60])
ok = {"FB-05a": "token: 128k context", "FB-05b": "token: 32768 tokens", "FB3-05": "PASSWORD-RESET"}
for k, v in ok.items():
    print(("ok  " if not refused(v) else "FP  ") + " " + k + " " + repr(v))
print("FB3-05 base", "ok" if not refused(["PASSWORD-RESET", 1]) else "FP")
