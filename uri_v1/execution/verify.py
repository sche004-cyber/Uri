"""URI-owned independent verification of an execution candidate.

The verifier never trusts the executor's report. It recomputes the workspace
diff itself, copies the candidate into a fresh verification directory, runs
the script in a URI-controlled subprocess and checks each hashed acceptance
item. Only this module's verdict can become a Memory `VERIFIER_RESULT`.

Limitation (disclosed): the script runs without an OS sandbox. It runs only on
a scratch copy, with a scrubbed environment, a confined working directory and
a timeout; network access is not blocked at OS level.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from .acceptance import AcceptanceCriteria
from .officefile import WorkbookReadError, read_workbook_structure
from .run_record import RunStore
from .workspace import Workspace, WorkspaceError, diff_fingerprint

VERIFIER_ID = "uri.verifier.execution.script_workbook.v1"
VERIFIER_TYPE = "EXECUTION_ACCEPTANCE"
VERIFIER_VERSION = "1"
_TAIL = 1024
# Variables that make a nested Claude Code / Codex process believe it runs inside
# another harness session (Paperclip §16 item 14) or that inject user tooling.
_NEVER_FORWARD = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_HOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME")


def scrubbed_env(tmp: Path, extra: dict | None = None) -> dict:
    keep = ("PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update({"TMP": str(tmp), "TEMP": str(tmp), "TMPDIR": str(tmp), "HOME": str(tmp), "USERPROFILE": str(tmp),
                "PYTHONHASHSEED": "0", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    for k in _NEVER_FORWARD: env.pop(k, None)
    env.update(extra or {})
    return env


def run_process(argv, *, cwd: Path, env: dict, timeout_s: float, stdin_bytes: bytes | None = None) -> dict:
    """Run a process in its own group; kill the whole group once it stops, whether it
    exits normally or times out (R-5), so an ordinary (non-detached) leftover child does
    not outlive the run. A child that calls `os.setsid()` / `start_new_session=True`
    leaves this process group before it exits and is not reachable this way -- closing
    that gap needs OS-level sandboxing, a disclosed limitation shared with M38. The
    ledger records outputs at RUN_RESULT time and `Workspace.write_back` refuses when the
    live workspace no longer matches what was verified, so a script that tampers with the
    workspace after this point cannot make its way back to the original undetected.
    """
    kwargs = {}
    if os.name == "nt": kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else: kwargs["start_new_session"] = True
    started = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    timed_out = False
    try:
        out, err = proc.communicate(stdin_bytes, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group(proc)
        out, err = proc.communicate()
    else:
        # Mirrors the harness path's own H-2 fix in `process.py`.
        kill_group(proc)
    return {"exit_code": proc.returncode, "timed_out": timed_out, "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "stdout": out, "stderr": err}


def kill_group(proc) -> None:
    try:
        if os.name == "nt": subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else: os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    proc.wait()


def _status(items) -> str:
    states = [i["status"] for i in items]
    if "FAIL" in states: return "FAILED"
    if "UNVERIFIABLE" in states: return "PARTIALLY_VERIFIED" if "PASS" in states else "UNVERIFIABLE"
    return "VERIFIED"


def verify_candidate(workspace: Workspace, criteria: AcceptanceCriteria, *, python=None, recompute=None) -> dict:
    """Evaluate every acceptance item against URI's own view of the candidate."""
    diff = workspace.diff()
    items = []
    if diff["containment_violations"]:
        items.append({"kind": "containment", "status": "FAIL", "detail": "CONTAINMENT_VIOLATION"})
        return {"status": "FAILED", "criteria_sha256": criteria.sha256, "items": items, "diff": diff}
    try:
        vdir = workspace.verification_copy()
    except WorkspaceError as exc:
        return {"status": "FAILED", "criteria_sha256": criteria.sha256, "items": [{"kind": "copy", "status": "FAIL", "detail": str(exc)}], "diff": diff}
    tmp = vdir.parent / (vdir.name + ".tmp"); tmp.mkdir()
    changed = {c["relpath"] for c in diff["changes"]}
    script_ok = None
    for item in criteria.items:
        kind = item["kind"]
        try:
            if kind == "only_changed":
                extra = sorted(changed - set(item["paths"]))
                items.append({"kind": kind, "status": "FAIL" if extra else "PASS", "detail": extra})
            elif kind == "script_exit_zero":
                script = vdir / item["script"]
                if not script.is_file():
                    items.append({"kind": kind, "status": "FAIL", "detail": "SCRIPT_MISSING"}); script_ok = False; continue
                result = run_process([python or sys.executable, str(script), *item.get("args", [])], cwd=vdir,
                                     env=scrubbed_env(tmp), timeout_s=item.get("timeout_s", 60))
                script_ok = result["exit_code"] == 0 and not result["timed_out"]
                items.append({"kind": kind, "status": "PASS" if script_ok else "FAIL",
                              "detail": {"exit_code": result["exit_code"], "timed_out": result["timed_out"],
                                         "duration_ms": result["duration_ms"],
                                         "stdout_sha256": hashlib.sha256(result["stdout"]).hexdigest(),
                                         "stderr_tail": result["stderr"][-_TAIL:].decode("utf-8", "replace")}})
            elif kind in ("output_workbook_exists", "workbook_has_sheets", "workbook_has_columns", "no_formula_errors"):
                path = vdir / item["path"]
                if not path.is_file():
                    items.append({"kind": kind, "status": "FAIL", "detail": "WORKBOOK_MISSING"}); continue
                if kind == "output_workbook_exists":
                    items.append({"kind": kind, "status": "PASS", "detail": None}); continue
                structure = read_workbook_structure(path)
                if kind == "workbook_has_sheets":
                    missing = [s for s in item["sheets"] if s not in structure.sheet_names]
                    # H-4/P7: a sheet with the right name but nothing in it beyond its own
                    # header row is indistinguishable from one the script never actually
                    # populated from the real input -- exit code zero and sheet presence
                    # alone are not evidence the output derives from anything. Require at
                    # least one cell beyond the header for every named sheet.
                    empty = [] if missing else [s for s in item["sheets"]
                                                if structure.sheet(s).scanned_cells <= len(structure.sheet(s).header)]
                    problems = missing + empty
                    items.append({"kind": kind, "status": "FAIL" if problems else "PASS", "detail": problems or None})
                elif kind == "workbook_has_columns":
                    sheet = structure.sheet(item["sheet"])
                    missing = list(item["columns"]) if sheet is None else [c for c in item["columns"] if c not in sheet.header]
                    items.append({"kind": kind, "status": "FAIL" if missing else "PASS", "detail": missing})
                else:
                    errors = sum(s.error_cells for s in structure.sheets)
                    items.append({"kind": kind, "status": "FAIL" if errors else "PASS", "detail": errors})
            elif kind == "report_recomputes":
                if recompute is None:
                    items.append({"kind": kind, "status": "UNVERIFIABLE", "detail": "NO_RECOMPUTE_REGISTERED"}); continue
                ok = recompute(item["task_class"], workspace, vdir / item["path"])
                items.append({"kind": kind, "status": "PASS" if ok else "FAIL", "detail": None})
        except WorkbookReadError as exc:
            items.append({"kind": kind, "status": "UNVERIFIABLE", "detail": str(exc)})
        except OSError as exc:
            items.append({"kind": kind, "status": "UNVERIFIABLE", "detail": type(exc).__name__})
    # The script under test can reach outside its verification copy (no OS sandbox) and
    # write back into the candidate it is being verified against, e.g. via `../../files/`.
    # Re-diff the candidate after the run: if it moved, the verdict must fail rather than
    # be recorded for bytes that no longer exist (F-8).
    after = workspace.diff()
    if after != diff:
        items.append({"kind": "containment", "status": "FAIL", "detail": "CANDIDATE_CHANGED_DURING_VERIFICATION"})
    return {"status": _status(items), "criteria_sha256": criteria.sha256, "items": items, "diff": diff}


