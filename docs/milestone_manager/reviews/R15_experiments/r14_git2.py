from common import *
import subprocess, io, contextlib
def cli_run(home, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: rc = cli.run(["--home", str(home), *args])
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue().replace("\n", " ")
def g(d, *a):
    r = subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@t", *a], capture_output=True, text=True)
    return r
base = Path(tempfile.mkdtemp())
g(base, "init", "-q", "--bare", str(base/"origin.git"))
A = base/"A"; g(base, "clone", "-q", str(base/"origin.git"), str(A))
print("init A", cli_run(A, "init", "--host-id", "ha", "--autocommit")[0])
g(A, "add", "-A"); g(A, "commit", "-qm", "init")
for i in range(3): print("A add", cli_run(A, "--actor", "impl:a", "milestone-add", f"MM-A{i}", "--title", "a")[0])
print("A push", g(A, "push", "-q", "origin", "HEAD:master").returncode)
B = base/"B"; print("clone B", g(base, "clone", "-q", str(base/"origin.git"), str(B)).returncode)
print("init-host B", cli_run(B, "init-host", "--host-id", "hb"))
print("B status porcelain", repr(g(B, "status", "--porcelain").stdout))
for i in range(3):
    rc, out = cli_run(B, "--actor", "impl:b", "milestone-add", f"MM-B{i}", "--title", "b"); print("B add", rc, out[:120] if rc else "")
print("B status porcelain", repr(g(B, "status", "--porcelain").stdout))
g(B, "add", "-A"); g(B, "commit", "-qm", "b"); print("B push", g(B, "push", "-q", "origin", "HEAD:master").returncode)
print("A pull", g(A, "pull", "-q", "--ff-only", "origin", "master").returncode)
rc, out = cli_run(A, "--actor", "impl:a", "milestone-add", "MM-A9", "--title", "a"); print("A after pull", rc, out[:120] if rc else "")
print("A push2", g(A, "push", "-q", "origin", "HEAD:master").returncode, "B pull", g(B, "pull", "-q", "--ff-only", "origin", "master").returncode)
rc, out = cli_run(B, "--actor", "impl:b", "milestone-add", "MM-B9", "--title", "b"); print("B after pull", rc, out[:120] if rc else "")
g(B, "add", "-A"); g(B, "commit", "-qm", "b2"); g(B, "push", "-q", "origin", "HEAD:master"); g(A, "pull", "-q", "--ff-only", "origin", "master")
C = base/"C"; g(base, "clone", "-q", str(base/"origin.git"), str(C)); print("init-host C", cli_run(C, "init-host", "--host-id", "hc")[0])
rc, out = cli_run(C, "--actor", "impl:c", "milestone-add", "MM-C0", "--title", "c"); print("C first write", rc, out[:150] if rc else "")
for h in (A, B, C):
    p = Manager(h, actor="x").projection(); v = EventStore(h).verify()
    print(h.name, "milestones", sorted(p["milestones"]), "verify", v["ok"], "conflicts", [(c["type"]) for c in p["conflicts"] if not c["resolved"]], "warn", p["integrity_warnings"], "errs", p["integrity_errors"])
# re-init-host with taken id on fresh clone
D = base/"D"; g(base, "clone", "-q", str(base/"origin.git"), str(D)); print("init-host D reuse ha", cli_run(D, "init-host", "--host-id", "ha")[1][:120])
