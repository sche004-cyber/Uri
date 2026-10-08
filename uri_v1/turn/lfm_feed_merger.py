"""Deterministic Semantic Merger for URIv1 (Batch A2.5 Stage 4).

Combines outputs from independent narrow feeds (Feed G, O, C, B) and deterministic RAR:
- Structural normalization only.
- Strict contradiction detection.
- Preserves ambiguities and unresolved dependencies.
- Zero post-hoc semantic repair.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

from uri_v1.turn.active_context import ActiveContext
from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    ConstraintScope,
    ContextDependency,
    ContextDependencyCategory,
    DecodedRequest,
    EntityCategory,
    IntendedOutcome,
    IntentFamily,
    MentionedEntity,
    OperationStatus,
    OutputPreferences,
    ReferenceKind,
    SemanticAmbiguity,
    SemanticConfidence,
    SemanticOperation,
    SemanticReference,
    TemporalReference,
)
from uri_v1.turn.lfm_adaptive_feeds import (
    FeedBOutput,
    FeedCOutput,
    FeedGOutput,
    FeedOOutput,
)
from uri_v1.turn.rar_contracts import RAROutcome, RARResolution
from uri_v1.turn.turn_frame import TurnFrame


class DeterministicSemanticMerger:
    """Merges narrow feed outputs and deterministic RAR facts into DecodedRequest."""

    def merge(
        self,
        user_text: str,
        feed_g: Optional[FeedGOutput] = None,
        feed_o: Optional[FeedOOutput] = None,
        feed_c: Optional[FeedCOutput] = None,
        feed_b: Optional[FeedBOutput] = None,
        rar_result: Optional[RARResolution] = None,
        turn_frame: Optional[TurnFrame] = None,
        active_context: Optional[ActiveContext] = None,
    ) -> DecodedRequest:
        """Deterministically merges available feed outputs and RAR state."""

        # -------------------------------------------------------------------
        # 1. Goal & Intent Family
        # -------------------------------------------------------------------
        if feed_g is not None and feed_g.goal:
            goal_text = feed_g.goal
            intent_family = feed_g.intent_family
        elif feed_o is not None and feed_o.requested_operations:
            goal_text = f"Perform {', '.join(feed_o.requested_operations)}"
            intent_family = IntentFamily.EXECUTE
        else:
            goal_text = user_text.strip()
            intent_family = IntentFamily.UNSPECIFIED

        intended_outcome = IntendedOutcome(
            description=goal_text,
            intent_family=intent_family,
        )

        # -------------------------------------------------------------------
        # 2. Semantic Operations & Contradiction Detection
        # -------------------------------------------------------------------
        ambiguities: List[SemanticAmbiguity] = []
        operations: List[SemanticOperation] = []

        req_verbs = list(feed_o.requested_operations) if feed_o else []
        pro_verbs = list(feed_o.prohibited_operations) if feed_o else []

        # Check for contradictions between requested and prohibited verbs
        req_set = set(req_verbs)
        pro_set = set(pro_verbs)
        conflicts = req_set.intersection(pro_set)

        if conflicts:
            ambiguities.append(
                SemanticAmbiguity(
                    kind=AmbiguityKind.MULTIPLE_INTERPRETATIONS,
                    description=f"Conflicting polarity for operations: {', '.join(sorted(conflicts))}",
                    candidates=tuple(sorted(conflicts)),
                )
            )
            # Safety rule: remove conflicting verbs from requested operations
            req_verbs = [v for v in req_verbs if v not in conflicts]

        # Build mapping of operation -> target from Feed B or deterministic fallback
        op_to_target: Dict[str, str] = {}
        if feed_b is not None:
            for binding in feed_b.bindings:
                if binding.target_id:
                    op_to_target[binding.operation] = binding.target_id

        # Fallback target binding: if exactly 1 op and 1 resolved RAR anchor
        rar_target = rar_result.candidate_id if (rar_result and rar_result.outcome == RAROutcome.RESOLVED) else None
        if rar_target and not op_to_target:
            if len(req_verbs) == 1:
                op_to_target[req_verbs[0]] = rar_target
            elif len(req_verbs) == 0 and len(pro_verbs) == 1:
                op_to_target[pro_verbs[0]] = rar_target

        for verb in req_verbs:
            t = op_to_target.get(verb)
            operations.append(
                SemanticOperation(
                    name=verb,
                    status=OperationStatus.REQUESTED,
                    target=t,
                )
            )

        for verb in pro_verbs:
            t = op_to_target.get(verb)
            operations.append(
                SemanticOperation(
                    name=verb,
                    status=OperationStatus.PROHIBITED,
                    target=t,
                )
            )

        # -------------------------------------------------------------------
        # 3. References & Context Dependencies (from Deterministic RAR)
        # -------------------------------------------------------------------
        references: List[SemanticReference] = []
        dependencies: List[ContextDependency] = []

        if rar_result is not None and rar_result.reference_expression:
            expr = rar_result.reference_expression
            if rar_result.outcome == RAROutcome.RESOLVED:
                references.append(
                    SemanticReference(
                        expression=expr,
                        kind=ReferenceKind.OTHER,
                        referent_hint=rar_result.candidate_id,
                        is_resolved=True,
                    )
                )
            elif rar_result.outcome == RAROutcome.UNKNOWN:
                references.append(
                    SemanticReference(
                        expression=expr,
                        kind=ReferenceKind.OTHER,
                        referent_hint=None,
                        is_resolved=False,
                    )
                )
                dependencies.append(
                    ContextDependency(
                        description=f"Unresolved reference anchor: '{expr}'",
                        category=ContextDependencyCategory.CONTEXT_REQUIRED,
                    )
                )
            elif rar_result.outcome == RAROutcome.AMBIGUOUS:
                references.append(
                    SemanticReference(
                        expression=expr,
                        kind=ReferenceKind.OTHER,
                        referent_hint=None,
                        is_resolved=False,
                    )
                )
                ambiguities.append(
                    SemanticAmbiguity(
                        kind=AmbiguityKind.UNRESOLVED_REFERENT,
                        description=f"Multiple ambiguous candidates for reference: '{expr}'",
                        candidates=tuple(rar_result.ambiguous_candidate_ids or ()),
                    )
                )

        # Also add unresolved relations from Feed B to context dependencies
        if feed_b is not None and feed_b.unresolved_relations:
            for unres in feed_b.unresolved_relations:
                dependencies.append(
                    ContextDependency(
                        description=f"Unresolved operation target relation: '{unres}'",
                        category=ContextDependencyCategory.CONTEXT_REQUIRED,
                    )
                )

        # -------------------------------------------------------------------
        # 4. Constraints & Output Preferences (from Feed C)
        # -------------------------------------------------------------------
        if feed_c is not None:
            scope = ConstraintScope(
                included_items=feed_c.included_items,
                excluded_items=feed_c.excluded_items,
            )
            out_prefs = OutputPreferences(
                artifact_type=feed_c.artifact_type or None,
                format=feed_c.format or None,
                tone=feed_c.tone or None,
                structure=feed_c.structure or None,
            )
            timing = feed_c.timing_condition
        else:
            scope = ConstraintScope()
            out_prefs = OutputPreferences()
            timing = None

        # -------------------------------------------------------------------
        # 5. Temporal References
        # -------------------------------------------------------------------
        temporal_refs: List[TemporalReference] = []
        if timing:
            temporal_refs.append(
                TemporalReference(
                    expression=timing,
                    is_relative=True,
                )
            )

        # -------------------------------------------------------------------
        # 6. Confidence Scoring
        # -------------------------------------------------------------------
        overall_level = ConfidenceLevel.HIGH if (not conflicts and not ambiguities) else ConfidenceLevel.MEDIUM
        confidence = SemanticConfidence(
            goal=ConfidenceLevel.HIGH,
            operations=ConfidenceLevel.HIGH if not conflicts else ConfidenceLevel.LOW,
            references=ConfidenceLevel.HIGH if (rar_result and rar_result.outcome == RAROutcome.RESOLVED) else ConfidenceLevel.MEDIUM,
            constraints=ConfidenceLevel.HIGH,
            overall=overall_level,
        )

        return DecodedRequest(
            raw_text=user_text,
            goal=intended_outcome,
            operations=tuple(operations),
            entities=(),
            references=tuple(references),
            temporal_references=tuple(temporal_refs),
            constraints=scope,
            output_preferences=out_prefs,
            ambiguities=tuple(ambiguities),
            dependencies=tuple(dependencies),
            confidence=confidence,
        )
