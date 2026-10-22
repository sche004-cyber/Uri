"""FB4 e8: Authorization: Basic in dict/JSON/YAML/table/flag notations; plus misc dict-walker edges."""
import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import model as M
B = "Basic dXNlcjpodW50ZXIy"  # user:hunter2
cases = {
 "text": f"Authorization: {B}", "text =": f"authorization={B}",
 "json text": f'{{"Authorization": "{B}"}}', "py text": f"{{'Authorization': '{B}'}}",
 "dict": {"Authorization": B}, "nested dict": {"headers": {"Authorization": B}},
 "yaml block": f"Authorization:\n  {B}\n", "table": f"| Authorization | {B} |",
 "curl flag": f'curl -H "Authorization: {B}" https://x', "md bold": f"**Authorization**: {B}",
 "dict bearer": {"Authorization": "Bearer " + "a"*30}, "header list": ["Authorization", B],
 "proxy-authorization": f"Proxy-Authorization: {B}",
 "dict tuple pairs": {"env": [["password", "Zq81mPx0aa"]]},
 "dict key int value": {"password": 12345678}, "dict float": {"token": 1234.5678},
 "dict key with spaces": {"DB password": "Zq81mPx0aa"}, "dict key md": {"**password**": "Zq81mPx0aa"},
 "dict value md": {"password": "**Zq81mPx0aa**"}, "dict key ___": {"___password___": "Zq81mPx0aa"},
 "dict str under list under key": {"password": ["required", "Zq81mPx0aa"]},
 "dict deep": {"a": {"b": {"c": {"api_key": "Zq81mPx0aa"}}}},
 "leaf key secret placeholder value": {"password": {"Zq81mPx0aa": "set"}},
 "leaf key secret str exempt value": {"password": {"Zq81mPx0aa": "required"}},
 "leaf key nested dict": {"password": {"Zq81mPx0aa": {"x": 1}}},
}
for k, v in cases.items():
    print(("REFUSED " if M.find_secret(v) else "PASSED  ") + f"{k}: {v!r}")
