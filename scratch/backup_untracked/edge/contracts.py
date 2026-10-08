"""M35 URIv1 Batch A2.8D — Edge-Brain & Fast-Path Eligibility Gate Contracts.

Governing Principles:
1. "Single-task prompt principle": The Edge Brain is designed for simple, bounded,
   realistic operational turns. It is never forced to behave like a general-purpose
   reasoning model.
2. "Reasoning belongs to the Main Brain": Tasks requiring multi-source synthesis,
   novel strategy formulation, or deep ambiguity must escalate to the Main Brain.
   Escalation is a successful safety outcome, not a failure.
3. "No invented work": Second Brain must strictly address the requested task without
   manufacturing unrequested policies, institutional entitlements, or unstated rules.
4. "Harness-level eligibility gate": URI's deterministic harness determines whether
   a request is eligible for fast-path execution before calling the Edge model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


class FastPathReadiness(str, Enum):
    """Routing state determined by the harness eligibility gate."""

    FAST_PATH_READY = "FAST_PATH_READY"
    # Request is bounded, single-intent, arguments are grounded, no reasoning dependencies.
    # Route immediately to Second Brain fast path.

    FAST_PATH_UNCERTAIN = "FAST_PATH_UNCERTAIN"
    # Harness cannot deterministically establish readiness; triggers fallback routing
    # (e.g. model confidence evaluation, explicit abstention check, or safe escalation).

    MAIN_BRAIN_REQUIRED = "MAIN_BRAIN_REQUIRED"
    # Task requires multi-source synthesis, architectural reasoning, legal/risk analysis,
    # or contains unresolvable ambiguity. Route directly to Main Brain.


@dataclass(frozen=True)
class FastPathEvidence:
    """The 8 structural evidence signals establishing fast-path readiness."""

    task_scope_grounded: bool
    # Is the user goal bounded to a single operational intent?

    required_arguments_grounded: bool
    # Are necessary target parameters present in prompt or active context?

    simple_resolution_path_available: bool
    # Can the task be solved by a direct tool call or deterministic transform?

    capability_available: bool
    # Does an available capability in the fast-path catalog match the request?

    capability_contract_match: bool
    # Do extracted arguments conform to the matching capability schema?

    context_reference_resolved: bool
    # Are pronouns/referents resolved without cross-turn conflict or ambiguity?

    reasoning_dependency_present: bool
    # Does the task require deep comparative analysis, strategy design, or triage?

    ambiguity_present: bool
    # Are there tied candidates or ungrounded destructive parameters?


@dataclass(frozen=True)
class GateDecision:
    """Outcome of the Harness Fast-Path Eligibility Gate."""

    readiness: FastPathReadiness
    evidence: FastPathEvidence
    matched_capability: Optional[str] = None
    target_arguments: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    gate_latency_ms: float = 0.0


class FallbackStrategy(str, Enum):
    """Fallback options when harness readiness is FAST_PATH_UNCERTAIN."""

    IMMEDIATE_ESCALATE = "IMMEDIATE_ESCALATE"
    # Safely escalate immediately to Main Brain without invoking Second Brain.

    CONFIDENCE_GATED = "CONFIDENCE_GATED"
    # Invoke Second Brain; if model confidence >= threshold, accept; else escalate.

    EXPLICIT_ABSTENTION = "EXPLICIT_ABSTENTION"
    # Invoke Second Brain; rely on model's explicit ESCALATE_MAIN_BRAIN emission.


@dataclass(frozen=True)
class SecondBrainProposal:
    """The concrete proposal emitted by an Edge Brain model or ensemble."""

    selected_tool: Optional[str]
    arguments: Dict[str, Any]
    confidence: Optional[float]
    escalate_to_main_brain: bool
    explanation: str
    latency_ms: float
    peak_ram_mb: Optional[float] = None
    model_id: str = "unknown"
    error: Optional[str] = None


class EdgeBrainConfig(str, Enum):
    """Candidate Second-Brain architectural configurations under test."""

    NEEDLE_SOLO = "NEEDLE_SOLO"
    # Config 1: Needle 3 alone (~35 MB weights).

    LFM_350M_SOLO = "LFM_350M_SOLO"
    # Config 2a: LiquidAI LFM2.5-350M alone (~379 MB).

    QWEN_0_8B_SOLO = "QWEN_0_8B_SOLO"
    # Config 2b: Qwen3.5-0.8B alone (~795 MB).

    SPECIALIST_PAIR = "SPECIALIST_PAIR"
    # Config 3: Needle 3 (reflex routing) + LFM2.5-350M (text drafting/fallback) (~414 MB).

    THREE_MODEL_EDGE = "THREE_MODEL_EDGE"
    # Config 4: Needle 3 + LFM2.5-350M + Qwen3.5-0.8B (~1.2 GB).

    QWEN_2B_SOLO = "QWEN_2B_SOLO"
    # Config 5: Qwen3.5-2B as a standalone larger Edge generalist (~1.27 GB).
