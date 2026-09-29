"""Re-audit N1 probes on a disposable clone of HEAD. Usage: python n1_guard_probe.py <clone>"""
import os, subprocess, sys, stat
from pathlib import Path
clone = Path(sys.argv[1]); sys.path.insert(0, os.getcwd())
import tests.test_m39_boundaries as b
b.ROOT = clone
def guard():
    try: b.test_m36_m37_m38_and_frozen_files_unchanged(); return "PASS"
    except AssertionError as e: return "FAIL " + str(e)[:160]
def git(*a, **k): return subprocess.check_output(["git", *a], cwd=clone, **k)
def reset(): subprocess.run(["git", "checkout", "-q", "--", "."], cwd=clone, check=True); subprocess.run(["git", "clean", "-qfdx", "uri_v1", "tests", "scripts", "fixtures", "uri_core", "uri_ui"], cwd=clone, check=True)
res = []
res.append(("control clean clone", guard()))
for rev in ("763d8e7", "b013dba"):
    files = git("diff", "--name-only", rev, "bd7c450", "--", "uri_v1/edge", "uri_v1/execution", "uri_v1/memory", text=True).split()
    for f in files:
        try: old = git("show", f"{rev}:{f}", stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError: continue
        (clone / f).write_bytes(old); res.append((f"rollback {f}@{rev}", guard())); reset()
m36 = git("log", "--format=%h", "-n", "2", "bd7c450", "--", "uri_v1/memory/sources.py", text=True).split()
(clone / "uri_v1/memory/sources.py").write_bytes(git("show", f"{m36[1]}:uri_v1/memory/sources.py")); res.append((f"rollback M36 sources.py@{m36[1]}", guard())); reset()
(clone / "uri_v1/execution/verify.py").unlink(); res.append(("delete frozen verify.py", guard())); reset()
(clone / "uri_v1/edge/extra_module.py").write_text("x=1\n"); res.append(("untracked new file uri_v1/edge", guard())); reset()
p = clone / "tests/test_m37_edge_resolution.py"; p.write_text(p.read_text() + "\n# drift\n"); res.append(("authorized M37 test drift", guard())); reset()
p = clone / "uri_v1/execution/workspace.py"; os.chmod(p, p.stat().st_mode | stat.S_IXUSR); res.append(("chmod +x frozen file", guard())); reset()
p = clone / "uri_core/app/server.py"; p.write_text(p.read_text() + "\n# live edit\n"); res.append(("live-app uri_core/app/server.py edit", guard())); reset()
p = clone / "uri_ui.py"; p.write_text(p.read_text() + "\n# live edit\n"); res.append(("root uri_ui.py edit (outside scanned roots)", guard())); reset()
pc = clone / "uri_v1/edge/__pycache__"; pc.mkdir(exist_ok=True); (pc / "planted.cpython-311.pyc").write_bytes(b"\0"); res.append(("gitignored __pycache__ plant", guard())); reset()
p = clone / "uri_v1/office/flow.py"; p.write_text(p.read_text() + "\n# m39 edit\n"); res.append(("M39 own file edit (should PASS)", guard())); reset()
for name, r in res: print(f"{r[:4]:4} | {name} | {r[5:]}")
