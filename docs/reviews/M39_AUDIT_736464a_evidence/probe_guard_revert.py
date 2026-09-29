"""Probe N1: revert frozen files to pre-freeze upstream-repair versions; run both frozen-scope guards."""
import subprocess, sys, json, importlib
from pathlib import Path
clone = Path(sys.argv[1]); sys.path.insert(0, str(clone))
import tests.test_m37_edge_resolution as m37
import tests.test_m39_boundaries as m39b
m37.ROOT = clone; m39b.ROOT = clone
def run(fn):
    try: fn(); return "PASS"
    except AssertionError as e: return "FAIL:" + str(e)[:160]
cases = [("none", None, None),
         ("uri_v1/execution/workspace.py", "763d8e7", None),
         ("uri_v1/execution/verify.py", "763d8e7", None),
         ("uri_v1/edge/resolver.py", "763d8e7", None),
         ("uri_v1/execution/harness/runner.py", "b013dba", None),
         ("uri_v1/execution/harness/contracts.py", "b013dba", None),
         ("uri_v1/execution/workspace.py", None, b"\n# arbitrary edit\n"),
         ("uri_v1/memory/contracts.py", None, b"\n# arbitrary edit\n")]
out = []
for path, rev, append in cases:
    subprocess.run(["git", "checkout", "-q", "--", "."], cwd=clone, check=True)
    if rev: (clone/path).write_bytes(subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=clone))
    elif append: (clone/path).write_bytes((clone/path).read_bytes() + append)
    r = {"mutation": path if path != "none" else "unmodified HEAD", "content": f"as at {rev}" if rev else ("appended comment" if append else "-"),
         "m37_guard": run(m37.test_m36_and_frozen_files_unchanged),
         "m39_boundary_guard": run(m39b.test_m36_m37_m38_and_frozen_files_unchanged)}
    out.append(r); print(json.dumps(r))
subprocess.run(["git", "checkout", "-q", "--", "."], cwd=clone, check=True)
