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

Every call returns a typed `PlanOutcome`; nothing an adapter, the ledger, the
recorder or the verifier raises escapes. Once RUN_STARTED is appended, the run
record always gets a terminal event: RUN_RESULT and VERIFICATION from
`record_and_verify`, or RUN_ABORTED (best effort if the run store itself fails).
Before anything runs, the plan is re-derived by the compiler from its own
content, the pinned snapshot and the candidates; a plan the compiler would not
produce byte for byte is refused (PLAN_NOT_COMPILED).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time

from uri_v1.execution.acceptance import AcceptanceCriteria
from uri_v1.execution.lineage import record_and_verify
from uri_v1.execution.officefile import WorkbookReadError
from uri_v1.execution.verify import VERIFIER_ID
from uri_v1.execution.workspace import Workspace, WorkspaceError, new_run_id
from .actions import ActionError, NodeContext, SourceInput
from .bindings import BindingError, HandleTable, bind_sources
from .compiler import compile_proposal
from .contracts import (CAPABILITY_ID, PROPOSAL_SCHEMA_VERSION, REPORT_NAME, ClarificationRequired, CompiledPlan, Limits, ProposalInvalid, Rejection,
                        SemanticProposal, canonical)
from .provider_port import ProviderResult, parse_raw

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
    def __init__(self, code, node_id, detail=None):
        super().__init__(code)
        self.code, self.node_id, self.detail = code, node_id, detail


_MAX_FORM_VARIANTS = 8


def _proposals_of(plan: CompiledPlan, snapshot):
    """Every proposal the plan could have been compiled from, rebuilt from the plan's own nodes.

    The only information a plan drops is whether a single ref to a multi-ref port was written as a
    list or a bare string, so each such port is tried both ways (bounded)."""
    nodes, forks = [], []
    for node in plan.nodes:
        contract = snapshot.get(node.action_id, node.version)
        inputs = {}
        for port, (kind, value) in node.inputs:
            if kind == "source":
                inputs[port] = {"source": value}
                continue
            refs = [f"{n}.{p}" for n, p in value]
            spec = contract.input(port) if contract else None
            inputs[port] = {"from": refs if len(refs) > 1 else refs[0]}
            if len(refs) == 1 and spec is not None and spec.max_refs > 1: forks.append(inputs[port])
        nodes.append({"id": node.node_id, "action": node.action_id, "action_version": node.version, "inputs": inputs,
                      "literals": {k: list(v) if isinstance(v, tuple) else v for k, v in node.literals}})
    if len(forks) > _MAX_FORM_VARIANTS: raise ValueError("PLAN_FORKS")
    for mask in range(2 ** len(forks)):
        for bit, binding in enumerate(forks):
            ref = binding["from"][0] if isinstance(binding["from"], list) else binding["from"]
            binding["from"] = [ref] if mask >> bit & 1 else ref
        yield json.loads(json.dumps({"schema_version": PROPOSAL_SCHEMA_VERSION, "nodes": nodes,
                                     "outputs": [f"{n}.{p}" for n, p in plan.outputs], "cannot": []}))


def _refusal(plan, snapshot, candidates, limits, raw_proposal):
    """None when the compiler reproduces `plan` exactly; otherwise the refusal detail."""
    if not isinstance(plan, CompiledPlan): return "NOT_A_COMPILED_PLAN"
    if snapshot is None or getattr(snapshot, "sha256", None) != plan.snapshot_sha256: return "SNAPSHOT_MISMATCH"
    try:
        target, matched, refusal = plan.canonical(), False, "PLAN_DIFFERS"
        for proposal in _proposals_of(plan, snapshot):
            again = compile_proposal(proposal, snapshot, candidates, limits=limits)
            if not isinstance(again, CompiledPlan):
                refusal = f"COMPILER_{getattr(again, 'code', 'REFUSED')}"
                break                  # the two forms of a ref compile alike or not at all
            if again.canonical() == target:
                matched = True
                break
        if not matched: return refusal
        if raw_proposal is not None:
            parsed = parse_raw(raw_proposal)
            try: raw_sha = SemanticProposal.parse(parsed).sha256 if parsed is not None else None
            except ProposalInvalid: raw_sha = None
            if raw_sha != plan.proposal_sha256: return "PROPOSAL_DIFFERS"
    except (ProposalInvalid, AttributeError, TypeError, ValueError, KeyError, IndexError, RecursionError):
        return "PLAN_MALFORMED"
    return None


