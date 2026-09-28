"""Execute a LOCAL decision in a bounded workspace; URI verifies the result.

A local completion is reported as complete only when the URI verifier returns
`VERIFIED`. Any other verdict is recorded (the failed attempt stays in Memory)
and the task is handed back as an escalation carrying the local findings and
the verification evidence (LF-1: correctness over avoidance).
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from uri_v1.execution.lineage import record_and_verify
from uri_v1.execution.verify import VERIFIER_ID, VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier
from uri_v1.execution.workspace import Workspace, WorkspaceInput, new_run_id
from .contracts import DecisionKind as D, EdgeDecision, EdgeTask, TaskClass as T
from .repair import RepairRefused, apply_remap
from .report import REPORT_NAME, build_report, canonical, recompute
from .resolver import escalation, structure_of

ACTION_LABELS = {T.WORKBOOK_INSPECT: "edge workbook inspection", T.SCRIPT_WORKBOOK_DIAGNOSE: "edge script-workbook diagnosis",
                 T.SCRIPT_WORKBOOK_REPAIR: "edge script-workbook literal remap"}


def verifier_entries(run_root, *, python=None) -> dict:
    """Entries for the M36 trusted verifier bootstrap (process start only)."""
    return {VERIFIER_ID: (VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier(run_root, recompute=recompute, python=python))}


@dataclass(frozen=True)
class LocalOutcome:
    completed: bool                 # True only with a VERIFIED verdict
    run_id: str
    verification_status: str
    claim_record_id: str | None
    verifier_record_id: str | None
    escalation: object | None       # EscalationRequest when the local attempt did not verify
    latency_ms: float


class LocalRunner:
    def __init__(self, *, user_id, scratch_root, run_store, recorder, ledger, sources):
        self.user_id, self.scratch_root, self.store = user_id, scratch_root, run_store
        self.recorder, self.ledger, self.sources = recorder, ledger, sources

    def run(self, task: EdgeTask, decision: EdgeDecision) -> LocalOutcome:
        if decision.kind is not D.LOCAL or decision.task_id != task.task_id: raise ValueError("LOCAL_DECISION_REQUIRED")
        started = time.perf_counter()
        run_id = new_run_id()
        ws = Workspace.create(user_id=self.user_id, scratch_root=self.scratch_root, sources=self.sources, run_id=run_id,
                              inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in task.inputs])
        ws.acquire(run_id)
        self.store.append(run_id, "RUN_STARTED", {"executor": "LOCAL_EDGE", "task_id": task.task_id, "trace_id": task.trace_id,
                                                  "capability_id": decision.capability_id, "workspace_dir": str(ws.base),
                                                  "manifest": [e.__dict__ for e in ws.manifest], "manifest_sha256": ws.manifest_sha256,
                                                  "acceptance": task.acceptance.to_dict(), "acceptance_sha256": task.acceptance.sha256})
        claim = {"capability_id": decision.capability_id, "reason": decision.reason.value}
        try:
            by_role = {e.role: e for e in ws.manifest}
            wb = by_role["workbook"]
            if task.task_class is T.SCRIPT_WORKBOOK_REPAIR:
                script = ws.files / by_role["script"].relpath
                structure = structure_of((ws.files / wb.relpath).read_bytes())
                repaired = apply_remap(script.read_bytes(), decision.findings["diagnosis"], structure, wb.relpath)
                if repaired != script.read_bytes(): script.write_bytes(repaired)
            else:
                script = ws.files / by_role["script"].relpath if "script" in by_role else None
                (ws.files / REPORT_NAME).write_bytes(canonical(build_report(task.task_class, ws.files / wb.relpath, wb.relpath, script)))
        except (RepairRefused, ValueError, OSError) as exc:
            self.store.append(run_id, "RUN_ABORTED", {"reason": type(exc).__name__, "detail": str(exc)[:200]})
            ws.release(run_id)
            return LocalOutcome(False, run_id, "NOT_ATTEMPTED", None, None,
                                escalation(task, decision.findings, (f"local capability refused: {exc}",)),
                                round((time.perf_counter() - started) * 1000, 1))
        ws.release(run_id)
        lineage = record_and_verify(recorder=self.recorder, ledger=self.ledger, store=self.store, workspace=ws, run_id=run_id,
                                    task_id=task.task_id, action_label=ACTION_LABELS[task.task_class], session_id=task.session_id,
                                    trace_id=task.trace_id, executor_claim=claim)
        completed = lineage.verification_status == "VERIFIED"
        esc = None
        if not completed:
            run = self.store.get(run_id)
            evidence = run["verifications"][-1]["items"] if run and run["verifications"] else []
            findings = dict(decision.findings, local_attempt={"run_id": run_id, "verification_status": lineage.verification_status,
                                                              "items": evidence})
            esc = escalation(task, findings, ("local attempt did not pass URI verification",))
        return LocalOutcome(completed, run_id, lineage.verification_status, lineage.claim_record_id, lineage.verifier_record_id,
                            esc, round((time.perf_counter() - started) * 1000, 1))
