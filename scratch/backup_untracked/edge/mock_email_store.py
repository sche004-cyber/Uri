"""M35 URIv1 Batch A2.8D Stage 1 — MockEmailStore.

A deterministic, fully in-memory mock of an email store for benchmark evaluation.
This MUST be used for all email test cases. No Gmail connector. No real network.
No side effects whatsoever.

All email operations return synthetic but realistic data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class MockEmail:
    """A synthetic email message."""

    message_id: str
    sender_name: str
    sender_email: str
    subject: str
    body_snippet: str
    date_str: str  # ISO 8601
    is_unread: bool
    thread_id: str
    has_attachment: bool = False


# -------------------------------------------------------------------------
# Synthetic email corpus — representative but entirely fictional
# -------------------------------------------------------------------------

_MOCK_EMAILS: List[MockEmail] = [
    MockEmail(
        message_id="msg-001",
        sender_name="Ravi Kumar",
        sender_email="ravi@company.com",
        subject="Re: Q3 Delivery Timeline",
        body_snippet="Hi, I've updated the milestone spreadsheet. Please review before Monday.",
        date_str="2026-09-22T14:30:00",
        is_unread=True,
        thread_id="thread-001",
    ),
    MockEmail(
        message_id="msg-002",
        sender_name="Ravi Kumar",
        sender_email="ravi@company.com",
        subject="Budget allocation for Module B",
        body_snippet="The budget figures are attached. Let me know if you need adjustments.",
        date_str="2026-09-20T09:15:00",
        is_unread=False,
        thread_id="thread-002",
    ),
    MockEmail(
        message_id="msg-003",
        sender_name="Sarah Chen",
        sender_email="sarah.chen@ops.com",
        subject="Infrastructure migration completed",
        body_snippet="All nodes have been migrated. Monitoring dashboards are live.",
        date_str="2026-09-23T08:00:00",
        is_unread=True,
        thread_id="thread-003",
    ),
    MockEmail(
        message_id="msg-004",
        sender_name="Nadia Petrov",
        sender_email="nadia@legal.com",
        subject="Contract renewal — vendor agreement",
        body_snippet="Please sign by Friday. Attached is the updated vendor contract.",
        date_str="2026-09-23T11:20:00",
        is_unread=True,
        thread_id="thread-004",
        has_attachment=True,
    ),
    MockEmail(
        message_id="msg-005",
        sender_name="Arjun Sharma",
        sender_email="arjun@design.io",
        subject="Sprint 22 — design review notes",
        body_snippet="Notes from today's design review are in the shared doc.",
        date_str="2026-09-23T09:45:00",
        is_unread=False,
        thread_id="thread-005",
    ),
    MockEmail(
        message_id="msg-006",
        sender_name="Team Alerts",
        sender_email="alerts@system.internal",
        subject="Deployment pipeline FAILED — build #4412",
        body_snippet="Build 4412 failed at the integration test stage. See logs.",
        date_str="2026-09-23T12:05:00",
        is_unread=True,
        thread_id="thread-006",
    ),
    MockEmail(
        message_id="msg-007",
        sender_name="Priya Nair",
        sender_email="priya.nair@client.com",
        subject="Meeting request — product roadmap",
        body_snippet="Can we schedule 30 minutes this week to review the roadmap?",
        date_str="2026-09-22T17:00:00",
        is_unread=True,
        thread_id="thread-007",
    ),
    MockEmail(
        message_id="msg-008",
        sender_name="Ravi Kumar",
        sender_email="ravi@company.com",
        subject="Follow-up: API gateway issue",
        body_snippet="I've reproduced the issue on my local setup. Attaching logs.",
        date_str="2026-09-18T10:30:00",
        is_unread=False,
        thread_id="thread-008",
    ),
]

_TODAY_STR = "2026-09-23"
_YESTERDAY_STR = "2026-09-22"


class MockEmailStore:
    """Deterministic in-memory email store for benchmark evaluation.

    Supports: search by query/sender, unread filter, date filter.
    All methods are synchronous and return predictable results.
    No external connections, no Gmail, no network.
    """

    def __init__(self) -> None:
        self._emails = list(_MOCK_EMAILS)

    def search(
        self,
        query: Optional[str] = None,
        unread: Optional[bool] = None,
        date: Optional[str] = None,
        sender: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search emails with optional filters. Returns dicts of matching emails."""
        results = list(self._emails)

        if unread is not None:
            results = [e for e in results if e.is_unread == unread]

        if date:
            date_lower = date.lower()
            if "today" in date_lower:
                results = [e for e in results if _TODAY_STR in e.date_str]
            elif "yesterday" in date_lower:
                results = [e for e in results if _YESTERDAY_STR in e.date_str]
            else:
                results = [e for e in results if date in e.date_str]

        if query:
            q = query.lower()
            results = [
                e for e in results
                if q in e.sender_name.lower()
                or q in e.sender_email.lower()
                or q in e.subject.lower()
                or q in e.body_snippet.lower()
            ]

        if sender:
            s = sender.lower()
            results = [
                e for e in results
                if s in e.sender_name.lower() or s in e.sender_email.lower()
            ]

        return [
            {
                "message_id": e.message_id,
                "from": e.sender_name,
                "email": e.sender_email,
                "subject": e.subject,
                "snippet": e.body_snippet,
                "date": e.date_str,
                "unread": e.is_unread,
                "has_attachment": e.has_attachment,
            }
            for e in results[:limit]
        ]

    def get_last_from(self, sender_name: str) -> Optional[Dict[str, Any]]:
        """Get the most recent email from a sender."""
        results = self.search(query=sender_name)
        if results:
            return max(results, key=lambda e: e["date"])
        return None

    def get_unread_today(self) -> List[Dict[str, Any]]:
        """Get all unread emails from today."""
        return self.search(unread=True, date="today")

    def draft_reply(self, message_id: str, tone: str = "short") -> Dict[str, Any]:
        """PROPOSAL ONLY: Generate a mock draft reply (does not send anything).

        Returns a draft proposal dict. This is a dry-run artifact only.
        """
        matching = [e for e in self._emails if e.message_id == message_id]
        if not matching:
            return {
                "status": "PROPOSAL",
                "message_id": message_id,
                "draft": f"[MOCK DRAFT — {tone}] Thank you for your message. I will review and respond shortly.",
                "sent": False,
            }
        email = matching[0]
        return {
            "status": "PROPOSAL",
            "message_id": message_id,
            "to": email.sender_email,
            "subject": f"Re: {email.subject}",
            "draft": f"[MOCK DRAFT — {tone}] Thank you for your message regarding '{email.subject}'. "
                     f"I will get back to you shortly.",
            "sent": False,  # NEVER sends; proposal only
        }
