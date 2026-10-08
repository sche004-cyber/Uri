"""Adaptive Semantic Feed Planner for URIv1 (Batch A2.5 Stage 4).

Determines which semantic dimensions require model interpretation for a given turn.
Structural detection only:
- Analyzes TurnFrame cues, negation spans, constraint keywords, and RAR outputs.
- Never infers or pre-determines the semantic answers.
- Minimizes token consumption and latency by skipping unnecessary feeds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set, Tuple

from uri_v1.turn.turn_frame import TurnFrame
from uri_v1.turn.lfm_adaptive_feeds import FeedType
from uri_v1.turn.rar_contracts import RAROutcome, RARResolution


# Regular expression cues for constraint detection
_CONSTRAINT_CUES = re.compile(
    r"\b(only|unless|except|without|shorter|short|brief|concise|formal|informal|"
    r"bullet|table|json|markdown|pdf|docx|under\s+\d+|after\s+approval|before)\b",
    re.IGNORECASE,
)

# Broad action verb cues if TurnFrame is absent
_ACTION_VERB_CUES = re.compile(
    r"\b(open|draft|send|compare|delete|create|convert|summarize|review|check|"
    r"read|revise|bring|archive|download|upload|search|find|update)\b",
    re.IGNORECASE,
)

_NEGATION_CUES = re.compile(
    r"\b(don't|dont|do\s+not|never|not|no|stop|prohibit|avoid)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FeedPlan:
    """The execution plan specifying which narrow feeds to invoke."""
    feeds: Tuple[FeedType, ...]
    rationale: str
    is_complex: bool = False
    requires_binding: bool = False
    estimated_calls: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "estimated_calls", len(self.feeds))

    def has_feed(self, feed_type: FeedType) -> bool:
        return feed_type in self.feeds


class AdaptiveSemanticFeedPlanner:
    """Plans narrow feed execution adaptively based on structural cues."""

    def __init__(self, always_include_goal: bool = True) -> None:
        self.always_include_goal = always_include_goal

    def plan_feeds(
        self,
        text: str,
        turn_frame: Optional[TurnFrame] = None,
        rar_result: Optional[RARResolution] = None,
    ) -> FeedPlan:
        """Determines the optimal subset of narrow feeds for the user turn."""
        planned: List[FeedType] = []
        rationales: List[str] = []

        # 1. Feed G: Goal / Intent
        if self.always_include_goal:
            planned.append(FeedType.GOAL)
            rationales.append("Goal feed included for primary intent classification.")

        # 2. Feed O: Operations & Polarity
        has_action_cues = False
        if turn_frame and turn_frame.candidate_actions:
            has_action_cues = True
            rationales.append(f"Action verbs detected in TurnFrame ({len(turn_frame.candidate_actions)} verbs).")
        elif _ACTION_VERB_CUES.search(text):
            has_action_cues = True
            rationales.append("Action verb cues matched in user turn text.")
        elif _NEGATION_CUES.search(text):
            has_action_cues = True
            rationales.append("Negation cues present requiring polarity classification.")

        if has_action_cues:
            planned.append(FeedType.OPERATIONS)

        # 3. Feed C: Constraints & Output Preferences
        has_constraint_cues = False
        if _CONSTRAINT_CUES.search(text):
            has_constraint_cues = True
            rationales.append("Constraint or output style/formatting keywords detected.")
        elif turn_frame and turn_frame.negation_spans:
            # Conditional negations often carry constraint clauses
            for span in turn_frame.negation_spans:
                if any(w in span.lower() for w in ["unless", "only", "after", "if"]):
                    has_constraint_cues = True
                    rationales.append("Conditional negation span detected requiring constraint interpretation.")
                    break

        if has_constraint_cues:
            planned.append(FeedType.CONSTRAINTS)

        # 4. Feed B: Semantic Binding
        requires_binding = False
        # Binding is only relevant when there are multiple operations or complex entity mapping
        num_actions = len(turn_frame.candidate_actions) if turn_frame else len(_ACTION_VERB_CUES.findall(text))
        has_resolved_anchors = rar_result is not None and rar_result.outcome == RAROutcome.RESOLVED and rar_result.candidate_id

        # If turn has multiple actions and resolved anchors, or explicit contrastive binding
        if num_actions > 1 and has_resolved_anchors:
            requires_binding = True
            planned.append(FeedType.BINDING)
            rationales.append("Multiple operations with resolved RAR anchors requiring semantic relation binding.")
        elif "earlier" in text.lower() or "revised" in text.lower() or "this one" in text.lower() or "that one" in text.lower():
            if num_actions >= 1 and rar_result:
                requires_binding = True
                planned.append(FeedType.BINDING)
                rationales.append("Comparative or deictic reference across multiple candidates requires binding.")

        is_complex = len(planned) >= 3 or requires_binding

        return FeedPlan(
            feeds=tuple(planned),
            rationale=" | ".join(rationales),
            is_complex=is_complex,
            requires_binding=requires_binding,
        )


@dataclass(frozen=True)
class EscalationDecision:
    """Evaluation of whether turn complexity exceeds LFM's reliable envelope."""
    should_escalate: bool
    reason: str
    recommended_provider: str = "qwen3-14b"


class SemanticEnvelopeEscalationGuard:
    """Evaluates whether turn complexity exceeds LFM2.5-350M's empirical operating envelope."""

    def __init__(
        self,
        max_context_tokens: int = 400,
        max_operations: int = 3,
        max_candidate_distractors: int = 5,
        max_negation_clauses: int = 2,
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.max_operations = max_operations
        self.max_candidate_distractors = max_candidate_distractors
        self.max_negation_clauses = max_negation_clauses

    def evaluate(
        self,
        estimated_tokens: int,
        num_operations: int,
        num_candidates: int,
        negation_clause_count: int,
        has_cross_target_dependency: bool = False,
    ) -> EscalationDecision:
        if estimated_tokens > self.max_context_tokens:
            return EscalationDecision(
                should_escalate=True,
                reason=f"Context tokens ({estimated_tokens}) exceed LFM budget ({self.max_context_tokens}).",
            )
        if num_operations > self.max_operations:
            return EscalationDecision(
                should_escalate=True,
                reason=f"Operation count ({num_operations}) exceeds LFM retention capacity ({self.max_operations}).",
            )
        if num_candidates > self.max_candidate_distractors:
            return EscalationDecision(
                should_escalate=True,
                reason=f"Candidate distractors ({num_candidates}) exceed LFM noise tolerance ({self.max_candidate_distractors}).",
            )
        if negation_clause_count > self.max_negation_clauses:
            return EscalationDecision(
                should_escalate=True,
                reason=f"Nested negation clauses ({negation_clause_count}) exceed LFM polarity parsing limit ({self.max_negation_clauses}).",
            )
        if has_cross_target_dependency:
            return EscalationDecision(
                should_escalate=True,
                reason="Cross-target relational dependency exceeds single-pass semantic binding.",
            )

        return EscalationDecision(
            should_escalate=False,
            reason="Within LFM2.5-350M reliable operating envelope.",
            recommended_provider="lfm2.5-350m",
        )
