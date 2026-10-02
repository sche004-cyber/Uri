"""Batch 3 Google catalogue, message evidence, and approval regressions."""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

from uri_core.capabilities import MultiActionCapabilityRegistry, MultiActionExecutor
from uri_core.capabilities.gmail.capability import GmailCapability
from uri_core.core.capability_feasibility import CapabilityFeasibility


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
    google_tools = ("gmail_search", "gmail_find_draft", "gmail_create_draft", "drive_search",
                    "fetch_drive_spreadsheet", "drive_upload", "google_workspace_create")
    assert all(alice_state[name]["usable"] for name in google_tools)
    assert all(not bob_state[name]["usable"] for name in google_tools)
    assert all("Sign in with Google" in bob_state[name]["blocked_by"][0] for name in google_tools)
    assert alice_state["gmail_create_draft"]["requires_approval"]


def test_unread_search_returns_bounded_plain_text_evidence_without_attachments():
    encoded = base64.urlsafe_b64encode(b"Please review the budget by Friday.").decode()
    client = MagicMock()
    client.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "m1"}], "nextPageToken": "more"
    }
    client.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "m1", "threadId": "t1", "snippet": "Please review", "payload": {
            "headers": [{"name": "Subject", "value": "Budget"}], "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded}},
                {"mimeType": "application/pdf", "filename": "budget.pdf", "body": {"attachmentId": "a1"}},
            ]}}
    service = SimpleNamespace(service=client)
    capability = GmailCapability(service)
    result = capability.search_messages("is:unread", max_results=100)
    assert result["status"] == "success"
    assert result["messages"][0]["body"] == "Please review the budget by Friday."
    assert result["messages"][0]["message_id"] == "m1"
    assert result["limit"] == 20 and result["truncated"]
    client.users.return_value.messages.return_value.list.assert_called_once_with(
        userId="me", q="is:unread", maxResults=20)
    client.users.return_value.messages.return_value.attachments.assert_not_called()


def test_draft_requires_approval_and_never_sends():
    service = SimpleNamespace(service=None, drafts=[], get_connection_status=lambda: {"connected": True})
    service.create_draft = lambda **kwargs: service.drafts.append(kwargs) or {"success": True, "draft_id": "d1"}
    registry = MultiActionCapabilityRegistry([GmailCapability(service)])
    executor = MultiActionExecutor(registry, granted_permissions={"gmail.readonly"})
    args = {"to": "reader@example.test", "subject": "Re: Budget", "body": "I will review it."}
    assert executor.execute("Gmail", "create_draft", args)["status"] == "approval_required"
    assert service.drafts == []
    assert executor.execute("Gmail", "create_draft", args, user_approved=True)["status"] == "success"
    assert service.drafts == [args]
