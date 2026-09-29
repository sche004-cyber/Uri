"""Bind the two request roles (script, workbook) to hash-bound originals (M39 §4.2 binding.py).

For each role: `MemoryQuery(ref_key=role)` -> `Retriever` -> `MemoryAdapter.project`
-> deterministic RAR -> `build_clarification` (`wrong_binding_impact="CONSEQUENTIAL"`)
-> `BindingService`. A role binds only on S1 `CONFIRMED`; anything else (a
clarification round, or a rejection) is returned as such -- never guessed.
`wrong_binding_impact="CONSEQUENTIAL"` structurally forbids `TENTATIVE`
(`uri_v1/reference_clarification/authority.py:tentative_eligible` requires
NONE/RECOVERABLE impact), so only CONFIRMED or a clarification round can
result.
"""
from __future__ import annotations

from dataclasses import dataclass
import uuid

from uri_v1.memory.contracts import MemoryQuery
from uri_v1.memory.uri_adapter.envelope import MemoryAdapter
from uri_v1.memory.uri_adapter.links import capture_binding
from uri_v1.reference_clarification.binding import BindingService
from uri_v1.reference_clarification.builder import build_clarification
from uri_v1.turn.rar_clarification_contract import BindingState
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended

ROLES = ("script", "workbook")


def _state_value(state):
    return state.value if hasattr(state, "value") else str(state)


@dataclass(frozen=True)
class RoleBinding:
    ref_key: str
    state: str                      # BindingState value: CONFIRMED | PENDING | REJECTED | EXPIRED | ...
    bound: object | None = None     # BoundReference, only when state == "CONFIRMED"
    contract_id: str | None = None  # pending clarification round id, only when state == "PENDING"
    reason: str | None = None
    result: object | None = None    # RetrievalResult carried forward for a later free-input answer
    query: object | None = None     # frozen RARQuery carried forward for a later free-input answer
    ask: bool = False               # True: an M39-level per-file question (contract_id is an office round id)


# Re-audit R2-1 (repair round 3). Frozen M36 only grants exact-filename
# certainty when every other word of the trusted turn is plainly affirmative
# (uri_v1/memory/uri_adapter/envelope.py `affirmative_around`). A request
# naming both files ("make report.py work with sales.xlsx") therefore never
# binds either role in one turn: each role's context contains the other
# filename. That rejection opens no Memory clarification round, so it used to
# be a dead end. M39 now turns exactly that rejection into its own per-file
# question ("Which file is the script?"), answered in a fresh trusted turn
# that holds only the file name -- which frozen M36 grounds and binds on its
# own terms. No frozen code changes, and no binding certainty is invented:
# the answer turn is bound by the same M36/RAR path as any request.
ASK_REASON = "NON_AFFIRMATIVE_CONTEXT"
ASK_PREFIX = "office-ask-"
ROLE_EXTENSIONS = {"script": (".py",), "workbook": (".xlsx", ".xlsm")}
_ANSWER_QUOTES = "\"'“”‘’`"


def needs_ask(rb: RoleBinding) -> bool:
    """A role that failed only on frozen M36's affirmative-context rule and
    has no Memory round to continue."""
    return rb.state != "CONFIRMED" and not rb.contract_id and rb.reason == ASK_REASON


def ask_role(ref_key, reason=ASK_REASON) -> RoleBinding:
    return RoleBinding(ref_key, "PENDING", contract_id=ASK_PREFIX + uuid.uuid4().hex, reason=reason, ask=True)


def with_asks(bindings: dict) -> dict:
    return {role: (ask_role(role) if needs_ask(rb) else rb) for role, rb in bindings.items()}


def answer_filename_span(raw_text, ref_key):
    """Span of the file name in a per-file answer, or None.

    The answer must be just one file name of the role's type: optional
    surrounding whitespace and quotes, and an optional sentence-final "."
    or "!" -- nothing else. Anything more is re-asked, never guessed."""
    a, b = 0, len(raw_text)
    while a < b and raw_text[a].isspace():
        a += 1
    while b > a and raw_text[b - 1].isspace():
        b -= 1
    if b > a and raw_text[b - 1] in ".!":
        b -= 1
    if b - a >= 2 and raw_text[a] in _ANSWER_QUOTES and raw_text[b - 1] in _ANSWER_QUOTES:
        a, b = a + 1, b - 1
    name = raw_text[a:b]
    if not name or name != name.strip() or any(q in name for q in _ANSWER_QUOTES):
        return None
    if not name.casefold().endswith(ROLE_EXTENSIONS[ref_key]):
        return None
    if len(name) <= max(len(x) for x in ROLE_EXTENSIONS[ref_key]):
        return None
    return a, b


