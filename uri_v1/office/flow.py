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
import string

from uri_v1.edge.contracts import EdgeTask, TaskClass, TaskInput
from uri_v1.edge.resolver import read_bound
from uri_v1.execution.harness.contracts import HarnessError, Limits, PermissionProfile
from uri_v1.memory.contracts import TaskStatus, TrustedInput, negated
from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.reference_clarification.binding import BindingService

from .acceptance_builder import build_acceptance
from .binding import ROLES, answer_ask, answer_filename_span, answer_role, ask_role, bind_role, with_asks
from .writeback import WritebackRefused, open_run_workspace, writeback as do_writeback

INTAKE = URIIntake()
# M39-2 (audit): consent must be a short, entirely-affirmative reply to the
# specific proposal shown -- not any sentence that merely contains a word like
# "run" or "go" ("how long will it run?", "go back, I want to rename the file
# first", and a brand-new request that happens to say "run" all used to start
# the harness before this fix). A question is never consent, whatever words it
# uses; every token in the reply must be drawn from the affirmative
# vocabulary, and at least one must be a real consent anchor (so "it", "do",
# "go" alone -- with nothing else -- cannot accidentally count).
_CONSENT_TOKENS = frozenset({
    "yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay",
    "approve", "approved", "confirm", "confirmed",
    "go", "ahead", "do", "it", "run", "proceed", "apply", "send", "please", "that", "one",
})
_CONSENT_ANCHORS = frozenset({
    "yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay",
    "approve", "approved", "confirm", "confirmed", "proceed", "apply",
})
# R1-C (re-audit, residual of M39-2): a question mark is not only the ASCII
# "?" -- full-width, interrobang and inverted forms all mark a question and
# must refuse consent the same way.
_QUESTION_MARKS = "?？‽¿؟⸮"


def _is_consent(raw_text: str) -> bool:
    if any(ch in raw_text for ch in _QUESTION_MARKS) or negated(raw_text):
        return False
    # R1-C: tokenising only `[a-z']+` silently dropped every character
    # outside ASCII letters, so a reply with an emoji, non-English word or
    # other script ("ok ❌ 不要", "okay \U0001F6D1") kept only its
    # ASCII words and could pass as a clean "yes". Splitting on whitespace and
    # requiring every token -- once its own leading/trailing ASCII
    # punctuation is stripped -- to be a recognised affirmative word means
    # anything unrecognised (another language, an emoji, a symbol) refuses
    # consent instead of being silently ignored.
    tokens = [t.strip(string.punctuation) for t in raw_text.casefold().split()]
    tokens = [t for t in tokens if t]
    if not tokens or not all(t in _CONSENT_TOKENS and re.fullmatch(r"[a-z']+", t) for t in tokens):
        return False
    if set(tokens) & _CONSENT_ANCHORS:
        return True
    pairs = set(zip(tokens, tokens[1:]))
    return bool({("go", "ahead"), ("do", "it"), ("run", "it"), ("send", "it")} & pairs)

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
    partial_record: str | None = None


