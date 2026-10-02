"""Regression checks for the INT-ARN-1 re-audit repairs."""

import time
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from uri_core.core import canonical_execution, decision_engine
from uri_core.app import server
from uri_v1.reference_clarification.binding import BindingService
from uri_v1.reference_clarification.store import BindingRecord, InMemoryClarificationStore
from uri_v1.turn.rar_clarification_contract import BindingState


def test_flag_off_uses_original_closed_key_prompt():
    captured = []

    def attempt(*args, **kwargs):
        captured.append(kwargs["system"])
        return SimpleNamespace(content="{}")

    directory = SimpleNamespace(summaries=lambda: [])
    with patch.object(decision_engine, "build_decision_request", return_value={}), patch.object(
            decision_engine, "get_router", return_value=SimpleNamespace(attempt=attempt)):
        with patch.dict("os.environ", {"URI_INT_ARN_1_ENABLED": "0"}):
            decision_engine.propose_decision(turn_state_data={}, capability_directory=directory)
        with patch.dict("os.environ", {"URI_INT_ARN_1_ENABLED": "1"}):
            decision_engine.propose_decision(turn_state_data={}, capability_directory=directory)
    assert "with exactly these keys:" in captured[0]
    assert "with these required keys:" in captured[1]
    assert "reference_slots is the only optional key" not in captured[0]
    assert "reference_slots is the only optional key" in captured[1]


def test_render_deadline_returns_template_fallback_on_slow_model():
    contract = SimpleNamespace(kind=SimpleNamespace(value="CHOOSE_ONE"),
                               original_reference="that document", overflow_count=0)
    request = SimpleNamespace(kind=contract.kind, reference="that document",
                              slots=(("s1", (("title", "A"),)),), overflow=0)

    def slow_attempt(*args, **kwargs):
        time.sleep(0.2)
        return SimpleNamespace(content='{"question":"Too late","labels":{"s1":"A"}}')

    with patch("uri_v1.reference_clarification.render_contracts.make_render_request",
               return_value=request), patch("uri_core.core.model_router.get_router",
                                           return_value=SimpleNamespace(attempt=slow_attempt)), patch.dict(
                                               "os.environ", {"URI_INT_ARN_1_RENDER_BUDGET_MS": "10"}):
        started = time.monotonic()
        assert canonical_execution._reference_render_draft(contract, None) is None
        assert time.monotonic() - started < 0.1


def test_frozen_change_lifecycle_separates_correction_and_redo():
    store = InMemoryClarificationStore()
    store.bindings["before"] = BindingRecord("before", "session", "a", BindingState.TENTATIVE, "fp")
    service = BindingService(store)
    assert store.bindings["before"].state == BindingState.TENTATIVE
    assert service.record_execution("before") == BindingState.TENTATIVE_APPLIED
    store.bindings["after"] = BindingRecord("after", "session", "b", BindingState.CONFIRMED,
                                            "fp2", from_change=True, prior_binding_id="before")
    assert service.authorize_redo("after", fresh_authorized=False,
                                  edited_result_status="UNKNOWN") == BindingState.REDO_NOT_EXECUTED


def test_successful_dispatch_records_applied_binding_but_unexecuted_does_not():
    store = InMemoryClarificationStore()
    store.bindings["bound"] = BindingRecord("bound", "session", "a", BindingState.TENTATIVE, "fp")

    class Journal:
        def __init__(self, **kwargs):
            pass

        @contextmanager
        def transaction(self, user_id, session_id):
            yield SimpleNamespace(store=store)

    contract = {"actions": [{"_binding_slots": [SimpleNamespace(round_id="bound")]}]}
    principal = SimpleNamespace(user_id="11111111-1111-4111-8111-111111111111")
    with patch("uri_desktop_seams.reference_clarification.store.ClarificationJournal", Journal):
        assert canonical_execution._reference_record_dispatch(
            contract, {"execution": {"status": "awaiting_approval"}}, principal, "session", None)
        assert store.bindings["bound"].state == BindingState.TENTATIVE
        assert canonical_execution._reference_record_dispatch(
            contract, {"execution": {"status": "success"}}, principal, "session", None)
        assert store.bindings["bound"].state == BindingState.TENTATIVE_APPLIED


