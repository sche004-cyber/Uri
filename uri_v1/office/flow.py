"""`OfficeSession`: request -> bind -> acceptance -> Edge -> (escalate) -> write-back (M39 §4.2/§4.3).

Each step checkpoints Memory via `Recorder.task_state`. No model/LLM call
anywhere in this module.

Defensive note (known upstream defects, disclosed, not fixed here -- M39 plan
stop condition S-3): a fresh, unrepaired finding on the M38 predecessor says
its harness process can escape its declared workspace boundary and that the
current wiring can expose host environment secrets to the harness process.
`invoke_harness` below only ever calls the `HarnessRunner`/adapter objects it
is given by the caller; it assumes nothing about their containment. The real
`ClaudeCodeAdapter` pointed at a live `claude` executable (built by
`uri_v1/office/bootstrap.py`) is therefore NOT SAFE to run against real user
files or real credentials until that M38 defect is repaired and re-qualified;
this module and its test suite only ever exercise it through the fake adapter
in `tests/m38_harness_support.py` (test-only, one Python file that never
touches the network or real credentials) or leave it uninvoked. See
`docs/plans/M39_IMPLEMENTATION_REPORT.md` "Known upstream defects" for detail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from uri_v1.edge.contracts import EdgeTask, TaskClass, TaskInput
from uri_v1.edge.resolver import read_bound
from uri_v1.execution.harness.contracts import HarnessError, Limits, PermissionProfile
from uri_v1.memory.contracts import TaskStatus, TrustedInput, negated
from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.reference_clarification.binding import BindingService

from .acceptance_builder import build_acceptance
from .binding import ROLES, answer_role, bind_role
from .writeback import WritebackRefused, open_run_workspace, writeback as do_writeback

INTAKE = URIIntake()
_CONSENT_WORDS = frozenset({"yes", "approve", "approved", "run", "send", "escalate", "proceed", "ok", "okay", "go"})

# Known-open M38 defect: containment / secret isolation is not repaired. This
# flag is checked (and can be asserted on in tests) rather than silently
# ignored; it does not itself block a *fake*-adapter run, since the fake
# adapter is a local test script with no containment assumptions to violate.
KNOWN_UNSAFE_HARNESS_SUBSTRATE = True


def _make_intake(user_id, session_id, turn_id, trace_id, raw_text, *, round_id=None, ref_key="text"):
    return INTAKE.capture(user_id, session_id, turn_id, trace_id, raw_text, spans={ref_key: (0, len(raw_text))}, round_id=round_id)


@dataclass(frozen=True)
class StepResult:
    kind: str
    task_id: str | None = None
    reason: str | None = None
    role: str | None = None
    roles: dict = field(default_factory=dict)
    escalation: object | None = None
    run_id: str | None = None
    relpaths: tuple = ()
    verification_status: str | None = None
    warnings: tuple = ()
    written: tuple = ()
    safety_flags: tuple = ()


class OfficeSession:
    def __init__(self, *, log, sources, recorder, retriever, edge, scratch_root, user_id,
                harness_runner=None, adapter=None, service=None):
        self.log, self.sources, self.recorder, self.retriever, self.edge = log, sources, recorder, retriever, edge
        self.scratch_root, self.user_id = scratch_root, user_id
        self.harness_runner, self.adapter = harness_runner, adapter
        self.service = service or BindingService()
        self._heads: dict[str, str] = {}
        self._pending: dict[str, dict] = {}          # task_id -> {ref_key: RoleBinding}
        self._escalation: dict[str, object] = {}      # task_id -> EscalationRequest awaiting consent
        self._run: dict[str, tuple] = {}              # task_id -> (run_id, source)

    # -- request -> bind -------------------------------------------------------
    def start(self, raw_text, *, session_id, turn_id, trace_id, parsed) -> StepResult:
        """`parsed` is a `uri_v1.office.request.ParsedRequest` with `ok=True`."""
        intake = INTAKE.capture(self.user_id, session_id, turn_id, trace_id, raw_text, spans=parsed.spans)
        objective = raw_text if len(raw_text) <= 500 else raw_text[:500]
        task_id, opened = self.recorder.open_task(intake, objective)
        if not opened.persisted:
            return StepResult("ERROR", reason=opened.reason)
        self._heads[task_id] = opened.record_ids[-1]
        return self._advance_binding(task_id, intake)

    def answer(self, task_id, raw_text, *, session_id, turn_id, trace_id, round_id) -> StepResult:
        """Answer the outstanding clarification round(s) for this task."""
        pending = self._pending.get(task_id, {})
        target = next((rb for rb in pending.values() if rb.contract_id == round_id), None)
        if target is None:
            return StepResult("ERROR", task_id=task_id, reason="UNKNOWN_ROUND")
        answer_intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, round_id=round_id, ref_key=target.ref_key)
        rb = answer_role(self.service, self.sources, target, answer_intake)
        pending[target.ref_key] = rb
        still_pending = [x for x in pending.values() if x.state != "CONFIRMED"]
        if still_pending:
            return StepResult("CLARIFY", task_id=task_id, roles=dict(pending))
        return self._bind_complete(task_id, answer_intake, pending)

    def _advance_binding(self, task_id, intake) -> StepResult:
        bindings = {role: bind_role(self.retriever, self.sources, self.service, intake, role, task_id=task_id) for role in ROLES}
        self._pending[task_id] = bindings
        if any(rb.state != "CONFIRMED" for rb in bindings.values()):
            return StepResult("CLARIFY", task_id=task_id, roles=dict(bindings))
        return self._bind_complete(task_id, intake, bindings)

    def _bind_complete(self, task_id, intake, bindings) -> StepResult:
        script_ref, workbook_ref = bindings["script"].bound.source, bindings["workbook"].bound.source
        if script_ref.source_id == workbook_ref.source_id:
            return StepResult("ERROR", task_id=task_id, reason="SAME_SOURCE_FOR_BOTH_ROLES")
        result = self.recorder.task_state(task_id, self._heads[task_id], intake=intake,
                                          bindings=[bindings["script"].bound, bindings["workbook"].bound])
        if not result.persisted:
            return StepResult("ERROR", task_id=task_id, reason=result.reason)
        self._heads[task_id] = result.record_ids[-1]
        read = read_bound(self.sources, script_ref.source_id, script_ref.content_sha256)
        if read is None:
            return StepResult("ERROR", task_id=task_id, reason="STALE_INPUT")
        script_bytes, script_name = read
        built = build_acceptance(script_bytes, script_name)
        task = EdgeTask(task_id, TaskClass.SCRIPT_WORKBOOK_REPAIR,
                        (TaskInput("script", script_ref.source_id, script_ref.content_sha256),
                         TaskInput("workbook", workbook_ref.source_id, workbook_ref.content_sha256)),
                        built.criteria, intake.trace_id, intake.session_id)
        edge_result = self.edge.handle(task)
        return self._after_edge(task_id, edge_result, built.warnings)

    def _after_edge(self, task_id, edge_result, warnings) -> StepResult:
        if edge_result.route == "LOCAL_VERIFIED":
            return self._offer_writeback(task_id, edge_result.local.run_id, warnings=warnings)
        if edge_result.route == "ESCALATE":
            self._escalation[task_id] = edge_result.escalation
            return StepResult("ESCALATION_PROPOSAL", task_id=task_id, escalation=edge_result.escalation, warnings=warnings)
        return StepResult("CLARIFY_MEMORY", task_id=task_id, reason=edge_result.decision.reason.value, warnings=warnings)

    def _offer_writeback(self, task_id, run_id, *, warnings=()) -> StepResult:
        ws = open_run_workspace(self.user_id, self.scratch_root, run_id)
        diff = ws.diff()
        modified = tuple(sorted(c["relpath"] for c in diff["changes"] if c["op"] == "MODIFIED"))
        if not modified:
            return StepResult("NOTHING_TO_WRITE", task_id=task_id, run_id=run_id, warnings=warnings)
        self._run[task_id] = run_id
        return StepResult("AWAITING_APPROVAL", task_id=task_id, run_id=run_id, relpaths=modified, warnings=warnings)

    # -- escalation consent -> harness -----------------------------------------
    def confirm_escalation(self, task_id, raw_text, *, session_id, turn_id, trace_id) -> StepResult:
        escalation = self._escalation.get(task_id)
        if escalation is None:
            return StepResult("ERROR", task_id=task_id, reason="NO_PENDING_ESCALATION")
        consent_intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, ref_key="consent")
        words = set(re.findall(r"\w+", raw_text.casefold()))
        if negated(raw_text) or not (words & _CONSENT_WORDS):
            return StepResult("ESCALATION_DECLINED", task_id=task_id)
        if self.adapter is None or self.harness_runner is None:
            return StepResult("HARNESS_UNAVAILABLE", task_id=task_id)
        probe = self.adapter.probe()
        if not probe.get("installed"):
            return StepResult("HARNESS_UNAVAILABLE", task_id=task_id)
        del self._escalation[task_id]
        try:
            outcome = self.harness_runner.run(escalation, self.adapter, session_id=consent_intake.session_id,
                                              posture=PermissionProfile(), limits=Limits(max_budget_usd=1.0))
        except HarnessError:
            return StepResult("HARNESS_UNAVAILABLE", task_id=task_id)
        if outcome.verified:
            return self._offer_writeback(task_id, outcome.run_id)
        return StepResult("HARNESS_FAILED", task_id=task_id, run_id=outcome.run_id,
                          verification_status=outcome.verification_status, safety_flags=outcome.safety_flags)

    def decline_escalation(self, task_id) -> StepResult:
        self._escalation.pop(task_id, None)
        return StepResult("ESCALATION_DECLINED", task_id=task_id)

    # -- write-back --------------------------------------------------------------
    def approve_writeback(self, task_id, raw_text, *, run_id=None, relpaths=None, session_id, turn_id, trace_id) -> StepResult:
        run_id = run_id or self._run.get(task_id)
        if run_id is None:
            return StepResult("ERROR", task_id=task_id, reason="NO_PENDING_RUN")
        approval_intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, ref_key="approval")
        try:
            outcome = do_writeback(recorder=self.recorder, sources=self.sources, user_id=self.user_id,
                                   scratch_root=self.scratch_root, task_id=task_id, run_id=run_id,
                                   expected_head_record_id=self._heads[task_id], session_id=approval_intake.session_id,
                                   trace_id=approval_intake.trace_id, approval_intake=approval_intake,
                                   relpaths=relpaths or ())
        except WritebackRefused as exc:
            return StepResult("WRITEBACK_REFUSED", task_id=task_id, reason=str(exc))
        self._heads[task_id] = outcome.task_state_result.record_ids[-1]
        self._run.pop(task_id, None)
        return StepResult("COMPLETED", task_id=task_id, run_id=run_id, written=outcome.written)

    # -- pause / resume ------------------------------------------------------------
    def pause(self, task_id, raw_text, *, run_id, session_id, turn_id, trace_id) -> StepResult:
        intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, ref_key="pause")
        result = self.recorder.task_state(task_id, self._heads[task_id], intake=intake, status="PAUSED",
                                          next_step=f"awaiting write-back approval for run {run_id}")
        if not result.persisted:
            return StepResult("ERROR", task_id=task_id, reason=result.reason)
        self._heads[task_id] = result.record_ids[-1]
        self._run[task_id] = run_id
        return StepResult("PAUSED", task_id=task_id, run_id=run_id)

    def resume(self, task_id, raw_text, *, session_id, turn_id, trace_id) -> StepResult:
        """Rediscover a paused task (a new process calls `status()` first)."""
        index = self.log.load()
        state = index.task(task_id)
        if state is None or state.payload["status"] != TaskStatus.PAUSED.value:
            return StepResult("ERROR", task_id=task_id, reason="NOT_PAUSED")
        run_id = self._run.get(task_id)
        if run_id is None:
            m = re.search(r"run ([0-9a-f]{32})", (state.payload.get("next_step") or {}).get("text", ""))
            run_id = m.group(1) if m else None
        if run_id is None:
            return StepResult("ERROR", task_id=task_id, reason="NO_PENDING_RUN")
        ws = open_run_workspace(self.user_id, self.scratch_root, run_id)
        originals_changed = ws.originals_unchanged(self.sources)
        intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, ref_key="resume")
        result = self.recorder.task_state(task_id, state.record_id, intake=intake, status="OPEN")
        if not result.persisted:
            return StepResult("ERROR", task_id=task_id, reason=result.reason)
        self._heads[task_id] = result.record_ids[-1]
        if originals_changed:
            return StepResult("WRITEBACK_REFUSED", task_id=task_id, reason="ORIGINAL_CHANGED_SINCE_COPY_IN")
        return self._offer_writeback(task_id, run_id)

    def status(self) -> tuple:
        """Open and paused tasks: task_id, status, next_step, last_outcome_record_id, references."""
        index = self.log.load()
        rows = []
        for task_id in index.openings:
            state = index.task(task_id)
            if state is None:
                continue
            rows.append({"task_id": task_id, "status": state.payload["status"],
                        "next_step": (state.payload.get("next_step") or {}).get("text"),
                        "last_outcome_record_id": state.payload.get("last_outcome_record_id"),
                        "references": [dict(r) for r in state.payload["references"]]})
        return tuple(rows)
