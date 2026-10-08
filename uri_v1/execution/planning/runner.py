"""Bounded deterministic plan runner (Stage 2, Slice 1).

Executes CompiledPlan sequentially in topological order over COPY_IN_COPY_OUT
workspace with per-node live snapshot revalidation, runtime-owned handles,
and URI verifier integration.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Callable

from uri_v1.execution.acceptance import AcceptanceCriteria
from uri_v1.execution.lineage import LineageResult, record_and_verify
from uri_v1.execution.run_record import RunStore
from uri_v1.execution.workspace import Workspace, WorkspaceError, new_run_id
from uri_v1.memory.recorder import Recorder
from uri_v1.memory.sources import SourceRegistry
from uri_v1.results.version_ledger import ResultVersionLedger

from .actions import (
    ActionExecutionError,
    action_inspect_structure,
    action_report_write,
    action_structure_compare,
    action_structure_select,
)
from .bindings import BindingError, HandleTable, bind_sources
from .contracts import (
    CapabilityContract,
    CapabilitySnapshot,
    CompiledPlan,
    PortType,
    Rejection,
    SourceRef,
)


@dataclass(frozen=True)
class PlanOutcome:
    """Outcome of plan execution, verified through canonical URI verifier."""
    status: str  # "COMPLETED" | "FAILED" | "REJECTED"
    run_id: str
    verification_status: str  # "VERIFIED" | "FAILED" | "UNVERIFIABLE" | "CLAIMED_ONLY" | "NOT_RECORDED"
    claim_record_id: str | None
    verifier_record_id: str | None
    rejection: Rejection | None = None
    node_receipts: tuple[dict[str, Any], ...] = ()


class PlanRunner:
    """Composition controller over approved deterministic actions."""

    def __init__(
        self,
        user_id: str,
        scratch_root: Path | str,
        run_store: RunStore,
        recorder: Recorder,
        ledger: ResultVersionLedger,
        sources: SourceRegistry,
        snapshot_provider: Callable[[], CapabilitySnapshot] | CapabilitySnapshot,
        node_timeout_s: float = 30.0,
    ):
        self.user_id = user_id
        self.scratch_root = Path(scratch_root)
        self.run_store = run_store
        self.recorder = recorder
        self.ledger = ledger
        self.sources = sources
        self.snapshot_provider = snapshot_provider
        self.node_timeout_s = node_timeout_s

    def _get_snapshot(self) -> CapabilitySnapshot:
        if callable(self.snapshot_provider):
            return self.snapshot_provider()
        return self.snapshot_provider

    def run(
        self,
        plan: CompiledPlan,
        *,
        task_id: str,
        trace_id: str,
        session_id: str,
    ) -> PlanOutcome:
        """Execute a compiled plan in a fresh COPY_IN_COPY_OUT workspace."""
        # 1. Bind sources
        candidate_map = {s.source_id: s.content_sha256 for s in plan.sources}
        try:
            workspace_inputs = bind_sources(plan, self.sources, candidate_map)
        except BindingError as exc:
            return PlanOutcome(
                status="REJECTED",
                run_id="",
                verification_status="UNVERIFIABLE",
                claim_record_id=None,
                verifier_record_id=None,
                rejection=Rejection(exc.code, exc.detail),
            )

        run_id = new_run_id()

        # 2. Create COPY_IN_COPY_OUT scratch workspace
        try:
            ws = Workspace.create(
                user_id=self.user_id,
                scratch_root=self.scratch_root,
                sources=self.sources,
                inputs=workspace_inputs,
                run_id=run_id,
            )
        except WorkspaceError as exc:
            return PlanOutcome(
                status="FAILED",
                run_id=run_id,
                verification_status="UNVERIFIABLE",
                claim_record_id=None,
                verifier_record_id=None,
                rejection=Rejection("WORKSPACE_CREATION_FAILED", str(exc)),
            )

        # 3. Store CompiledPlan in workspace.bundle/plan.json (outside files/)
        plan_bytes = plan.canonical()
        plan_file = ws.bundle / "plan.json"
        plan_file.write_bytes(plan_bytes)

        # 4. Formulate Acceptance Criteria
        acceptance = AcceptanceCriteria(
            revision=1,
            items=(
                {"kind": "only_changed", "paths": ["plan_report.json"]},
                {"kind": "report_recomputes", "path": "plan_report.json", "task_class": f"PLANNED_STRUCTURE_REPORT@{plan.sha256}"},
            ),
        )

        # 5. Record RUN_STARTED with LOCAL_EDGE executor
        self.run_store.append(run_id, "RUN_STARTED", {
            "executor": "LOCAL_EDGE",
            "capability_id": "uri.plan.compiled",
            "plan_sha256": plan.sha256,
            "task_id": task_id,
            "trace_id": trace_id,
            "workspace_dir": str(ws.base),
            "manifest": [e.__dict__ for e in ws.manifest],
            "manifest_sha256": ws.manifest_sha256,
            "acceptance": acceptance.to_dict(),
            "acceptance_sha256": acceptance.sha256,
        })

        # 6. Initialize HandleTable and Source map
        handle_table = HandleTable(self.user_id, task_id, run_id)
        source_files = {e.source_id: ws.files / e.relpath for e in ws.manifest}

        node_receipts: list[dict[str, Any]] = []
        claimed_failed = False
        rejection_cause: Rejection | None = None
        safety_flags: list[str] = []

        # 7. Execute topological plan
        for node in plan.nodes:
            # Per-node live capability re-validation (F4)
            current_snap = self._get_snapshot()
            live_contract = current_snap.get(node.action_id, node.version)
            if live_contract is None or live_contract.qualification != node.qualification_sha:
                claimed_failed = True
                safety_flags.append("CAPABILITY_CHANGED")
                rejection_cause = Rejection(
                    "CAPABILITY_CHANGED",
                    f"Action '{node.action_id}' qualification changed during run"
                )
                break

            # Resolve inputs
            resolved_inputs: dict[str, Any] = {}
            input_error = False
            for port_name, binding in node.inputs.items():
                if isinstance(binding, SourceRef):
                    if binding.source_id not in source_files:
                        claimed_failed = True
                        rejection_cause = Rejection("SOURCE_NOT_BOUND", f"Source {binding.source_id} not in workspace")
                        input_error = True
                        break
                    resolved_inputs[port_name] = source_files[binding.source_id]
                else:
                    try:
                        resolved_inputs[port_name] = handle_table.get(binding.from_node, binding.from_port)
                    except BindingError as exc:
                        claimed_failed = True
                        rejection_cause = Rejection(exc.code, exc.detail)
                        input_error = True
                        break

            if input_error:
                break

            # Execute action with timeout
            start_t = time.monotonic()
            action_id = node.action_id
            output_dict: dict[str, Any] = {}

            try:
                if action_id == "uri.plan.workbook.inspect_structure":
                    output_dict = action_inspect_structure(resolved_inputs["source"])
                elif action_id == "uri.plan.structure.select":
                    output_dict = action_structure_select(
                        resolved_inputs["structure"],
                        node.literals["sheets"],
                        node.literals.get("headers"),
                    )
                elif action_id == "uri.plan.structure.compare":
                    output_dict = action_structure_compare(
                        resolved_inputs["left"],
                        resolved_inputs["right"],
                        node.literals["match_on"],
                    )
                elif action_id == "uri.plan.report.write":
                    items = [resolved_inputs[k] for k in sorted(resolved_inputs.keys()) if k.startswith("item")]
                    output_dict = action_report_write(items, ws.files, plan.sha256)
                else:
                    raise ActionExecutionError("UNKNOWN_ACTION_HANDLER", f"No executor for {action_id}")

                elapsed = time.monotonic() - start_t
                if elapsed > self.node_timeout_s:
                    claimed_failed = True
                    safety_flags.append("NODE_TIMEOUT")
                    rejection_cause = Rejection("NODE_TIMEOUT", f"Node '{node.node_id}' exceeded timeout")
                    break

                # Issue opaque handles for outputs
                for out_port, out_val in output_dict.items():
                    if out_port in live_contract.outputs:
                        port_type = live_contract.outputs[out_port]
                        handle_table.issue(node.node_id, out_port, out_val, port_type)

                node_receipts.append({
                    "node_id": node.node_id,
                    "action_id": node.action_id,
                    "status": "OK",
                    "elapsed_s": elapsed,
                })

            except ActionExecutionError as exc:
                claimed_failed = True
                rejection_cause = Rejection(exc.code, exc.detail)
                node_receipts.append({
                    "node_id": node.node_id,
                    "action_id": node.action_id,
                    "status": "FAILED",
                    "error": exc.code,
                })
                break
            except Exception as exc:
                claimed_failed = True
                rejection_cause = Rejection("UNEXPECTED_ERROR", str(exc))
                node_receipts.append({
                    "node_id": node.node_id,
                    "action_id": node.action_id,
                    "status": "FAILED",
                    "error": type(exc).__name__,
                })
                break

        # 8. Record and verify through existing canonical URI verification
        obs = {"safety_flags": safety_flags}
        lineage: LineageResult = record_and_verify(
            recorder=self.recorder,
            ledger=self.ledger,
            store=self.run_store,
            workspace=ws,
            run_id=run_id,
            task_id=task_id,
            action_label=f"execute compiled plan {plan.sha256[:8]}",
            session_id=session_id,
            trace_id=trace_id,
            claimed_failed=claimed_failed,
            exit_code=1 if claimed_failed else 0,
            executor_claim={
                "plan_sha256": plan.sha256,
                "status": "FAILED" if claimed_failed else "COMPLETED",
            },
            uri_observations=obs,
        )

        overall_status = "COMPLETED" if lineage.verification_status == "VERIFIED" else "FAILED"
        return PlanOutcome(
            status=overall_status,
            run_id=run_id,
            verification_status=lineage.verification_status,
            claim_record_id=lineage.claim_record_id,
            verifier_record_id=lineage.verifier_record_id,
            rejection=rejection_cause,
            node_receipts=tuple(node_receipts),
        )
