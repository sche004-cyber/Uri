"""C5 request-scoped canonical preparation; no provider or private-store IO.

This is an independently testable composition seam, not a qualified complete
agent loop. The paired application keeps its pending-C5 response until the
provider/execution/feedback integration has passed its owning gates.
"""
from copy import deepcopy
from dataclasses import fields
from types import SimpleNamespace

from uri_core.client_contracts import CONTEXT_LIMIT, ReasoningSelection, canonical, public_projection
from uri_core.core.client_state_ports import StatePortError


class ReasoningUnavailable(ValueError):
    pass


class ReasoningSelectionPolicy:
    """Trusted composition metadata, never advertisements supplied by a model.

Rows are exact (kind, provider, model) tuples. Even declared fallback lists
are not acted upon by this layer; caller must explicitly select a source.
"""
    def __init__(self, supported=()):
        self.supported = frozenset(supported)

    def require(self, selection):
        selection = ReasoningSelection.model_validate(selection)
        if (selection.kind, selection.provider, selection.model) not in self.supported:
            code = {"server_local_model": "SELECTED_MODEL_UNAVAILABLE",
                    "client_cloud_model": "CLIENT_PROVIDER_UNAVAILABLE",
                    "client_external_harness": "ADAPTER_NOT_QUALIFIED"}[selection.kind]
            raise ReasoningUnavailable(code)
        return selection


class _SnapshotHistory:
    def __init__(self, history):
        self.history = history

    def get_session(self, session_id):
        return deepcopy(self.history)


def prepare_canonical_context(ports, request, principal, descriptors, qualified_capabilities=()):
    """Reuse Turn State, directory, Graphify and decision request construction.

Read mandatory ports BEFORE invoking forgiving legacy projection helpers:
they must not turn a missing private read into empty ambient/default state.
Descriptors must already be intersected through the existing resolver.
Availability/advertisement is never an execution grant.
"""
    if principal.user_id != request.principal_id:
        raise StatePortError("PRINCIPAL_SCOPE")
    # Prevent a caller accidentally reusing another turn's otherwise valid ports.
    if any(getattr(ports.binding, k) != getattr(request, k) for k in
           ("server_id", "client_id", "principal_id", "session_id")):
        raise StatePortError("CONTEXT_SCOPE")
    data = ports.read("sessions", "get_session", request.session_id)
    history = ports.read("history", "get_session", request.session_id)
    from uri_core.core.state import SessionState, SessionManager
    session = None
    if data is not None:
        if not isinstance(data, dict) or data.get("session_id") != request.session_id or set(data) - {f.name for f in fields(SessionState)}:
            raise StatePortError("SESSION_PROJECTION_INVALID")
        session = SessionState(**deepcopy(data))
        # Pure existing codecs only: no SessionManager constructor/store.
        codec = SessionManager.__new__(SessionManager)
        for name in ("current_facts", "evidence_facts", "historical_facts"):
            setattr(session, name, codec._deserialize_fact_collection(getattr(session, name)))
        session.fact_history = codec._deserialize_fact_history(session.fact_history)
    if not isinstance(history, list) or any(not isinstance(t, dict) for t in history):
        raise StatePortError("HISTORY_PROJECTION_INVALID")

    from uri_core.core.capability_feasibility import _feasibility_entry
    from uri_core.core.capability_directory import CapabilityDirectory
    from uri_core.core.graphify_index import build_index
    from uri_core.core.turn_state import assemble_turn_state
    from uri_core.core.decision_engine import build_decision_request, graphify_hint_enabled, preselect_candidate_ids

    known = {}
    qualified = set(qualified_capabilities)
    for descriptor in descriptors:
        entry = _feasibility_entry(descriptor, {})
        # Without a qualified client execution/connection port, catalogue
        # existence is honest but availability must not be inferred.
        if descriptor.id not in qualified:
            entry.update(usable=False, gap_reason="client_execution_not_qualified")
        elif descriptor.is_executable and not entry["blocked_by"]:
            # The qualified paired client is the executor; the SERVER runtime's own availability
            # (e.g. external_harness_task is unavailable_on_runtime) does not describe it. Grants,
            # approval, ticket and client-side harness qualification still decide actual use.
            entry.update(usable=True, gap_reason=None)
        known[descriptor.id] = entry
    directory = CapabilityDirectory(capability_feasibility=SimpleNamespace(snapshot=lambda: deepcopy(known)),
                                    include_procedures=False)
    index = build_index(capability_directory=directory)
    # GRF-P0-1: same hint rule as the canonical path (decision_engine): GRAPHIFY_HINT_ENABLED killswitch, only
    # skill/memory_pointer orientation records (capabilities already reach the Brain through the directory), and a
    # failing index gives no hint rather than an error.
    hint = None
    if graphify_hint_enabled():
        try:
            hint = [r for r in index.relevant_subset(request.text, limit=5)
                    if r.get("kind") in ("skill", "memory_pointer")] or None
        except Exception:
            hint = None
    selection = request.reasoning
    result = assemble_turn_state(user_text=request.text, session_id=request.session_id,
        principal=principal, session=session, conversation_history_store=_SnapshotHistory(history),
        capability_directory=directory, capability_index_hint=hint,
        active_provider_id=selection.provider, active_model=selection.model)
    ids = preselect_candidate_ids(result.data, directory)
    envelope = build_decision_request(result.data, preselected_ids=ids, capability_directory=directory)
    public_projection(envelope)
    if len(canonical(envelope)) > CONTEXT_LIMIT:
        raise StatePortError("CONTEXT_LIMIT")
    return {"request": envelope, "turn_state": result, "directory": directory,
            "graphify": index, "selection": selection.model_dump()}


def validate_canonical_proposal(prepared, proposal, principal, permission_checker):
    """Untrusted proposals reuse existing validation and deterministic gates.

No READY result in this helper can dispatch anything. A qualified owning
composition still needs private approval, ticket, execution and feedback.
"""
    public_projection(proposal)
    if len(canonical(proposal)) > CONTEXT_LIMIT:
        raise StatePortError("PROPOSAL_LIMIT")
    from uri_core.core.decision_engine import _validate_contract
    from uri_core.core.decision_gates import evaluate_gates
    directory = prepared["directory"]
    ids = {r["capability_id"] for r in directory.summaries()}
    decision = _validate_contract(proposal, ids, directory)
    return evaluate_gates(decision, capability_directory=directory, principal=principal,
                          permission_checker=permission_checker, turn_state_data=prepared["turn_state"].data)


def prepare_for_paired_client(service, request, identity, qualified_capabilities=()):
    """Composition entrypoint: enforce binding and real grant intersection."""
    from uri_core.client_contracts import Binding
    from uri_core.core.capability_resolver import CapabilityResolver
    from uri_core.core.client_service import ExplicitGrants
    from uri_core.core.client_state_ports import ClientStatePorts
    service.check_binding(request, identity)
    binding = Binding(**{k: getattr(request, k) for k in ("server_id", "client_id", "principal_id", "session_id")})
    ports = ClientStatePorts(request.snapshot, binding.model_dump())
    descriptors = CapabilityResolver.resolve(identity.principal, service.registry, ExplicitGrants(service.pairings, identity))
    return prepare_canonical_context(ports, request, identity.principal, descriptors, qualified_capabilities)
