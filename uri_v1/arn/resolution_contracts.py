"""URIv1 Batch A2.8C — Resolution-Path Discovery & Capability-Grounding Contracts.

Governing Principles:
1. "URI defines URI. Models provide replaceable cognitive capacity."
2. "Capability selection must be grounded in an understood resolution requirement
   rather than selected directly from surface user language."
3. "Not knowing an answer is NOT inherently a failure if URI has a reliable,
   grounded path to obtain it."
4. "URI must recognize when no external capability is needed (NO_TOOL), when
   user clarification is mandatory (ASK_USER), and when a problem requires
   exploratory strategy discovery (STRATEGY_DISCOVERY_REQUIRED)."
5. Neutral experimental terminology only: ResolutionRequirement, ResolutionPath,
   ResolutionStep, CapabilityRequirement, CapabilityMatch.
   (Terms like 'Resolution Engine', 'Planner', 'ARN 2.0' are NOT approved components).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


class ResolutionRequirementStatus(str, Enum):
    """Taxonomy of resolution requirement states."""

    ALREADY_GROUNDED = "ALREADY_GROUNDED"
    # Information/state is already known, present in active context, or deterministically computable.

    RESOLVABLE_VIA_PATH = "RESOLVABLE_VIA_PATH"
    # Information is currently unresolved, but a known, qualified, authorized retrieval/execution path exists.

    UNRESOLVABLE_AMBIGUITY = "UNRESOLVABLE_AMBIGUITY"
    # Information cannot be retrieved, reference is genuinely ambiguous across multiple candidates,
    # intent is underspecified, or capability is unauthorized/absent. Must ask user.

    UNQUALIFIED_STRATEGY = "UNQUALIFIED_STRATEGY"
    # Goal is understood and data may be present, but no qualified resolution path or tool
    # currently exists in URI. Requires strategy discovery.


class ResolutionStepType(str, Enum):
    """Categories of atomic steps in a resolution path."""

    DETERMINISTIC_COMPUTATION = "DETERMINISTIC_COMPUTATION"  # In-memory arithmetic, string transformation
    RETRIEVE_PRIVATE_COMMUNICATION = "RETRIEVE_PRIVATE_COMMUNICATION"  # Authorized email/message access
    SEARCH_PUBLIC_KNOWLEDGE = "SEARCH_PUBLIC_KNOWLEDGE"      # Public web / documentation lookup
    RETRIEVE_SESSION_HISTORY = "RETRIEVE_SESSION_HISTORY"    # Prior conversation / decision lookup
    INSPECT_LOCAL_DOCUMENT = "INSPECT_LOCAL_DOCUMENT"        # Local filesystem file read
    CHECK_SCHEDULE = "CHECK_SCHEDULE"                        # User calendar inspection
    EXECUTE_EXTERNAL_SYSTEM = "EXECUTE_EXTERNAL_SYSTEM"      # Third-party transaction/ERP submission
    REQUEST_USER_CLARIFICATION = "REQUEST_USER_CLARIFICATION"# Clarification / disambiguation request
    DISCOVER_NOVEL_STRATEGY = "DISCOVER_NOVEL_STRATEGY"      # Exploratory strategy formulation


class AvailableCapability(str, Enum):
    """Standardized catalog of available system capabilities and meta-destinations."""

    EMAIL_SEARCH_READ = "email_search_read"
    # Search and read user's private emails and authorized inboxes.

    WEB_SEARCH = "web_search"
    # Public web search engine for indexed online pages, papers, and public news.

    SESSION_HISTORY_SEARCH = "session_history_search"
    # Search prior conversation turns and session logs for past agreements/decisions.

    DOCUMENT_READER = "document_reader"
    # Read local documents, spreadsheets, and configuration files from local disk.

    CALENDAR_CHECK = "calendar_check"
    # Check user's calendar schedule, meetings, and availability.

    ORDER_SUBMISSION_SYSTEM = "order_submission_system"
    # Submit purchase/procurement orders to enterprise ERP. Requires pre-verified sign-off.

    PYTHON_REPL = "python_repl"
    # Isolated Python interpreter for ad-hoc script execution.

    NO_TOOL = "NO_TOOL"
    # Deterministic computation, string transformation, or state already grounded in active context.

    ASK_USER = "ASK_USER"
    # Mandatory user clarification for ambiguous referents, missing offline secrets, or unauthorized requests.

    STRATEGY_DISCOVERY_REQUIRED = "STRATEGY_DISCOVERY_REQUIRED"
    # Novel task requiring exploratory strategy formulation; no qualified automated tool exists.


CAPABILITY_DESCRIPTIONS: Dict[str, str] = {
    AvailableCapability.EMAIL_SEARCH_READ.value: (
        "Search and read user's private emails and messages in authorized mailboxes. "
        "Use for internal emails, colleague messages, Dean's correspondence, and private inbox notes."
    ),
    AvailableCapability.WEB_SEARCH.value: (
        "Public web search engine for open Internet pages, published scientific papers, and news. "
        "Use ONLY for public information; never for private internal emails or confidential records."
    ),
    AvailableCapability.SESSION_HISTORY_SEARCH.value: (
        "Search previous conversation turns and local session logs for past agreements, decisions, "
        "and architectural discussions from earlier URI sessions."
    ),
    AvailableCapability.DOCUMENT_READER.value: (
        "Read local files, configuration files (YAML, JSON), and documents on the local filesystem."
    ),
    AvailableCapability.CALENDAR_CHECK.value: (
        "Inspect user's calendar and schedule for availability, upcoming meetings, and dates."
    ),
    AvailableCapability.ORDER_SUBMISSION_SYSTEM.value: (
        "Submit purchase orders to procurement ERP. Requires verified written sign-off before submission."
    ),
    AvailableCapability.PYTHON_REPL.value: (
        "Isolated Python interpreter for ad-hoc script execution and numerical analysis."
    ),
    AvailableCapability.NO_TOOL.value: (
        "Deterministic computation (arithmetic, string casing, list formatting) or information already "
        "grounded in active context. No external capability needed."
    ),
    AvailableCapability.ASK_USER.value: (
        "Ask user for clarification when an entity is genuinely ambiguous between candidates, a required "
        "secret was delivered offline, or the requested action is unauthorized/outside system scope."
    ),
    AvailableCapability.STRATEGY_DISCOVERY_REQUIRED.value: (
        "Goal is understood but no qualified tool or execution path currently exists in URI. "
        "Requires exploratory strategy discovery."
    ),
}


@dataclass(frozen=True)
class ResolutionRequirement:
    """Represents what is unverified, missing, or required before progress can occur."""

    status: ResolutionRequirementStatus
    description: str
    is_grounded: bool = False
    evidence_span: Optional[str] = None


@dataclass(frozen=True)
class ResolutionStep:
    """An atomic operation in a proposed resolution sequence."""

    step_type: ResolutionStepType
    description: str
    target_object: Optional[str] = None
    preconditions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionPath:
    """A bounded sequence of steps designed to satisfy the resolution requirements."""

    path_exists: bool
    steps: Tuple[ResolutionStep, ...] = ()
    requires_user_clarification: bool = False
    requires_strategy_discovery: bool = False


@dataclass(frozen=True)
class CapabilityRequirement:
    """Abstract specification of the cognitive or system capability needed for a step."""

    functional_description: str
    required_scope: str  # e.g., "private_mailbox", "public_web", "deterministic_math", "user_interaction"
    is_external_capability: bool = True


@dataclass(frozen=True)
class CapabilityMatch:
    """Binding between an abstract capability requirement and an available capability."""

    selected_capability: AvailableCapability
    justification: str
    is_correct_match: bool = True
    distractor_avoided: Optional[str] = None
