"""Postcondition checks: URI-observed evidence, strictly separated from executor self-report.

Postconditions are declared by URI Core (never by an executor). Evaluating one means URI looks at
the world itself (file system, git, a command it runs, an external reconciler) and records the
observation as evidence. PASS requires `uri_verified` evidence (enforced by trigger), except the
special kind `terminal_success`, which may cite an executor terminal claim and is only honoured
when every declared effect of the task is `read` class (enforced by trigger).
"""
from __future__ import annotations

import hashlib
import re
import uuid
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .ledger import Ledger, jdump

PASS, FAIL, INDET = "PASS", "FAIL", "INDETERMINATE"
MAX_HASH_BYTES = 256 * 1024 * 1024
MAX_FINGERPRINT_ENTRIES = 20000


@dataclass
class Check:
    status: str
    observation: dict


# ---- fingerprints (pre-attempt state for local_write absence proofs) ---------------------------

def _unprovable(why):
    """A fingerprint that can never equal another: used when state cannot be fully captured. Absence of an
    effect is then NOT provable, and recovery escalates instead of retrying."""
    return f"UNPROVABLE:{why}:{uuid.uuid4().hex}"


def _file_sha(p: Path):
    if p.stat().st_size > MAX_HASH_BYTES:
        return _unprovable("too_large")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint_path(path) -> str:
    p = Path(path)
    try:
        if not p.exists():
            return "MISSING"
        if p.is_file():
            return "file:" + _file_sha(p)
        if p.is_dir():
            h = hashlib.sha256()
            children = []
            for child in p.rglob("*"):
                children.append(child)
                if len(children) > MAX_FINGERPRINT_ENTRIES:
                    return _unprovable("too_many_entries")
            for child in sorted(children, key=lambda c: str(c.relative_to(p)).encode("utf-8", "surrogatepass")):
                rel = str(child.relative_to(p)).replace("\\", "/")
                h.update(rel.encode("utf-8", "surrogatepass") + b"\0")
                h.update((_file_sha(child) if child.is_file() else "dir").encode() + b"\0")
            return "dir:" + h.hexdigest()
        return "other"
    except OSError as e:
        return _unprovable("unreadable_" + type(e).__name__)


def fingerprint_paths(paths) -> dict:
    return {str(p): fingerprint_path(p) for p in paths}


# ---- checkers -----------------------------------------------------------------------------------

def _file_exists(spec, ctx):
    p = Path(spec["path"])
    try:
        ok = p.is_file()
    except OSError as e:
        return Check(INDET, {"path": str(p), "error": type(e).__name__})
    return Check(PASS if ok else FAIL, {"path": str(p), "exists": ok})


def _file_hash(spec, ctx):
    p = Path(spec["path"])
    try:
        if not p.is_file():
            return Check(FAIL, {"path": str(p), "exists": False})
        got = _file_sha(p)
    except OSError as e:
        return Check(INDET, {"path": str(p), "error": type(e).__name__})
    return Check(PASS if got == spec["sha256"] else FAIL, {"path": str(p), "sha256": got, "expected": spec["sha256"]})


def _file_regular_nonempty(spec, ctx):
    """A regular, non-symlink, non-empty file (Phase 1 harness_output_check semantics, URI-observed)."""
    p = Path(spec["path"])
    try:
        if p.is_symlink() or not p.is_file():
            return Check(FAIL, {"path": str(p), "exists": p.exists(), "symlink": p.is_symlink()})
        size = p.stat().st_size
    except OSError as e:
        return Check(INDET, {"path": str(p), "error": type(e).__name__})
    return Check(PASS if size > 0 else FAIL, {"path": str(p), "bytes": size})


def _file_absent(spec, ctx):
    p = Path(spec["path"])
    try:
        return Check(PASS if not p.exists() else FAIL, {"path": str(p), "exists": p.exists()})
    except OSError as e:
        return Check(INDET, {"path": str(p), "error": type(e).__name__})


def _git(repo, *args, timeout=30):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)


def _git_commit_exists(spec, ctx):
    try:
        r = _git(spec["repo"], "cat-file", "-e", f"{spec['rev']}^{{commit}}")
    except (OSError, subprocess.TimeoutExpired) as e:
        return Check(INDET, {"repo": spec["repo"], "error": type(e).__name__})
    if r.returncode == 0:
        head = _git(spec["repo"], "rev-parse", f"{spec['rev']}^{{commit}}").stdout.decode().strip()
        return Check(PASS, {"repo": spec["repo"], "rev": spec["rev"], "commit": head})
    return Check(FAIL, {"repo": spec["repo"], "rev": spec["rev"], "git_exit": r.returncode})


def _worktree_matches(spec, ctx):
    try:
        r = _git(spec["repo"], "status", "--porcelain")
    except (OSError, subprocess.TimeoutExpired) as e:
        return Check(INDET, {"error": type(e).__name__})
    if r.returncode != 0:
        return Check(INDET, {"git_exit": r.returncode})
    status = r.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    expected = spec.get("expected_porcelain", "")
    return Check(PASS if status == expected else FAIL, {"porcelain": status, "expected": expected})


