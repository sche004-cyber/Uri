"""M35 URIv1 Batch A2.8A — ARN Foundation Benchmark Set.

Covers the 12 mandated test cases:
1. Simple ("Review the email.")
2. Explicit negation ("Draft the reply but don't send it.")
3. Multiple negation ("Review it, don't send it, and don't upload anything.")
4. Conditional ("Send it if the Dean approves.")
5. Unless ("Don't send it unless the Dean approves.")
6. Temporal ("Don't send it until Monday.")
7. Reference ("Use the revised approval and draft the order from it.")
8. Contrast ("Use the revised approval, not the earlier one.")
9. Multi-object ("Sign the affidavit and shred the draft notes.")
10. Ambiguous reference ("Don't do that yet.")
11. Implicit semantics ("Deal with the Dean's email appropriately.")
12. Combined/adversarial (references + negation + conditional/temporal markers + multiple objects).

INVARIANT:
    Evaluates uncertainty discovery and question framing strictly separately
    from final semantic answering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

from uri_v1.turn.rar_contracts import RARCandidate, RAROutcome, RARResolution
from uri_v1.turn.turn_frame import CandidateAction, CandidateReference, TurnFrame
from uri_v1.arn.uncertainty_contracts import StructuralSignalType, UncertaintyType


@dataclass(frozen=True)
class ARNTestCase:
    """Test case specification for Batch A2.8A ARN Foundation benchmark."""

    case_id: str
    category: str
    user_text: str
    turn_frame: TurnFrame
    rar_results: Tuple[RARResolution, ...] = ()
    expected_critical_signals: Tuple[str, ...] = ()
    expected_uncertainty_types: Tuple[UncertaintyType, ...] = ()
    description: str = ""


def build_a2_8a_benchmark_suite() -> Tuple[ARNTestCase, ...]:
    """Constructs the complete 12-case benchmark suite mandated for A2.8A."""
    cases: list[ARNTestCase] = []

    # 1. Simple
    cases.append(
        ARNTestCase(
            case_id="A28A-01-SIMPLE",
            category="Simple",
            user_text="Review the email.",
            turn_frame=TurnFrame(
                raw_text="Review the email.",
                normalized_text="review the email.",
                candidate_actions=(CandidateAction(id="a0", verb="review", clause_index=0),),
                candidate_references=(CandidateReference(id="r0", expression="the email", clause_index=0),),
            ),
            rar_results=(
                RARResolution(
                    reference_expression="the email",
                    outcome=RAROutcome.RESOLVED,
                    candidate_id="email_dean_latest_2026",
                ),
            ),
            expected_critical_signals=("review",),
            expected_uncertainty_types=(),  # Direct turn without unresolved uncertainties
            description="Simple unambiguous single directive with resolved reference.",
        )
    )

    # 2. Explicit negation
    cases.append(
        ARNTestCase(
            case_id="A28A-02-EXPLICIT-NEG",
            category="Explicit_Negation",
            user_text="Draft the reply but don't send it.",
            turn_frame=TurnFrame(
                raw_text="Draft the reply but don't send it.",
                normalized_text="draft the reply but don't send it.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="draft", clause_index=0),
                    CandidateAction(id="a1", verb="send", clause_index=1),
                ),
                negation_spans=("don't send it",),
                candidate_references=(CandidateReference(id="r0", expression="it", clause_index=1),),
            ),
            expected_critical_signals=("don't", "but", "send", "draft"),
            expected_uncertainty_types=(
                UncertaintyType.NEGATION_SCOPE,
                UncertaintyType.OPERATION_POLARITY,
                UncertaintyType.CONTRAST_RELATIONSHIP,
            ),
            description="Explicit contrastive negation ('draft' vs 'don't send').",
        )
    )

    # 3. Multiple negation
    cases.append(
        ARNTestCase(
            case_id="A28A-03-MULTI-NEG",
            category="Multiple_Negation",
            user_text="Review it, don't send it, and don't upload anything.",
            turn_frame=TurnFrame(
                raw_text="Review it, don't send it, and don't upload anything.",
                normalized_text="review it, don't send it, and don't upload anything.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="review", clause_index=0),
                    CandidateAction(id="a1", verb="send", clause_index=1),
                    CandidateAction(id="a2", verb="upload", clause_index=2),
                ),
                negation_spans=("don't send it", "don't upload anything"),
            ),
            expected_critical_signals=("don't", "upload", "send", "review"),
            expected_uncertainty_types=(
                UncertaintyType.NEGATION_SCOPE,
                UncertaintyType.OPERATION_POLARITY,
            ),
            description="Multiple distinct negative operators applying to distinct verbs.",
        )
    )

    # 4. Conditional
    cases.append(
        ARNTestCase(
            case_id="A28A-04-CONDITIONAL",
            category="Conditional",
            user_text="Send it if the Dean approves.",
            turn_frame=TurnFrame(
                raw_text="Send it if the Dean approves.",
                normalized_text="send it if the dean approves.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="send", clause_index=0),
                    CandidateAction(id="a1", verb="approve", clause_index=1),
                ),
                candidate_references=(CandidateReference(id="r0", expression="it", clause_index=0),),
            ),
            expected_critical_signals=("if", "send"),
            expected_uncertainty_types=(
                UncertaintyType.CONDITIONAL_DEPENDENCY,
            ),
            description="Positive action contingent upon external approval predicate.",
        )
    )

    # 5. Unless
    cases.append(
        ARNTestCase(
            case_id="A28A-05-UNLESS",
            category="Unless",
            user_text="Don't send it unless the Dean approves.",
            turn_frame=TurnFrame(
                raw_text="Don't send it unless the Dean approves.",
                normalized_text="don't send it unless the dean approves.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="send", clause_index=0),
                    CandidateAction(id="a1", verb="approve", clause_index=1),
                ),
                negation_spans=("don't send it",),
            ),
            expected_critical_signals=("don't", "unless", "send"),
            expected_uncertainty_types=(
                UncertaintyType.NEGATION_SCOPE,
                UncertaintyType.CONDITIONAL_DEPENDENCY,
            ),
            description="Negative default contingent on an exception clause.",
        )
    )

    # 6. Temporal
    cases.append(
        ARNTestCase(
            case_id="A28A-06-TEMPORAL",
            category="Temporal",
            user_text="Don't send it until Monday.",
            turn_frame=TurnFrame(
                raw_text="Don't send it until Monday.",
                normalized_text="don't send it until monday.",
                candidate_actions=(CandidateAction(id="a0", verb="send", clause_index=0),),
                negation_spans=("don't send it",),
                temporal_surface_spans=("until monday",),
            ),
            expected_critical_signals=("don't", "until", "send"),
            expected_uncertainty_types=(
                UncertaintyType.NEGATION_SCOPE,
                UncertaintyType.TEMPORAL_DEPENDENCY,
            ),
            description="Deferred timing where action is gated by temporal condition.",
        )
    )

    # 7. Reference
    cases.append(
        ARNTestCase(
            case_id="A28A-07-REFERENCE",
            category="Reference",
            user_text="Use the revised approval and draft the order from it.",
            turn_frame=TurnFrame(
                raw_text="Use the revised approval and draft the order from it.",
                normalized_text="use the revised approval and draft the order from it.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="use", clause_index=0),
                    CandidateAction(id="a1", verb="draft", clause_index=1),
                ),
                candidate_references=(
                    CandidateReference(id="r0", expression="the revised approval", clause_index=0),
                    CandidateReference(id="r1", expression="it", clause_index=1),
                ),
            ),
            rar_results=(
                RARResolution(
                    reference_expression="the revised approval",
                    outcome=RAROutcome.RESOLVED,
                    candidate_id="approval_revised_2026",
                ),
            ),
            expected_critical_signals=("draft", "use"),
            expected_uncertainty_types=(
                UncertaintyType.OPERATION_TARGET,
            ),
            description="Multi-action turn with anaphora requiring target binding.",
        )
    )

    # 8. Contrast
    cases.append(
        ARNTestCase(
            case_id="A28A-08-CONTRAST",
            category="Contrast",
            user_text="Use the revised approval, not the earlier one.",
            turn_frame=TurnFrame(
                raw_text="Use the revised approval, not the earlier one.",
                normalized_text="use the revised approval, not the earlier one.",
                candidate_actions=(CandidateAction(id="a0", verb="use", clause_index=0),),
                negation_spans=("not the earlier one",),
                candidate_references=(
                    CandidateReference(id="r0", expression="the revised approval", clause_index=0),
                    CandidateReference(id="r1", expression="the earlier one", clause_index=1),
                ),
            ),
            rar_results=(
                RARResolution(
                    reference_expression="the earlier one",
                    outcome=RAROutcome.RESOLVED,
                    candidate_id="approval_old_2025",
                ),
            ),
            expected_critical_signals=("not", "use"),
            expected_uncertainty_types=(
                UncertaintyType.NEGATION_SCOPE,
                UncertaintyType.CONTRAST_RELATIONSHIP,
            ),
            description="Contrastive selection explicitly rejecting an earlier candidate.",
        )
    )

    # 9. Multi-object (TORT-11 Invariant)
    cases.append(
        ARNTestCase(
            case_id="A28A-09-MULTI-OBJECT",
            category="Multi_Object",
            user_text="Sign the affidavit and shred the draft notes.",
            turn_frame=TurnFrame(
                raw_text="Sign the affidavit and shred the draft notes.",
                normalized_text="sign the affidavit and shred the draft notes.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="sign", clause_index=0),
                    CandidateAction(id="a1", verb="shred", clause_index=1),
                ),
                artifact_mentions=("the affidavit", "the draft notes"),
            ),
            expected_critical_signals=("sign", "shred", "and"),
            expected_uncertainty_types=(
                UncertaintyType.OPERATION_TARGET,
            ),
            description="Disjoint multi-target operations with opposing valences (constructive vs destructive).",
        )
    )

    # 10. Ambiguous reference
    cases.append(
        ARNTestCase(
            case_id="A28A-10-AMBIGUOUS-REF",
            category="Ambiguous_Reference",
            user_text="Don't do that yet.",
            turn_frame=TurnFrame(
                raw_text="Don't do that yet.",
                normalized_text="don't do that yet.",
                candidate_actions=(CandidateAction(id="a0", verb="do", clause_index=0),),
                negation_spans=("don't do that yet",),
                candidate_references=(CandidateReference(id="r0", expression="that", clause_index=0),),
            ),
            rar_results=(
                RARResolution(
                    reference_expression="that",
                    outcome=RAROutcome.AMBIGUOUS,
                    ambiguous_candidate_ids=("action_send_email", "action_delete_file"),
                ),
            ),
            expected_critical_signals=("don't", "that"),
            expected_uncertainty_types=(
                UncertaintyType.NEGATION_SCOPE,
                UncertaintyType.UNRESOLVED_REFERENCE,
                UncertaintyType.OPERATION_POLARITY,
            ),
            description="Deictic pronoun 'that' tied to multiple candidates in RAR.",
        )
    )

    # 11. Implicit semantics
    cases.append(
        ARNTestCase(
            case_id="A28A-11-IMPLICIT-SEMANTICS",
            category="Implicit_Semantics",
            user_text="Deal with the Dean's email appropriately.",
            turn_frame=TurnFrame(
                raw_text="Deal with the Dean's email appropriately.",
                normalized_text="deal with the dean's email appropriately.",
                candidate_actions=(CandidateAction(id="a0", verb="deal", clause_index=0),),
                candidate_references=(CandidateReference(id="r0", expression="the Dean's email", clause_index=0),),
            ),
            expected_critical_signals=("appropriately", "deal"),
            expected_uncertainty_types=(
                UncertaintyType.MODIFIER_SCOPE,
            ),
            description="Implicit phrasing requiring concrete operational disambiguation.",
        )
    )

    # 12. Combined / Adversarial
    cases.append(
        ARNTestCase(
            case_id="A28A-12-COMBINED-ADVERSARIAL",
            category="Combined_Adversarial",
            user_text="Sign the amended contract, but don't execute or distribute it until the board approves next Friday.",
            turn_frame=TurnFrame(
                raw_text="Sign the amended contract, but don't execute or distribute it until the board approves next Friday.",
                normalized_text="sign the amended contract, but don't execute or distribute it until the board approves next friday.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="sign", clause_index=0),
                    CandidateAction(id="a1", verb="execute", clause_index=1),
                    CandidateAction(id="a2", verb="distribute", clause_index=1),
                    CandidateAction(id="a3", verb="approve", clause_index=2),
                ),
                negation_spans=("don't execute or distribute it",),
                candidate_references=(
                    CandidateReference(id="r0", expression="the amended contract", clause_index=0),
                    CandidateReference(id="r1", expression="it", clause_index=1),
                ),
                temporal_surface_spans=("until the board approves", "next friday"),
            ),
            rar_results=(
                RARResolution(
                    reference_expression="it",
                    outcome=RAROutcome.RESOLVED,
                    candidate_id="contract_amended_2026",
                ),
            ),
            expected_critical_signals=("don't", "but", "until", "sign", "execute", "distribute"),
            expected_uncertainty_types=(
                UncertaintyType.NEGATION_SCOPE,
                UncertaintyType.OPERATION_POLARITY,
                UncertaintyType.TEMPORAL_DEPENDENCY,
                UncertaintyType.CONTRAST_RELATIONSHIP,
                UncertaintyType.OPERATION_TARGET,
            ),
            description="Complex composite turn with negation, temporal trigger, condition, and multi-targets.",
        )
    )

    return tuple(cases)
