import sys, os, shutil, subprocess; old, new, base = sys.argv[1], sys.argv[2], sys.argv[3]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
h = os.path.join(base, "fpid3"); shutil.rmtree(h, ignore_errors=True)
def cli(src, *a):
    r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", h, "--actor", "impl:a", *a], cwd=src, env=dict(env, PYTHONPATH=src), capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip().replace("\n", " ")[-150:]
print("old init", cli(old, "init", "--host-id", "h1")[0])
print("old add OAUTH-TOKEN", cli(old, "milestone-add", "OAUTH-TOKEN", "--title", "OAuth token refresh")[0])
print("old add M2", cli(old, "milestone-add", "M2", "--title", "x")[0])
print("new handoff", cli(new, "handoff", "OAUTH-TOKEN", "--summary", "progress"))
print("new update", cli(new, "milestone-update", "OAUTH-TOKEN", "--next-action", "write tests"))
print("new dep-add", cli(new, "dep-add", "M2", "OAUTH-TOKEN"))
print("new status", cli(new, "status")[0])
