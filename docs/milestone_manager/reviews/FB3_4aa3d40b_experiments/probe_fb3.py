import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones.model import find_secret as f
R, A = "refuse", "allow"
cases = [
 # table rows (in contract: key/value table rows)
 ("tbl spaced value", "| password | correct horse battery staple |", R),
 ("tbl spaced key", "| API key | 9f8e7d6c5b4a3f2e1d0c |", R),
 ("tbl spaced key2", "| DB password | hunter2 |", R),
 ("tbl quoted key", '| "password" | hunter2 |', R),
 ("tbl 2col header+row", "| Key | Value |\n|---|---|\n| password | hunter2 |", R),
 ("tbl backtick val", "| `password` | `hunter2` |", R),
 # bare multi-word keys in key: v
 ("API key: v", "API key: 9f8e7d6c5b4a3f2e1d0c", R),
 ("Secret key: v", "Secret key: 9f8e7d6c5b4a3f2e", R),
 ("Private key: v", "Private key: abcdef0123456789", R),
 ("Access key = v", "Access key = abcdef0123456789", R),
 ("Session key: v", "Session key: abcdef0123456789", R),
 ("md API key", "- **API key:** 9f8e7d6c5b4a3f2e1d0c", R),
 ("API_KEY ok", "API_KEY: 9f8e7d6c5b4a", R),
 # compound one-word keys
 ("PGPASSWORD", "PGPASSWORD=hunter2", R), ("MYSQL_PWD", "MYSQL_PWD=hunter2", R),
 ("accesstoken", "accesstoken=abcdef123456", R), ("ACCESSTOKEN", "ACCESSTOKEN=abcdef123456", R),
 ("authtoken", "authtoken: abcdef123456", R), ("adminpassword", "adminpassword=hunter2", R),
 ("dict PGPASSWORD", {"PGPASSWORD": "hunter2"}, R),
 # markdown underscore emphasis
 ("md __key__", "__password__: hunter2", R), ("md _key_", "_password_: hunter2", R),
 ("md ~~", "~~password~~: hunter2", R),
 # yaml block multi-line with exempt first line
 ("yaml | none+secret", "password: |\n  none\n  hunter2", R),
 ("yaml > ref+secret", "password: >-\n  ${PASS}\n  hunter2", R),
 ("yaml list", "password:\n  - hunter2", R),
 ("yaml nested", "db:\n  password: hunter2", R),
 ("yaml inline map", "{password: hunter2, user: bob}", R),
 ("yaml dash item", "- password: hunter2", R),
 ("yaml quoted val spaces", 'password: "correct horse battery"', R),
 # flags
 ("flag dash value", "app --password -Xy9z!", R), ("flag tab", "app --password\thunter2", R),
 ("flag quoted", "app --password 'hunter two'", R), ("flag ps", "Connect -Password hunter2", R),
 ("flag win", "tool /password:hunter2", R), ("flag nbsp", "app --password hunter2", R),
 ("flag after ref", "app --password ${PASS} --token abc123def456", R),
 ("flag with equals space", "app --password = hunter2", R),
 # dict structure
 ("dict exempt-inner", {"password": {"hunter2": {"none": None}}}, R),
 ("dict list in", {"password": ["none", "hunter2"]}, R),
 ("dict int", {"pin_token": 48291}, R),
 ("dict nested key-in-str", {"cfg": "{'password': 'hunter2'}"}, R),
 ("json key apostrophe", '{"user\'s password": "hunter2"}', R),
 ("json key >60", '{"' + "a"*55 + '_password": "hunter2"}', R),
 ("json escaped key", '{"pass\u0077ord": "hunter2"}', R),
 ("json spaced colon", '{"password" : "hunter2"}', R),
 ("python kwargs", "connect(user='bob', password='hunter2')", R),
 ("subscript", "os.environ['DB_PASSWORD'] = 'hunter2'", R),
 ("ini", "[db]\npassword = hunter2", R),
 ("dotenv quoted", 'PASSWORD="hunter two"', R),
 ("ruby", "password => 'hunter2'", R),
 ("cut via fake key", "password: none, hunter2: x", R),
 ("token k suffix", "token: 482913k", R),
 ("env-shaped value", "password=HUNTER_TOKEN", R),
 ("angle placeholder val", "password=<hunter_two>", R),
 ("status word val", "password: enabled hidden", A),
 # descriptive keys
 ("pw_file path", "password_file: /run/secrets/db", A), ("token_type", "token_type: Bearer", A),
 ("secret_mode letters", "secret_mode: HunterTwoPass", A),
 ("password_length", "password_length: 16", A), ("token_limit", "token_limit=8192", A),
 # FPs typical docs
 ("fp token budget prose", "token budget: 32k per turn", A),
 ("fp max_tokens", "max_tokens: 4096", A),
 ("fp secret refusal prose", "Secret refusal: F16 contract", A),
 ("fp tokens table", "| tokens | 65536 |", A),
 ("fp password table header", "| Field | Password policy |", A),
 ("fp api_key ref", "api_key: ${OPENAI_API_KEY}", A),
 ("fp env name", "TAVILY_API_KEY: set", A),
]
bad = 0
for lab, v, exp in cases:
    got = f(v); act = R if got else A
    ok = act == exp; bad += not ok
    print(("OK  " if ok else "MISS"), lab, "|", repr(v)[:70], "| exp", exp, "got", act)
print("MISMATCH", bad, "of", len(cases))
