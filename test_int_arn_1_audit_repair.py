"""Focused, filesystem-free checks for the INT-ARN-1 audit repair."""

import json
import asyncio
import shutil
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import patch

from uri_core.core import decision_engine
from uri_core.core import canonical_execution
from uri_core.core.context_budget import estimate_tokens
from uri_core.core.canonical_execution import _reference_render_draft
from uri_core.app import server


class Directory:
    def summaries(self):
        return [{"capability_id": "Demo", "source": "multi_action",
                 "actions": ["open"]}]

    def describe(self, capability_id):
        return {"actions": ["open"], "action_schemas": {
            "open": {"description": "Open a file", "parameters": {
                "file_id": {"type": "string"}}}}}


def test_decision_contract_exposes_real_argument_and_accepts_brain_slot():
    assert "reference_slots is the only optional key" in decision_engine._REFERENCE_SLOT_PROMPT
    assert "exactly these keys" not in decision_engine.DECISION_CONTRACT_SYSTEM_PROMPT
    state = {"turn": {"user_text": "Open that document"},
             "recent_conversation": [], "active_pointer": {},
             "capability_summaries": Directory().summaries(),
             "session_facts": [], "attempt_history": []}
    proposal = {"goal": "Open a file", "mode": "single_action", "capability": "Demo",
                "actions": [{"name": "open", "inputs": {}}], "clarification": None,
                "unsupported_reason": None, "requires_approval": False,
                "confidence": "high", "reason": "file request",
                "reference_slots": [{"span": {"start": 5, "end": 18,
                                             "text": "that document"},
                                     "ref_key": "r1", "target": {
                                         "capability_id": "Demo", "action_name": "open",
                                         "argument_name": "file_id"},
                                     "relation": "direct", "source_class": "file"}]}
    with patch.dict("os.environ", {"URI_INT_ARN_1_ENABLED": "1"}), patch.object(
        decision_engine, "preselect_candidate_ids", return_value=["Demo"]
    ):
        request = decision_engine.build_decision_request(
            state, preselected_ids=["Demo"], capability_directory=Directory())
        assert request["capability_action_arguments"]["Demo"]["open"] == ["file_id"]
        outcome = decision_engine.propose_decision(
            turn_state_data=state, capability_directory=Directory(), preselect=True,
            model_callable=lambda _: json.dumps(proposal))
    assert outcome.status == "ok"
    assert outcome.contract["reference_slots"] == proposal["reference_slots"]


def test_reference_decision_prompt_stays_bounded_for_realistic_registry():
    class Registry:
        def summaries(self):
            return [{"capability_id": f"Capability{i}", "source": "multi_action"}
                    for i in range(5)]

        def describe(self, capability_id):
            return {"action_schemas": {
                f"action{j}": {"description": "Read or update a selected item",
                               "parameters": {f"argument{k}": {"type": "string"}
                                              for k in range(5)}}
                for j in range(6)}}

    registry = Registry()
    state = {"turn": {"user_text": "Summarize the sales report I uploaded"},
             "recent_conversation": [], "active_pointer": {},
             "capability_summaries": registry.summaries(),
             "session_facts": [], "attempt_history": []}
    with patch.dict("os.environ", {"URI_INT_ARN_1_ENABLED": "1"}):
        request = decision_engine.build_decision_request(
            state, preselected_ids=[entry["capability_id"] for entry in registry.summaries()],
            capability_directory=registry)
    with patch.dict("os.environ", {"URI_INT_ARN_1_ENABLED": "0"}):
        off_request = decision_engine.build_decision_request(
            state, preselected_ids=[entry["capability_id"] for entry in registry.summaries()],
            capability_directory=registry)
    prompt_tokens = estimate_tokens(decision_engine._REFERENCE_DECISION_PROMPT)
    request_tokens = estimate_tokens(json.dumps(request, ensure_ascii=False))
    off_tokens = (estimate_tokens(decision_engine._BASE_DECISION_PROMPT)
                  + estimate_tokens(json.dumps(off_request, ensure_ascii=False)))
    # 6,000 estimated input tokens leaves ample room in the live 16,384
    # context window for output and later turns. Five selected capabilities,
    # 30 actions, and 150 argument names are deliberately represented.
    assert prompt_tokens + request_tokens <= 6000
    assert prompt_tokens + request_tokens <= off_tokens + 500
    assert len(request["capability_action_arguments"]) == 5
    assert sum(len(actions) for actions in request["capability_action_arguments"].values()) == 30