class OfficeSession:
    def __init__(self, *, log, sources, recorder, retriever, edge, scratch_root, user_id, run_store,
                harness_runner=None, adapter=None, service=None):
        self.log, self.sources, self.recorder, self.retriever, self.edge = log, sources, recorder, retriever, edge
        self.scratch_root, self.user_id, self.run_store = scratch_root, user_id, run_store
        self.harness_runner, self.adapter = harness_runner, adapter
        self.service = service or BindingService()
        self._heads: dict[str, str] = {}
        self._pending: dict[str, dict] = {}          # task_id -> {ref_key: RoleBinding}
        self._escalation: dict[str, object] = {}      # task_id -> EscalationRequest awaiting consent
        self._escalation_warnings: dict[str, tuple] = {}  # task_id -> warnings carried from the proposal (M39-5)
        self._run: dict[str, tuple] = {}              # task_id -> (run_id, source)

    # -- request -> bind -------------------------------------------------------
    def start(self, raw_text, *, session_id, turn_id, trace_id, parsed) -> StepResult:
        """`parsed` is a `uri_v1.office.request.ParsedRequest` with `ok=True`."""
        if not getattr(parsed, "ok", False) or not parsed.spans:
            # Repair round 3: a refused parse (e.g. R2-3 ROLE_AMBIGUOUS) is a
            # typed answer, never a crash and never an opened task.
            return StepResult("UNSUPPORTED", reason=getattr(parsed, "reason", None) or "UNSUPPORTED_REQUEST",
                              role=getattr(parsed, "role", None))
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
        if target.ask:
            # R2-1 per-file question: the answer turn must be just the file
            # name; its span is grounded and bound by frozen M36 like any
            # request. Anything else is asked again, never guessed.
            span = answer_filename_span(raw_text, target.ref_key)
            if span is None:
                pending[target.ref_key] = ask_role(target.ref_key, reason="ANSWER_NOT_A_FILE_NAME")
                return StepResult("CLARIFY", task_id=task_id, roles=dict(pending))
            answer_intake = INTAKE.capture(self.user_id, session_id, turn_id, trace_id, raw_text,
                                           spans={target.ref_key: span})
            rb = answer_ask(self.retriever, self.sources, self.service, target, answer_intake)
        else:
            answer_intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, round_id=round_id,
                                         ref_key=target.ref_key)
            rb = answer_role(self.service, self.sources, target, answer_intake)
        pending[target.ref_key] = rb
        still_pending = [x for x in pending.values() if x.state != "CONFIRMED"]
        if still_pending:
            return StepResult("CLARIFY", task_id=task_id, roles=dict(pending))
        return self._bind_complete(task_id, answer_intake, pending)

    def _advance_binding(self, task_id, intake) -> StepResult:
        # task_id is intentionally NOT passed to bind_role: a brand-new task has
        # no prior references yet, and uri_v1/memory/retrieval.py's registry
        # fallback (deictic/type-word phrases like "the spreadsheet") is only
        # reached when the query is *not* task-scoped -- scoping it here would
        # silently return zero candidates for every phrase reference.
        bindings = with_asks({role: bind_role(self.retriever, self.sources, self.service, intake, role) for role in ROLES})
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
            self._escalation_warnings[task_id] = warnings
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
        if not _is_consent(raw_text):
            # M39-7: a decline (or anything that is not a clean "yes") must
            # not leave the proposal stuck pending forever -- the caller is
            # free to answer again or start something new.
            del self._escalation[task_id]
            self._escalation_warnings.pop(task_id, None)
            return StepResult("ESCALATION_DECLINED", task_id=task_id)
        if self.adapter is None or self.harness_runner is None:
            return StepResult("HARNESS_UNAVAILABLE", task_id=task_id)
        probe = self.adapter.probe()
        if not probe.get("installed"):
            return StepResult("HARNESS_UNAVAILABLE", task_id=task_id)
        # M39-2: record the explicit consent in Memory before the harness runs,
        # so the decision to escalate is itself durable and auditable.
        consent_note = self.recorder.task_state(task_id, self._heads[task_id], intake=consent_intake,
                                                next_step="harness escalation approved by explicit user consent")
        if not consent_note.persisted:
            return StepResult("ERROR", task_id=task_id, reason=consent_note.reason)
        self._heads[task_id] = consent_note.record_ids[-1]
        del self._escalation[task_id]
        warnings = self._escalation_warnings.pop(task_id, ())
        try:
            outcome = self.harness_runner.run(escalation, self.adapter, session_id=consent_intake.session_id,
                                              posture=PermissionProfile(), limits=Limits(max_budget_usd=1.0))
        except HarnessError:
            return StepResult("HARNESS_UNAVAILABLE", task_id=task_id)
        if outcome.verified:
            # M39-5: the "URI can only check that the script runs" warning
            # (and any other acceptance warning) must survive the harness
            # path too -- it was previously dropped here, so a neutered
            # harness "fix" could render as a plain "Verified." with no
            # caveat at all.
            return self._offer_writeback(task_id, outcome.run_id, warnings=warnings)
        return StepResult("HARNESS_FAILED", task_id=task_id, run_id=outcome.run_id,
                          verification_status=outcome.verification_status, safety_flags=outcome.safety_flags)

    def decline_escalation(self, task_id) -> StepResult:
        self._escalation.pop(task_id, None)
        self._escalation_warnings.pop(task_id, None)
        return StepResult("ESCALATION_DECLINED", task_id=task_id)

    # -- write-back --------------------------------------------------------------
    def approve_writeback(self, task_id, raw_text, *, run_id=None, relpaths=None, session_id, turn_id, trace_id) -> StepResult:
        # M39-4: only the run this session itself offered for approval can be
        # approved. Previously a caller-supplied `run_id` was trusted outright
        # (`run_id or self._run.get(task_id)`), so any run_id -- including one
        # this same session already reported as HARNESS_FAILED -- could be
        # written back if a caller (e.g. a future API) passed it explicitly.
        offered = self._run.get(task_id)
        if offered is None:
            return StepResult("ERROR", task_id=task_id, reason="NO_PENDING_RUN")
        if run_id is not None and run_id != offered:
            return StepResult("ERROR", task_id=task_id, reason="RUN_ID_NOT_OFFERED")
        run_id = offered
        approval_intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, ref_key="approval")
        try:
            outcome = do_writeback(recorder=self.recorder, sources=self.sources, run_store=self.run_store,
                                   user_id=self.user_id, scratch_root=self.scratch_root, task_id=task_id, run_id=run_id,
                                   expected_head_record_id=self._heads[task_id], session_id=approval_intake.session_id,
                                   trace_id=approval_intake.trace_id, approval_intake=approval_intake,
                                   relpaths=relpaths or ())
        except WritebackRefused as exc:
            return StepResult("WRITEBACK_REFUSED", task_id=task_id, reason=str(exc), written=exc.written,
                              partial_record=exc.partial_record)
        self._heads[task_id] = outcome.task_state_result.record_ids[-1]
        self._run.pop(task_id, None)
        return StepResult("COMPLETED", task_id=task_id, run_id=run_id, written=outcome.written)

    # -- cancel ---------------------------------------------------------------------
    def cancel(self, task_id, raw_text, *, session_id, turn_id, trace_id) -> StepResult:
        """Re-audit 3 F-4: let the user leave a task (e.g. one waiting on a
        file question) instead of being asked again forever.

        The task moves to ABANDONED only through frozen M36's explicit user
        transition, with the user's own words ("cancel", "abandon", ...); M36
        decides whether those words declare it. If M36 refuses, nothing
        changes and the reason is returned."""
        if task_id not in self._heads:
            return StepResult("ERROR", task_id=task_id, reason="UNKNOWN_TASK")
        intake = _make_intake(self.user_id, session_id, turn_id, trace_id, raw_text, ref_key="cancel")
        try:
            result = self.recorder.task_state(task_id, self._heads[task_id], intake=intake, status="ABANDONED")
        except ValueError as exc:
            return StepResult("ERROR", task_id=task_id, reason=str(exc))
        if not result.persisted:
            return StepResult("ERROR", task_id=task_id, reason=result.reason)
        self._heads[task_id] = result.record_ids[-1]
        for pending in (self._pending, self._escalation, self._escalation_warnings, self._run):
            pending.pop(task_id, None)
        return StepResult("CANCELLED", task_id=task_id)

    # -- pause / resume ------------------------------------------------------------
    def pause(self, task_id, raw_text, *, run_id, session_id, turn_id, trace_id) -> StepResult:
        # R1-A (re-audit, residual of M39-4): this used to store whatever
        # run_id the caller passed, with no check at all -- so any caller
        # (the Python API, not just the CLI) could re-arm ANY run, including
        # one this same session had already reported HARNESS_FAILED/flagged,
        # as the run offered for approval. `approve_writeback`'s "only the
        # offered run" check (M39-4) only holds if `pause()` cannot be used to
        # forge what "offered" means. So `pause()` now accepts only the run_id
        # this exact session already offered via `_offer_writeback` (the same
        # run `self._run[task_id]` already holds) -- it can re-affirm that
        # offer durably in Memory, never introduce a new one.
        offered = self._run.get(task_id)
        if offered is None or run_id != offered:
            return StepResult("ERROR", task_id=task_id, reason="RUN_ID_NOT_OFFERED")
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