def bind_role(retriever, sources, service: BindingService, intake, ref_key, *,
              task_id=None, wrong_binding_impact="CONSEQUENTIAL") -> RoleBinding:
    spans = {key: (a, b) for key, a, b in intake.spans}
    if ref_key not in spans:
        return RoleBinding(ref_key, "REJECTED", reason="NO_REQUEST_SPAN")
    a, b = spans[ref_key]
    expression = intake.raw_text[a:b]
    query = MemoryQuery(user_id=intake.user_id, session_id=intake.session_id, reference_expression=expression,
                        ref_key=ref_key, intake=intake, task_id=task_id)
    result = retriever.retrieve(query)
    adapter = MemoryAdapter(sources)
    projection = adapter.project(result, slot_count=2, distinct_files=True)
    if projection.query is None:
        return RoleBinding(ref_key, "REJECTED", reason=projection.degraded or "EXPRESSION_GROUNDING_UNESTABLISHED")
    resolution = resolve_rar_deterministic_extended(projection.query).resolution
    built = build_clarification(projection.query, resolution, session_id=intake.session_id, turn_id=intake.turn_id,
                                wrong_binding_impact=wrong_binding_impact)
    outcome = adapter.register(service, built, result, projection.query)
    if outcome.state == BindingState.CONFIRMED:
        bound = capture_binding(service, outcome, result, sources, ref_key)
        return RoleBinding(ref_key, _state_value(outcome.state), bound=bound)
    if outcome.next_contract_id:
        return RoleBinding(ref_key, _state_value(outcome.state), contract_id=outcome.next_contract_id,
                           reason=outcome.reason, result=result, query=projection.query)
    return RoleBinding(ref_key, _state_value(outcome.state), reason=outcome.reason)


def answer_role(service: BindingService, sources, pending: RoleBinding, answer_intake, *,
                wrong_binding_impact="CONSEQUENTIAL") -> RoleBinding:
    """Continue a pending clarification round with a trusted free-input answer."""
    if pending.contract_id is None or pending.result is None or pending.query is None:
        return RoleBinding(pending.ref_key, "REJECTED", reason="NO_PENDING_ROUND")
    adapter = MemoryAdapter(sources)
    outcome = adapter.respond_free_input(service, pending.result, pending.query, pending.contract_id, answer_intake,
                                         wrong_binding_impact=wrong_binding_impact)
    if outcome.state == BindingState.CONFIRMED:
        bound = capture_binding(service, outcome, pending.result, sources, pending.ref_key)
        return RoleBinding(pending.ref_key, _state_value(outcome.state), bound=bound)
    if outcome.next_contract_id:
        return RoleBinding(pending.ref_key, _state_value(outcome.state), contract_id=outcome.next_contract_id,
                           reason=outcome.reason, result=pending.result, query=pending.query)
    return RoleBinding(pending.ref_key, _state_value(outcome.state), reason=outcome.reason)


def answer_ask(retriever, sources, service: BindingService, pending: RoleBinding, answer_intake, *,
               wrong_binding_impact="CONSEQUENTIAL") -> RoleBinding:
    """Bind a role from a per-file answer turn (see `ASK_REASON`).

    `answer_intake` must carry a span under the role's ref_key covering the
    file name (`answer_filename_span`). The answer is bound exactly like a
    request: M36 retrieval, RAR, `BindingService`. A second affirmative-
    context rejection is asked again; a Memory round (e.g. two files with
    that name) is returned for the normal clarification path."""
    rb = bind_role(retriever, sources, service, answer_intake, pending.ref_key,
                   wrong_binding_impact=wrong_binding_impact)
    if rb.state != "CONFIRMED" and not rb.contract_id:
        # No Memory round to continue (another affirmative-context rejection,
        # a name that matches no file, ...): ask again, carrying the reason.
        return ask_role(pending.ref_key, reason=rb.reason or ASK_REASON)
    return rb


def bind_all(retriever, sources, service, intake, *, task_id=None) -> dict:
    return {role: bind_role(retriever, sources, service, intake, role, task_id=task_id) for role in ROLES}
