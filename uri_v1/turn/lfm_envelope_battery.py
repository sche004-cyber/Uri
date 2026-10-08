"""LFM2.5-350M Semantic Operating Envelope Qualification Batteries (Batch A2.5 Stage 4).

Defines structured qualification batteries for empirical boundary characterization:
1. Context Envelope Battery (L0 to L7)
2. Noise Sensitivity Controlled Pairs (300 to 1500 tokens)
3. Semantic Complexity Ladder (C0 to C8)
4. Negation Ladder (N1 to N6)
5. Operation Retention Ladder (O-R1 to O-R5)
6. Progressive Feed Width Ladder (O0 to O5)
7. Multi-Mode Comparative Suite (Modes A, B, C, D)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.turn.active_context import (
    ActiveContext,
    ArtifactDescriptor,
    EntityDescriptor,
)
from uri_v1.turn.contracts import (
    IntentFamily,
)
from uri_v1.turn.turn_frame import (
    CandidateAction,
    CandidateReference,
    TurnFrame,
)
from uri_v1.turn.rar_contracts import RARCandidate


@dataclass(frozen=True)
class EnvelopeTestCase:
    case_id: str
    category: str
    user_text: str
    expected_goal: str
    expected_intent_family: IntentFamily
    expected_requested_ops: Tuple[str, ...]
    expected_prohibited_ops: Tuple[str, ...]
    expected_reference_expression: Optional[str] = None
    expected_target_id: Optional[str] = None
    expected_constraints: Tuple[str, ...] = ()
    expected_timing_condition: Optional[str] = None
    context_tokens_approx: int = 0
    relevant_tokens_approx: int = 0
    noise_tokens_approx: int = 0
    turn_frame: Optional[TurnFrame] = None
    active_context: Optional[ActiveContext] = None
    candidate_pool: Tuple[RARCandidate, ...] = ()
    description: str = ""


# ---------------------------------------------------------------------------
# Battery 1: Context Envelope Experiment (L0 to L7)
# Fixed semantic task: "Review the draft order but do not send it."
# ---------------------------------------------------------------------------

_CORE_USER_TEXT = "Review the draft order but do not send it."
_CORE_REQ_OPS = ("review",)
_CORE_PRO_OPS = ("send",)
_CORE_TARGET_ID = "doc_draft_order_2026"
_CORE_EXPR = "the draft order"

_BASE_CANDIDATE = RARCandidate(
    id=_CORE_TARGET_ID,
    candidate_type="document",
    title="Draft Order 2026",
    exact_aliases=("draft order", "order draft"),
    recency_rank=1,
)

def build_context_envelope_battery() -> Tuple[EnvelopeTestCase, ...]:
    cases: List[EnvelopeTestCase] = []

    # L0: user message only
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L0",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            context_tokens_approx=15,
            relevant_tokens_approx=15,
            noise_tokens_approx=0,
            description="L0: Raw user message only, zero external context.",
        )
    )

    # L1: + minimal TurnFrame
    tf_l1 = TurnFrame(
        raw_text=_CORE_USER_TEXT,
        normalized_text=_CORE_USER_TEXT.lower(),
        candidate_actions=(
            CandidateAction(id="act1", verb="review", clause_index=0),
            CandidateAction(id="act2", verb="send", clause_index=0),
        ),
        candidate_references=(
            CandidateReference(id="ref1", expression=_CORE_EXPR, clause_index=0),
        ),
        negation_spans=("do not send it",),
    )
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L1",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            context_tokens_approx=45,
            relevant_tokens_approx=45,
            noise_tokens_approx=0,
            turn_frame=tf_l1,
            description="L1: Minimal TurnFrame candidate actions and negation spans.",
        )
    )

    # L2: + deterministic RAR anchors
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L2",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            expected_reference_expression=_CORE_EXPR,
            expected_target_id=_CORE_TARGET_ID,
            context_tokens_approx=85,
            relevant_tokens_approx=85,
            noise_tokens_approx=0,
            turn_frame=tf_l1,
            candidate_pool=(_BASE_CANDIDATE,),
            description="L2: TurnFrame + deterministic RAR resolved anchor.",
        )
    )

    # L3: + compact relevant ActiveContext
    act_l3 = ActiveContext(
        active_artifacts=(
            ArtifactDescriptor(id=_CORE_TARGET_ID, name="Draft Order 2026.docx", artifact_type="document"),
        ),
        active_topic="Hostel Regulations Order",
    )
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L3",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            expected_reference_expression=_CORE_EXPR,
            expected_target_id=_CORE_TARGET_ID,
            context_tokens_approx=140,
            relevant_tokens_approx=140,
            noise_tokens_approx=0,
            turn_frame=tf_l1,
            active_context=act_l3,
            candidate_pool=(_BASE_CANDIDATE,),
            description="L3: Compact relevant ActiveContext (active document & section).",
        )
    )

    # L4: + additional relevant entities/artifacts (4-5 entities in active memory)
    cands_l4 = (
        _BASE_CANDIDATE,
        RARCandidate(id="doc_prior_order_2025", candidate_type="document", title="Prior Order 2025", recency_rank=2),
        RARCandidate(id="contact_warden", candidate_type="person", title="Chief Warden Office", recency_rank=3),
        RARCandidate(id="tmpl_sanction", candidate_type="template", title="Sanction Template", recency_rank=4),
    )
    act_l4 = ActiveContext(
        active_artifacts=(
            ArtifactDescriptor(id=_CORE_TARGET_ID, name="Draft Order 2026.docx", artifact_type="document"),
            ArtifactDescriptor(id="doc_prior_order_2025", name="Prior Order 2025", artifact_type="document"),
        ),
        active_entities=(
            EntityDescriptor(id="contact_warden", name="Chief Warden Office", category="person"),
        ),
    )
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L4",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            expected_reference_expression=_CORE_EXPR,
            expected_target_id=_CORE_TARGET_ID,
            context_tokens_approx=240,
            relevant_tokens_approx=240,
            noise_tokens_approx=0,
            turn_frame=tf_l1,
            active_context=act_l4,
            candidate_pool=cands_l4,
            description="L4: 4 related active entities in working memory.",
        )
    )

    # L5: + plausible distractors (8 entities with similar filenames/tokens)
    distractors_l5 = [
        RARCandidate(id=f"doc_draft_sub_{i}", candidate_type="document", title=f"Draft Submissions Part {i}", recency_rank=5+i)
        for i in range(1, 5)
    ]
    cands_l5 = cands_l4 + tuple(distractors_l5)
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L5",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            expected_reference_expression=_CORE_EXPR,
            expected_target_id=_CORE_TARGET_ID,
            context_tokens_approx=420,
            relevant_tokens_approx=240,
            noise_tokens_approx=180,
            turn_frame=tf_l1,
            active_context=act_l4,
            candidate_pool=cands_l5,
            description="L5: 8 total candidates including plausible lexical distractors.",
        )
    )

    # L6: + larger working-session context (15 items, prior turn summaries)
    distractors_l6 = [
        RARCandidate(id=f"doc_hist_{i}", candidate_type="document", title=f"Historical Meeting Record {i}", recency_rank=10+i)
        for i in range(1, 8)
    ]
    cands_l6 = cands_l5 + tuple(distractors_l6)
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L6",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            expected_reference_expression=_CORE_EXPR,
            expected_target_id=_CORE_TARGET_ID,
            context_tokens_approx=680,
            relevant_tokens_approx=240,
            noise_tokens_approx=440,
            turn_frame=tf_l1,
            active_context=act_l4,
            candidate_pool=cands_l6,
            description="L6: 15 items in candidate memory with prior turn summaries.",
        )
    )

    # L7: + increasingly irrelevant/noisy context (25 items, unrelated code snippets, system logs)
    distractors_l7 = [
        RARCandidate(id=f"log_audit_{i}", candidate_type="system_log", title=f"Audit Event Log 2026-09-22-00{i}.log", recency_rank=20+i)
        for i in range(1, 11)
    ]
    cands_l7 = cands_l6 + tuple(distractors_l7)
    cases.append(
        EnvelopeTestCase(
            case_id="ENV-L7",
            category="Context_Envelope",
            user_text=_CORE_USER_TEXT,
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=_CORE_REQ_OPS,
            expected_prohibited_ops=_CORE_PRO_OPS,
            expected_reference_expression=_CORE_EXPR,
            expected_target_id=_CORE_TARGET_ID,
            context_tokens_approx=1150,
            relevant_tokens_approx=240,
            noise_tokens_approx=910,
            turn_frame=tf_l1,
            active_context=act_l4,
            candidate_pool=cands_l7,
            description="L7: 25 items with system audit logs and noisy background items.",
        )
    )

    return tuple(cases)


# ---------------------------------------------------------------------------
# Battery 2: Noise Sensitivity Controlled Pairs (Section 9)
# ---------------------------------------------------------------------------

def build_noise_sensitivity_battery() -> Tuple[EnvelopeTestCase, ...]:
    cases: List[EnvelopeTestCase] = []

    # Noise 1: 300 useful tokens
    cases.append(
        EnvelopeTestCase(
            case_id="NOISE-0",
            category="Noise_Sensitivity",
            user_text="Draft a formal response to the warden citing regulations, but do not send it.",
            expected_goal="Draft formal response to warden",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("send",),
            context_tokens_approx=300,
            relevant_tokens_approx=300,
            noise_tokens_approx=0,
            description="300 useful context tokens, 0 noise tokens.",
        )
    )

    # Noise 2: 300 useful + 300 noise
    cases.append(
        EnvelopeTestCase(
            case_id="NOISE-300",
            category="Noise_Sensitivity",
            user_text="Draft a formal response to the warden citing regulations, but do not send it.",
            expected_goal="Draft formal response to warden",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("send",),
            context_tokens_approx=600,
            relevant_tokens_approx=300,
            noise_tokens_approx=300,
            description="300 useful tokens + 300 irrelevant system noise tokens.",
        )
    )

    # Noise 3: 300 useful + 600 noise
    cases.append(
        EnvelopeTestCase(
            case_id="NOISE-600",
            category="Noise_Sensitivity",
            user_text="Draft a formal response to the warden citing regulations, but do not send it.",
            expected_goal="Draft formal response to warden",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("send",),
            context_tokens_approx=900,
            relevant_tokens_approx=300,
            noise_tokens_approx=600,
            description="300 useful tokens + 600 irrelevant system noise tokens.",
        )
    )

    # Noise 4: 300 useful + 1200 noise
    cases.append(
        EnvelopeTestCase(
            case_id="NOISE-1200",
            category="Noise_Sensitivity",
            user_text="Draft a formal response to the warden citing regulations, but do not send it.",
            expected_goal="Draft formal response to warden",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("send",),
            context_tokens_approx=1500,
            relevant_tokens_approx=300,
            noise_tokens_approx=1200,
            description="300 useful tokens + 1200 irrelevant system noise tokens.",
        )
    )

    return tuple(cases)


# ---------------------------------------------------------------------------
# Battery 3: Semantic Complexity Ladder (C0 to C8) (Section 10)
# ---------------------------------------------------------------------------

def build_complexity_ladder_battery() -> Tuple[EnvelopeTestCase, ...]:
    return (
        EnvelopeTestCase(
            case_id="CMPLX-C0",
            category="Complexity_Ladder",
            user_text="Open the calculator.",
            expected_goal="Open calculator",
            expected_intent_family=IntentFamily.EXECUTE,
            expected_requested_ops=("open",),
            expected_prohibited_ops=(),
            description="C0: Single positive operation.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C1",
            category="Complexity_Ladder",
            user_text="Draft the memo and summarize it.",
            expected_goal="Draft and summarize memo",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("draft", "summarize"),
            expected_prohibited_ops=(),
            description="C1: Two positive operations.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C2",
            category="Complexity_Ladder",
            user_text="Compare the report, revise the numbers, and archive it.",
            expected_goal="Compare, revise, and archive report",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("compare", "revise", "archive"),
            expected_prohibited_ops=(),
            description="C2: Three operations.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C3",
            category="Complexity_Ladder",
            user_text="Draft the email but do not send it.",
            expected_goal="Draft email without sending",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("send",),
            description="C3: One positive + one prohibited operation.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C4",
            category="Complexity_Ladder",
            user_text="Compare the orders and revise the draft, but do not send or delete anything.",
            expected_goal="Compare orders and revise draft without sending or deleting",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("compare", "revise"),
            expected_prohibited_ops=("send", "delete"),
            description="C4: Multiple positive + multiple prohibited operations.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C5",
            category="Complexity_Ladder",
            user_text="Send the email only after the warden approves it.",
            expected_goal="Send email after approval",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("send",),
            expected_prohibited_ops=(),
            expected_timing_condition="after approval",
            description="C5: Conditional operation with temporal guard.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C6",
            category="Complexity_Ladder",
            user_text="Review the spreadsheet and format the document.",
            expected_goal="Review spreadsheet and format document",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review", "format"),
            expected_prohibited_ops=(),
            description="C6: Multiple distinct targets.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C7",
            category="Complexity_Ladder",
            user_text="Compare the earlier order with the revised order and copy the totals into the invoice.",
            expected_goal="Compare orders and copy totals to invoice",
            expected_intent_family=IntentFamily.COMPARE,
            expected_requested_ops=("compare", "copy"),
            expected_prohibited_ops=(),
            description="C7: Cross-target relational dataflow and binding.",
        ),
        EnvelopeTestCase(
            case_id="CMPLX-C8",
            category="Complexity_Ladder",
            user_text="Don't send the previous version before Friday; revise the draft, compare figures with the ledger, and archive the old notes.",
            expected_goal="Revise draft, compare figures, and archive notes without sending previous version before Friday",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("revise", "compare", "archive"),
            expected_prohibited_ops=("send",),
            expected_timing_condition="before Friday",
            description="C8: Multi-operation + negation + temporal constraint + multi-target binding.",
        ),
    )


# ---------------------------------------------------------------------------
# Battery 4: Negation Ladder (N1 to N6) (Section 11)
# ---------------------------------------------------------------------------

def build_negation_ladder_battery() -> Tuple[EnvelopeTestCase, ...]:
    return (
        EnvelopeTestCase(
            case_id="NEG-N1",
            category="Negation_Ladder",
            user_text="Don't send it.",
            expected_goal="Do not send",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=(),
            expected_prohibited_ops=("send",),
            description="N1: Simple prohibition.",
        ),
        EnvelopeTestCase(
            case_id="NEG-N2",
            category="Negation_Ladder",
            user_text="Don't send it; draft it.",
            expected_goal="Draft without sending",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("send",),
            description="N2: Contrastive negation (prohibit X, request Y).",
        ),
        EnvelopeTestCase(
            case_id="NEG-N3",
            category="Negation_Ladder",
            user_text="Don't send or delete it; only revise it.",
            expected_goal="Revise without sending or deleting",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("revise",),
            expected_prohibited_ops=("send", "delete"),
            description="N3: Multi-prohibition with exclusive positive action.",
        ),
        EnvelopeTestCase(
            case_id="NEG-N4",
            category="Negation_Ladder",
            user_text="Send it only after approval.",
            expected_goal="Send only after approval",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("send",),
            expected_prohibited_ops=(),
            expected_timing_condition="after approval",
            description="N4: Conditional execution barrier (do not send until approval).",
        ),
        EnvelopeTestCase(
            case_id="NEG-N5",
            category="Negation_Ladder",
            user_text="Do not send the previous version; send the revised version.",
            expected_goal="Send revised version instead of previous version",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("send",),
            expected_prohibited_ops=("send",),
            description="N5: Displaced version negation (prohibit target A, execute target B for same verb).",
        ),
        EnvelopeTestCase(
            case_id="NEG-N6",
            category="Negation_Ladder",
            user_text="Don't summarize it unless the figures differ.",
            expected_goal="Summarize only if figures differ",
            expected_intent_family=IntentFamily.ANALYZE,
            expected_requested_ops=(),
            expected_prohibited_ops=("summarize",),
            expected_timing_condition="unless figures differ",
            description="N6: Exception-condition negation ('unless' clause).",
        ),
    )


# ---------------------------------------------------------------------------
# Battery 5: Operation Retention Ladder (O-R1 to O-R5) (Section 12)
# ---------------------------------------------------------------------------

def build_operation_retention_battery() -> Tuple[EnvelopeTestCase, ...]:
    return (
        EnvelopeTestCase(
            case_id="RET-OR1",
            category="Operation_Retention",
            user_text="Draft the response.",
            expected_goal="Draft response",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=(),
            description="O-R1: 1 operation.",
        ),
        EnvelopeTestCase(
            case_id="RET-OR2",
            category="Operation_Retention",
            user_text="Draft the response and shorten it.",
            expected_goal="Draft response and shorten it",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("draft", "shorten"),
            expected_prohibited_ops=(),
            description="O-R2: 2 operations.",
        ),
        EnvelopeTestCase(
            case_id="RET-OR3",
            category="Operation_Retention",
            user_text="Compare the guidelines, draft the response, and shorten it.",
            expected_goal="Compare guidelines, draft response, and shorten",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("compare", "draft", "shorten"),
            expected_prohibited_ops=(),
            description="O-R3: 3 operations.",
        ),
        EnvelopeTestCase(
            case_id="RET-OR4",
            category="Operation_Retention",
            user_text="Compare the guidelines, revise the text, shorten it, and send it.",
            expected_goal="Compare guidelines, revise text, shorten, and send",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("compare", "revise", "shorten", "send"),
            expected_prohibited_ops=(),
            description="O-R4: 4 operations.",
        ),
        EnvelopeTestCase(
            case_id="RET-OR5",
            category="Operation_Retention",
            user_text="Compare the guidelines, revise the text, draft the summary, send it, and archive the notes.",
            expected_goal="Compare guidelines, revise text, draft summary, send, and archive notes",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("compare", "revise", "draft", "send", "archive"),
            expected_prohibited_ops=(),
            description="O-R5: 5 operations.",
        ),
    )


# ---------------------------------------------------------------------------
# Battery 6: Progressive Feed Width (O0 to O5) (Section 15)
# ---------------------------------------------------------------------------

def build_progressive_feed_width_battery() -> Tuple[EnvelopeTestCase, ...]:
    return (
        EnvelopeTestCase(
            case_id="WIDTH-O0",
            category="Progressive_Width",
            user_text="Review the draft order but do not send it.",
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            description="O0: Raw clause only.",
        ),
        EnvelopeTestCase(
            case_id="WIDTH-O1",
            category="Progressive_Width",
            user_text="Review the draft order but do not send it.",
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            description="O1: Raw clause + candidate action verbs (['review', 'send']).",
        ),
        EnvelopeTestCase(
            case_id="WIDTH-O2",
            category="Progressive_Width",
            user_text="Review the draft order but do not send it.",
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            description="O2: + resolved RAR anchor ID ('doc_draft_order_2026').",
        ),
        EnvelopeTestCase(
            case_id="WIDTH-O3",
            category="Progressive_Width",
            user_text="Review the draft order but do not send it.",
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            description="O3: + compact active-context labels ('Draft Order 2026.docx').",
        ),
        EnvelopeTestCase(
            case_id="WIDTH-O4",
            category="Progressive_Width",
            user_text="Review the draft order but do not send it.",
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            description="O4: + extra candidate metadata (file size, modified timestamp, author).",
        ),
        EnvelopeTestCase(
            case_id="WIDTH-O5",
            category="Progressive_Width",
            user_text="Review the draft order but do not send it.",
            expected_goal="Review draft order",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            description="O5: + distractors (unrelated system audit events).",
        ),
    )


# ---------------------------------------------------------------------------
# Complete Master Corpus Assembly
# ---------------------------------------------------------------------------

def get_stage4_full_battery() -> Dict[str, Tuple[EnvelopeTestCase, ...]]:
    """Returns all 6 qualification batteries structured for Stage 4 evaluation."""
    return {
        "context_envelope": build_context_envelope_battery(),
        "noise_sensitivity": build_noise_sensitivity_battery(),
        "complexity_ladder": build_complexity_ladder_battery(),
        "negation_ladder": build_negation_ladder_battery(),
        "operation_retention": build_operation_retention_battery(),
        "progressive_feed_width": build_progressive_feed_width_battery(),
    }
