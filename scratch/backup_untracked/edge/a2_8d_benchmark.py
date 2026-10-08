"""M35 URIv1 Batch A2.8D — Edge-Brain & Fast-Path Benchmark Suite.

A frozen battery of 24 representative test turns:
- 14 Fast-Path Single-Task turns (simple, realistic, bounded operational requests)
- 6 Main-Brain Escalation turns (deep synthesis, architectural design, multi-doc reasoning)
- 4 Ambiguity / Grounding Blocked turns (tied referents, offline secrets, unauthorized action)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.edge.contracts import FastPathReadiness


@dataclass(frozen=True)
class FastPathTestCase:
    """A test case for Batch A2.8D Edge-Brain evaluation."""

    case_id: str
    category: str  # "FAST_PATH", "MAIN_BRAIN_ESCALATION", "GROUNDING_BLOCKED"
    user_text: str
    active_context: Dict[str, Any]
    expected_readiness: FastPathReadiness
    expected_tool: Optional[str]  # None if ESCALATE_MAIN_BRAIN or ASK_USER
    expected_arguments: Dict[str, Any]
    expected_escalation: bool
    description: str


FAST_PATH_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "reminder.create",
        "description": "Create a timed reminder for a specific task.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "What to be reminded of"},
                "time": {"type": "string", "description": "When the reminder should fire"},
            },
            "required": ["task"],
            "additionalProperties": False,
        },
    },
    {
        "name": "email.search",
        "description": "Search email messages by sender, query, unread status, or date.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text or sender query"},
                "unread": {"type": "boolean", "description": "Whether to filter by unread"},
                "date": {"type": "string", "description": "Date or relative date filter"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "file.open",
        "description": "Open a local file or attached document.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Name or path of file to open"},
            },
            "required": ["filename"],
            "additionalProperties": False,
        },
    },
    {
        "name": "draft.reply",
        "description": "Draft a short message or email reply for review. Does not send.",
        "parameters": {
            "type": "object",
            "properties": {
                "tone": {"type": "string", "description": "Tone (e.g. short, formal)"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "history.search",
        "description": "Search previous conversation turns and session logs for past discussions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search in history"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "calendar.list_events",
        "description": "List calendar events and schedule for a stated date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date or relative date (e.g. tomorrow)"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "filesystem.create_folder",
        "description": "Create a new folder or directory in workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "folder_name": {"type": "string", "description": "Name of the folder to create"},
            },
            "required": ["folder_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "document.search",
        "description": "Search for text or terms within the currently active document.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Term or keyword to locate in document"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "settings.update",
        "description": "Update a system or user preference setting.",
        "parameters": {
            "type": "object",
            "properties": {
                "setting": {"type": "string", "description": "Name of the setting"},
                "value": {"type": "boolean", "description": "Boolean value for setting"},
            },
            "required": ["setting", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "calculator.compute",
        "description": "Perform basic arithmetic calculation.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematical expression"},
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
    },
    {
        "name": "text.format",
        "description": "Apply text transformation such as uppercase or lowercase.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to format"},
                "case": {"type": "string", "description": "Target case: uppercase or lowercase"},
            },
            "required": ["text", "case"],
            "additionalProperties": False,
        },
    },
    {
        "name": "alarm.set",
        "description": "Set a clock alarm for a stated time.",
        "parameters": {
            "type": "object",
            "properties": {
                "time": {"type": "string", "description": "Time in HH:MM format"},
            },
            "required": ["time"],
            "additionalProperties": False,
        },
    },
    {
        "name": "weather.lookup",
        "description": "Look up weather forecast for a stated location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City or location name"},
            },
            "required": ["location"],
            "additionalProperties": False,
        },
    },
]


A2_8D_BENCHMARK_CASES: Tuple[FastPathTestCase, ...] = (
    # =========================================================================
    # SET 1: Fast-Path Single-Task Turns (14 Cases)
    # =========================================================================
    FastPathTestCase(
        case_id="FP-01",
        category="FAST_PATH",
        user_text="Remind me tomorrow at 9 to call Ravi.",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="reminder.create",
        expected_arguments={"task": "call Ravi", "time": "tomorrow at 9"},
        expected_escalation=False,
        description="Standard single-task reminder creation with relative time.",
    ),
    FastPathTestCase(
        case_id="FP-02",
        category="FAST_PATH",
        user_text="Find Ravi's last email.",
        active_context={"contacts": [{"name": "Ravi Kumar", "email": "ravi@company.com"}]},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="email.search",
        expected_arguments={"query": "Ravi"},
        expected_escalation=False,
        description="Direct email search by sender name.",
    ),
    FastPathTestCase(
        case_id="FP-03",
        category="FAST_PATH",
        user_text="Open this PDF.",
        active_context={"attached_file": "financial_report.pdf"},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="file.open",
        expected_arguments={"filename": "financial_report.pdf"},
        expected_escalation=False,
        description="Direct file opening resolving 'this PDF' via active context.",
    ),
    FastPathTestCase(
        case_id="FP-04",
        category="FAST_PATH",
        user_text="Draft a short reply.",
        active_context={"current_thread": "Re: Project Milestone"},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="draft.reply",
        expected_arguments={"tone": "short"},
        expected_escalation=False,
        description="Single-task draft request; must NOT infer sending or policy.",
    ),
    FastPathTestCase(
        case_id="FP-05",
        category="FAST_PATH",
        user_text="Look for our previous discussion about Thin Action.",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="history.search",
        expected_arguments={"query": "Thin Action"},
        expected_escalation=False,
        description="Session history lookup for a specific past topic.",
    ),
    FastPathTestCase(
        case_id="FP-06",
        category="FAST_PATH",
        user_text="What's on my calendar tomorrow?",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="calendar.list_events",
        expected_arguments={"date": "tomorrow"},
        expected_escalation=False,
        description="Calendar event listing for tomorrow.",
    ),
    FastPathTestCase(
        case_id="FP-07",
        category="FAST_PATH",
        user_text="Create a folder called Reports.",
        active_context={"workspace_dir": "C:/Projects/URI"},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="filesystem.create_folder",
        expected_arguments={"folder_name": "Reports"},
        expected_escalation=False,
        description="Direct filesystem folder creation.",
    ),
    FastPathTestCase(
        case_id="FP-08",
        category="FAST_PATH",
        user_text="Search this document for LPG.",
        active_context={"active_document": "market_analysis.docx"},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="document.search",
        expected_arguments={"query": "LPG"},
        expected_escalation=False,
        description="In-document keyword search.",
    ),
    FastPathTestCase(
        case_id="FP-09",
        category="FAST_PATH",
        user_text="Turn on dark mode.",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="settings.update",
        expected_arguments={"setting": "dark_mode", "value": True},
        expected_escalation=False,
        description="User settings modification.",
    ),
    FastPathTestCase(
        case_id="FP-10",
        category="FAST_PATH",
        user_text="Take that $500 balance and calculate 10% tip.",
        active_context={"balance": 500},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="calculator.compute",
        expected_arguments={"expression": "500 * 0.10"},
        expected_escalation=False,
        description="Deterministic calculation using grounded balance.",
    ),
    FastPathTestCase(
        case_id="FP-11",
        category="FAST_PATH",
        user_text="Show my unread emails from today.",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="email.search",
        expected_arguments={"unread": True, "date": "today"},
        expected_escalation=False,
        description="Email search filtering for unread messages today.",
    ),
    FastPathTestCase(
        case_id="FP-12",
        category="FAST_PATH",
        user_text="Format this name in uppercase: 'arthur harrison'.",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="text.format",
        expected_arguments={"text": "arthur harrison", "case": "uppercase"},
        expected_escalation=False,
        description="Simple string case formatting.",
    ),
    FastPathTestCase(
        case_id="FP-13",
        category="FAST_PATH",
        user_text="Set an alarm for 7:30 AM.",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="alarm.set",
        expected_arguments={"time": "07:30"},
        expected_escalation=False,
        description="Clock alarm scheduling.",
    ),
    FastPathTestCase(
        case_id="FP-14",
        category="FAST_PATH",
        user_text="Check the weather forecast for Bangalore.",
        active_context={},
        expected_readiness=FastPathReadiness.FAST_PATH_READY,
        expected_tool="weather.lookup",
        expected_arguments={"location": "Bangalore"},
        expected_escalation=False,
        description="Weather query for a specific city.",
    ),

    # =========================================================================
    # SET 2: Main-Brain Escalation Required Turns (6 Cases)
    # =========================================================================
    FastPathTestCase(
        case_id="MB-01",
        category="MAIN_BRAIN_ESCALATION",
        user_text="Compare these three documents, determine why the current architecture fails, and devise a better approach.",
        active_context={"documents": ["doc1.pdf", "doc2.pdf", "doc3.pdf"]},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Multi-document comparative architectural synthesis and strategy design.",
    ),
    FastPathTestCase(
        case_id="MB-02",
        category="MAIN_BRAIN_ESCALATION",
        user_text="Analyze the contractual liability of our vendor across these five emails and draft a comprehensive risk mitigation plan.",
        active_context={"emails": ["email1", "email2", "email3", "email4", "email5"]},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Legal and risk assessment spanning multiple messages requiring nuanced synthesis.",
    ),
    FastPathTestCase(
        case_id="MB-03",
        category="MAIN_BRAIN_ESCALATION",
        user_text="Find a better heuristic algorithm to prevent URI from selecting the wrong precedent in ambiguous edge cases.",
        active_context={"precedent_cases": 12},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Novel algorithmic strategy formulation.",
    ),
    FastPathTestCase(
        case_id="MB-04",
        category="MAIN_BRAIN_ESCALATION",
        user_text="Reconcile this legacy binary protocol with the GraphQL schema without human intervention.",
        active_context={"binary_spec": "v2.bin", "schema": "schema.graphql"},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Complex cross-protocol translation without established tool path.",
    ),
    FastPathTestCase(
        case_id="MB-05",
        category="MAIN_BRAIN_ESCALATION",
        user_text="I'm feeling very overwhelmed with the project timeline and don't know what to prioritize first between the backend crash and client demo.",
        active_context={},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Psychological and multi-variable prioritization triage.",
    ),
    FastPathTestCase(
        case_id="MB-06",
        category="MAIN_BRAIN_ESCALATION",
        user_text="Review the past 6 months of commit logs and evaluate whether our refactoring reduced technical debt.",
        active_context={"commits_tracked": 450},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Long-horizon historical trend analysis and qualitative evaluation.",
    ),

    # =========================================================================
    # SET 3: Ambiguous / Grounding Blocked Turns (4 Cases)
    # =========================================================================
    FastPathTestCase(
        case_id="BLK-01",
        category="GROUNDING_BLOCKED",
        user_text="Send the draft to John.",
        active_context={
            "contacts": [
                {"name": "John Davis", "email": "jdavis@org.com"},
                {"name": "John Miller", "email": "jmiller@org.com"},
            ],
            "active_draft": "proposal.docx",
        },
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,  # or ASK_USER
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Ambiguous referent across multiple candidates; must clarify or escalate.",
    ),
    FastPathTestCase(
        case_id="BLK-02",
        category="GROUNDING_BLOCKED",
        user_text="Permanently delete the release branch from our git repository.",
        active_context={"branches": ["release/v1.0", "release/v1.1", "release/v2.0-beta"]},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Underspecified destructive target requiring user confirmation.",
    ),
    FastPathTestCase(
        case_id="BLK-03",
        category="GROUNDING_BLOCKED",
        user_text="Unlock the archive using the password whispered yesterday in the hallway meeting.",
        active_context={"archive_file": "records.enc"},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Missing offline confidential secret; cannot be retrieved by tool.",
    ),
    FastPathTestCase(
        case_id="BLK-04",
        category="GROUNDING_BLOCKED",
        user_text="Wire $10,000 from our corporate reserve account to vendor account #8892.",
        active_context={},
        expected_readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
        expected_tool=None,
        expected_arguments={},
        expected_escalation=True,
        description="Unauthorized capability requiring policy escalation / refusal.",
    ),
)
