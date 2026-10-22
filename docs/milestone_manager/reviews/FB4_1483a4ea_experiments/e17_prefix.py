"""FB4 e17: key prefix characters and formatting edges (key=v notation with a credential-word key)."""
import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import model as M
S = "Zq81mPx0aa"
cases = [f"_password = '{S}'", f"self._password = '{S}'", f"__password = '{S}'", f"_api_key: {S}", f"_DB_PASSWORD={S}",
 f"$password = '{S}'", f"@password = {S}", f"1password: {S}", f"1.password: {S}", f"#password={S}", f"&password={S}",
 f"?token={S}", f"https://x/cb?access_token={S}", f"https://x/cb?a=1&api_key={S}", f"x.password={S}",
 f"cfg['password'] = '{S}'", f'cfg["api_key"]="{S}"', f"os.environ['DB_PASSWORD'] = '{S}'",
 f"export _TOKEN={S}", f"set -x; PASSWORD={S} ./run", f"{{\n  \"password\":\n  \"{S}\"\n}}",
 f"password\n= {S}", f"password :\n  {S}", f"<password>{S}</password>", f"password\t{S}",
 f"PASSWORD:{S}", f"pass_word={S}", f"Password(s): {S}", f"passwords: {S}", f"tokens: {S}"]
for t in cases:
    print(("REFUSED " if M.find_secret(t) else "PASSED  ") + repr(t))
