"""FB4 e2: in-contract notations through model.find_secret (the detector used by every write path)."""
import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import model as M
S = "Zq81mPx0aa"  # a plausible secret value
MUST = {  # expected refused (in contract)
 "kv =": f"password={S}", "kv :": f"password: {S}", "kv spaced": f"password = {S}",
 "prefix": f"db_password={S}", "UPPER": f"DB_PASSWORD={S}", "camel": f"dbPassword: {S}", "dash": f"github-token: {S}",
 "api key words": f"API key: {S}", "secret key words": f"- Secret key = {S}", "DB password": f"DB password: {S}",
 "three-word": f"Prod DB password: {S}", "client secret": f"client secret: {S}",
 "json": f'{{"password": "{S}"}}', "json nospace": f'{{"user":"bob","password":"{S}"}}',
 "json spaced key": f'{{"db password": "{S}"}}', "py dict": f"{{'api_key': '{S}'}}",
 "yaml inline": f"db:\n  password: {S}\n", "yaml block": f"password:\n  {S}\n",
 "yaml literal": f"password: |\n  line1\n  {S}\n", "yaml folded 2nd line": f"token: >\n  ok\n  {S}\n",
 "yaml block nested in list": f"- name: x\n  password:\n    {S}\n",
 "yaml quoted": f"password: '{S}'", "md bold": f"**password**: {S}", "md bold colon inside": f"**Password:** {S}",
 "md code": f"`api_key`: {S}", "md underscore": f"__password__: {S}", "md strike": f"~~password~~: {S}",
 "md single underscore": f"_password_: {S}", "md bold underscore multiword": f"__API key__: {S}",
 "md list bold": f"- **DB password**: {S}",
 "table": f"| password | {S} |", "table multiword key": f"| DB password | {S} |",
 "table quoted key": f"| 'password' | {S} |", "table 3col": f"| svc | password | {S} |",
 "table multiword value": f"| password | {S} and more |", "table md key": f"| **password** | {S} |",
 "table code key": f"| `api_key` | {S} |",
 "flag =": f"--password={S}", "flag space": f"--password {S}", "flag single dash": f"-pwd {S}",
 "flag in cmd": f"psql -h db --db-password {S} -U x", "flag quoted": f'--password "{S}"',
 "compound one-word": f"PGPASSWORD={S}", "compound lower": f"accesstoken: {S}", "compound mixed": f"MyApiKey={S}",
 "basic auth": "Authorization: Basic dXNlcjpwYXNzd29yZA==", "bearer": "Authorization: Bearer " + "a"*30,
 "url creds": "postgres://user:hunter2@db/x", "sk key": "sk-" + "a"*24, "ghp": "ghp_" + "a"*36,
 "AKIA": "AKIA" + "A"*16, "jwt": "eyJhbGciOiJI.eyJzdWIiOiIx.c2lnbmF0dXJl",
 "privkey": "-----BEGIN RSA PRIVATE KEY-----", "hf": "hf_" + "a"*34, "stripe": "sk_live_" + "a"*20,
 "slack": "xoxb-1234567890-abc",
 "fullwidth eq": f"password＝{S}", "zero width": f"pass​word={S}",
 "ref then secret": f"password: ${{DB_PASSWORD}} {S}", "env then secret": f"password: env:X {S}",
 "short pw": "password: abc", "dollar pw": "password: $uperS3cret!", "slash pw": "password: /s3cret99",
 "comma pw": "password: abc,defghi9", "7digit token": "token: 1234567", "placeholder+secret": f"password: <redacted> {S}",
 "two kv one line": f"user: bob password: {S}", "semicolon conn": f"Server=x;User Id=u;Password={S};",
 "kv after prose": f"Use this, password={S} ok", "ini": f"[db]\npassword = {S}\n",
 "env export": f"export API_KEY={S}", "env set": f"set DB_PASSWORD={S}", "toml": f'password = "{S}"',
 "python kwarg": f'connect(user="u", password="{S}")', "dict json nested": f'{{"db": {{"password": "{S}"}}}}',
 "json array of obj": f'[{{"token": "{S}"}}]', "yaml dash key": f"- password: {S}",
 "table dash key": f"| - password | {S} |",
 "key with dot": f"db.password={S}", "header style": f"X-Api-Key: {S}", "secret_access_key": f"aws_secret_access_key = {S}",
 "passphrase": f"passphrase: {S}", "passcode": f"passcode={S}", "session_key": f"session_key={S}",
 "value with dash start": f"password: -{S}", "yaml block after comment": f"password: # note\n  {S}\n",
 "yaml block anchor": f"password: &a\n  {S}\n", "yaml tag": f"password: !!str {S}",
 "json escaped quote key": f'{{"password" :\t"{S}"}}',
 "md table w/ emphasis value": f"| password | **{S}** |", "md heading key": f"### password: {S}",
 "html-ish": f"<b>password</b>: {S}", "bold value": f"password: **{S}**", "code value": f"password: `{S}`",
 "tilde fence key": f"~password~: {S}", "triple underscore": f"___password___: {S}",
 "quoted key yaml block": f'"password":\n  {S}\n', "yaml block deeper first blank": f"password:\n\n  {S}\n",
 "CRLF yaml block": f"password:\r\n  {S}\r\n", "CRLF kv": f"x: 1\r\npassword: {S}\r\n",
 "tab table": f"|\tpassword\t|\t{S}\t|", "flag tab": f"--password\t{S}",
 "plus-sign flag": f"+password={S}", "colon-eq": f"password := {S}", "arrow": f"password => {S}",
}
OK = {  # expected allowed (normal use)
 "id": "PASSWORD-RESET milestone", "ref": "password: ${DB_PASSWORD}", "env": "api_key: $OPENAI_API_KEY",
 "placeholder": "password: <redacted>", "state": "token: expired", "ctx": "token: 128k context",
 "count": "token_count: 4096", "file": "password_file: /etc/x.txt", "type": "api_key_type: bearer",
 "prose": "We rotated the password yesterday.", "header": "| Token | Value |",
 "milestone ids": "MM-TOKEN-REFRESH depends on API-KEY-ROTATION", "mask": "password: ********",
 "decision": "DEC-012: secrets live in the OS keyring, never in the ledger",
 "md list": "- secret refusal: done", "yaml list ok": "password:\n  - required\n",
}
fails = []
for k, v in MUST.items():
    r = M.find_secret(v)
    if not r: fails.append(k)
    print(("ok   " if r else "MISS ") + f"{k!r}: {v!r} -> {r}")
print("---- normal use")
fp = []
for k, v in OK.items():
    r = M.find_secret(v)
    if r: fp.append(k)
    print(("FP   " if r else "ok   ") + f"{k!r}: {v!r} -> {r}")
print("MISSES:", fails); print("FALSE POSITIVES:", fp)
