"""FB4 e3: markdown emphasis variants and other FB3-repair edges."""
import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import model as M
S = "Zq81mPx0aa"
cases = ["___password___: {S}", "_**password**_: {S}", "**_password_**: {S}", "__**password**__: {S}",
 "*password*: {S}", "***password***: {S}", "__password__ = {S}", "~~**password**~~: {S}", "_password_={S}",
 "__API_KEY__: {S}", "__db_password__: {S}", "_db password_: {S}", "__DB password__: {S}",
 "**DB** password: {S}", "DB **password**: {S}", "the db password: {S}", "my API key: {S}",
 "API secret key: {S}", "api\tkey: {S}", "API  key: {S}", "Super secret key: {S}",
 "| API key | {S} |", "|API key|{S}|", "| my api key | {S} |", "| Prod DB password | {S} |", "| password | {S} | x |",
 "| x | password | {S} |", "| **API key** | {S} |", "|password|`{S}`|",
 "password:\n    {S}\n  other: 1\n", "  password: |\n    ok\n    {S}\n", "password: >-\n  {S}\n",
 "password: |2\n  {S}\n", "password: >\n\n  {S}\n", "password:\n\t{S}\n", "db:\n  password:\n  {S}\n",
 "PGPASSWORD={S}", "MYSQL_PWD={S}", "apitoken: {S}", "authtoken={S}", "xpassword: {S}", "Accesstoken: {S}",
 "clientsecret={S}", "OPENAIAPIKEY={S}", "bearertoken: {S}", "AUTHKEY={S}", "sessiontoken={S}",
 "--api-key {S}", "--apiKey={S}", "-p {S}", "--token={S} --x y", "--secret '{S}'", "--client-secret=\"{S}\"",
 "-password:{S}", "/password:{S}",
 "{{\"api key\": \"{S}\"}}", "{{'DB Password': '{S}'}}", "{{\"x-api-key\":\"{S}\"}}",
 "password: none {S}", "password: set, {S}", "password = \"none, b: {S}\"", "password: \"set,x={S}\"",
 "password: HUNTER_TWO_PASSWORD", "password: <hunter>", "password: Required{S}", "password: ********{S}",
 "token: 65536 {S}", "token: 128k {S}", "token_count: 4096{S}", "password_file: {S}", "password_file: a/{S}",
 "api_key_type: {S}", "password_policy: {S}", "token_type: Bearer", "token_ttl: 1h", "password_hint: {S}",
 "password_mode: abc", "password_len: 12a",
]
for c in cases:
    t = c.format(S=S)
    print(("REFUSED " if M.find_secret(t) else "PASSED  ") + repr(t))