class PlanRunner:
    def __init__(self, *, user_id, scratch_root, run_store, recorder, ledger, sources, snapshot_provider, adapters,
                 limits: Limits = Limits()):
        self.user_id, self.scratch_root, self.store = user_id, scratch_root, run_store
        self.recorder, self.ledger, self.sources = recorder, ledger, sources
        self.snapshot_provider, self.adapters, self.limits = snapshot_provider, adapters, limits

    def run(self, plan: CompiledPlan, *, task_id, trace_id, session_id, candidates, snapshot=None,
            raw_proposal=None) -> PlanOutcome:
        """`snapshot` is the capability snapshot the plan was compiled against (its hash is in the plan)."""
        started = time.perf_counter()
        elapsed = lambda: round((time.perf_counter() - started) * 1000, 1)
        refused = _refusal(plan, snapshot, candidates, self.limits, raw_proposal)
        if refused is not None:
            return PlanOutcome("REJECTED", rejection=Rejection("PLAN_NOT_COMPILED", refused), reason="PLAN_NOT_COMPILED",
                               latency_ms=elapsed())
        run_id = new_run_id()
        try:
            inputs = bind_sources(plan, self.sources, candidates)
            ws = Workspace.create(user_id=self.user_id, scratch_root=self.scratch_root, sources=self.sources,
                                  inputs=list(inputs), run_id=run_id)
        except (BindingError, WorkspaceError) as exc:
            return PlanOutcome("NOT_ATTEMPTED", run_id=None, reason=str(exc), latency_ms=elapsed())
        except Exception as exc:
            return PlanOutcome("NOT_ATTEMPTED", run_id=None, reason=f"SETUP_ERROR:{type(exc).__name__}", latency_ms=elapsed())
        executed = []
        try:
            (ws.bundle / "plan.json").write_bytes(plan.canonical())
            proposal_sha = None
            if raw_proposal is not None:
                (ws.bundle / "proposal.json").write_bytes(raw_proposal.encode("utf-8"))
                proposal_sha = hashlib.sha256(raw_proposal.encode("utf-8")).hexdigest()
            acceptance = plan_acceptance(plan)
            ws.acquire(run_id)
        except Exception as exc:
            return PlanOutcome("NOT_ATTEMPTED", run_id=None, reason=f"SETUP_ERROR:{type(exc).__name__}", latency_ms=elapsed())
        try:
            try:
                self.store.append(run_id, "RUN_STARTED", {
                    "executor": "LOCAL_EDGE", "capability_id": CAPABILITY_ID, "plan_sha256": plan.sha256,
                    "proposal_raw_sha256": proposal_sha, "task_id": task_id, "trace_id": trace_id,
                    "workspace_dir": str(ws.base), "manifest": [e.__dict__ for e in ws.manifest],
                    "manifest_sha256": ws.manifest_sha256, "acceptance": acceptance.to_dict(),
                    "acceptance_sha256": acceptance.sha256})
            except Exception as exc:
                # Nothing was recorded as started, so there is nothing to close.
                return PlanOutcome("NOT_ATTEMPTED", run_id=None, reason=f"RUN_RECORD_ERROR:{type(exc).__name__}",
                                   latency_ms=elapsed())
            try:
                self._execute(plan, ws, task_id, run_id, executed, started)
            except Exception as exc:
                abort = exc if isinstance(exc, _Abort) else _Abort("RUNNER_ERROR", None, type(exc).__name__)
                closed = self._close(run_id, abort.code, abort.node_id, executed, abort.detail)
                # A run that executed every node was attempted in full; only its result is unverified.
                status = "NOT_VERIFIED" if executed == list(plan.order) else "NOT_ATTEMPTED"
                return PlanOutcome(status, run_id=run_id, reason=abort.code if closed else f"{abort.code}|RUN_NOT_CLOSED",
                                   executed=tuple(executed), latency_ms=elapsed())
        finally:
            try: ws.release(run_id)
            except Exception: pass
        try:
            lineage = record_and_verify(recorder=self.recorder, ledger=self.ledger, store=self.store, workspace=ws, run_id=run_id,
                                        task_id=task_id, action_label=ACTION_LABEL, session_id=session_id, trace_id=trace_id,
                                        executor_claim={"capability_id": CAPABILITY_ID, "plan_sha256": plan.sha256,
                                                        "executed": list(executed)},
                                        verifier_id=VERIFIER_ID)
        except Exception as exc:
            reason = str(exc)[:64] if isinstance(exc, (ValueError, OSError)) else f"VERIFICATION_ERROR:{type(exc).__name__}"
            closed = self._close(run_id, reason, None, executed, type(exc).__name__)
            return PlanOutcome("NOT_VERIFIED", run_id=run_id, reason=reason if closed else f"{reason}|RUN_NOT_CLOSED"[:96],
                               executed=tuple(executed), latency_ms=elapsed())
        status = "VERIFIED" if lineage.verification_status == "VERIFIED" else "NOT_VERIFIED"
        return PlanOutcome(status, run_id=run_id, verification_status=lineage.verification_status,
                           claim_record_id=lineage.claim_record_id, verifier_record_id=lineage.verifier_record_id,
                           reason=None if status == "VERIFIED" else (lineage.reason or lineage.verification_status),
                           executed=tuple(executed), latency_ms=elapsed())

    def _close(self, run_id, reason, node_id, executed, detail=None) -> bool:
        """Append RUN_ABORTED unless the run already has a verdict or an abort. False if the store fails."""
        try:
            run = self.store.get(run_id) or {}
            if "VERIFICATION" in run.get("events", ()) or "RUN_ABORTED" in run.get("events", ()): return True
            data = {"reason": reason, "node": node_id, "executed": list(executed)}
            if detail is not None: data["detail"] = str(detail)[:200]
            self.store.append(run_id, "RUN_ABORTED", data)
            return True
        except Exception:
            return False

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
            except Exception as exc:
                # Anything else an approved adapter raises on user data (a damaged zip member, an
                # unsupported compression method, an encrypted entry) is a typed abort, not a crash.
                raise _Abort("ACTION_FAILED", node_id, type(exc).__name__)
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
    try:
        result = provider.propose(goal_context, snapshot.to_dict(), candidates)
    except Exception:
        result = ProviderResult(None, None, str(getattr(provider, "provider_id", "unknown")), str(getattr(provider, "model_id", "unknown")),
                                str(getattr(provider, "config_sha256", "")), 0.0, "PROVIDER_UNAVAILABLE")
    if result.error is not None or result.parsed is None:
        return PlanOutcome("NOT_ATTEMPTED", reason=result.error or "PROPOSAL_INVALID"), None, result
    try:
        compiled = compile_proposal(result.parsed, snapshot, candidates, limits=limits)
    except RecursionError:
        compiled = Rejection("PROPOSAL_INVALID", "NESTING_DEPTH")
    if isinstance(compiled, Rejection):
        return PlanOutcome("REJECTED", rejection=compiled, reason=compiled.code), None, result
    if isinstance(compiled, ClarificationRequired):
        return PlanOutcome("NEEDS_CLARIFICATION", clarification=compiled, reason="AMBIGUOUS_SOURCE"), None, result
    if not isinstance(compiled, CompiledPlan):
        return PlanOutcome("REJECTED", reason="PARTIAL_NOT_SUPPORTED"), None, result
    outcome = runner.run(compiled, task_id=task_id, trace_id=trace_id, session_id=session_id, candidates=candidates,
                         snapshot=snapshot, raw_proposal=result.raw_text)
    return outcome, compiled, result
