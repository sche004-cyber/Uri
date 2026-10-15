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
import re
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
            "uri_scheduler", "tests/scheduler", "scripts/scheduler_live_test.py",
            "scripts/scheduler_task_ctl.ps1",
            # URI A2UI (docs/a2ui/A2UI_ARCHITECTURE.md): new paths only. uri_scheduler/a2ui_host.py and
            # uri_operational_intelligence/schedule_intent.py arrive with their packages (listed above).
            "uri_a2ui", "tests/a2ui", "scripts/a2ui_live_check.py",
            # Web Intelligence W1 and URI Assist A0 (docs/assist/00_PLAN_AND_ACCEPTANCE_CRITERIA.md): new paths only.
            "uri_web", "tests/web", "uri_assist", "tests/assist",
            # Owner 2026-10-14: immutable authority for exactly two canonical security blobs.
            "docs/graphify/GRAPHIFY_LEAK_1_PLAN_AND_ACCEPTANCE.md",
            "docs/ssrf/SSRF_1_PLAN_AND_ACCEPTANCE.md", "docs/web/IDN_1B_PLAN_AND_ACCEPTANCE.md",
            "docs/governance/windows_restoration/OWNER_RUNTIME_AUTHORIZATION.json",
            "docs/governance/windows_restoration/EXACT_RUNTIME_SECURITY_TRANSITIONS.patch",
            "scripts/oi_materialize_test_runtime.py", "scripts/ws_materialized_verify.py",
            # URI Office (docs/office/unified/01_O2_PLAN_AND_ACCEPTANCE_CRITERIA.md) and its device provider: new
            # paths only. Without them the app's Office start (manifest source_root) finds no service (finding B4).
            "uri_office", "uri_devices", "scripts/run_uri_office_service.py",
            "tests/office", "tests/office_u2", "tests/devices"]
TEST_PATHS = ("tests/oi", "tests/ws", "tests/scheduler", "tests/a2ui", "tests/web", "tests/assist", "tests/office",
              "tests/office_u2", "tests/devices")
# Third-party modules the copied paths need at run time. requirements.txt has declared all of them since the first
# commit, but venvs on the PC drifted (pypdf was missing from every runtime venv: finding O2-RT-1). A runtime missing
# one is refused instead of starting an Office service that loses PDF text and search.
RUNTIME_MODULES = ("pypdf", "docx", "pptx", "openpyxl", "lxml")
# Accepted files the owner authorized to extend (WS-D3: exact-path scope guards). They replace the overlay copy; the
# receipt records both digests so the replacement is auditable.
REPLACED_PATHS = ("tests/phase2a/test_frozen_core.py", "scripts/phase2close_chain.py")


def git(*args, cwd=SRC, **kw):
    return subprocess.run(["git", "-c", "core.longpaths=true", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, **kw).stdout


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _dist(name: str) -> str:
    """PEP 503 normalized distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_requirements(path: Path = SRC / "requirements.txt") -> set:
    """Distribution names declared in requirements.txt (comments, options and markers ignored)."""
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if m and not line.startswith("-"):
            out.add(_dist(m.group(1)))
    return out


def install_wheels(venv: Path, wheels, declared=None) -> dict:
    """Install local wheels of DECLARED requirements into the runtime's venv copy: no index, no dependencies.
    A wheel whose distribution is not in requirements.txt is refused (Codex review R1-3). Returns {file: sha256}."""
    done = {}
    declared = declared_requirements() if declared is None else declared
    for w in wheels:
        w = Path(w).resolve()
        if w.suffix != ".whl" or not w.is_file():
            sys.exit("WHEEL_REFUSED:" + w.name)
        if _dist(w.name.split("-", 1)[0]) not in declared:
            sys.exit("WHEEL_NOT_DECLARED:" + w.name)
        done[w.name] = sha(w)
        subprocess.run([str(venv_python(venv)), "-m", "pip", "install", "--no-index", "--no-deps",
                        "--disable-pip-version-check", str(w)], check=True, capture_output=True, text=True)
    return done


def missing_modules(venv: Path, modules=RUNTIME_MODULES) -> list:
    """Modules the runtime's own interpreter cannot import (checked in a separate, isolated process)."""
    out = []
    for m in modules:
        r = subprocess.run([str(venv_python(venv)), "-I", "-c", "import " + m], capture_output=True, text=True)
        if r.returncode != 0:
            out.append(m)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--venv", default=str(SRC / ".venv"))
    ap.add_argument("--wheel", action="append", default=[],
                    help="a local wheel of a declared requirement to install into the runtime's own venv copy "
                         "(offline, no dependencies; the source venv is never changed). May be repeated.")
    ap.add_argument("--exclude-oi-tests", action="store_true",
                    help="regression-gate checkout: copy the OI package but not tests/oi, so the accepted Phase 1/2 "
                         "gates collect exactly their accepted test set in the presence of the OI package")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(SRC))
    from scripts import ws_materialized_verify as V
    V.source_authority(SRC)
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
    transitions = V.reconcile(SRC, dest)
    shutil.copytree(a.venv, dest / ".venv")
    wheels = install_wheels(dest / ".venv", a.wheel)
    missing = missing_modules(dest / ".venv")
    if missing:
        sys.exit("RUNTIME_DEPENDENCY_MISSING:" + ",".join(missing))
    head = git("rev-parse", "HEAD", cwd=dest).strip()
    status = git("status", "--porcelain", cwd=dest).splitlines()
    receipt = {"dest": str(dest), "head": head, "head_is_base": head == BASE, "overlay_commit": OVERLAY_COMMIT,
               "overlay_paths": len(paths), "candidate_source": str(SRC),
               "candidate_head": git("rev-parse", "HEAD").strip(), "oi_files_copied": copied,
               "candidate_tree": git("rev-parse", "HEAD^{tree}").strip(),
               "security_patch_sha256": V.PATCH_SHA256, "security_transitions": transitions,
               "porcelain_entries": len(status), "venv_source": a.venv,
               "oi_tests_included": not a.exclude_oi_tests, "replaced_accepted_files": replaced,
               "installed_wheels": wheels, "runtime_modules_checked": list(RUNTIME_MODULES)}
    (dest / "OI_MATERIALIZATION_RECEIPT.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    verified = V.verify(SRC, dest)
    if not verified["ok"]:
        sys.exit("MATERIALIZED_OUTPUT_REFUSED:" + verified.get("error", "UNKNOWN"))
    print(json.dumps({k: v for k, v in receipt.items() if k != "oi_files_copied"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