def test_unreachable_brain_fails_closed_with_truthful_response():
    orchestrator = SimpleNamespace(process_user_input=lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("legacy execution must not run")))
    directory = Directory()
    with patch.dict("os.environ", {"URI_INT_ARN_1_ENABLED": "1"}), patch.object(
        canonical_execution, "build_turn_state_and_directory",
        return_value=(SimpleNamespace(data={"turn": {"user_text": "Summarize the sales report I uploaded"}}), directory)
    ), patch.object(canonical_execution, "propose_decision", return_value=decision_engine.DecisionOutcome(
        "unavailable", error="provider timeout"
    )), patch.object(canonical_execution, "record_canonical_telemetry") as telemetry, patch.object(
        canonical_execution, "_execute_canonical"
    ) as execute:
        result = canonical_execution.run_canonical_for_ask(
            orchestrator=orchestrator, session_id="test-unreachable",
            user_text="Summarize the sales report I uploaded", principal=None)
    assert result["status"] == "unavailable"
    assert result["execution"] == {"status": "not_executed", "reason": "BRAIN_UNAVAILABLE"}
    assert "couldn't reach the Brain" in result["response"]["message"]
    assert "clarify the reference" not in result["response"]["message"]
    execute.assert_not_called()
    telemetry.assert_not_called()
    route_block = canonical_execution._reference_block("test-unreachable", "CANONICAL_REFERENCE_ROUTE_UNAVAILABLE")
    assert route_block["status"] == "unavailable"
    assert "route is unavailable" in route_block["response"]["message"]


def test_render_call_is_bounded_and_budget_can_skip_it():
    contract = SimpleNamespace(kind=SimpleNamespace(value="CHOOSE_ONE"),
                               original_reference="that document", overflow_count=0)
    request = SimpleNamespace(kind=contract.kind, reference="that document",
                              slots=(("s1", (("title", "A"),)),), overflow=0)
    router = SimpleNamespace(attempt=lambda *args, **kwargs: SimpleNamespace(
        content='{"question":"Which file?","labels":{"s1":"A"}}'))
    with patch("uri_v1.reference_clarification.render_contracts.make_render_request",
               return_value=request), patch("uri_core.core.model_router.get_router",
                                           return_value=router):
        with patch.dict("os.environ", {"URI_INT_ARN_1_RENDER_BUDGET_MS": "800"}):
            assert "Which file?" in _reference_render_draft(contract, None)
        with patch.dict("os.environ", {"URI_INT_ARN_1_RENDER_BUDGET_MS": "0"}):
            assert _reference_render_draft(contract, None) is None


def test_first_streamed_reference_without_reserved_keys_uses_ask():
    payload = server.AskRequest(session_id="s1", text="Open that document")
    called = []

    def canonical_ask(request, **kwargs):
        called.append(request.text)
        return {"status": "awaiting_user_response", "clarification": {
            "question": "Which document?"}}

    async def run():
        with patch.dict("os.environ", {"URI_INT_ARN_1_ENABLED": "1"}), patch.object(
            server, "_resolve_ask_context", return_value=(SimpleNamespace(), None, None)
        ), patch.object(server, "_current_turn_attachment_references", return_value=[]), patch.object(
            server, "ask", side_effect=canonical_ask
        ), patch.object(server, "_ask_stream_eligible", side_effect=AssertionError("stream bypass")):
            response = await server.ask_stream(payload, None, user_id="user", _size_check=None)
            return "".join([chunk async for chunk in response.body_iterator])

    body = asyncio.run(run())
    assert called == ["Open that document"]
    assert "Which document?" in body


def test_history_projection_is_persisted_as_display_only():
    root = Path(".int-arn-test-work") / uuid4().hex
    path = root / "turns.json"

    class Store:
        def _path_for(self, session_id):
            return str(path)

        def _load_raw(self, session_id):
            return json.loads(path.read_text()) if path.exists() else {"turns": []}

        def _ensure_dir(self):
            root.mkdir(parents=True, exist_ok=True)

        def append_turn(self, **kwargs):
            self._ensure_dir()
            path.write_text(json.dumps({"turns": [{
                "turn_id": kwargs["turn_id"], "user_text": kwargs["user_text"]}]}))

    context = SimpleNamespace(orchestrator=SimpleNamespace(conversation_history=Store()))
    payload = SimpleNamespace(session_id="s1", text="Open that document")
    try:
        server._persist_reference_projection(context, payload, {
            "clarification": {"question": "Which document?", "options": []},
            "response": {"message": "Which document?"}})
        saved = json.loads(path.read_text())["turns"][0]
        assert saved["status"] == "awaiting_clarification"
        assert saved["clarification"]["question"] == "Which document?"
        assert "binding_identity" not in saved
    finally:
        if root.exists():
            shutil.rmtree(root)
