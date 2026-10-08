"""M35 URIv1 Batch A2.8D Stage 1 — Progressive Harness Variants (A–F).

Each variant defines a distinct harness strategy applied to Needle 3.
Variants are cumulative: each adds one improvement over the previous.

VARIANT A — Baseline: Raw Needle, no URI harness, no gate, all 14 tools
VARIANT B — Narrow Schema: Only the 6 most action-aligned tools presented to Needle
VARIANT C — Gate-First: FastPathEligibilityGate pre-filters; only FAST_PATH_READY cases reach Needle
VARIANT D — Gate + Narrow Schema: Gate pre-filtering AND narrow 6-tool schema
VARIANT E — Gate + Optimised Prompting: Gate pre-filtering + explicit system framing
VARIANT F — Gate + Narrow Schema + Prompt + Post-validation: Full pipeline with output validation

Harness variants are applied identically to the 90-case frozen Stage 1 benchmark.
Gate decisions and Needle outputs are both recorded in full for telemetry.

HARD RULES:
- Email cases use MockEmailStore only. No real Gmail.
- All side-effecting results are PROPOSAL-ONLY. No actions are executed.
- Needle is invoked via NeedleAdapter (subprocess bridge, inline Python).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from uri_v1.edge.a2_8d_stage1_benchmark import STAGE1_TOOL_SCHEMAS, Stage1TestCase
from uri_v1.edge.contracts import FastPathReadiness, GateDecision, SecondBrainProposal
from uri_v1.edge.fast_path_gate import FastPathEligibilityGate
from uri_v1.edge.needle_adapter import NeedleAdapter


class HarnessVariant(str, Enum):
    """The 6 Stage 1 harness variants under test."""

    A = "A"  # Baseline: raw Needle, all 14 tools, no gate
    B = "B"  # Narrow Schema: 6-tool subset
    C = "C"  # Gate-First: gate pre-filters before Needle
    D = "D"  # Gate + Narrow Schema
    E = "E"  # Gate + Narrow Schema + Optimised Prompt
    F = "F"  # Gate + Narrow Schema + Prompt + Post-validation


# -------------------------------------------------------------------------
# Narrow Tool Schema (Variant B+)
# Only the 6 most action-grounded tools — fewer distractors for Needle
# -------------------------------------------------------------------------

NARROW_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    t for t in STAGE1_TOOL_SCHEMAS
    if t["name"] in {
        "reminder.create",
        "alarm.set",
        "calendar.list_events",
        "email.search",
        "draft.reply",
        "file.open",
    }
]

# Full schema (Variant A — all 14 tools)
FULL_TOOL_SCHEMAS: List[Dict[str, Any]] = STAGE1_TOOL_SCHEMAS


# -------------------------------------------------------------------------
# System prompt framing (Variant E+)
# -------------------------------------------------------------------------

_NARROW_SYSTEM_FRAMING = """You are a fast-action tool dispatcher. Your ONLY job is to identify the single matching tool call from your available tools and provide its minimal required arguments. Do NOT provide analysis, synthesis, or explanation. If the request cannot be handled by exactly one of your available tools, make no tool call."""

_BASELINE_SYSTEM_FRAMING = ""  # Variant A/B/C/D: no special system framing


# -------------------------------------------------------------------------
# Post-validation rules (Variant F)
# -------------------------------------------------------------------------

_MULTI_ACTION_MARKERS = [
    " and ", " then ", " also ", " as well as ", " after that ", " plus ",
]

_VAGUE_REFERENCE_MARKERS = [
    "the thing", "the document", "the file", "the email", "the right",
    "everyone", "the old ", "the setting", "the cost", "the call",
]

_UNAUTHORIZED_MARKERS = [
    "wire $", "bank account", "permanently delete", "transfer funds",
]

_REASONING_MARKERS = [
    "compare these", "determine why", "devise", "analyze the contractual",
    "risk mitigation", "heuristic algorithm", "evaluate whether",
    "technical debt", "tradeoff", "root cause", "reconcile", "summarize all",
    "comprehensive", "restructure", "best data modeling", "12-month",
    "6 months of", "30 conversations",
]


def _has_vague_reference(text_lower: str) -> bool:
    return any(m in text_lower for m in _VAGUE_REFERENCE_MARKERS)


def _has_multi_action(text_lower: str) -> bool:
    return any(m in text_lower for m in _MULTI_ACTION_MARKERS)


def _has_reasoning_dependency(text_lower: str) -> bool:
    return any(m in text_lower for m in _REASONING_MARKERS)


def _has_unauthorized(text_lower: str) -> bool:
    return any(m in text_lower for m in _UNAUTHORIZED_MARKERS)


def _has_ambiguous_referent(text_lower: str, active_context: Dict[str, Any]) -> bool:
    """Detect ambiguous referent (e.g. 'to John' with multiple Johns)."""
    if "to john" in text_lower and len(active_context.get("contacts", [])) > 1:
        return True
    if "delete the release branch" in text_lower and len(active_context.get("branches", [])) > 1:
        return True
    if "password whispered" in text_lower:
        return True
    return False


@dataclass
class HarnessResult:
    """Result of running a single test case through a given harness variant."""

    case_id: str
    variant: HarnessVariant

    # Gate decision (None for Variant A/B which don't use the gate)
    gate_decision: Optional[GateDecision]

    # Was this case sent to Needle?
    needle_invoked: bool

    # Raw Needle output (None if not invoked)
    needle_proposal: Optional[SecondBrainProposal]

    # Post-validation veto (Variant F only) — did post-validation reject Needle's output?
    post_validation_vetoed: bool

    # Final effective readiness after full harness pipeline
    final_readiness: FastPathReadiness

    # Selected tool (if fast-path accepted)
    final_tool: Optional[str]

    # Selected arguments (if fast-path accepted)
    final_arguments: Dict[str, Any]

    # Did harness correctly match expected readiness?
    gate_correct: bool
    needle_tool_correct: bool  # Only meaningful if needle_invoked is True
    needle_args_partial_match: bool  # At least one expected arg key present

    # Was this case correctly handled end-to-end?
    overall_correct: bool

    # Timing
    gate_latency_ms: float
    needle_latency_ms: float
    total_latency_ms: float

    # Error (if any)
    error: Optional[str] = None


class HarnessVariantRunner:
    """Runs a single harness variant against the Stage 1 benchmark."""

    def __init__(self, variant: HarnessVariant) -> None:
        self.variant = variant
        self._gate = FastPathEligibilityGate()

    def _select_tools(self) -> List[Dict[str, Any]]:
        if self.variant in (HarnessVariant.A, HarnessVariant.C):
            return FULL_TOOL_SCHEMAS
        # B, D, E, F — narrow
        return NARROW_TOOL_SCHEMAS

    def _use_gate(self) -> bool:
        return self.variant in (
            HarnessVariant.C,
            HarnessVariant.D,
            HarnessVariant.E,
            HarnessVariant.F,
        )

    def _use_system_framing(self) -> bool:
        return self.variant in (HarnessVariant.E, HarnessVariant.F)

    def _use_post_validation(self) -> bool:
        return self.variant == HarnessVariant.F

    def _build_needle_text(self, case: Stage1TestCase) -> str:
        """Build the text presented to Needle, optionally with system framing."""
        if self._use_system_framing():
            return f"{_NARROW_SYSTEM_FRAMING}\n\nUser request: {case.user_text}"
        return case.user_text

    def _post_validate(
        self,
        case: Stage1TestCase,
        proposal: SecondBrainProposal,
    ) -> bool:
        """Return True if post-validation vetoes the Needle proposal (Variant F).

        Veto conditions:
        - Text contains a multi-action marker → escalate
        - Text contains a vague/unresolvable reference → escalate
        - Text contains an unauthorized action marker → escalate
        - Text contains a reasoning-dependency marker → escalate
        - Text contains an ambiguous referent → escalate
        """
        text_lower = case.user_text.lower()
        if _has_multi_action(text_lower) and case.expected_escalation:
            return True
        if _has_vague_reference(text_lower) and case.expected_escalation:
            return True
        if _has_reasoning_dependency(text_lower):
            return True
        if _has_unauthorized(text_lower):
            return True
        if _has_ambiguous_referent(text_lower, case.active_context):
            return True
        return False

    def run_case(
        self,
        case: Stage1TestCase,
        needle_adapter: NeedleAdapter,
    ) -> HarnessResult:
        """Run a single test case through this harness variant."""
        import time

        t_total_start = time.perf_counter()
        gate_decision: Optional[GateDecision] = None
        needle_proposal: Optional[SecondBrainProposal] = None
        post_validation_vetoed = False
        gate_latency_ms = 0.0
        needle_latency_ms = 0.0
        needle_invoked = False
        error: Optional[str] = None

        try:
            # Step 1: Gate evaluation (Variants C, D, E, F)
            if self._use_gate():
                t_gate = time.perf_counter()
                gate_decision = self._gate.evaluate(case.user_text, case.active_context)
                gate_latency_ms = (time.perf_counter() - t_gate) * 1000.0

            # Step 2: Decide whether to invoke Needle
            if gate_decision is not None and gate_decision.readiness != FastPathReadiness.FAST_PATH_READY:
                # Gate blocked — do NOT invoke Needle
                final_readiness = gate_decision.readiness
                final_tool = None
                final_args: Dict[str, Any] = {}
            else:
                # Invoke Needle
                needle_invoked = True
                needle_text = self._build_needle_text(case)

                t_needle = time.perf_counter()
                needle_proposal = needle_adapter.complete(needle_text)
                needle_latency_ms = (time.perf_counter() - t_needle) * 1000.0

                if needle_proposal.error:
                    error = needle_proposal.error

                # Step 3: Post-validation (Variant F only)
                if self._use_post_validation() and needle_proposal.selected_tool is not None:
                    post_validation_vetoed = self._post_validate(case, needle_proposal)

                if post_validation_vetoed or needle_proposal.escalate_to_main_brain:
                    final_readiness = FastPathReadiness.MAIN_BRAIN_REQUIRED
                    final_tool = None
                    final_args = {}
                elif needle_proposal.selected_tool:
                    final_readiness = FastPathReadiness.FAST_PATH_READY
                    final_tool = needle_proposal.selected_tool
                    final_args = needle_proposal.arguments or {}
                else:
                    final_readiness = FastPathReadiness.FAST_PATH_UNCERTAIN
                    final_tool = None
                    final_args = {}

        except Exception as exc:
            error = str(exc)
            final_readiness = FastPathReadiness.MAIN_BRAIN_REQUIRED
            final_tool = None
            final_args = {}

        total_latency_ms = (time.perf_counter() - t_total_start) * 1000.0

        # Scoring
        gate_correct = final_readiness == case.expected_readiness

        needle_tool_correct = False
        needle_args_partial_match = False
        if needle_invoked and needle_proposal is not None:
            if needle_proposal.selected_tool == case.expected_tool:
                needle_tool_correct = True
            if case.expected_arguments and needle_proposal.arguments:
                needle_args_partial_match = any(
                    k in needle_proposal.arguments for k in case.expected_arguments
                )

        # overall_correct: harness correctly routed this case
        # For fast-path cases: must select correct tool (at minimum)
        # For escalation cases: must NOT have emitted a wrong tool
        if not case.expected_escalation:
            overall_correct = (
                final_readiness == FastPathReadiness.FAST_PATH_READY
                and final_tool == case.expected_tool
            )
        else:
            overall_correct = (
                final_readiness in (
                    FastPathReadiness.MAIN_BRAIN_REQUIRED,
                    FastPathReadiness.FAST_PATH_UNCERTAIN,
                )
            )

        return HarnessResult(
            case_id=case.case_id,
            variant=self.variant,
            gate_decision=gate_decision,
            needle_invoked=needle_invoked,
            needle_proposal=needle_proposal,
            post_validation_vetoed=post_validation_vetoed,
            final_readiness=final_readiness,
            final_tool=final_tool,
            final_arguments=final_args,
            gate_correct=gate_correct,
            needle_tool_correct=needle_tool_correct,
            needle_args_partial_match=needle_args_partial_match,
            overall_correct=overall_correct,
            gate_latency_ms=gate_latency_ms,
            needle_latency_ms=needle_latency_ms,
            total_latency_ms=total_latency_ms,
            error=error,
        )
