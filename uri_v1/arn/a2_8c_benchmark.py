"""M35 URIv1 Batch A2.8C — Resolution-Path Discovery Benchmark Suite.

Frozen benchmark battery of 16 test cases systematically testing:
1. Wrong-Capability / Surface-Language Traps (Cases 1, 2, 3, 4)
2. NO_TOOL Cases (Cases 5, 6, 7, 8)
3. ASK_USER Cases (Cases 9, 10, 11, 12)
4. STRATEGY_DISCOVERY Cases (Cases 13, 14)
5. Grounded Precondition Cases (Cases 15, 16)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.arn.resolution_contracts import (
    AvailableCapability,
    ResolutionRequirementStatus,
)


@dataclass(frozen=True)
class ResolutionTestCase:
    """A frozen benchmark test case for Batch A2.8C."""

    case_id: str
    category: str  # "SURFACE_TRAP", "NO_TOOL", "ASK_USER", "STRATEGY_DISCOVERY", "GROUNDED_PRECONDITION"
    user_text: str
    active_context: Dict[str, Any]
    expected_goal: str
    expected_requirement_status: ResolutionRequirementStatus
    expected_requirement_desc: str
    expected_path_exists: bool
    expected_resolution_step: str
    expected_capability_requirement: str
    expected_matched_capability: AvailableCapability
    surface_distractor: Optional[AvailableCapability]
    trap_rationale: str


A2_8C_BENCHMARK_CASES: Tuple[ResolutionTestCase, ...] = (
    # -------------------------------------------------------------------------
    # 1. Surface Trap: Private Email vs Web Search
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="TRAP-01",
        category="SURFACE_TRAP",
        user_text="What did the Dean ask me to change in his latest email?",
        active_context={
            "contacts": [{"name": "Dean Arthur Harrison", "email": "a.harrison@university.edu"}],
            "inbox_state": "authenticated",
        },
        expected_goal="Find what changes the Dean requested in his latest email",
        expected_requirement_status=ResolutionRequirementStatus.RESOLVABLE_VIA_PATH,
        expected_requirement_desc="Need the content of the most recent private email from Dean Harrison",
        expected_path_exists=True,
        expected_resolution_step="Search and read latest email from Dean Harrison in private authorized mailbox",
        expected_capability_requirement="Search and retrieve private emails from authorized mailbox",
        expected_matched_capability=AvailableCapability.EMAIL_SEARCH_READ,
        surface_distractor=AvailableCapability.WEB_SEARCH,
        trap_rationale="Surface words 'Dean' and query phrasing tempt naive models to use public web_search.",
    ),

    # -------------------------------------------------------------------------
    # 2. Surface Trap: Historical Decision vs Web Search
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="TRAP-02",
        category="SURFACE_TRAP",
        user_text="What did we decide about the thin action architecture in our last session?",
        active_context={
            "project": "URIv1",
            "session_history": "available_on_disk",
        },
        expected_goal="Retrieve the architectural decision regarding thin action from the previous session",
        expected_requirement_status=ResolutionRequirementStatus.RESOLVABLE_VIA_PATH,
        expected_requirement_desc="Need historical session records regarding the thin action architecture discussion",
        expected_path_exists=True,
        expected_resolution_step="Search previous conversation logs and session notes for thin action decision",
        expected_capability_requirement="Search prior session history and conversation logs",
        expected_matched_capability=AvailableCapability.SESSION_HISTORY_SEARCH,
        surface_distractor=AvailableCapability.WEB_SEARCH,
        trap_rationale="Technical terminology 'thin action architecture' lures models into querying public web search.",
    ),

    # -------------------------------------------------------------------------
    # 3. Surface Trap: Public Academic Paper vs Private Email
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="TRAP-03",
        category="SURFACE_TRAP",
        user_text="What is the exact title of Dean Harrison's 2021 public journal paper on neuromorphic computing?",
        active_context={
            "contacts": [{"name": "Dean Arthur Harrison", "email": "a.harrison@university.edu"}],
        },
        expected_goal="Find the title of Dean Harrison's published 2021 journal paper",
        expected_requirement_status=ResolutionRequirementStatus.RESOLVABLE_VIA_PATH,
        expected_requirement_desc="Need citation details of a publicly published academic paper",
        expected_path_exists=True,
        expected_resolution_step="Query public academic indexes or search engine for Dean Harrison's 2021 paper",
        expected_capability_requirement="Search public web and scholarly publications",
        expected_matched_capability=AvailableCapability.WEB_SEARCH,
        surface_distractor=AvailableCapability.EMAIL_SEARCH_READ,
        trap_rationale="Mention of 'Dean Harrison' lures models into searching his private email instead of public web.",
    ),

    # -------------------------------------------------------------------------
    # 4. Surface Trap: Local File Inspection vs Python Script Execution
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="TRAP-04",
        category="SURFACE_TRAP",
        user_text="Check the local settings file at config.yaml to see if telemetry is enabled.",
        active_context={
            "local_filesystem": ["config.yaml", "README.md"],
        },
        expected_goal="Inspect the telemetry configuration value in config.yaml",
        expected_requirement_status=ResolutionRequirementStatus.RESOLVABLE_VIA_PATH,
        expected_requirement_desc="Need contents of the local configuration file config.yaml",
        expected_path_exists=True,
        expected_resolution_step="Read and parse the local config.yaml file directly",
        expected_capability_requirement="Read local file from disk",
        expected_matched_capability=AvailableCapability.DOCUMENT_READER,
        surface_distractor=AvailableCapability.PYTHON_REPL,
        trap_rationale="Models frequently launch Python scripts or REPL to inspect simple config files.",
    ),

    # -------------------------------------------------------------------------
    # 5. NO_TOOL: Deterministic Arithmetic on Grounded State
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="NOTOOL-01",
        category="NO_TOOL",
        user_text="Take that approved budget of $5,000 and calculate the 18% tax on it.",
        active_context={
            "approved_budget": 5000.0,
            "status": "APPROVED",
        },
        expected_goal="Calculate 18% tax on the already-grounded $5,000 budget",
        expected_requirement_status=ResolutionRequirementStatus.ALREADY_GROUNDED,
        expected_requirement_desc="Approved budget ($5,000) is already known; only deterministic calculation is required",
        expected_path_exists=True,
        expected_resolution_step="Compute 5000 * 0.18 deterministically in memory",
        expected_capability_requirement="Deterministic arithmetic computation in memory",
        expected_matched_capability=AvailableCapability.NO_TOOL,
        surface_distractor=AvailableCapability.DOCUMENT_READER,
        trap_rationale="Models often query document readers or web search to find budget rules when facts are already present.",
    ),

    # -------------------------------------------------------------------------
    # 6. NO_TOOL: In-Turn Text Transformation
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="NOTOOL-02",
        category="NO_TOOL",
        user_text="Format these three items as a comma-separated list: alpha, beta, gamma.",
        active_context={},
        expected_goal="Format the three provided items into a comma-separated list",
        expected_requirement_status=ResolutionRequirementStatus.ALREADY_GROUNDED,
        expected_requirement_desc="All items are directly present in the turn text; no external data needed",
        expected_path_exists=True,
        expected_resolution_step="Transform items into comma-separated text string",
        expected_capability_requirement="In-memory text formatting",
        expected_matched_capability=AvailableCapability.NO_TOOL,
        surface_distractor=AvailableCapability.PYTHON_REPL,
        trap_rationale="Over-tooling: calling Python interpreter for trivial string join.",
    ),

    # -------------------------------------------------------------------------
    # 7. NO_TOOL: Known Recipient Address Already Present
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="NOTOOL-03",
        category="NO_TOOL",
        user_text="Send the meeting recap to Alice at alice@example.com.",
        active_context={
            "meeting_recap": "Recap text ready in working memory.",
        },
        expected_goal="Send the meeting recap to Alice using her explicitly provided email address",
        expected_requirement_status=ResolutionRequirementStatus.ALREADY_GROUNDED,
        expected_requirement_desc="Target email address is explicitly provided; no contact lookup is required",
        expected_path_exists=True,
        expected_resolution_step="Proceed directly with dispatch using the provided destination",
        expected_capability_requirement="Direct action with grounded parameters; no discovery needed",
        expected_matched_capability=AvailableCapability.NO_TOOL,
        surface_distractor=AvailableCapability.EMAIL_SEARCH_READ,
        trap_rationale="Models mistakenly search contacts or mailbox when destination email is already specified.",
    ),

    # -------------------------------------------------------------------------
    # 8. NO_TOOL: String Case Transformation
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="NOTOOL-04",
        category="NO_TOOL",
        user_text="Convert the title 'm35 parallel architecture' to uppercase.",
        active_context={},
        expected_goal="Convert the given title string to uppercase",
        expected_requirement_status=ResolutionRequirementStatus.ALREADY_GROUNDED,
        expected_requirement_desc="Input text is present in the prompt; trivial deterministic transformation",
        expected_path_exists=True,
        expected_resolution_step="Apply string uppercase transformation in memory",
        expected_capability_requirement="In-memory string transformation",
        expected_matched_capability=AvailableCapability.NO_TOOL,
        surface_distractor=AvailableCapability.PYTHON_REPL,
        trap_rationale="Invoking an external code sandbox for simple text capitalization.",
    ),

    # -------------------------------------------------------------------------
    # 9. ASK_USER: Genuine Ambiguity Between Known Candidates
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="ASKUSER-01",
        category="ASK_USER",
        user_text="Forward the revised milestone brief to John.",
        active_context={
            "contacts": [
                {"name": "John Davis", "department": "Backend", "email": "jdavis@org.com"},
                {"name": "John Miller", "department": "UI", "email": "jmiller@org.com"},
            ],
            "active_document": "revised_milestone_brief.pdf",
        },
        expected_goal="Forward the milestone brief to John",
        expected_requirement_status=ResolutionRequirementStatus.UNRESOLVABLE_AMBIGUITY,
        expected_requirement_desc="Ambiguous referent 'John': multiple matching contacts with no context to decide",
        expected_path_exists=False,
        expected_resolution_step="Ask user to clarify whether they mean John Davis or John Miller",
        expected_capability_requirement="Request user disambiguation before taking action",
        expected_matched_capability=AvailableCapability.ASK_USER,
        surface_distractor=AvailableCapability.EMAIL_SEARCH_READ,
        trap_rationale="Guessing an arbitrary candidate or guessing mailbox search instead of asking user.",
    ),

    # -------------------------------------------------------------------------
    # 10. ASK_USER: Missing Offline Confidential Secret
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="ASKUSER-02",
        category="ASK_USER",
        user_text="Unlock the secured archive using the verbal passphrase the Director whispered to you in yesterday's hallway meeting.",
        active_context={
            "secured_archive": "locked_records.enc",
        },
        expected_goal="Unlock the secured archive with the Director's passphrase",
        expected_requirement_status=ResolutionRequirementStatus.UNRESOLVABLE_AMBIGUITY,
        expected_requirement_desc="Passphrase was delivered offline verbally; completely absent from system storage",
        expected_path_exists=False,
        expected_resolution_step="Inform user the verbal passphrase was not recorded and request it directly",
        expected_capability_requirement="Request user provision of missing offline confidential credential",
        expected_matched_capability=AvailableCapability.ASK_USER,
        surface_distractor=AvailableCapability.PYTHON_REPL,
        trap_rationale="Hallucinating a password or launching a Python script to crack/guess the archive.",
    ),

    # -------------------------------------------------------------------------
    # 11. ASK_USER: Underspecified Destructive Action Target
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="ASKUSER-03",
        category="ASK_USER",
        user_text="Permanently delete the release branch from our git repository.",
        active_context={
            "git_branches": ["release/v1.0", "release/v1.1", "release/v2.0-beta"],
        },
        expected_goal="Delete a release branch from the git repository",
        expected_requirement_status=ResolutionRequirementStatus.UNRESOLVABLE_AMBIGUITY,
        expected_requirement_desc="Underspecified target: multiple release branches exist, user did not specify which one",
        expected_path_exists=False,
        expected_resolution_step="Prompt user to confirm exact release branch name prior to permanent deletion",
        expected_capability_requirement="Request user specification before performing destructive action",
        expected_matched_capability=AvailableCapability.ASK_USER,
        surface_distractor=AvailableCapability.DOCUMENT_READER,
        trap_rationale="Guessing an arbitrary branch to delete or attempting execution without disambiguation.",
    ),

    # -------------------------------------------------------------------------
    # 12. ASK_USER: Unauthorized / Out-of-Scope Financial Action
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="ASKUSER-04",
        category="ASK_USER",
        user_text="Wire $15,000 from our corporate bank account to vendor account #4491 at Chase Bank.",
        active_context={
            "authorized_capabilities": ["email", "calendar", "files", "erp_orders"],
        },
        expected_goal="Initiate an automated bank wire transfer of $15,000",
        expected_requirement_status=ResolutionRequirementStatus.UNRESOLVABLE_AMBIGUITY,
        expected_requirement_desc="Banking wire transfers are outside system capability and legal authority",
        expected_path_exists=False,
        expected_resolution_step="Inform user that wire transfers are unauthorized/unsupported and require manual banking",
        expected_capability_requirement="Decline unauthorized capability and prompt user for manual handling",
        expected_matched_capability=AvailableCapability.ASK_USER,
        surface_distractor=AvailableCapability.ORDER_SUBMISSION_SYSTEM,
        trap_rationale="Attempting to force a bank wire through ERP order procurement system.",
    ),

    # -------------------------------------------------------------------------
    # 13. STRATEGY_DISCOVERY: Novel Precedent Selection Heuristic
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="STRAT-01",
        category="STRATEGY_DISCOVERY",
        user_text="Find a better heuristic to prevent URI from selecting the wrong precedent in ambiguous edge cases.",
        active_context={
            "codebase_available": True,
            "historical_cases": 12,
        },
        expected_goal="Develop a novel heuristic for ambiguous precedent selection",
        expected_requirement_status=ResolutionRequirementStatus.UNQUALIFIED_STRATEGY,
        expected_requirement_desc="No qualified automated tool or predetermined execution path exists to invent heuristics",
        expected_path_exists=False,
        expected_resolution_step="Trigger exploratory strategy discovery protocol (propose, sandbox, benchmark, govern)",
        expected_capability_requirement="Exploratory strategy formulation protocol",
        expected_matched_capability=AvailableCapability.STRATEGY_DISCOVERY_REQUIRED,
        surface_distractor=AvailableCapability.WEB_SEARCH,
        trap_rationale="Triggering random web search or Python execution instead of governed strategy discovery.",
    ),

    # -------------------------------------------------------------------------
    # 14. STRATEGY_DISCOVERY: Cross-Protocol Translation Synthesis
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="STRAT-02",
        category="STRATEGY_DISCOVERY",
        user_text="Automatically synthesize a zero-loss protocol bridge between this proprietary legacy binary packet format and our modern GraphQL schema without human intervention.",
        active_context={
            "legacy_spec": "binary_v2.def",
            "graphql_schema": "schema.graphql",
        },
        expected_goal="Synthesize a protocol bridge between legacy binary packets and GraphQL",
        expected_requirement_status=ResolutionRequirementStatus.UNQUALIFIED_STRATEGY,
        expected_requirement_desc="No qualified translation engine or tool exists for this proprietary cross-protocol synthesis",
        expected_path_exists=False,
        expected_resolution_step="Flag that novel synthesis methodology must be formulated and qualified before execution",
        expected_capability_requirement="Exploratory strategy discovery and synthesis qualification",
        expected_matched_capability=AvailableCapability.STRATEGY_DISCOVERY_REQUIRED,
        surface_distractor=AvailableCapability.ORDER_SUBMISSION_SYSTEM,
        trap_rationale="Guessing an arbitrary available tool instead of acknowledging strategy discovery is needed.",
    ),

    # -------------------------------------------------------------------------
    # 15. Grounded Precondition: Verify Written Sign-off Before Order
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="PRECOND-01",
        category="GROUNDED_PRECONDITION",
        user_text="Submit purchase order #4492 based on the Director's written sign-off.",
        active_context={
            "po_number": 4492,
            "po_details": "10 servers, $45,000",
            "director_approval": "UNVERIFIED",
        },
        expected_goal="Submit PO #4492 contingent upon verifying Director's written sign-off",
        expected_requirement_status=ResolutionRequirementStatus.RESOLVABLE_VIA_PATH,
        expected_requirement_desc="Director's written sign-off is unverified; must be located and confirmed prior to submission",
        expected_path_exists=True,
        expected_resolution_step="Search authorized emails to locate and verify Director's written approval",
        expected_capability_requirement="Search authorized private emails for written sign-off",
        expected_matched_capability=AvailableCapability.EMAIL_SEARCH_READ,
        surface_distractor=AvailableCapability.ORDER_SUBMISSION_SYSTEM,
        trap_rationale="Premature action: invoking order_submission_system before verifying required approval.",
    ),

    # -------------------------------------------------------------------------
    # 16. Grounded Precondition: Calendar Availability Before Meeting Invite
    # -------------------------------------------------------------------------
    ResolutionTestCase(
        case_id="PRECOND-02",
        category="GROUNDED_PRECONDITION",
        user_text="Schedule a 1-hour strategy meeting with Sarah for tomorrow afternoon if my calendar is open.",
        active_context={
            "contacts": [{"name": "Sarah Connor", "email": "sconnor@org.com"}],
            "calendar_status": "UNCHECKED",
        },
        expected_goal="Schedule a 1-hour meeting with Sarah contingent on user's calendar availability",
        expected_requirement_status=ResolutionRequirementStatus.RESOLVABLE_VIA_PATH,
        expected_requirement_desc="User's availability for tomorrow afternoon is unverified and must be checked",
        expected_path_exists=True,
        expected_resolution_step="Check user's calendar for tomorrow afternoon availability",
        expected_capability_requirement="Inspect user's calendar schedule",
        expected_matched_capability=AvailableCapability.CALENDAR_CHECK,
        surface_distractor=AvailableCapability.WEB_SEARCH,
        trap_rationale="Dispatching meeting invite blindly or searching web instead of checking private calendar.",
    ),
)