def _command_passes(spec, ctx):
    try:
        r = subprocess.run(spec["argv"], cwd=spec.get("cwd"), capture_output=True, timeout=spec.get("timeout_s", 300),
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return Check(INDET, {"argv": spec["argv"], "timeout": True})
    except OSError as e:
        return Check(INDET, {"argv": spec["argv"], "error": type(e).__name__})
    out = (r.stdout + b"\n" + r.stderr).decode("utf-8", "replace")
    obs = {"argv": spec["argv"], "exit_code": r.returncode}
    rx = spec.get("summary_regex")  # named groups passed,total
    if rx:
        m = re.search(rx, out)
        if m and {"passed", "total"} <= set(m.groupdict()):
            obs["passed"], obs["total"] = int(m["passed"]), int(m["total"])
    return Check(PASS if r.returncode == spec.get("expect_exit", 0) else FAIL, obs)


def _external_object(spec, ctx):
    rec = ctx.reconcilers.get(spec["reconciler"])
    if rec is None:
        return Check(INDET, {"reconciler": spec["reconciler"], "error": "NO_RECONCILER"})
    try:
        verdict, detail = rec(spec["key"], spec)
    except Exception as e:  # reconciler failure is uncertainty, never absence
        return Check(INDET, {"reconciler": spec["reconciler"], "error": type(e).__name__})
    if verdict == "FOUND":
        return Check(PASS, {"reconciler": spec["reconciler"], "key": spec["key"], "detail": detail})
    if verdict == "NOT_FOUND":
        return Check(FAIL, {"reconciler": spec["reconciler"], "key": spec["key"], "detail": detail})
    return Check(INDET, {"reconciler": spec["reconciler"], "key": spec["key"], "detail": detail})


CHECKERS = {"file_exists": _file_exists, "file_hash": _file_hash, "file_absent": _file_absent,
            "file_regular_nonempty": _file_regular_nonempty,
            "git_commit_exists": _git_commit_exists, "worktree_matches": _worktree_matches,
            "command_passes": _command_passes, "external_object": _external_object}


@dataclass
class EvalContext:
    reconcilers: dict
    attempt_id: int | None
    recorded_by: str


def evaluate_postconditions(ledger: Ledger, task_id: str, ctx: EvalContext):
    """Fresh-observe every declared postcondition. Appends evidence + results. -> list of dicts."""
    out = []
    pcs = ledger.q("SELECT * FROM postcondition WHERE task_id=? ORDER BY postcondition_id", (task_id,))
    for pc in pcs:
        import json
        spec = json.loads(pc["spec_json"])
        if pc["kind"] == "terminal_success":
            row = ledger.q1("SELECT evidence_id FROM evidence WHERE task_id=? AND source='executor_report' "
                            "AND kind='terminal_success_claim' AND (? IS NULL OR attempt_id=?) "
                            "ORDER BY evidence_id DESC LIMIT 1", (task_id, ctx.attempt_id, ctx.attempt_id))
            att = ledger.q1("SELECT exit_code,end_reason FROM attempt WHERE attempt_id=?", (ctx.attempt_id,)) if ctx.attempt_id else None
            clean_exit = att is not None and (att["exit_code"] == 0 or att["end_reason"] == "terminal_then_hang_killed")
            if row is None or not clean_exit:
                why = "no executor terminal success claim" if row is None else "terminal success claimed but process did not exit cleanly"
                check, ev_source, cite = Check(FAIL, {"reason": why, "exit_code": att["exit_code"] if att else None}), "uri_observed", None
            else:
                check, ev_source, cite = Check(PASS, {"executor_evidence_id": row[0]}), "executor_report", row[0]
        else:
            fn = CHECKERS.get(pc["kind"])
            if fn is None:
                check = Check(INDET, {"error": "UNKNOWN_POSTCONDITION_KIND", "kind": pc["kind"]})
            else:
                try:
                    check = fn(spec, ctx)
                except Exception as e:
                    check = Check(INDET, {"error": type(e).__name__})
            ev_source, cite = ("uri_verified" if check.status == PASS else "uri_observed"), None
        with ledger.tx() as db:
            now = ledger.now_us()
            if cite is None:
                cur = db.execute(
                    "INSERT INTO evidence(task_id,attempt_id,source,kind,subject,payload,occurred_at_us,recorded_at_us,recorded_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (task_id, ctx.attempt_id, ev_source, "postcondition_check", f"postcondition:{pc['postcondition_id']}",
                     jdump({"kind": pc["kind"], "status": check.status, "observation": check.observation}), now, now,
                     ctx.recorded_by))
                eid = cur.lastrowid
            else:
                eid = cite
            cur = db.execute("INSERT INTO postcondition_result(postcondition_id,task_id,attempt_id,status,evidence_id,checked_at_us) "
                             "VALUES (?,?,?,?,?,?)", (pc["postcondition_id"], task_id, ctx.attempt_id, check.status, eid, now))
            ledger.emit("postcondition.result", task_id, ctx.attempt_id, ("postcondition_result", cur.lastrowid),
                        {"kind": pc["kind"], "status": check.status})
        out.append({"postcondition_id": pc["postcondition_id"], "kind": pc["kind"], "required": bool(pc["required"]),
                    "status": check.status, "evidence_id": eid, "observation": check.observation})
    return out