def test_post_dispatch_record_failure_preserves_result_and_blocks_later_change():
    from uri_core.core.approval_resumption import resume_by_action_id

    binding_id = "record-failed"
    user_id = "11111111-1111-4111-8111-111111111111"
    principal = SimpleNamespace(user_id=user_id)
    slot = SimpleNamespace(round_id=binding_id)
    identity = SimpleNamespace(slots=(slot,))
    record = SimpleNamespace(session_id="session", action_name="open", capability_id="Demo",
                             arguments={}, requires_reference_binding=True,
                             binding_identity=identity)
    store = SimpleNamespace(get=lambda _: record, decide=lambda *args, **kwargs: record,
                            consume=lambda *args, **kwargs: None)
    gate = SimpleNamespace(approval_store=store, file_store=SimpleNamespace(
        storage_dir="uri_workspace/users/11111111-1111-4111-8111-111111111111/uploads"))
    dispatch = SimpleNamespace(dispatch_explicit=lambda *args, **kwargs: {
        "status": "success", "execution": {"status": "success"}})
    orchestrator = SimpleNamespace(approval_gate=gate, multi_action_dispatch=dispatch)
    with patch("uri_core.core.approval_resumption._recheck_binding", return_value=(slot,)), patch(
            "uri_core.core.canonical_execution._reference_record_dispatch", return_value=False):
        result = resume_by_action_id(orchestrator=orchestrator, action_id="action",
                                     session_id="session", approved=True, principal=principal)
    assert result["execution"]["status"] == "success"
    assert result["status"] == "success"

    contract = {"actions": [{"_binding_slots": [slot]}]}
    class MissingJournal:
        def __init__(self, **kwargs):
            pass

        @contextmanager
        def transaction(self, user_id, session_id):
            yield SimpleNamespace(store=InMemoryClarificationStore())

    with patch("uri_desktop_seams.reference_clarification.store.ClarificationJournal", MissingJournal), patch(
            "uri_core.core.canonical_execution._record_reference_stage"):
        assert not canonical_execution._reference_record_dispatch(
            contract, result, principal, "session", None)
    assert canonical_execution.reference_execution_record_failed(user_id, "session", binding_id)


def test_change_after_execution_never_repeats_dispatch_but_correction_can():
    from uri_desktop_seams.reference_clarification.proposal import ReferenceSlot
    from uri_v1.turn.rar_clarification_contract import ResponseKind

    slot = ReferenceSlot(0, 4, "that", "r1", "Demo", "open", "file_id", "direct", "file")
    metadata = json.dumps({"text": "Open that", "slot": vars(slot), "attachments": []})
    store = InMemoryClarificationStore()
    dispatched = []
    outcomes = []

    class Journal:
        def __init__(self, **kwargs):
            pass

        @contextmanager
        def transaction(self, user_id, session_id):
            yield SimpleNamespace(store=store)

    class Service:
        def __init__(self, journal):
            self.journal = journal

        def respond(self, **kwargs):
            return SimpleNamespace(status="BOUND", binding_id="after", contract=None, reason=None)

    action = SimpleNamespace()
    registry = SimpleNamespace(get_capability=lambda _: SimpleNamespace(get_action=lambda _: action))
    dispatch = SimpleNamespace(registry=registry, _action_permitted=lambda *args: True)
    context = SimpleNamespace(orchestrator=SimpleNamespace(multi_action_dispatch=dispatch))
    principal = SimpleNamespace(user_id="11111111-1111-4111-8111-111111111111")
    payload = SimpleNamespace(session_id="session", clarification_response={
        "ambiguity_id": "round", "response_kind": ResponseKind.CANDIDATE.value,
        "candidate_id": "b", "candidate_set_fingerprint": "fp"})
    pending = ("round", SimpleNamespace(), metadata)

    def run(**kwargs):
        dispatched.append(kwargs["user_text"])
        return {"status": "success", "execution": {"status": "success"}}

    with patch("uri_desktop_seams.reference_clarification.store.ClarificationJournal", Journal), patch(
            "uri_desktop_seams.reference_clarification.service.ReferenceClarificationService", Service), patch(
            "uri_core.core.canonical_execution.run_canonical_for_ask", side_effect=run):
        for applied in (False, True):
            store.bindings["after"] = BindingRecord("after", "session", "b", BindingState.CONFIRMED,
                "fp", from_change=applied, prior_binding_id="before")
            result = server._reference_ask_turn(context, principal, payload, pending, [])
            outcomes.append(result)
            assert (result.get("execution", {}).get("reason") ==
                    "REDO_REQUIRES_AUTHORIZATION_AND_RESULT_VERSION") == applied
        assert dispatched == ["Open that"], [item["execution"]["reason"] for item in outcomes]
        assert store.bindings["after"].state == BindingState.REDO_NOT_EXECUTED
