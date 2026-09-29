"""Approval-gated write-back, recorded in Memory (M39 §4.2 writeback.py, rule 4.3.5/4.3.6).

Defensive note (known upstream defect, disclosed, not fixed here): a fresh
finding on the M37 predecessor (F-7) says `Workspace.write_back`'s
`verified_status` parameter is *trusted from the caller* rather than derived
from a real verification lookup. This module never lets a caller of this
package hand it a "VERIFIED" flag: `_live_verification_status` below always
re-reads the verdict from the Memory `VERIFIER_RESULT` record itself
(`Recorder.log`), and that is the *only* value ever passed as `verified_status`
into `Workspace.write_back`. Nothing in this module's public API accepts a
verification-status argument from its caller. Rule 4.3.4 ("claims are claims")
is enforced the same way for the run itself and for the write-back's own
verifier invocation (`WRITEBACK_VERIFIER_ID`, invoked through
`Recorder.invoke_verifier`, never written to Memory directly by this module).
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import uuid

from uri_v1.execution.workspace import Workspace, WorkspaceError, WritebackApproval, new_run_id
from uri_v1.memory.contracts import RecordKind as K, Provenance as P
from uri_v1.memory.recorder import _runtime_observation
from uri_v1.user_storage import user_scoped_path

WRITEBACK_VERIFIER_ID = "uri.verifier.office.writeback.v1"
WRITEBACK_VERIFIER_TYPE = "OFFICE_WRITEBACK"
WRITEBACK_VERIFIER_VERSION = "1"


class WritebackRefused(ValueError):
    """Typed failure: the reason code is the message.

    `written` carries any files that were actually replaced on disk before
    the refusal happened (M39 repair M39-1). Once `Workspace.write_back` has
    run, every later refusal in this module must report and record what
    really happened -- never "nothing was written" for a write that did.
    """

    def __init__(self, reason, written=(), partial_record=None):
        super().__init__(reason)
        self.written = tuple(written)
        # How the partial write was recorded in Memory (repair round 3,
        # R2-2): "FAILED" (task moved to FAILED through M36's runtime
        # FAILURE path), "NOTED" (checkpoint note only), or the reason the
        # record itself could not persist. None when nothing was written.
        self.partial_record = partial_record


def writeback_verifier_entry() -> dict:
    """Entry for the M36 trusted verifier bootstrap (process start only).

    The registered callable is invoked only after `Recorder.invoke_verifier`
    has itself re-checked, against live `sources`, that every claimed input
    link is still the current content of its original
    (`uri_v1/memory/recorder.py:156-157`, `VERIFIER_SOURCE_NOT_CURRENT`). This
    callable re-affirms that check defensively (never trusting the pre-check
    alone) and never returns VERIFIED on a claim it has not itself checked.
    """
    def verifier(claim, sources):
        for link in claim.payload["inputs"]:
            if not sources.verify_source(link["source_id"], link["content_sha256"]):
                return "FAILED", (uuid.uuid4().hex,), {"verifier_id": WRITEBACK_VERIFIER_ID, "reason": "ORIGINAL_HASH_MISMATCH"}
        return ("VERIFIED", (uuid.uuid4().hex,),
                {"verifier_id": WRITEBACK_VERIFIER_ID,
                 "source_ids": sorted({link["source_id"] for link in claim.payload["inputs"]})})
    return {WRITEBACK_VERIFIER_ID: (WRITEBACK_VERIFIER_TYPE, WRITEBACK_VERIFIER_VERSION, verifier)}


def workspace_base(user_id: str, scratch_root, run_id: str) -> Path:
    return Path(user_scoped_path(user_id, os.path.join("workspaces", run_id), str(Path(scratch_root).resolve())))


def open_run_workspace(user_id: str, scratch_root, run_id: str) -> Workspace:
    return Workspace.open(workspace_base(user_id, scratch_root, run_id))


def _live_verification_status(recorder, task_id: str, run_id: str):
    """The ONLY source of truth for whether a run is VERIFIED: a live read of
    Memory's own VERIFIER_RESULT record for this exact run, never a flag any
    caller supplies (see module docstring; M37 audit finding F-7)."""
    index = recorder.log.load()
    candidates = [r for r in index.current(K.OUTCOME, task_id)
                 if r.provenance == P.VERIFIER_RESULT and r.payload.get("attempt_id") == run_id]
    if not candidates:
        return None, None
    record = sorted(candidates, key=lambda r: r.recorded_at)[-1]
    return str(record.payload["verification_status"]), record.record_id


@dataclass(frozen=True)
class WritebackOutcome:
    written: tuple
    verifier_record_id: str
    task_state_result: object


def _actually_written(ws, expected_after, sources) -> list:
    """After a failed `Workspace.write_back`, ask the live originals (never
    workspace-internal state) which of `relpaths` actually landed on disk --
    `write_back` writes one file at a time and can raise partway through."""
    by_rel = {e.relpath: e for e in ws.manifest}
    written = []
    for rel, after_sha in expected_after.items():
        entry = by_rel.get(rel)
        if entry is not None and sources.verify_source(entry.source_id, after_sha):
            written.append({"relpath": rel, "source_id": entry.source_id,
                            "before_sha256": entry.content_sha256, "after_sha256": after_sha})
    return written


def _record_partial_write(recorder, task_id, expected_head_record_id, intake, written, reason):
    """Record in Memory that originals were changed even though this
    write-back is being refused (repair round 3, R2-2: never leave the task
    silently OPEN after a write).

    First choice: move the task to FAILED through frozen M36's governed
    runtime path (`runtime_action=FAILURE`), with a checkpoint text naming
    the files and the reason. If M36 refuses that (e.g. a concurrent head
    change), fall back to a checkpoint note with no status change. Returns
    how it was recorded; the refusal to the caller carries `written` either
    way, so the report is never dishonest even if Memory could not be
    updated."""
    note = (f"write-back partially applied before refusal ({reason}): "
            + ", ".join(f"{w['relpath']} {w['before_sha256'][:12]}->{w['after_sha256'][:12]}" for w in written))
    try:
        failed = recorder.task_state(task_id, expected_head_record_id, intake=intake, status="FAILED",
                                     runtime_action=_runtime_observation(intake, "FAILURE"), next_step=note)
        if failed.persisted:
            return "FAILED"
        noted = recorder.task_state(task_id, expected_head_record_id, intake=intake, next_step=note)
        return "NOTED" if noted.persisted else f"NOT_RECORDED:{noted.reason}"
    except Exception as exc:  # noqa: BLE001 -- the refusal must still reach the caller
        return f"NOT_RECORDED:{type(exc).__name__}:{exc}"


def _refuse_after_write(recorder, task_id, expected_head_record_id, intake, written, reason):
    how = _record_partial_write(recorder, task_id, expected_head_record_id, intake, written, reason)
    return WritebackRefused(reason, written=written, partial_record=how)


def writeback(*, recorder, sources, run_store, user_id, scratch_root, task_id, run_id, expected_head_record_id,
             session_id, trace_id, approval_intake, relpaths) -> WritebackOutcome:
    """Approve, write, verify and complete -- gated only on live verdicts, never a caller flag.

    Raises `WritebackRefused` (reason in `args[0]`, any files actually
    written in `.written`) on any refusal: the run is not VERIFIED yet, the
    run carries a safety flag (M39-4), the approval text is not
    explicit/non-negated (`WritebackApproval.from_user`), a task reference
    is no longer current, nothing at `relpaths` actually changed, or an
    original/candidate changed since verification (`WorkspaceError` from
    `Workspace.write_back`, e.g. `ORIGINAL_CHANGED_SINCE_COPY_IN` /
    `WRITEBACK_CANDIDATE_CHANGED`).

    Two independent, both caller-flag-free checks gate this: this module's own
    `_live_verification_status` re-reads the Memory `VERIFIER_RESULT` record
    (M37 audit finding F-7's original concern), and `Workspace.write_back`
    itself now independently re-derives the same verdict from `run_store`
    (the M37 repair, commit 763d8e7, landed the same fix at that layer). This
    module passes `run_store` through rather than any status string of its
    own, so a caller of this module cannot short-circuit either check.

    M39-1 (audit): every one of the task's *current* references -- not only
    the ones being written -- must be live *before* any `os.replace` happens.
    Previously this was only checked afterwards, as a side effect of the
    write-back verifier's own precondition scan; a stale *other* reference
    (e.g. the workbook, when only the script is being written) then let the
    write happen and only refused afterwards, so the refusal wrongly reported
    "nothing was written". Checking first means that scenario now refuses
    before writing anything, so "nothing was written" is true again. The
    `written`/`_record_partial_write` machinery below is defense in depth for
    any refusal that can still happen *after* a successful `write_back`
    (TOCTOU between this check and the write, or a downstream Memory write
    failing) -- it is not expected to fire in the common case.
    """
    status, _ = _live_verification_status(recorder, task_id, run_id)
    if status != "VERIFIED":
        raise WritebackRefused("WRITEBACK_REQUIRES_VERIFIED_RUN")
    run = run_store.get(run_id)
    if (run or {}).get("result", {}).get("uri_observations", {}).get("safety_flags"):
        raise WritebackRefused("WRITEBACK_REFUSES_FLAGGED_RUN")

    task_head = recorder.log.load().task(task_id)
    if task_head is None:
        raise WritebackRefused("UNKNOWN_TASK")
    for ref in task_head.payload["references"]:
        if not sources.verify_source(ref["source_id"], ref["content_sha256"]):
            raise WritebackRefused("WRITEBACK_SOURCE_NOT_CURRENT")

    ws = open_run_workspace(user_id, scratch_root, run_id)
    diff = ws.diff()
    changes = {c["relpath"]: c for c in diff["changes"]}
    expected_after = {}
    for rel in relpaths:
        c = changes.get(rel)
        if not c or c["op"] != "MODIFIED":
            raise WritebackRefused("NOTHING_TO_WRITE_BACK")
        expected_after[rel] = c["after_sha256"]
    try:
        approval = WritebackApproval.from_user(approval_intake, run_id, expected_after)
        written = ws.write_back(approval, sources=sources, run_store=run_store)
    except WorkspaceError as exc:
        partial = _actually_written(ws, expected_after, sources)
        if partial:
            raise _refuse_after_write(recorder, task_id, expected_head_record_id, approval_intake,
                                      partial, str(exc)) from exc
        raise WritebackRefused(str(exc)) from exc

    # From this point the write already happened on disk: every refusal or
    # unexpected error below must carry and record `written`, never claim
    # nothing happened and never escape as a bare exception (R2-2).
    try:
        return _verify_and_complete(recorder=recorder, task_id=task_id, run_id=run_id,
                                    expected_head_record_id=expected_head_record_id, session_id=session_id,
                                    trace_id=trace_id, approval_intake=approval_intake, written=written)
    except WritebackRefused as exc:
        raise _refuse_after_write(recorder, task_id, expected_head_record_id, approval_intake,
                                  written, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _refuse_after_write(recorder, task_id, expected_head_record_id, approval_intake,
                                  written, f"POST_WRITE_ERROR:{type(exc).__name__}:{exc}") from exc


def _verify_and_complete(*, recorder, task_id, run_id, expected_head_record_id, session_id, trace_id,
                         approval_intake, written) -> WritebackOutcome:
    # The completing OUTCOME's inputs must cover every one of the task's
    # *current* Memory references (uri_v1/memory/index.py:145
    # VERIFIED_CURRENT_REFERENCES_REQUIRED), not only the files just written:
    # the task's references still name the pre-write hash for anything this
    # write-back did not touch (rule 4.3.6), so those keep their recorded,
    # still-live hash, while a just-written file uses its new, now-live hash.
    after_by_source = {w["source_id"]: w["after_sha256"] for w in written}
    task_head = recorder.log.load().task(task_id)
    current_refs = task_head.payload["references"] if task_head else ()
    inputs = tuple({"source_id": r["source_id"], "content_sha256": after_by_source.get(r["source_id"], r["content_sha256"])}
                   for r in current_refs)
    if not inputs:
        inputs = tuple({"source_id": w["source_id"], "content_sha256": w["after_sha256"]} for w in written)
    claim = recorder.outcome(task_id, action_label="office write-back", inputs=inputs, outputs=(),
                             session_id=session_id, trace_id=trace_id, attempt_id=new_run_id())
    if not claim.persisted:
        raise WritebackRefused(claim.reason)
    verdict = recorder.invoke_verifier(claim.record_ids[0], WRITEBACK_VERIFIER_ID, trace_id=trace_id, session_id=session_id)
    if not verdict.persisted:
        raise WritebackRefused(verdict.reason)
    record = recorder.log.load().records[verdict.record_ids[0]]
    if str(record.payload["verification_status"]) != "VERIFIED":
        raise WritebackRefused("WRITEBACK_NOT_VERIFIED")

    # M39-6 / re-audit R2-2 (repair round 3): completion goes through frozen
    # M36's governed runtime path (`runtime_action=VERIFIED_COMPLETE`,
    # uri_v1/memory/recorder.py:113-117), never through a synthesized user
    # turn. The earlier synthetic write-back-complete intake put words in
    # the user's mouth, and frozen M36 correctly refuses it
    # (EXPLICIT_USER_TRANSITION_REQUIRED) -- after the originals were already
    # overwritten.
    #
    # Frozen M36's index requires the completing verdict's inputs to cover
    # the task's *current* references (uri_v1/memory/index.py:145-149). The
    # task's references deliberately keep the pre-write hashes (rule 4.3.6),
    # so the verdict that satisfies that is the run's own VERIFIER_RESULT:
    # the run was verified against exactly those inputs, and the write-back
    # verifier above has just independently confirmed that the live
    # originals now hold exactly that run's verified output. Both record ids
    # are kept: `last_outcome_record_id` names the run verdict, and the
    # checkpoint text names the write-back verdict.
    _, run_verdict_id = _live_verification_status(recorder, task_id, run_id)
    note = ("write-back applied and verified (" + ", ".join(w["relpath"] for w in written)
            + f"; write-back verifier record {record.record_id})")
    result = recorder.task_state(task_id, expected_head_record_id, intake=approval_intake, status="COMPLETED",
                                 runtime_action=_runtime_observation(approval_intake, "VERIFIED_COMPLETE"),
                                 last_outcome_record_id=run_verdict_id, next_step=note)
    if not result.persisted:
        raise WritebackRefused(result.reason)
    return WritebackOutcome(tuple(written), record.record_id, result)
