import sys, json
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones.model import find_secret as f
# (label, value, expected 'refuse'|'allow')
R, A = "refuse", "allow"
cases = [
 # prior FB ids
 ("FB-01 db_password", "db_password=hunter2", R), ("FB-01 DB_PASSWORD", "DB_PASSWORD: hunter2", R),
 ("FB-01 github_token", "github_token=abc123def", R), ("FB-01 myPassword", "myPassword=hunter2", R),
 ("FB-01 dict", {"db_password": "hunter2"}, R), ("FB-01 dict camel", {"myPassword": "hunter2"}, R),
 ("FB-02 json", '{"password": "x1y2"}', R), ("FB-02 quoted eq", '"password"="x1y2"', R), ("FB-02 single", "'password': 'x1y2'", R),
 ("FB-03 none", {"password": {"hunter2": None}}, R), ("FB-03 bool", {"password": {"hunter2": True}}, R), ("FB-03 empty", {"password": {"hunter2": {}}}, R),
 ("FB-04 caps", "password=HUNTER_TWO", R), ("FB-04 digits", "secret=1234567", R),
 ("FB-04 fullwidth", "password\uff1dhunter2", R), ("FB-04 zw", "pass\u200bword=hunter2", R), ("FB-04 zw2", "password=hun\u200bter2", R),
 ("FB-05 128k", "token: 128k context", A), ("FB-05 32768", "token: 32768 tokens", A),
 # new hunting: CLI flags
 ("cli --password=", "mysql -u root --password=hunter2", R), ("cli --api-key=", "run --api-key=abc123def456", R),
 ("cli --token=", "gh auth --token=abcdef123456", R), ("cli -password=", "tool -password=hunter2", R),
 ("cli --password space", "mysql --password hunter2", R),
 # markdown
 ("md bold key", "**password**: hunter2", R), ("md code key", "`password`: hunter2", R), ("md table", "| password | hunter2 |", R),
 ("md bold colon inside", "**Password:** hunter2", R),
 # yaml / multiline
 ("yaml block |", "password: |\n  hunter2", R), ("yaml newline", "password:\n  hunter2", R), ("yaml >", "password: >\n  hunter2", R),
 # json key with space
 ("json key space", '{"db password": "hunter2"}', R), ("json key trailing sp", '{"password ": "hunter2"}', R),
 # xml / html
 ("xml", "<password>hunter2</password>", R),
 # other key words
 ("pass", "pass=hunter2", R), ("pw", "pw: hunter2", R), ("passcode", "passcode=482913", R), ("pin", "pin=4829", A),
 ("auth basic", "Authorization: Basic dXNlcjpodW50ZXIy", R), ("cookie", "cookie: sessionid=9f8e7d6c5b4a", R),
 ("session_key", "session_key=9f8e7d6c5b4a3f2e", R),
 # descriptive words
 ("password_file hunter2", "password_file=hunter2", R), ("password_hint", "password_hint: hunter2", R),
 ("token_type", "token_type: Bearer", A), ("password_used", "password_used=Hunter2!", R), ("secret_path", "secret_path=Xk9vQ2", R),
 ("api_key_size", "api_key_size=abc123def456ghi", R), ("token_usage", "token_usage: ghx9a8b7c6", R),
 ("dict password_file", {"password_file": "hunter2"}, R), ("dict api_key_type", {"api_key_type": "q8W3eR5tY7"}, R),
 # env name exemption
 ("env-ish secret", "password=SUPER_SECRET_99", R), ("env-ish token", "token=TOKEN_8F3A9C2B7D1E6F", R),
 ("env-ish apikey", "api_key=API_KEY_9F8E7D6C5B4A3F2E", R), ("env-ish $", "password=$ADMIN_PASSWORD_2024", R),
 ("dict env-ish", {"api_key": "PROD_API_KEY_7Q2W9E4R"}, R),
 # numbers under token
 ("token 6 digits", "token: 482913", R), ("dict token int", {"token": 4829131}, R), ("token 7 digits k", "token=1234567k", R),
 # placeholder words
 ("password set + secret?", "password: set hunter2", R), ("password none;x", "password: none;hunter2", R),
 ("password none|x", "password=none|hunter2", R), ("password x mask", "password=xXx.X", R),
 ("password <ref>", "password=<my secret is hunter2>", R),
 # structure
 ("dict nested non-leaf", {"password": {"hunter2": "x"}}, R), ("dict nested none str", {"password": {"hunter2": "none"}}, R),
 ("list pair", ["password", "hunter2"], R), ("k8s env", {"name": "DB_PASSWORD", "value": "hunter2"}, R),
 ("tuple key", {("password",): "hunter2"}, R),
 ("bytes", {"password": b"hunter2"}, R),
 # multiple assignments
 ("multi", "user=bob password=hunter2", R), ("multi2", "password=none, token=abc123xyz", R),
 ("multi3", "password: none user: bob hunter2", R),
 # separators / unicode
 ("colon fullwidth", "password\uff1ahunter2", R), ("cyrillic o", "passw\u043erd=hunter2", R), ("nbsp", "password\u00a0=\u00a0hunter2", R),
 ("tab", "password\t=\thunter2", R), ("arrow", "password => hunter2", R), ("dash", "password - hunter2", R),
 ("is", "the password is hunter2", R),
 ("url creds", "postgres://admin:hunter2@db:5432/x", R), ("url query", "https://x.io/cb?token=abc123def456", R),
 ("dotted", "spring.datasource.password=hunter2", R),
 # false positive checks
 ("fp path", r"C:\uri-model-lab\models\token_budget.json", A), ("fp context", "context 65536 tokens; token budget 32k", A),
 ("fp env prose", "set TAVILY_API_KEY in the environment", A), ("fp env assign ref", "api_key=${OPENAI_API_KEY}", A),
 ("fp password policy", "password_policy: strong", A), ("fp token_count", "token_count=4096", A),
 ("fp prose secret", "no secrets are stored in the ledger", A), ("fp sha", "commit de0354ef16558afe26045e7c69e02f86ebaa1b1e", A),
 ("fp token prose colon", "Token: the brain spends tokens on prompts", A), ("fp secret prose", "Secret handling: references only", A),
 ("fp password field", "password: required", A), ("fp key ref", "api_key=env:TAVILY_API_KEY", A),
 ("fp token streaming", "token: streaming enabled", A), ("fp auth key", "auth_key: rotated", A),
 ("fp max_tokens", "max_tokens=8192", A), ("fp token budget", "token: 64K budget", A),
 ("fp secrets dir", "secrets: stored in D:/vault", A), ("fp tokens per sec", "tokens: 25 tok/s", A),
 ("fp tokenizer", "tokenizer: qwen3", A), ("fp credential mgr", "credentials: Windows Credential Manager", A),
]
rows=[]; bad=[]
for lab, v, exp in cases:
    got = f(v); act = R if got else A
    ok = act == exp
    rows.append((ok, lab, repr(v)[:60], exp, act, got))
    if not ok: bad.append(lab)
for r in rows: print(("OK  " if r[0] else "MISS"), r[1], "|", r[2], "| exp", r[3], "got", r[4], r[5] or "")
print("MISMATCH", len(bad), "of", len(cases))
