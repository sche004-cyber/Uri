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


def bind_all(retriever, sources, service, intake, *, task_id=None) -> dict:
    return {role: bind_role(retriever, sources, service, intake, role, task_id=task_id) for role in ROLES}
