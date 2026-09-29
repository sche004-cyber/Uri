"""Bounded, sequential execution of a CompiledPlan; completion only by the URI verifier.

Stage 2 §2.5 and §4. The runner is a composition controller over injected,
approved action adapters, not a new dispatcher. Before each node it
re-validates `(action_id, version, qualification_sha)` against the live
snapshot; on any mismatch the node and every unfinished node stop with
CAPABILITY_CHANGED. A failed node issues no handle, so nothing downstream can
run on a default. `bundle/plan.json` is written before RUN_STARTED, and the
plan hash is bound into the acceptance task class, so the verifier checks the
exact plan that ran.

Only a `VERIFIED` verdict from the registered verifier is reported as
`VERIFIED`. Every other path is REJECTED, NEEDS_CLARIFICATION, NOT_ATTEMPTED
or NOT_VERIFIED.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time

from uri_v1.execution.acceptance import AcceptanceCriteria
from uri_v1.execution.lineage import record_and_verify
from uri_v1.execution.officefile import WorkbookReadError
from uri_v1.execution.verify import VERIFIER_ID
from uri_v1.execution.workspace import Workspace, WorkspaceError, new_run_id
from .actions import ActionError, NodeContext, SourceInput
from .bindings import BindingError, HandleTable, bind_sources
from .compiler import compile_proposal
from .contracts import (CAPABILITY_ID, REPORT_NAME, ClarificationRequired, CompiledPlan, Limits, Rejection, canonical)

ACTION_LABEL = "planned workbook structure report"
STATUSES = frozenset({"VERIFIED", "NOT_VERIFIED", "REJECTED", "NEEDS_CLARIFICATION", "NOT_ATTEMPTED"})


@dataclass(frozen=True)
class PlanOutcome:
    status: str
    run_id: str | None = None
    verification_status: str | None = None
    claim_record_id: str | None = None
    verifier_record_id: str | None = None
    rejection: Rejection | None = None
    clarification: ClarificationRequired | None = None
    reason: str | None = None
    executed: tuple = ()
    latency_ms: float = 0.0

    def __post_init__(self):
        if self.status not in STATUSES: raise ValueError("PLAN_OUTCOME_STATUS")


def plan_acceptance(plan: CompiledPlan) -> AcceptanceCriteria:
    return AcceptanceCriteria(1, ({"kind": "only_changed", "paths": [REPORT_NAME]},
                                  {"kind": "report_recomputes", "path": REPORT_NAME, "task_class": plan.task_class}))


class _Abort(Exception):
    def __init__(self, code, node_id):
        super().__init__(code)
        self.code, self.node_id = code, node_id


class PlanRunner:
    def __init__(self, *, user_id, scratch_root, run_store, recorder, ledger, sources, snapshot_provider, adapters,
                 limits: Limits = Limits()):
        self.user_id, self.scratch_root, self.store = user_id, scratch_root, run_store
        self.recorder, self.ledger, self.sources = recorder, ledger, sources
        self.snapshot_provider, self.adapters, self.limits = snapshot_provider, adapters, limits

    def run(self, plan: CompiledPlan, *, task_id, trace_id, session_id, candidates, raw_proposal=None) -> PlanOutcome:
        if not isinstance(plan, CompiledPlan): raise ValueError("COMPILED_PLAN_REQUIRED")
        started = time.perf_counter()
        elapsed = lambda: round((time.perf_counter() - started) * 1000, 1)
        run_id = new_run_id()
        try:
            inputs = bind_sources(plan, self.sources, candidates)
            ws = Workspace.create(user_id=self.user_id, scratch_root=self.scratch_root, sources=self.sources,
                                  inputs=list(inputs), run_id=run_id)
        except (BindingError, WorkspaceError) as exc:
            return PlanOutcome("NOT_ATTEMPTED", run_id=None, reason=str(exc), latency_ms=elapsed())
        (ws.bundle / "plan.json").write_bytes(plan.canonical())
        proposal_sha = None
        if raw_proposal is not None:
            (ws.bundle / "proposal.json").write_bytes(raw_proposal.encode("utf-8"))
            proposal_sha = hashlib.sha256(raw_proposal.encode("utf-8")).hexdigest()
        acceptance = plan_acceptance(plan)
        ws.acquire(run_id)
        executed = []
        try:
            self.store.append(run_id, "RUN_STARTED", {
                "executor": "LOCAL_EDGE", "capability_id": CAPABILITY_ID, "plan_sha256": plan.sha256,
                "proposal_raw_sha256": proposal_sha, "task_id": task_id, "trace_id": trace_id,
                "workspace_dir": str(ws.base), "manifest": [e.__dict__ for e in ws.manifest],
                "manifest_sha256": ws.manifest_sha256, "acceptance": acceptance.to_dict(),
                "acceptance_sha256": acceptance.sha256})
            try:
                self._execute(plan, ws, task_id, run_id, executed, started)
            except _Abort as exc:
                self.store.append(run_id, "RUN_ABORTED", {"reason": exc.code, "node": exc.node_id, "executed": list(executed)})
                return PlanOutcome("NOT_ATTEMPTED", run_id=run_id, reason=exc.code, executed=tuple(executed), latency_ms=elapsed())
        finally:
            ws.release(run_id)
        try:
            lineage = record_and_verify(recorder=self.recorder, ledger=self.ledger, store=self.store, workspace=ws, run_id=run_id,
                                        task_id=task_id, action_label=ACTION_LABEL, session_id=session_id, trace_id=trace_id,
                                        executor_claim={"capability_id": CAPABILITY_ID, "plan_sha256": plan.sha256,
                                                        "executed": list(executed)},
                                        verifier_id=VERIFIER_ID)
        except (ValueError, OSError) as exc:
            return PlanOutcome("NOT_VERIFIED", run_id=run_id, reason=str(exc)[:64], executed=tuple(executed), latency_ms=elapsed())
        status = "VERIFIED" if lineage.verification_status == "VERIFIED" else "NOT_VERIFIED"
        return PlanOutcome(status, run_id=run_id, verification_status=lineage.verification_status,
                           claim_record_id=lineage.claim_record_id, verifier_record_id=lineage.verifier_record_id,
                           reason=None if status == "VERIFIED" else (lineage.reason or lineage.verification_status),
                           executed=tuple(executed), latency_ms=elapsed())

    def _execute(self, plan, ws, task_id, run_id, executed, started):
        paths = {e.source_id: ws.files / e.relpath for e in ws.manifest}
        table = HandleTable(user_id=self.user_id, task_id=task_id, run_id=run_id)
        for node_id in plan.order:
            node = plan.node(node_id)
            live = self.snapshot_provider()
            contract = live.get(node.action_id, node.version)
            adapter = self.adapters.get((node.action_id, node.version))
            if (contract is None or adapter is None or contract.qualification != node.qualification_sha
                    or contract.verifier_coverage != node.verifier_coverage):
                raise _Abort("CAPABILITY_CHANGED", node_id)
            if time.perf_counter() - started > self.limits.run_seconds: raise _Abort("RUN_TIME_EXCEEDED", node_id)
            inputs = {}
            try:
                for port, (kind, value) in node.inputs:
                    if kind == "source":
                        inputs[port] = SourceInput(value, paths[value])
                        continue
                    items = []
                    for src, src_port in value:
                        producer = plan.node(src)
                        out_type = live.get(producer.action_id, producer.version).output(src_port)
                        items.append({"ref": f"{src}.{src_port}", "type": out_type.value, "value": table.get(src, src_port)})
                    spec = contract.input(port)
                    if spec is None: raise _Abort("CAPABILITY_CHANGED", node_id)
                    inputs[port] = items if spec.max_refs > 1 else items[0]["value"]
            except (BindingError, AttributeError, KeyError) as exc:
                raise _Abort(str(exc) if isinstance(exc, BindingError) else "UNBOUND_INPUT", node_id)
            literals = {k: list(v) if isinstance(v, tuple) else v for k, v in node.literals}
            executed.append(node_id)
            node_started = time.perf_counter()
            try:
                out = adapter(NodeContext(ws.files, plan.sha256, node_id), inputs, literals)
            except (ActionError, WorkbookReadError) as exc:
                raise _Abort(str(exc), node_id)
            except OSError:
                raise _Abort("ACTION_IO_ERROR", node_id)
            if time.perf_counter() - node_started > self.limits.node_seconds: raise _Abort("NODE_TIME_EXCEEDED", node_id)
            if not isinstance(out, dict) or set(out) != {p for p, _ in contract.outputs}: raise _Abort("OUTPUT_TYPE_INVALID", node_id)
            for port, port_type in contract.outputs:
                try:
                    if len(canonical(out[port])) > self.limits.max_output_bytes: raise _Abort("OUTPUT_TOO_LARGE", node_id)
                    table.issue(node_id, port, out[port], port_type)
                except (BindingError, TypeError, ValueError) as exc:
                    raise _Abort(str(exc) if isinstance(exc, BindingError) else "OUTPUT_TYPE_INVALID", node_id)


def run_proposal(provider, snapshot, candidates, runner: PlanRunner, *, goal_context, task_id, trace_id, session_id,
                 limits: Limits = Limits()) -> tuple:
    """provider → compile → run. Returns (PlanOutcome, CompiledPlan | None, ProviderResult)."""
    result = provider.propose(goal_context, snapshot.to_dict(), candidates)
    if result.error is not None or result.parsed is None:
        return PlanOutcome("NOT_ATTEMPTED", reason=result.error or "PROPOSAL_INVALID"), None, result
    compiled = compile_proposal(result.parsed, snapshot, candidates, limits=limits)
    if isinstance(compiled, Rejection):
        return PlanOutcome("REJECTED", rejection=compiled, reason=compiled.code), None, result
    if isinstance(compiled, ClarificationRequired):
        return PlanOutcome("NEEDS_CLARIFICATION", clarification=compiled, reason="AMBIGUOUS_SOURCE"), None, result
    if not isinstance(compiled, CompiledPlan):
        return PlanOutcome("REJECTED", reason="PARTIAL_NOT_SUPPORTED"), None, result
    outcome = runner.run(compiled, task_id=task_id, trace_id=trace_id, session_id=session_id, candidates=candidates,
                         raw_proposal=result.raw_text)
    return outcome, compiled, result
