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
import shutil
import subprocess
import sys
import time
import uuid

from . import proctree
from .acceptance import AcceptanceCriteria
from .officefile import WorkbookReadError, make_perturbed_copy, read_workbook_structure, workbook_content_sha256
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
    leaves this process group before it exits and is not reachable this way on POSIX --
    closing that gap needs OS-level sandboxing, a disclosed limitation shared with M38.
    On Windows the child runs in a kill-on-close Job Object (`proctree`), which does
    reach such detached descendants. The
    ledger records outputs at RUN_RESULT time and `Workspace.write_back` refuses when the
    live workspace no longer matches what was verified, so a script that tampers with the
    workspace after this point cannot make its way back to the original undetected.
    """
    started = time.monotonic()
    proc = proctree.spawn(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timed_out = False
    try:
        out, err = proc.communicate(stdin_bytes, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        contained = kill_group(proc)
        out, err = proc.communicate()
    else:
        # Mirrors the harness path's own H-2 fix in `process.py`.
        contained = kill_group(proc)
    finally:
        proctree.release(proc)
    return {"exit_code": proc.returncode, "timed_out": timed_out, "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "stdout": out, "stderr": err, "contained": contained}


def kill_group(proc) -> bool:
    """Kill the process and its whole tree: the POSIX process group, or on Windows the
    kill-on-close Job Object `proctree.spawn` placed it in (reaches orphans whose parent
    has already exited, which `taskkill /T` cannot). Returns False when the tree could
    not be confirmed dead; callers must not treat that run as settled."""
    return proctree.kill_tree(proc)


def _status(items) -> str:
    states = [i["status"] for i in items]
    if "FAIL" in states: return "FAILED"
    if "UNVERIFIABLE" in states: return "PARTIALLY_VERIFIED" if "PASS" in states else "UNVERIFIABLE"
    return "VERIFIED"


def _differential_rerun(script_item, output_paths, vdir: Path, tmp: Path, python) -> dict | None:
    """Rerun the script against a copy of the workspace with one real input
    value changed, and check that a validated workbook output changes too.

    Finding 1 (M38 repair round 3 re-audit): `script_exit_zero` plus the
    workbook shape checks above all pass identically for a script that
    reads its input correctly, one that hardcodes the right answer without
    opening the input, and one that silently computes a wrong value -- none
    of those checks are causal. SCRIPT_WORKBOOK_REPAIR-shaped tasks (a
    `script_exit_zero` item, no `report_recomputes` oracle) have no exact
    recomputation available, so this is the strongest check available: it
    cannot confirm the original output was *correct*, only that it was
    *derived* from the input rather than fixed in advance. Its PASS is what
    promotes an otherwise-VERIFIED result to STRUCTURALLY_VERIFIED, a
    deliberately weaker label (see `verify_candidate`).

    Returns None if there is no output path with an already-passing check to
    compare against (nothing to run a differential against); otherwise an
    item dict with status PASS, FAIL or UNVERIFIABLE. UNVERIFIABLE (no
    perturbable input, or the perturbed run itself fails to complete) is
    reported honestly rather than folded into PASS or FAIL -- it means this
    check was not actually exercised, not that it succeeded or failed.
    """
    if not output_paths: return None
    def content(p: Path) -> str:
        # Compare what the output says, not its bytes: an .xlsx embeds its save time,
        # so identical content saved a second apart differs byte-wise.
        try: return workbook_content_sha256(p)
        except WorkbookReadError: return "bytes:" + hashlib.sha256(p.read_bytes()).hexdigest()
    originals = {}
    for rel in output_paths:
        p = vdir / rel
        if p.is_file(): originals[rel] = content(p)
    if not originals:
        return {"kind": "differential_rerun", "status": "UNVERIFIABLE", "detail": "NO_VALIDATED_OUTPUT"}
    candidates = sorted(p for p in vdir.rglob("*.xlsx") if p.relative_to(vdir).as_posix() not in output_paths)
    if not candidates:
        return {"kind": "differential_rerun", "status": "UNVERIFIABLE", "detail": "NO_CANDIDATE_INPUT"}
    ddir = tmp.parent / (tmp.name + ".diff")
    try:
        shutil.copytree(vdir, ddir)
        perturbed_ok = False
        for target in candidates:
            rel_target = target.relative_to(vdir)
            scratch = ddir / (rel_target.as_posix() + ".perturbed")
            try:
                if make_perturbed_copy(ddir / rel_target, scratch):
                    (ddir / rel_target).write_bytes(scratch.read_bytes())
                    perturbed_ok = True
                    break
            finally:
                scratch.unlink(missing_ok=True)
        if not perturbed_ok:
            return {"kind": "differential_rerun", "status": "UNVERIFIABLE", "detail": "NO_PERTURBABLE_CELL"}
        script = ddir / script_item["script"]
        if not script.is_file():
            return {"kind": "differential_rerun", "status": "UNVERIFIABLE", "detail": "SCRIPT_MISSING"}
        dtmp = ddir.parent / (ddir.name + ".tmp"); dtmp.mkdir()
        result = run_process([python or sys.executable, str(script), *script_item.get("args", [])], cwd=ddir,
                             env=scrubbed_env(dtmp), timeout_s=script_item.get("timeout_s", 60))
        if not result["contained"]:
            return {"kind": "differential_rerun", "status": "FAIL", "detail": "PROCESS_TREE_NOT_CONTAINED"}
        if result["exit_code"] != 0 or result["timed_out"]:
            return {"kind": "differential_rerun", "status": "UNVERIFIABLE", "detail": "PERTURBED_RUN_FAILED"}
        changed = any((ddir / rel).is_file() and content(ddir / rel) != before for rel, before in originals.items())
        return {"kind": "differential_rerun", "status": "PASS" if changed else "FAIL",
                "detail": {"perturbed_input": rel_target.as_posix()}}
    finally:
        shutil.rmtree(ddir, ignore_errors=True)


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
    script_item = None
    passed_output_paths = []
    has_recompute = any(i["kind"] == "report_recomputes" for i in criteria.items)
    for item in criteria.items:
        kind = item["kind"]
        try:
            if kind == "only_changed":
                extra = sorted(changed - set(item["paths"]))
                items.append({"kind": kind, "status": "FAIL" if extra else "PASS", "detail": extra})
            elif kind == "script_exit_zero":
                script_item = item
                script = vdir / item["script"]
                if not script.is_file():
                    items.append({"kind": kind, "status": "FAIL", "detail": "SCRIPT_MISSING"}); script_ok = False; continue
                result = run_process([python or sys.executable, str(script), *item.get("args", [])], cwd=vdir,
                                     env=scrubbed_env(tmp), timeout_s=item.get("timeout_s", 60))
                # A script whose process tree could not be confirmed dead may still be
                # writing: never a pass (Codex audit of 3cd3557).
                script_ok = result["exit_code"] == 0 and not result["timed_out"] and result["contained"]
                items.append({"kind": kind, "status": "PASS" if script_ok else "FAIL",
                              "detail": {"exit_code": result["exit_code"], "timed_out": result["timed_out"],
                                         "process_tree_contained": result["contained"],
                                         "duration_ms": result["duration_ms"],
                                         "stdout_sha256": hashlib.sha256(result["stdout"]).hexdigest(),
                                         "stderr_tail": result["stderr"][-_TAIL:].decode("utf-8", "replace")}})
            elif kind in ("output_workbook_exists", "workbook_has_sheets", "workbook_has_columns", "no_formula_errors"):
                path = vdir / item["path"]
                if not path.is_file():
                    items.append({"kind": kind, "status": "FAIL", "detail": "WORKBOOK_MISSING"}); continue
                if kind == "output_workbook_exists":
                    items.append({"kind": kind, "status": "PASS", "detail": None})
                    passed_output_paths.append(item["path"]); continue
                structure = read_workbook_structure(path)
                if kind == "workbook_has_sheets":
                    missing = [s for s in item["sheets"] if s not in structure.sheet_names]
                    # H-4/P7: a sheet with the right name but nothing in it beyond its own
                    # header row is indistinguishable from one the script never actually
                    # populated from the real input -- exit code zero and sheet presence
                    # alone are not evidence the output derives from anything. Require at
                    # least one cell beyond the header for every named sheet.
                    #
                    # Finding 1 (M38 repair round 3 re-audit): the original check compared
                    # `scanned_cells` (every `<c>` node the sheet has, header included, blank
                    # or not) against the header length -- a sheet whose data rows exist but
                    # are entirely blank scanned the same as a header-only sheet, so it still
                    # passed. `data_cells` (officefile.py) counts only non-empty cells outside
                    # the header row, so an all-blank data area now correctly reads as empty.
                    empty = [] if missing else [s for s in item["sheets"]
                                                if structure.sheet(s).data_cells == 0]
                    problems = missing + empty
                    items.append({"kind": kind, "status": "FAIL" if problems else "PASS", "detail": problems or None})
                    if not problems: passed_output_paths.append(item["path"])
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
    # SCRIPT_WORKBOOK_REPAIR-shaped tasks have no exact recompute oracle (Finding 1,
    # M38 repair round 3): run the causal differential-rerun check instead, but only
    # once the first run itself passed and produced at least one validated output --
    # rerunning a script that already failed, or comparing against an output that
    # never validated, would tell us nothing.
    if script_ok and script_item is not None and not has_recompute and passed_output_paths:
        diff_item = _differential_rerun(script_item, passed_output_paths, vdir, tmp, python)
        if diff_item is not None: items.append(diff_item)
    # The script under test can reach outside its verification copy (no OS sandbox) and
    # write back into the candidate it is being verified against, e.g. via `../../files/`.
    # Re-diff the candidate after the run: if it moved, the verdict must fail rather than
    # be recorded for bytes that no longer exist (F-8).
    after = workspace.diff()
    if after != diff:
        items.append({"kind": "containment", "status": "FAIL", "detail": "CANDIDATE_CHANGED_DURING_VERIFICATION"})
    status = _status(items)
    # A script-based repair can only ever be checked causally (above), never recomputed
    # exactly -- so a VERIFIED reached via a passing differential-rerun is a strictly
    # weaker guarantee than one reached via `report_recomputes`'s exact oracle. Say so
    # explicitly (Chetan's decision, M38 repair round 3) rather than let both look like
    # the same "VERIFIED" to a reader of Memory.
    if status == "VERIFIED" and any(i["kind"] == "differential_rerun" and i["status"] == "PASS" for i in items):
        status = "STRUCTURALLY_VERIFIED"
    return {"status": status, "criteria_sha256": criteria.sha256, "items": items, "diff": diff}


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
        # Finding 2 (M38 repair round 3): the script under verification runs with no OS
        # sandbox and can modify an original directly (not just the workspace) as a side
        # effect of running -- `run_process`'s own process-group sweep closes the
        # background-orphan variant of this, but a script that tampers with an original
        # synchronously, as part of its own main flow, does so before that sweep can act.
        # `HarnessRunner` already re-checks this and blocks write-back on it, but this
        # function is what Memory's VERIFIER_RESULT actually records, and it used to
        # record whatever `verify_candidate` computed regardless -- so Memory could say
        # VERIFIED for a run that had, by this exact point, already tampered with an
        # original. Check it here, before Memory ever sees anything but the true status.
        tampered = workspace.originals_unchanged(sources)
        items = report["items"]
        status = report["status"]
        if tampered:
            status = "FAILED"
            items = items + [{"kind": "original_integrity", "status": "FAIL", "detail": tampered}]
        verification_id = uuid.uuid4().hex
        store.append(run["run_id"], "VERIFICATION", {"verification_id": verification_id, "verifier_id": VERIFIER_ID,
                                                   "verifier_version": VERIFIER_VERSION, "claim_record_id": claim.record_id,
                                                   # The run ledger is uri_v1's own record, not M36's, so it keeps the
                                                   # honest, weaker "STRUCTURALLY_VERIFIED" label here when that is what
                                                   # actually happened -- unlike the `verdict` returned below.
                                                   "status": status, "criteria_sha256": report["criteria_sha256"],
                                                   "items": items,
                                                   # Binds this verdict to exactly the candidate bytes it covered, so
                                                   # write_back never checks against a later, unverified RUN_RESULT (R-6).
                                                   "diff_sha256": diff_fingerprint(report["diff"])})
        # M36's `VerificationStatus` enum (memory/contracts.py) is out of this repair's
        # scope and has no "STRUCTURALLY_VERIFIED" member -- `invoke_verifier` would
        # reject any other string outright (`V(verdict)`). Rather than widen M36's own
        # enum from an M38 repair, the verdict handed to Memory stays a real, valid
        # status ("VERIFIED"), and the weaker, causally-only-checked basis is disclosed
        # in the acceptance evidence Memory stores alongside it instead -- the run
        # ledger above (and every consumer inside uri_v1/execution) still sees and acts
        # on the true "STRUCTURALLY_VERIFIED" label.
        structurally_verified = status == "STRUCTURALLY_VERIFIED"
        verdict = "VERIFIED" if structurally_verified else status
        return verdict, (verification_id,), dict(acceptance, criteria_sha256=criteria.sha256,
                                                structurally_verified=structurally_verified,
                                                items=[{"kind": i["kind"], "status": i["status"]} for i in items])
    return verifier
