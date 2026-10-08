"""Materialize a disposable OI TEST runtime checkout (development only; never a production runtime).

Why: frozen `uri_core/core/runtime_identity.py` refuses to provision or validate unless `git HEAD == e8e3b65`
(consolidation finding CONS-7). The accepted runtime is therefore materialized as e8e3b65 + the committed Phase 2 OQ
overlay (runbook `docs/governance/consolidation/URI_RUNTIME_BUILD_AND_ROLLBACK_RUNBOOK.md` section 1). This script
does the same and then copies the Operational Intelligence candidate files (new paths only) on top, so the REAL
paired Core can be exercised with Runtime v1 without editing any frozen or accepted file.

    .venv\\Scripts\\python.exe scripts\\oi_materialize_test_runtime.py <dest> [--venv <venv to copy>]

Writes <dest>/OI_MATERIALIZATION_RECEIPT.json. Refuses an existing <dest>.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
BASE = "e8e3b65259c45fc823addc3ef8969425a265bd1b"
OVERLAY_COMMIT = "759d0d4e4069ddb490e6ce52ac58bf86ef0248f0"
OVERLAY_LIST = "docs/governance/consolidation/RUNTIME_OVERLAY_PHASE2OQ_G.txt"
# New Operational Intelligence paths copied from the candidate working tree (none exists at BASE or in the overlay).
OI_PATHS = ["uri_operational_intelligence", "tests/oi", "model_lab/integration", "model_lab/lab",
            "model_lab/__init__.py",
            # Working-system integration (docs/working_system/WS_BLUEPRINT.md): new paths only.
            "scripts/run_uri_integrated_worker.py", "scripts/run_uri_integrated_server.py", "scripts/ws_provision.py",
            "scripts/ws_frozen_check.py", "scripts/ws_server_identity.py", "tests/ws", "work/oi/.gitignore",
            # WS hardening (docs/working_system/WS_HARDENING_PLAN.md): new paths only.
            "scripts/ws_brain_host.py",
            # URI Scheduler (docs/scheduler/SCHEDULER_ARCHITECTURE.md): new paths only.
            "uri_scheduler", "tests/scheduler", "scripts/scheduler_live_test.py"]
TEST_PATHS = ("tests/oi", "tests/ws", "tests/scheduler")
# Accepted files the owner authorized to extend (WS-D3: exact-path scope guards). They replace the overlay copy; the
# receipt records both digests so the replacement is auditable.
REPLACED_PATHS = ("tests/phase2a/test_frozen_core.py", "scripts/phase2close_chain.py")


def git(*args, cwd=SRC, **kw):
    return subprocess.run(["git", "-c", "core.longpaths=true", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, **kw).stdout


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--venv", default=str(SRC / ".venv"))
    ap.add_argument("--exclude-oi-tests", action="store_true",
                    help="regression-gate checkout: copy the OI package but not tests/oi, so the accepted Phase 1/2 "
                         "gates collect exactly their accepted test set in the presence of the OI package")
    a = ap.parse_args(argv)
    dest = Path(a.dest).resolve()
    if dest.exists():
        sys.exit("DEST_EXISTS")
    git("worktree", "add", "--detach", str(dest), BASE)
    git("config", "core.autocrlf", "false", cwd=dest)
    overlay = git("show", "%s:%s" % (git("rev-parse", "HEAD").strip(), OVERLAY_LIST))
    paths = [p.strip() for p in overlay.splitlines() if p.strip()]
    lst = dest.parent / (dest.name + ".overlay.txt")
    lst.write_text("\n".join(paths) + "\n", encoding="ascii")
    git("checkout", OVERLAY_COMMIT, "--pathspec-from-file=" + str(lst), cwd=dest)
    git("reset", "-q", cwd=dest)
    lst.unlink()
    collisions, copied = [], {}
    for rel in OI_PATHS:
        if a.exclude_oi_tests and rel in TEST_PATHS:
            continue
        s, d = SRC / rel, dest / rel
        if not s.exists():
            continue
        if d.exists():
            collisions.append(rel)
            continue
        if s.is_dir():
            shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for f in d.rglob("*"):
                if f.is_file():
                    copied[f.relative_to(dest).as_posix()] = sha(f)
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            copied[rel] = sha(d)
    if collisions:
        sys.exit("OI_PATH_COLLISION:" + ",".join(collisions))
    replaced = {}
    for rel in REPLACED_PATHS:
        s_, d_ = SRC / rel, dest / rel
        replaced[rel] = {"overlay_sha256": sha(d_) if d_.exists() else None}
        shutil.copy2(s_, d_)
        replaced[rel]["integration_sha256"] = sha(d_)
    shutil.copytree(a.venv, dest / ".venv")
    head = git("rev-parse", "HEAD", cwd=dest).strip()
    status = git("status", "--porcelain", cwd=dest).splitlines()
    receipt = {"dest": str(dest), "head": head, "head_is_base": head == BASE, "overlay_commit": OVERLAY_COMMIT,
               "overlay_paths": len(paths), "candidate_source": str(SRC),
               "candidate_head": git("rev-parse", "HEAD").strip(), "oi_files_copied": copied,
               "porcelain_entries": len(status), "venv_source": a.venv,
               "oi_tests_included": not a.exclude_oi_tests, "replaced_accepted_files": replaced}
    (dest / "OI_MATERIALIZATION_RECEIPT.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "oi_files_copied"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
