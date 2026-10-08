"""ARN Uncertainty Discovery Engine (Batch A2.8A).

Identifies what remains semantically uncertain after TurnFrame + RAR.
Preserves critical structural signals without answering the uncertainties.

Governing Rule:
    StructuralSignal != SemanticConclusion.
    Detecting 'don't' records a NEGATION_MARKER signal, but NEVER hard-codes
    a prohibited operation conclusion.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Set, Tuple

from uri_v1.turn.active_context import ActiveContext
from uri_v1.turn.rar_contracts import RAROutcome, RARResolution
from uri_v1.turn.turn_frame import CandidateAction, CandidateReference, TurnFrame
from uri_v1.arn.uncertainty_contracts import (
    SemanticUncertainty,
    StructuralSignal,
    StructuralSignalType,
    UncertaintyType,
)


# Compiled regex patterns for structural marker discovery with character spans
_NEGATION_PATTERN = re.compile(
    r"\b(don't|dont|do\s+not|never|not|no|without|avoid|stop|prohibit|hold\s+off)\b",
    re.IGNORECASE,
)
_CONTRAST_PATTERN = re.compile(
    r"\b(but|instead\s+of|instead|rather\s+than|however|except|unlike)\b|(?:,\s*not\b)",
    re.IGNORECASE,
)
_CONDITIONAL_PATTERN = re.compile(
    r"\b(if|unless|only\s+if|provided\s+that|in\s+case|whether)\b",
    re.IGNORECASE,
)
_TEMPORAL_PATTERN = re.compile(
    r"\b(until|after|before|once|when|tomorrow|next\s+\w+|hold\s+off|pending)\b",
    re.IGNORECASE,
)
_COORDINATION_PATTERN = re.compile(
    r"\b(and|or|as\s+well\s+as)\b",
    re.IGNORECASE,
)
_IMPLICIT_QUALIFIER_PATTERN = re.compile(
    r"\b(appropriately|as\s+needed|properly|as\s+required|as\s+usual|accordingly)\b",
    re.IGNORECASE,
)


class UncertaintyDiscoveryEngine:
    """Discovers and structures semantic uncertainties from structural signals and RAR."""

    def extract_structural_signals(
        self,
        text: str,
        turn_frame: Optional[TurnFrame] = None,
        rar_results: Sequence[RARResolution] = (),
    ) -> Tuple[StructuralSignal, ...]:
        """Preserves all critical structural signals with character offsets."""
        signals: List[StructuralSignal] = []

        # 1. Negation markers
        for m in _NEGATION_PATTERN.finditer(text):
            signals.append(
                StructuralSignal(
                    signal_type=StructuralSignalType.NEGATION_MARKER,
                    span_text=m.group(0),
                    start_char=m.start(),
                    end_char=m.end(),
                    provenance="LexicalNegationScan",
                )
            )

        # 2. Contrast markers
        for m in _CONTRAST_PATTERN.finditer(text):
            signals.append(
                StructuralSignal(
                    signal_type=StructuralSignalType.CONTRAST_MARKER,
                    span_text=m.group(0),
                    start_char=m.start(),
                    end_char=m.end(),
                    provenance="LexicalContrastScan",
                )
            )

        # 3. Conditional markers
        for m in _CONDITIONAL_PATTERN.finditer(text):
            signals.append(
                StructuralSignal(
                    signal_type=StructuralSignalType.CONDITIONAL_MARKER,
                    span_text=m.group(0),
                    start_char=m.start(),
                    end_char=m.end(),
                    provenance="LexicalConditionalScan",
                )
            )

        # 4. Temporal markers
        for m in _TEMPORAL_PATTERN.finditer(text):
            signals.append(
                StructuralSignal(
                    signal_type=StructuralSignalType.TEMPORAL_MARKER,
                    span_text=m.group(0),
                    start_char=m.start(),
                    end_char=m.end(),
                    provenance="LexicalTemporalScan",
                )
            )

        # 5. Coordination markers
        for m in _COORDINATION_PATTERN.finditer(text):
            signals.append(
                StructuralSignal(
                    signal_type=StructuralSignalType.COORDINATION_MARKER,
                    span_text=m.group(0),
                    start_char=m.start(),
                    end_char=m.end(),
                    provenance="LexicalCoordinationScan",
                )
            )

        # 6. Implicit modifier / qualifier markers
        for m in _IMPLICIT_QUALIFIER_PATTERN.finditer(text):
            signals.append(
                StructuralSignal(
                    signal_type=StructuralSignalType.MODIFIER_MARKER,
                    span_text=m.group(0),
                    start_char=m.start(),
                    end_char=m.end(),
                    provenance="LexicalModifierScan",
                )
            )

        # 7. Action Verbs from TurnFrame or fallback
        if turn_frame and turn_frame.candidate_actions:
            for act in turn_frame.candidate_actions:
                idx = text.lower().find(act.verb.lower())
                start = idx if idx >= 0 else 0
                end = start + len(act.verb)
                signals.append(
                    StructuralSignal(
                        signal_type=StructuralSignalType.ACTION_VERB,
                        span_text=act.verb,
                        start_char=start,
                        end_char=end,
                        clause_index=act.clause_index,
                        provenance="TurnFrameCandidateActions",
                    )
                )

        # 7. Unresolved or Ambiguous References from RAR
        for rar in rar_results:
            if rar.outcome == RAROutcome.UNKNOWN:
                idx = text.lower().find(rar.reference_expression.lower())
                start = idx if idx >= 0 else 0
                end = start + len(rar.reference_expression)
                signals.append(
                    StructuralSignal(
                        signal_type=StructuralSignalType.UNRESOLVED_REFERENCE,
                        span_text=rar.reference_expression,
                        start_char=start,
                        end_char=end,
                        provenance="RARUnresolvedOutcome",
                    )
                )
            elif rar.outcome == RAROutcome.AMBIGUOUS:
                idx = text.lower().find(rar.reference_expression.lower())
                start = idx if idx >= 0 else 0
                end = start + len(rar.reference_expression)
                signals.append(
                    StructuralSignal(
                        signal_type=StructuralSignalType.AMBIGUOUS_REFERENCE,
                        span_text=rar.reference_expression,
                        start_char=start,
                        end_char=end,
                        provenance="RARAmbiguousOutcome",
                    )
                )

        # Sort signals by start character
        signals.sort(key=lambda s: s.start_char)
        return tuple(signals)

    def discover_uncertainties(
        self,
        text: str,
        signals: Sequence[StructuralSignal],
        rar_results: Sequence[RARResolution] = (),
        turn_frame: Optional[TurnFrame] = None,
        active_context: Optional[ActiveContext] = None,
    ) -> Tuple[SemanticUncertainty, ...]:
        """Identifies explicit semantic uncertainties based on preserved structural signals."""
        uncertainties: List[SemanticUncertainty] = []
        u_idx = 1

        neg_signals = [s for s in signals if s.signal_type == StructuralSignalType.NEGATION_MARKER]
        con_signals = [s for s in signals if s.signal_type == StructuralSignalType.CONDITIONAL_MARKER]
        temp_signals = [s for s in signals if s.signal_type == StructuralSignalType.TEMPORAL_MARKER]
        contrast_signals = [s for s in signals if s.signal_type == StructuralSignalType.CONTRAST_MARKER]
        action_signals = [s for s in signals if s.signal_type == StructuralSignalType.ACTION_VERB]
        unres_ref_signals = [s for s in signals if s.signal_type in (
            StructuralSignalType.UNRESOLVED_REFERENCE,
            StructuralSignalType.AMBIGUOUS_REFERENCE,
        )]

        # 1. Negation Scope & Polarity Uncertainty
        if neg_signals:
            for neg in neg_signals:
                verbs_nearby = [a.span_text for a in action_signals]
                verb_desc = f" (candidate verbs: {', '.join(verbs_nearby)})" if verbs_nearby else ""
                uncertainties.append(
                    SemanticUncertainty(
                        uncertainty_id=f"UNC-{u_idx:03d}-NEG-SCOPE",
                        uncertainty_type=UncertaintyType.NEGATION_SCOPE,
                        description=f"Scope of negation marker '{neg.span_text}'{verb_desc}.",
                        relevance_justification="Misidentifying negation scope inverts operational polarity.",
                        anchored_signals=(neg,),
                        is_critical=True,
                        provenance="UncertaintyDiscovery.NegationScope",
                    )
                )
                u_idx += 1

                uncertainties.append(
                    SemanticUncertainty(
                        uncertainty_id=f"UNC-{u_idx:03d}-OP-POLARITY",
                        uncertainty_type=UncertaintyType.OPERATION_POLARITY,
                        description=f"Intended polarity of operations governed by '{neg.span_text}'.",
                        relevance_justification="Critical to prevent executing prohibited or deferred operations.",
                        anchored_signals=(neg,),
                        is_critical=True,
                        provenance="UncertaintyDiscovery.OperationPolarity",
                    )
                )
                u_idx += 1

        # 2. Conditional Dependency Uncertainty
        if con_signals:
            for cond in con_signals:
                uncertainties.append(
                    SemanticUncertainty(
                        uncertainty_id=f"UNC-{u_idx:03d}-COND-DEP",
                        uncertainty_type=UncertaintyType.CONDITIONAL_DEPENDENCY,
                        description=f"Contingency condition introduced by marker '{cond.span_text}'.",
                        relevance_justification="Action execution is contingent upon prerequisite evaluation.",
                        anchored_signals=(cond,),
                        is_critical=True,
                        provenance="UncertaintyDiscovery.ConditionalDependency",
                    )
                )
                u_idx += 1

        # 3. Temporal Dependency Uncertainty
        if temp_signals:
            for temp in temp_signals:
                uncertainties.append(
                    SemanticUncertainty(
                        uncertainty_id=f"UNC-{u_idx:03d}-TEMP-DEP",
                        uncertainty_type=UncertaintyType.TEMPORAL_DEPENDENCY,
                        description=f"Temporal constraint or gating trigger introduced by '{temp.span_text}'.",
                        relevance_justification="Premature immediate execution violates temporal deferral.",
                        anchored_signals=(temp,),
                        is_critical=True,
                        provenance="UncertaintyDiscovery.TemporalDependency",
                    )
                )
                u_idx += 1

        # 4. Contrast Relationship Uncertainty
        if contrast_signals:
            for cont in contrast_signals:
                uncertainties.append(
                    SemanticUncertainty(
                        uncertainty_id=f"UNC-{u_idx:03d}-CONTRAST-REL",
                        uncertainty_type=UncertaintyType.CONTRAST_RELATIONSHIP,
                        description=f"Relational contrast or exception introduced by '{cont.span_text}'.",
                        relevance_justification="Contrast distinguishes positive directive from replacement or restriction.",
                        anchored_signals=(cont,),
                        is_critical=True,
                        provenance="UncertaintyDiscovery.ContrastRelationship",
                    )
                )
                u_idx += 1

        # 5. Unresolved / Ambiguous Reference Uncertainty
        for ref in unres_ref_signals:
            uncertainties.append(
                SemanticUncertainty(
                    uncertainty_id=f"UNC-{u_idx:03d}-UNRES-REF",
                    uncertainty_type=UncertaintyType.UNRESOLVED_REFERENCE,
                    description=f"Target entity bound to reference expression '{ref.span_text}'.",
                    relevance_justification="Executing actions against an unconfirmed entity risks data loss.",
                    anchored_signals=(ref,),
                    is_critical=True,
                    provenance="UncertaintyDiscovery.UnresolvedReference",
                )
            )
            u_idx += 1

        # Also inspect RAR results if passed directly
        for rar in rar_results:
            if rar.outcome in (RAROutcome.UNKNOWN, RAROutcome.AMBIGUOUS):
                # Avoid duplicate if already captured via signals
                if not any(rar.reference_expression in u.description for u in uncertainties):
                    uncertainties.append(
                        SemanticUncertainty(
                            uncertainty_id=f"UNC-{u_idx:03d}-RAR-REF",
                            uncertainty_type=UncertaintyType.UNRESOLVED_REFERENCE,
                            description=f"Reference '{rar.reference_expression}' is {rar.outcome.value} in RAR.",
                            relevance_justification="Candidate must be grounded before tool execution.",
                            anchored_signals=(),
                            is_critical=True,
                            provenance="UncertaintyDiscovery.RAROutcome",
                        )
                    )
                    u_idx += 1

        # 6. Multi-Target Operation Coupling (TORT-11 Invariant)
        # If there are >=2 candidate actions and >=2 noun targets/entities, check operation-target binding
        if len(action_signals) >= 2:
            verbs = [a.span_text for a in action_signals]
            uncertainties.append(
                SemanticUncertainty(
                    uncertainty_id=f"UNC-{u_idx:03d}-OP-TARGET",
                    uncertainty_type=UncertaintyType.OPERATION_TARGET,
                    description=f"Coupling between operations ({', '.join(verbs)}) and respective targets.",
                    relevance_justification="Decoupling verbs from targets in multi-action turns creates unsafe polarity inversion.",
                    anchored_signals=tuple(action_signals),
                    is_critical=True,
                    provenance="UncertaintyDiscovery.MultiTargetCoupling",
                )
            )
            u_idx += 1

        # 7. Implicit qualifier semantics (e.g. "appropriately", "as needed")
        mod_signals = [s for s in signals if s.signal_type == StructuralSignalType.MODIFIER_MARKER]
        for m_sig in mod_signals:
            uncertainties.append(
                SemanticUncertainty(
                    uncertainty_id=f"UNC-{u_idx:03d}-MOD-SCOPE",
                    uncertainty_type=UncertaintyType.MODIFIER_SCOPE,
                    description=f"Concrete operational scope required by implicit qualifier '{m_sig.span_text}'.",
                    relevance_justification="Vague qualifiers require semantic disambiguation into explicit steps.",
                    anchored_signals=(m_sig,),
                    is_critical=False,
                    provenance="UncertaintyDiscovery.ImplicitQualifier",
                )
            )
            u_idx += 1

        return tuple(uncertainties)