def make_memory_verifier(run_root, *, recompute=None, python=None):
    """Build the callable registered with the M36 trusted verifier bootstrap.

    The claim's `attempt_id` names the run. The verifier checks that the claim
    matches URI's run record (task, inputs, URI-computed outputs) before
    running acceptance, so a claim cannot be re-pointed at another candidate.
    """
    def verifier(claim, sources):
        store = RunStore(claim.user_id, run_root)
        run = store.get(claim.payload["attempt_id"])
        acceptance = {"verifier_id": VERIFIER_ID, "run_id": claim.payload["attempt_id"]}
        if run is None or "result" not in run:
            return "UNVERIFIABLE", (uuid.uuid4().hex,), dict(acceptance, reason="RUN_RECORD_MISSING")
        started = run["started"]
        flags = run["result"].get("uri_observations", {}).get("safety_flags", [])
        if flags:
            return "FAILED", (uuid.uuid4().hex,), dict(acceptance, reason="SAFETY_FLAGS", flags=list(flags))
        if started["task_id"] != claim.task_id:
            return "FAILED", (uuid.uuid4().hex,), dict(acceptance, reason="CLAIM_TASK_MISMATCH")
        claimed_inputs = sorted((x["source_id"], x["content_sha256"]) for x in claim.payload["inputs"])
        manifest_inputs = sorted((e["source_id"], e["content_sha256"]) for e in started["manifest"])
        if claimed_inputs != manifest_inputs:
            return "FAILED", (uuid.uuid4().hex,), dict(acceptance, reason="CLAIM_INPUTS_MISMATCH")
        workspace = Workspace.open(started["workspace_dir"])
        if workspace.manifest_sha256 != started["manifest_sha256"]:
            return "FAILED", (uuid.uuid4().hex,), dict(acceptance, reason="MANIFEST_TAMPERED")
        recorded = sorted((c["relpath"], c["after_sha256"]) for c in run["result"]["uri_computed_diff"]["changes"])
        live = workspace.diff()
        if sorted((c["relpath"], c["after_sha256"]) for c in live["changes"]) != recorded:
            return "FAILED", (uuid.uuid4().hex,), dict(acceptance, reason="CANDIDATE_CHANGED_AFTER_CLAIM")
        claimed_outputs = sorted(x["content_sha256"] for x in claim.payload["outputs"])
        if claimed_outputs != sorted(c["after_sha256"] for c in live["changes"] if c["after_sha256"]):
            return "FAILED", (uuid.uuid4().hex,), dict(acceptance, reason="CLAIM_OUTPUTS_MISMATCH")
        criteria = AcceptanceCriteria.from_dict(started["acceptance"])
        if criteria.sha256 != started["acceptance_sha256"]:
            return "FAILED", (uuid.uuid4().hex,), dict(acceptance, reason="ACCEPTANCE_TAMPERED")
        report = verify_candidate(workspace, criteria, python=python, recompute=recompute)
        verification_id = uuid.uuid4().hex
        store.append(run["run_id"], "VERIFICATION", {"verification_id": verification_id, "verifier_id": VERIFIER_ID,
                                                   "verifier_version": VERIFIER_VERSION, "claim_record_id": claim.record_id,
                                                   "status": report["status"], "criteria_sha256": report["criteria_sha256"],
                                                   "items": report["items"],
                                                   # Binds this verdict to exactly the candidate bytes it covered, so
                                                   # write_back never checks against a later, unverified RUN_RESULT (R-6).
                                                   "diff_sha256": diff_fingerprint(report["diff"])})
        return report["status"], (verification_id,), dict(acceptance, criteria_sha256=criteria.sha256,
                                                          items=[{"kind": i["kind"], "status": i["status"]} for i in report["items"]])
    return verifier
