import os, subprocess, sys, shutil, json
from pathlib import Path
here = Path(__file__).parent.resolve()
V = Path(os.environ["APPDATA"]) / "npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc"
sr = os.environ["SYSTEMROOT"]
env = {"SYSTEMROOT": sr, "WINDIR": os.environ["WINDIR"], "COMSPEC": os.environ["COMSPEC"], "PATHEXT": os.environ["PATHEXT"],
       "PATH": os.pathsep.join([str(Path(sys.executable).parent), sr + r"\System32", str(Path(shutil.which("git")).parent)]),
       "USERPROFILE": str(here/"home"), "HOME": str(here/"home"), "TEMP": str(here/"temp"), "TMP": str(here/"temp"), "CODEX_HOME": str(here/"home/.codex")}
p = subprocess.run([str(V/"bin/codex.exe"), "exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check", "-C", str(here/"ws"), "-c", 'approval_policy="never"', "-c", 'windows.sandbox="unelevated"', "-"],
                   input=b"write PONG into pong.txt", capture_output=True, env=env, timeout=120)
print(p.returncode); print(p.stdout.decode(errors="replace")[-3000:]); print(p.stderr.decode(errors="replace")[-1500:])
