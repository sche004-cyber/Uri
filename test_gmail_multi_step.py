"""Canonical Gmail multi-step execution with mocked Brain proposals."""

from types import SimpleNamespace
from unittest.mock import patch

from uri_core.capabilities import MultiActionCapabilityRegistry
from uri_core.capabilities.gmail import GmailCapability
from uri_core.core.capability_directory import CapabilityDirectory
from uri_core.core.canonical_execution import run_canonical_for_ask
from uri_core.core.decision_engine import DecisionOutcome
from uri_core.core.multi_action_dispatch import MultiActionDispatch
from uri_core.core.turn_state import _project_recent_conversation
from test_multi_action_capabilities import FakeGmailService


def _run(actions, service=None):
    service = service or FakeGmailService()
    registry = MultiActionCapabilityRegistry([GmailCapability(service)])
    dispatch = MultiActionDispatch(registry=registry, permission_checker=lambda *_: True)
    directory = CapabilityDirectory(multi_action_registry=registry)
    contract = {
        "goal": "Check my unread mail", "mode": "multi_action" if len(actions) > 1 else "single_action",
        "capability": "Gmail", "actions": actions,
        "clarification": None, "requires_approval": False,
    }
    class Brain:
        multi_action_dispatch = dispatch
        conversation_history = None
        session_manager = None
        capability_registry = None

        def __init__(self):
            self.drafted = None

        def _draft_narrative_safely(self, **kwargs):
            self.drafted = kwargs["response"]

        def _persist_session(self, *_):
            pass

    brain = Brain()
    with patch("uri_core.core.canonical_execution.build_turn_state_and_directory", return_value=(SimpleNamespace(data={}), directory)), \
         patch("uri_core.core.canonical_execution.propose_decision", return_value=DecisionOutcome(status="ok", contract=contract)), \
         patch("uri_core.core.canonical_execution.record_canonical_telemetry"):
        result = run_canonical_for_ask(
            orchestrator=brain, session_id="s1", user_text="check my unread email",
            principal=None,
        )
    return result, brain, service


def test_ready_read_prefix_returns_search_evidence_and_defers_later_steps():
    result, brain, service = _run([
        {"name": "search_messages", "inputs": {"query": "is:unread in:inbox", "max_results": 10}},
        {"name": "read_message", "inputs": {}},
        {"name": "create_draft", "inputs": {}},
    ])
    assert result["execution"]["partial_read_only"] is True
    assert result["plan"]["deferred_actions"] == [
        {"capability": "Gmail", "name": "read_message"},
        {"capability": "Gmail", "name": "create_draft"},
    ]
    assert result["response"]["messages"][0]["subject"] == "Insurance renewal"
    assert brain.drafted is not None
    assert service.drafts == []


def test_pure_missing_parameter_still_clarifies():
    result, _, service = _run([{"name": "read_message", "inputs": {}}])
    assert result["status"] == "awaiting_user_response"
    assert result["execution"]["status"] == "not_executed"
    assert service.drafts == []


def test_non_read_only_prefix_never_auto_executes():
    result, _, service = _run([
        {"name": "create_draft", "inputs": {"to": "a@example.test", "subject": "Re: note", "body": "Thanks"}},
        {"name": "read_message", "inputs": {}},
    ])
    assert result["execution"]["status"] == "not_executed"
    assert service.drafts == []


def test_complete_draft_still_requires_approval():
    result, _, service = _run([
        {"name": "create_draft", "inputs": {"to": "a@example.test", "subject": "Re: note", "body": "Thanks"}},
    ])
    assert result["execution"]["status"] == "awaiting_approval"
    assert service.drafts == []


def test_missing_query_cannot_be_supplied_by_prior_label_read():
    result, _, _ = _run([
        {"name": "list_labels", "inputs": {}},
        {"name": "search_messages", "inputs": {}},
    ])
    assert result["status"] == "awaiting_user_response"


def test_label_listing_cannot_supply_a_message_id():
    result, _, _ = _run([
        {"name": "list_labels", "inputs": {}},
        {"name": "read_message", "inputs": {}},
    ])
    assert result["execution"]["status"] == "not_executed"


def test_previous_narrative_is_available_to_followup_decision():
    history = SimpleNamespace(get_session=lambda _: [
        {"user_text": "Check unread emails", "response_text": "First: Insurance renewal from agent@example.test. Want a draft reply?"}
    ])
    assert "Insurance renewal" in _project_recent_conversation(history, "s1", 5)[0]["uri"]
