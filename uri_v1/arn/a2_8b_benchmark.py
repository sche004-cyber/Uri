"""M35 URIv1 Batch A2.8B — RAR + ARN Model Amplification Benchmark Suite.

Defines the 12 frozen semantic benchmark test cases with comprehensive ground truth
for all 13 evaluation dimensions across Modes A, B, C, and D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.rar_contracts import RARCandidate, RAROutcome, RARResolution
from uri_v1.turn.turn_frame import CandidateAction, CandidateReference, TurnFrame
from uri_v1.arn.uncertainty_contracts import UncertaintyType


@dataclass(frozen=True)
class AmplificationTestCase:
    """Full specification of an amplification benchmark case."""

    case_id: str
    category: str
    user_text: str
    expected_goal: str
    expected_requested_ops: Tuple[str, ...]
    expected_prohibited_ops: Tuple[str, ...]
    expected_target_bindings: Dict[str, str] = field(default_factory=dict)
    expected_condition: Optional[str] = None
    expected_temporal_trigger: Optional[str] = None
    expected_reference_expression: Optional[str] = None
    expected_target_id: Optional[str] = None
    is_ambiguous_ref: bool = False
    turn_frame: Optional[TurnFrame] = None
    active_context: Optional[ActiveContext] = None
    candidate_pool: Tuple[RARCandidate, ...] = ()
    rar_results: Tuple[RARResolution, ...] = ()
    description: str = ""


def build_a2_8b_benchmark_suite() -> Tuple[AmplificationTestCase, ...]:
    """Builds the 12 frozen benchmark cases for model amplification qualification."""
    cases: List[AmplificationTestCase] = []

    # -----------------------------------------------------------------------
    # 1. Simple Instruction
    # -----------------------------------------------------------------------
    cases.append(
        AmplificationTestCase(
            case_id="A28B-01-SIMPLE",
            category="Simple",
            user_text="Review the email.",
            expected_goal="Review email",
            expected_requested_ops=("review",),
            expected_prohibited_ops=(),
            expected_target_bindings={"review": "the email"},
            turn_frame=TurnFrame(
                raw_text="Review the email.",
                normalized_text="review the email.",
                candidate_actions=(CandidateAction(id="a0", verb="review", clause_index=0),),
                candidate_references=(CandidateReference(id="r0", expression="the email", clause_index=0),),
            ),
            candidate_pool=(
                RARCandidate(id="email_dean_incoming", candidate_type="email", title="Dean Memo", exact_aliases=("the email", "email"), recency_rank=1),
            ),
            rar_results=(
                RARResolution(reference_expression="the email", outcome=RAROutcome.RESOLVED, candidate_id="email_dean_incoming"),
            ),
            description="Direct atomic instruction without constraints, negation, or ambiguity.",
        )
    )

    # -----------------------------------------------------------------------
    # 2. Reference Resolution
    # -----------------------------------------------------------------------
    cand_appr = RARCandidate(id="approval_revised_2026", candidate_type="document", title="Revised Approval Note", exact_aliases=("revised approval", "the revised approval"), recency_rank=1)
    cand_earl = RARCandidate(id="approval_earlier_2026", candidate_type="document", title="Earlier Approval Note", exact_aliases=("earlier approval", "earlier one"), recency_rank=2)

    cases.append(
        AmplificationTestCase(
            case_id="A28B-02-REFERENCE",
            category="Reference",
            user_text="Use the revised approval and draft the order from it.",
            expected_goal="Draft order from revised approval",
            expected_requested_ops=("use", "draft"),
            expected_prohibited_ops=(),
            expected_target_bindings={"use": "approval_revised_2026", "draft": "the order"},
            expected_reference_expression="the revised approval",
            expected_target_id="approval_revised_2026",
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
            candidate_pool=(cand_appr, cand_earl),
            rar_results=(
                RARResolution(reference_expression="the revised approval", outcome=RAROutcome.RESOLVED, candidate_id="approval_revised_2026"),
                RARResolution(reference_expression="it", outcome=RAROutcome.RESOLVED, candidate_id="approval_revised_2026"),
            ),
            description="Cross-clause anaphoric reference requiring entity binding.",
        )
    )

    # -----------------------------------------------------------------------
    # 3. Explicit Negation
    # -----------------------------------------------------------------------
    cases.append(
        AmplificationTestCase(
            case_id="A28B-03-EXPLICIT-NEG",
            category="Explicit_Negation",
            user_text="Draft the reply but don't send it.",
            expected_goal="Draft reply without sending",
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("send",),
            expected_target_bindings={"draft": "the reply", "send": "the reply"},
            turn_frame=TurnFrame(
                raw_text="Draft the reply but don't send it.",
                normalized_text="draft the reply but don't send it.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="draft", clause_index=0),
                    CandidateAction(id="a1", verb="send", clause_index=1),
                ),
                negation_spans=("don't send it",),
                candidate_references=(
                    CandidateReference(id="r0", expression="the reply", clause_index=0),
                    CandidateReference(id="r1", expression="it", clause_index=1),
                ),
            ),
            candidate_pool=(
                RARCandidate(id="msg_reply_draft", candidate_type="message", title="Draft Reply", exact_aliases=("the reply", "reply"), recency_rank=1),
            ),
            rar_results=(
                RARResolution(reference_expression="the reply", outcome=RAROutcome.RESOLVED, candidate_id="msg_reply_draft"),
                RARResolution(reference_expression="it", outcome=RAROutcome.RESOLVED, candidate_id="msg_reply_draft"),
            ),
            description="Directive requesting drafting while explicitly forbidding transmission.",
        )
    )

    # -----------------------------------------------------------------------
    # 4. Multiple Negation
    # -----------------------------------------------------------------------
    cases.append(
        AmplificationTestCase(
            case_id="A28B-04-MULTI-NEG",
            category="Multiple_Negation",
            user_text="Review it, don't send it, and don't upload anything.",
            expected_goal="Review item without sending or uploading",
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send", "upload"),
            expected_target_bindings={"review": "it", "send": "it", "upload": "anything"},
            turn_frame=TurnFrame(
                raw_text="Review it, don't send it, and don't upload anything.",
                normalized_text="review it, don't send it, and don't upload anything.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="review", clause_index=0),
                    CandidateAction(id="a1", verb="send", clause_index=1),
                    CandidateAction(id="a2", verb="upload", clause_index=2),
                ),
                negation_spans=("don't send it", "don't upload anything"),
                candidate_references=(CandidateReference(id="r0", expression="it", clause_index=0),),
            ),
            candidate_pool=(
                RARCandidate(id="doc_memo_2026", candidate_type="document", title="Confidential Memo", exact_aliases=("it",), recency_rank=1),
            ),
            rar_results=(
                RARResolution(reference_expression="it", outcome=RAROutcome.RESOLVED, candidate_id="doc_memo_2026"),
            ),
            description="Multi-action turn with multiple negation scopes prohibiting two separate actions.",
        )
    )

    # -----------------------------------------------------------------------
    # 5. Conditional Dependency
    # -----------------------------------------------------------------------
    cases.append(
        AmplificationTestCase(
            case_id="A28B-05-CONDITIONAL",
            category="Conditional",
            user_text="Send it if the Dean approves.",
            expected_goal="Send contingent upon Dean approval",
            expected_requested_ops=("send",),
            expected_prohibited_ops=(),
            expected_condition="the Dean approves",
            expected_target_bindings={"send": "it"},
            turn_frame=TurnFrame(
                raw_text="Send it if the Dean approves.",
                normalized_text="send it if the dean approves.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="send", clause_index=0),
                    CandidateAction(id="a1", verb="approve", clause_index=1),
                ),
                candidate_references=(CandidateReference(id="r0", expression="it", clause_index=0),),
            ),
            candidate_pool=(
                RARCandidate(id="doc_report_2026", candidate_type="document", title="Annual Report", exact_aliases=("it",), recency_rank=1),
            ),
            rar_results=(
                RARResolution(reference_expression="it", outcome=RAROutcome.RESOLVED, candidate_id="doc_report_2026"),
            ),
            description="Action contingent upon an external approval condition.",
        )
    )

    # -----------------------------------------------------------------------
    # 6. Unless (Negative Condition)
    # -----------------------------------------------------------------------
    cases.append(
        AmplificationTestCase(
            case_id="A28B-06-UNLESS",
            category="Unless",
            user_text="Don't send it unless the Dean approves.",
            expected_goal="Prohibit sending unless Dean approves",
            expected_requested_ops=(),
            expected_prohibited_ops=("send",),
            expected_condition="unless the Dean approves",
            expected_target_bindings={"send": "it"},
            turn_frame=TurnFrame(
                raw_text="Don't send it unless the Dean approves.",
                normalized_text="don't send it unless the dean approves.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="send", clause_index=0),
                    CandidateAction(id="a1", verb="approve", clause_index=1),
                ),
                negation_spans=("don't send it",),
                candidate_references=(CandidateReference(id="r0", expression="it", clause_index=0),),
            ),
            candidate_pool=(
                RARCandidate(id="doc_report_2026", candidate_type="document", title="Annual Report", exact_aliases=("it",), recency_rank=1),
            ),
            rar_results=(
                RARResolution(reference_expression="it", outcome=RAROutcome.RESOLVED, candidate_id="doc_report_2026"),
            ),
            description="Default prohibition qualified by an exception condition.",
        )
    )

    # -----------------------------------------------------------------------
    # 7. Temporal Deferral
    # -----------------------------------------------------------------------
    cases.append(
        AmplificationTestCase(
            case_id="A28B-07-TEMPORAL",
            category="Temporal",
            user_text="Hold the announcement until next Friday.",
            expected_goal="Hold announcement until next Friday",
            expected_requested_ops=("hold",),
            expected_prohibited_ops=("announce",),
            expected_temporal_trigger="until next Friday",
            expected_target_bindings={"hold": "the announcement"},
            turn_frame=TurnFrame(
                raw_text="Hold the announcement until next Friday.",
                normalized_text="hold the announcement until next friday.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="hold", clause_index=0),
                    CandidateAction(id="a1", verb="announce", clause_index=0),
                ),
                candidate_references=(CandidateReference(id="r0", expression="the announcement", clause_index=0),),
                temporal_surface_spans=("until next friday",),
            ),
            candidate_pool=(
                RARCandidate(id="announcement_press_release", candidate_type="document", title="Press Release", exact_aliases=("the announcement", "announcement"), recency_rank=1),
            ),
            rar_results=(
                RARResolution(reference_expression="the announcement", outcome=RAROutcome.RESOLVED, candidate_id="announcement_press_release"),
            ),
            description="Temporal gating deferring execution until a future time trigger.",
        )
    )

    # -----------------------------------------------------------------------
    # 8. Contrastive Selection
    # -----------------------------------------------------------------------
    cases.append(
        AmplificationTestCase(
            case_id="A28B-08-CONTRAST",
            category="Contrast",
            user_text="Use the revised approval, not the earlier one.",
            expected_goal="Use revised approval excluding earlier approval",
            expected_requested_ops=("use",),
            expected_prohibited_ops=(),
            expected_target_bindings={"use": "approval_revised_2026"},
            expected_reference_expression="the revised approval",
            expected_target_id="approval_revised_2026",
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
            candidate_pool=(cand_appr, cand_earl),
            rar_results=(
                RARResolution(reference_expression="the revised approval", outcome=RAROutcome.RESOLVED, candidate_id="approval_revised_2026"),
                RARResolution(reference_expression="the earlier one", outcome=RAROutcome.RESOLVED, candidate_id="approval_earlier_2026"),
            ),
            description="Contrastive selection explicitly adopting one candidate and excluding another.",
        )
    )

    # -----------------------------------------------------------------------
    # 9. Multi-Object Disjoint Coupling (TORT-11 Invariant)
    # -----------------------------------------------------------------------
    cand_aff = RARCandidate(id="doc_affidavit_signed", candidate_type="document", title="Affidavit", exact_aliases=("the affidavit", "affidavit"), recency_rank=1)
    cand_notes = RARCandidate(id="doc_draft_notes", candidate_type="document", title="Draft Notes", exact_aliases=("the draft notes", "draft notes"), recency_rank=2)

    cases.append(
        AmplificationTestCase(
            case_id="A28B-09-MULTI-OBJECT",
            category="Multi_Object",
            user_text="Sign the affidavit and shred the draft notes.",
            expected_goal="Sign affidavit and shred draft notes",
            expected_requested_ops=("sign", "shred"),
            expected_prohibited_ops=(),
            expected_target_bindings={"sign": "doc_affidavit_signed", "shred": "doc_draft_notes"},
            turn_frame=TurnFrame(
                raw_text="Sign the affidavit and shred the draft notes.",
                normalized_text="sign the affidavit and shred the draft notes.",
                candidate_actions=(
                    CandidateAction(id="a0", verb="sign", clause_index=0),
                    CandidateAction(id="a1", verb="shred", clause_index=1),
                ),
                artifact_mentions=("the affidavit", "the draft notes"),
            ),
            candidate_pool=(cand_aff, cand_notes),
            rar_results=(
                RARResolution(reference_expression="the affidavit", outcome=RAROutcome.RESOLVED, candidate_id="doc_affidavit_signed"),
                RARResolution(reference_expression="the draft notes", outcome=RAROutcome.RESOLVED, candidate_id="doc_draft_notes"),
            ),
            description="Multi-action turn with opposing operation valences requiring strict target pairing.",
        )
    )

    # -----------------------------------------------------------------------
    # 10. Ambiguous Reference (Honest Uncertainty)
    # -----------------------------------------------------------------------
    cand_email_act = RARCandidate(id="action_send_email", candidate_type="action", title="Send Email Action", exact_aliases=("that",), recency_rank=1)
    cand_file_act = RARCandidate(id="action_delete_file", candidate_type="action", title="Delete File Action", exact_aliases=("that",), recency_rank=1)

    cases.append(
        AmplificationTestCase(
            case_id="A28B-10-AMBIGUOUS-REF",
            category="Ambiguous_Reference",
            user_text="Don't do that yet.",
            expected_goal="Prohibit action until later",
            expected_requested_ops=(),
            expected_prohibited_ops=("do",),
            expected_temporal_trigger="yet",
            is_ambiguous_ref=True,
            turn_frame=TurnFrame(
                raw_text="Don't do that yet.",
                normalized_text="don't do that yet.",
                candidate_actions=(CandidateAction(id="a0", verb="do", clause_index=0),),
                negation_spans=("don't do that yet",),
                candidate_references=(CandidateReference(id="r0", expression="that", clause_index=0),),
            ),
            candidate_pool=(cand_email_act, cand_file_act),
            rar_results=(
                RARResolution(
                    reference_expression="that",
                    outcome=RAROutcome.AMBIGUOUS,
                    ambiguous_candidate_ids=("action_send_email", "action_delete_file"),
                ),
            ),
            description="Deictic pronoun tied between candidates; model must honestly surface ambiguity without guessing.",
        )
    )

    # -----------------------------------------------------------------------
    # 11. Implicit Semantics
    # -----------------------------------------------------------------------
    cand_email_dean = RARCandidate(id="email_dean_unread", candidate_type="email", title="Dean Unread Email", exact_aliases=("the Dean's email", "Dean's email"), recency_rank=1)

    cases.append(
        AmplificationTestCase(
            case_id="A28B-11-IMPLICIT-SEMANTICS",
            category="Implicit_Semantics",
            user_text="Deal with the Dean's email appropriately.",
            expected_goal="Handle Dean's email appropriately",
            expected_requested_ops=("deal",),
            expected_prohibited_ops=(),
            expected_target_bindings={"deal": "email_dean_unread"},
            turn_frame=TurnFrame(
                raw_text="Deal with the Dean's email appropriately.",
                normalized_text="deal with the dean's email appropriately.",
                candidate_actions=(CandidateAction(id="a0", verb="deal", clause_index=0),),
                candidate_references=(CandidateReference(id="r0", expression="the Dean's email", clause_index=0),),
            ),
            candidate_pool=(cand_email_dean,),
            rar_results=(
                RARResolution(reference_expression="the Dean's email", outcome=RAROutcome.RESOLVED, candidate_id="email_dean_unread"),
            ),
            description="Vague qualifier ('appropriately') requiring operational clarification or safe inspection.",
        )
    )

    # -----------------------------------------------------------------------
    # 12. Combined / Adversarial
    # -----------------------------------------------------------------------
    cand_contract = RARCandidate(id="contract_amended_2026", candidate_type="contract", title="Amended Contract", exact_aliases=("the amended contract", "amended contract", "it"), recency_rank=1)

    cases.append(
        AmplificationTestCase(
            case_id="A28B-12-COMBINED-ADVERSARIAL",
            category="Combined_Adversarial",
            user_text="Sign the amended contract, but don't execute or distribute it until the board approves next Friday.",
            expected_goal="Sign contract while deferring execution and distribution until board approval next Friday",
            expected_requested_ops=("sign",),
            expected_prohibited_ops=("execute", "distribute"),
            expected_condition="until the board approves",
            expected_temporal_trigger="next Friday",
            expected_target_bindings={
                "sign": "contract_amended_2026",
                "execute": "contract_amended_2026",
                "distribute": "contract_amended_2026",
            },
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
            candidate_pool=(cand_contract,),
            rar_results=(
                RARResolution(reference_expression="the amended contract", outcome=RAROutcome.RESOLVED, candidate_id="contract_amended_2026"),
                RARResolution(reference_expression="it", outcome=RAROutcome.RESOLVED, candidate_id="contract_amended_2026"),
            ),
            description="Combined multi-operation, negation, temporal constraint, condition, and pronoun resolution.",
        )
    )

    return tuple(cases)
