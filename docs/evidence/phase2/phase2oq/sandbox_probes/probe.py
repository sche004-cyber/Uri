import os, subprocess, sys, json, shutil
from pathlib import Path
here = Path(__file__).parent.resolve()
V = Path(os.environ["APPDATA"]) / "npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc"
exe = V / "bin/codex.exe"
sr = os.environ["SYSTEMROOT"]
env = {"SYSTEMROOT": sr, "WINDIR": os.environ["WINDIR"], "COMSPEC": os.environ["COMSPEC"], "PATHEXT": os.environ["PATHEXT"],
       "PATH": os.pathsep.join([str(Path(sys.executable).parent), sr + r"\System32", str(Path(shutil.which("git")).parent)]),
       "USERPROFILE": str(here/"home"), "HOME": str(here/"home"), "APPDATA": str(here/"home/roaming"),
       "LOCALAPPDATA": str(here/"home/local"), "TEMP": str(here/"temp"), "TMP": str(here/"temp"),
       "CODEX_HOME": str(here/"home/.codex")}
out = {}
for name, argv in {"version": ["--version"], "login_status": ["login", "status"]}.items():
    p = subprocess.run([str(exe), *argv], capture_output=True, env=env, stdin=subprocess.DEVNULL, timeout=60)
    out[name] = {"rc": p.returncode, "stdout": p.stdout.decode(errors="replace")[-400:], "stderr": p.stderr.decode(errors="replace")[-400:]}
p = subprocess.run([str(exe), "exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check", "-C", str(here/"ws"), "-c", 'approval_policy="never"', "-"],
                   input=b"say hi", capture_output=True, env=env, timeout=120)
out["exec_unauth"] = {"rc": p.returncode, "stdout": p.stdout.decode(errors="replace")[-1500:], "stderr": p.stderr.decode(errors="replace")[-1500:]}
out["home_listing"] = sorted(str(x.relative_to(here)) for x in (here/"home").rglob("*"))
print(json.dumps(out, indent=1))
