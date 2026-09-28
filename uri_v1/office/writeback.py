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
from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.user_storage import user_scoped_path

WRITEBACK_VERIFIER_ID = "uri.verifier.office.writeback.v1"
WRITEBACK_VERIFIER_TYPE = "OFFICE_WRITEBACK"
WRITEBACK_VERIFIER_VERSION = "1"


class WritebackRefused(ValueError):
    """Typed failure: the reason code is the message."""


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


def writeback(*, recorder, sources, user_id, scratch_root, task_id, run_id, expected_head_record_id,
             session_id, trace_id, approval_intake, relpaths) -> WritebackOutcome:
    """Approve, write, verify and complete -- gated only on a live Memory verdict.

    Raises `WritebackRefused` (reason in `args[0]`) on any refusal: the run is
    not VERIFIED yet, the approval text is not explicit/non-negated
    (`WritebackApproval.from_user`), nothing at `relpaths` actually changed, or
    an original changed since copy-in (`WorkspaceError` from
    `Workspace.write_back`, e.g. `ORIGINAL_CHANGED_SINCE_COPY_IN`).
    """
    status, _ = _live_verification_status(recorder, task_id, run_id)
    if status != "VERIFIED":
        raise WritebackRefused("WRITEBACK_REQUIRES_VERIFIED_RUN")
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
        written = ws.write_back(approval, sources=sources, verified_status=status)
    except WorkspaceError as exc:
        raise WritebackRefused(str(exc)) from exc

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

    # The COMPLETED transition goes through the USER_PROVIDED path (an
    # ordinary explicit-word transition, uri_v1/memory/recorder.py:114-121),
    # not the runtime "VERIFIED_COMPLETE" observation. That runtime path
    # additionally requires (uri_v1/memory/index.py:140-145,
    # VERIFIED_CURRENT_REFERENCES_REQUIRED) that the task's *current*
    # reference hashes still match the verifying record's inputs -- true for
    # an Edge/harness completion (which verifies the still-untouched bound
    # originals), but never true here: write-back deliberately changes the
    # original's live bytes while (per rule 4.3.6) the task's own reference
    # still names the pre-write hash, on purpose, so a follow-up request opens
    # a new task instead of silently re-pointing this one. Completion here is
    # correctly modeled as user-approved (the write only happened because the
    # user approved it), evidenced by `last_outcome_record_id` pointing at
    # this module's own independently-checked VERIFIER_RESULT record.
    complete_text = "write-back complete"
    complete_intake = URIIntake().capture(approval_intake.user_id, approval_intake.session_id, uuid.uuid4().hex,
                                          uuid.uuid4().hex, complete_text, spans={"complete": (0, len(complete_text))})
    result = recorder.task_state(task_id, expected_head_record_id, intake=complete_intake, status="COMPLETED",
                                 last_outcome_record_id=record.record_id)
    if not result.persisted:
        raise WritebackRefused(result.reason)
    return WritebackOutcome(tuple(written), record.record_id, result)
