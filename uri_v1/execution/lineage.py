"""Claim → URI verification → lineage, shared by local (Edge) and harness runs.

Order is fixed: URI computes the candidate diff, stores changed artifacts as
S11 result versions, writes the run result, records the executor's claim in
M36 Memory as `CLAIMED_ONLY`, and only then invokes the registered URI
verifier through `Recorder.invoke_verifier`. Nothing here can write
`VERIFIED` directly.

Recorded dependency: M36 `Recorder.outcome` / `Recorder.invoke_verifier`
(be4451c, PROVISIONAL, under independent audit).
"""
from __future__ import annotations

from dataclasses import dataclass

from .verify import VERIFIER_ID


@dataclass(frozen=True)
class LineageResult:
    run_id: str
    claim_record_id: str | None
    verifier_record_id: str | None
    verification_status: str
    outputs: tuple
    uri_computed_diff: dict
    reason: str | None = None


def record_and_verify(*, recorder, ledger, store, workspace, run_id, task_id, action_label, session_id, trace_id,
                      claimed_failed=False, exit_code=None, executor_claim=None, uri_observations=None,
                      verifier_id=VERIFIER_ID) -> LineageResult:
    diff = workspace.diff()
    outputs = []
    for n, change in enumerate(c for c in diff["changes"] if c["after_sha256"]):
        content = (workspace.files / change["relpath"]).read_bytes()
        version = ledger.record_generated(f"exec-{run_id}-{n}", content, trace_id=trace_id)
        if version.content_sha256 != change["after_sha256"]:
            raise ValueError("OUTPUT_CHANGED_DURING_RECORDING")
        outputs.append({"result_id": version.result_id, "result_version": version.version, "content_sha256": version.content_sha256})
    store.append(run_id, "RUN_RESULT", {"uri_computed_diff": diff, "outputs": outputs, "executor_claim": executor_claim or {},
                                        "uri_observations": uri_observations or {"safety_flags": []},
                                        "claimed_failed": bool(claimed_failed)})
    inputs = tuple({"source_id": e.source_id, "content_sha256": e.content_sha256} for e in workspace.manifest)
    claim = recorder.outcome(task_id, action_label=action_label, inputs=inputs, outputs=tuple(outputs), session_id=session_id,
                             trace_id=trace_id, failed=claimed_failed, exit_code=exit_code, attempt_id=run_id)
    if not claim.persisted:
        return LineageResult(run_id, None, None, "NOT_RECORDED", tuple(outputs), diff, claim.reason)
    claim_id = claim.record_ids[0]
    verdict = recorder.invoke_verifier(claim_id, verifier_id, trace_id=trace_id, session_id=session_id)
    if not verdict.persisted:
        return LineageResult(run_id, claim_id, None, "CLAIMED_ONLY", tuple(outputs), diff, verdict.reason)
    record = recorder.log.load().records[verdict.record_ids[0]]
    return LineageResult(run_id, claim_id, record.record_id, str(record.payload["verification_status"]), tuple(outputs), diff)
