"""Batch 3 Google catalogue, message evidence, and approval regressions."""

import base64
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("URI_EXTERNAL_CREDENTIAL_SECRET", "test-only-credential-secret")
os.environ.setdefault("URI_PROVIDER_KEY_SECRET", "test-only-provider-secret")

from uri_core.capabilities import MultiActionCapabilityRegistry, MultiActionExecutor
from uri_core.capabilities.gmail.capability import GmailCapability
from uri_core.core.capability_feasibility import CapabilityFeasibility
from uri_core.core.conversation_history import ConversationHistoryStore
from uri_core.core.decision_engine import build_turn_state_and_directory
from uri_core.core.orchestrator import UriOrchestrator
from uri_core.core.state import SessionManager


def test_google_availability_is_live_and_user_scoped(tmp_path, monkeypatch):
    from uri_core.core import capability_feasibility as module

    (tmp_path / "credentials.json").write_text("{}")
    alice = tmp_path / "alice.json"
    alice.write_text("{}")
    monkeypatch.setattr(module, "_repo_root", lambda: str(tmp_path))
    monkeypatch.setattr(module, "resolve_google_token_path", lambda user: str(tmp_path / f"{user}.json"))
    monkeypatch.setattr(module, "list_connection_status", lambda user_id=None: [
        {"id": name, "status": "connected" if user_id == "alice" else "needs_authorization", "detail": "Sign in"}
        for name in ("gmail", "drive")
    ])
    monkeypatch.setattr(module, "load_usable_credentials", lambda **kwargs: SimpleNamespace(has_scopes=lambda scopes: True))

    alice_state = CapabilityFeasibility(user_id="alice").snapshot()
    bob_state = CapabilityFeasibility(user_id="bob").snapshot()
    google_tools = (
        "gmail_search",
        "gmail_find_draft",
        "gmail_create_draft",
        "drive_search",
        "fetch_drive_spreadsheet",
        "drive_upload",
        "google_workspace_create",
    )
    assert all(alice_state[name]["usable"] for name in google_tools)
    assert all(alice_state[name]["gap_reason"] is None for name in google_tools)
    assert all(alice_state[name]["blocked_by"] == [] for name in google_tools)

    assert all(not bob_state[name]["usable"] for name in google_tools)
    assert all("Sign in with Google" in bob_state[name]["blocked_by"][0] for name in google_tools)
    assert all(bob_state[name]["gap_reason"] == "blocked_by_permission" for name in google_tools)

    assert alice_state["gmail_create_draft"]["requires_approval"]

    # When credentials.json is missing on the server host, report actionable reason
    (tmp_path / "credentials.json").unlink()
    no_creds_state = CapabilityFeasibility(user_id="alice").snapshot()
    assert all(not no_creds_state[name]["usable"] for name in google_tools)
    assert all("Configure credentials.json" in no_creds_state[name]["blocked_by"][0] for name in google_tools)


def test_unread_search_returns_bounded_plain_text_evidence_without_attachments():
    encoded = base64.urlsafe_b64encode(b"Please review the budget by Friday.").decode()
    client = MagicMock()
    client.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "m1"}],
        "nextPageToken": "more",
    }
    client.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "m1",
        "threadId": "t1",
        "snippet": "Please review",
        "payload": {
            "headers": [{"name": "Subject", "value": "Budget"}],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded}},
                {"mimeType": "application/pdf", "filename": "budget.pdf", "body": {"attachmentId": "a1"}},
            ],
        },
    }
    service = SimpleNamespace(service=client)
    capability = GmailCapability(service)
    result = capability.search_messages("is:unread", max_results=100)
    assert result["status"] == "success"
    assert result["messages"][0]["body"] == "Please review the budget by Friday."
    assert result["messages"][0]["message_id"] == "m1"
    assert result["limit"] == 20 and result["truncated"]
    client.users.return_value.messages.return_value.list.assert_called_once_with(
        userId="me", q="is:unread", maxResults=20
    )
    client.users.return_value.messages.return_value.attachments.assert_not_called()


def test_draft_requires_approval_and_never_sends():
    service = SimpleNamespace(service=None, drafts=[], get_connection_status=lambda: {"connected": True})
    service.create_draft = lambda **kwargs: service.drafts.append(kwargs) or {"success": True, "draft_id": "d1"}
    registry = MultiActionCapabilityRegistry([GmailCapability(service)])
    executor = MultiActionExecutor(registry, granted_permissions={"gmail.readonly"})
    args = {"to": "reader@example.test", "subject": "Re: Budget", "body": "I will review it."}

    # Executing mutating action without approval halts and does not draft
    assert executor.execute("Gmail", "create_draft", args)["status"] == "approval_required"
    assert service.drafts == []

    # Executing with approval succeeds and drafts, never sends
    assert executor.execute("Gmail", "create_draft", args, user_approved=True)["status"] == "success"
    assert service.drafts == [args]


def test_canonical_turn_recorded_and_visible_in_next_turn_state(tmp_path):
    # Isolated storage: never write test turns into the real workspace.
    history_store = ConversationHistoryStore(storage_dir=str(tmp_path / "history"))
    session_manager = SessionManager()
    session_id = "flutter-98765"
    session_manager.get_session(session_id)

    orchestrator = UriOrchestrator(
        conversation_history=history_store,
        session_manager=session_manager,
    )

    # First turn: canonical /ask returns an outcome with an error or narrative
    canonical_turn_result = {
        "status": "unavailable",
        "response": {"message": "Google credentials are missing on the host."},
        "error": "Google credentials are missing on the host.",
    }
    orchestrator._record_conversation_turn_safely(
        session_id=session_id,
        user_text="Summarize my unread emails",
        result=canonical_turn_result,
    )

    # Verify conversation history has the recorded turn with its response text
    turns = history_store.get_session(session_id)
    assert len(turns) == 1
    assert turns[0]["user_text"] == "Summarize my unread emails"
    assert turns[0]["response_text"] == "Google credentials are missing on the host."

    # Next turn: follow-up "How to fix this issue?" builds Turn State
    principal = SimpleNamespace(user_id="alice")
    turn_state_result, directory = build_turn_state_and_directory(
        orchestrator=orchestrator,
        session_id=session_id,
        user_text="How to fix this issue?",
        principal=principal,
    )

    recent = turn_state_result.data["recent_conversation"]
    assert len(recent) == 1
    assert recent[0]["user"] == "Summarize my unread emails"
    assert recent[0]["uri"] == "Google credentials are missing on the host."

    # Also verify orchestrator's conversation context window reflects this turn
    context_window = orchestrator._build_conversation_context(session_id)
    assert len(context_window) == 1
    assert context_window[0]["user"] == "Summarize my unread emails"
    assert context_window[0]["uri"] == "Google credentials are missing on the host."
