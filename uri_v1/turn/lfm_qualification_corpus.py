"""Qualification Corpus for M35 URIv1 Batch A2.5 Stage 3.

Contains 3 evaluation tranches:
- Tranche A: 18 baseline semantic prompts (R1-R10, S1-S8) reused from A2-family corpus.
- Tranche B: 6 active-context fixtures (C1-C6) from A2.3.
- Tranche C: 16 RAR Residual Stress cases (T1-T16) testing residual semantic burden
  (negation, multi-target operation binding, ambiguity preservation, constraint handling).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor


class ContextCategory(str, Enum):
    SELF_CONTAINED = "SELF_CONTAINED"
    CURRENT_TURN_CONTEXT = "CURRENT_TURN_CONTEXT"
    ACTIVE_CONTEXT_REQUIRED = "ACTIVE_CONTEXT_REQUIRED"
    STEP2_CONTEXT_REQUIRED = "STEP2_CONTEXT_REQUIRED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class LFMQualificationCase:
    """A test case for LFM2.5-350M semantic decoder qualification."""

    id: str
    text: str
    category: ContextCategory
    expected_goal_keywords: Tuple[str, ...]
    expected_intent: str
    expected_requested_ops: Tuple[str, ...]
    expected_prohibited_ops: Tuple[str, ...]
    expected_references: Tuple[str, ...]
    has_negation: bool = False
    context: Optional[ActiveContext] = None
    expected_resolved_target: Optional[str] = None
    expected_operation_bindings: Tuple[Tuple[str, str], ...] = ()
    expected_ambiguity: bool = False
    notes: str = ""


# ---------------------------------------------------------------------------
# Tranche A: 18 Baseline Semantic Prompts (R1..R10, S1..S8)
# ---------------------------------------------------------------------------

TRANCHE_A_CASES: Tuple[LFMQualificationCase, ...] = (
    LFMQualificationCase(
        id="R1",
        text="Convert this to PDF.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        expected_goal_keywords=("convert", "pdf"),
        expected_intent="modify",
        expected_requested_ops=("convert",),
        expected_prohibited_ops=(),
        expected_references=("this",),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="R2",
        text="Bring that file up.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        expected_goal_keywords=("bring", "open", "file", "display", "retrieve"),
        expected_intent="retrieve",
        expected_requested_ops=("bring", "open", "display", "retrieve"),
        expected_prohibited_ops=(),
        expected_references=("that file",),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="R3",
        text="Do the same thing for them.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        expected_goal_keywords=("same", "thing", "repeat", "apply", "do"),
        expected_intent="execute",
        expected_requested_ops=("do", "repeat", "apply", "execute"),
        expected_prohibited_ops=(),
        expected_references=("same thing", "them"),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="R4",
        text="Don't send it. Just draft the email.",
        category=ContextCategory.SELF_CONTAINED,
        expected_goal_keywords=("draft", "email"),
        expected_intent="create",
        expected_requested_ops=("draft",),
        expected_prohibited_ops=("send",),
        expected_references=("it",),
        has_negation=True,
    ),
    LFMQualificationCase(
        id="R5",
        text="Find the previous approval, compare it with this one and draft a revised order.",
        category=ContextCategory.STEP2_CONTEXT_REQUIRED,
        expected_goal_keywords=("compare", "draft", "order", "approval", "find"),
        expected_intent="create",
        expected_requested_ops=("find", "compare", "draft"),
        expected_prohibited_ops=(),
        expected_references=("previous approval", "it", "this one"),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="R6",
        text=(
            "The committee has already changed its view twice and the latest letter doesn't "
            "seem to match what was decided earlier. I need something I can put up tomorrow."
        ),
        category=ContextCategory.STEP2_CONTEXT_REQUIRED,
        expected_goal_keywords=("letter", "put up", "prepare", "draft", "compare", "something"),
        expected_intent="create",
        expected_requested_ops=("put up", "prepare", "draft", "create"),
        expected_prohibited_ops=(),
        expected_references=("latest letter", "what was decided earlier", "something"),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="R7",
        text="Compare only the 2025 and 2026 decisions, do not use anything before 2025, and keep the result under one page.",
        category=ContextCategory.STEP2_CONTEXT_REQUIRED,
        expected_goal_keywords=("compare", "decisions"),
        expected_intent="compare",
        expected_requested_ops=("compare",),
        expected_prohibited_ops=("use anything before 2025", "use"),
        expected_references=(),
        has_negation=True,
    ),
    LFMQualificationCase(
        id="R8",
        text="Draft a short formal email in Indian English to the Chief Warden.",
        category=ContextCategory.SELF_CONTAINED,
        expected_goal_keywords=("draft", "email", "chief warden"),
        expected_intent="create",
        expected_requested_ops=("draft",),
        expected_prohibited_ops=(),
        expected_references=(),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="R9",
        text="Do not summarize this; compare the exact figures in a table.",
        category=ContextCategory.SELF_CONTAINED,
        expected_goal_keywords=("compare", "figures", "table"),
        expected_intent="compare",
        expected_requested_ops=("compare",),
        expected_prohibited_ops=("summarize",),
        expected_references=("this",),
        has_negation=True,
    ),
    LFMQualificationCase(
        id="R10",
        text="What was approved yesterday?",
        category=ContextCategory.STEP2_CONTEXT_REQUIRED,
        expected_goal_keywords=("approved", "yesterday", "what", "determine"),
        expected_intent="retrieve",
        expected_requested_ops=("retrieve", "find", "query", "check"),
        expected_prohibited_ops=(),
        expected_references=(),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="S1",
        text="Hello",
        category=ContextCategory.SELF_CONTAINED,
        expected_goal_keywords=("hello", "greet", "greeting"),
        expected_intent="unspecified",
        expected_requested_ops=(),
        expected_prohibited_ops=(),
        expected_references=(),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="S2",
        text="Thanks",
        category=ContextCategory.SELF_CONTAINED,
        expected_goal_keywords=("thanks", "thank", "acknowledge"),
        expected_intent="unspecified",
        expected_requested_ops=(),
        expected_prohibited_ops=(),
        expected_references=(),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="S3",
        text="Open calculator.",
        category=ContextCategory.SELF_CONTAINED,
        expected_goal_keywords=("calculator", "open", "launch"),
        expected_intent="retrieve",
        expected_requested_ops=("open",),
        expected_prohibited_ops=(),
        expected_references=(),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="S4",
        text="Don't open it yet.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        expected_goal_keywords=("open", "wait", "hold", "do not open"),
        expected_intent="unspecified",
        expected_requested_ops=(),
        expected_prohibited_ops=("open",),
        expected_references=("it",),
        has_negation=True,
    ),
    LFMQualificationCase(
        id="S5",
        text="Send it to him after they approve it.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        expected_goal_keywords=("send", "approve"),
        expected_intent="execute",
        expected_requested_ops=("send",),
        expected_prohibited_ops=(),
        expected_references=("it", "him", "they"),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="S6",
        text="Compare the attached PDF with this spreadsheet.",
        category=ContextCategory.CURRENT_TURN_CONTEXT,
        expected_goal_keywords=("compare", "pdf", "spreadsheet"),
        expected_intent="compare",
        expected_requested_ops=("compare",),
        expected_prohibited_ops=(),
        expected_references=("attached PDF", "this spreadsheet"),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="S7",
        text="Make something I can submit tomorrow.",
        category=ContextCategory.SELF_CONTAINED,
        expected_goal_keywords=("make", "submit", "prepare", "create", "document"),
        expected_intent="create",
        expected_requested_ops=("make", "create", "prepare", "draft"),
        expected_prohibited_ops=(),
        expected_references=("something",),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="S8",
        text="No, I meant the earlier one.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        expected_goal_keywords=("earlier", "correct", "select", "refer"),
        expected_intent="retrieve",
        expected_requested_ops=("select", "retrieve", "refer"),
        expected_prohibited_ops=(),
        expected_references=("earlier one",),
        has_negation=False,
    ),
)


# ---------------------------------------------------------------------------
# Tranche B: 6 Original Active-Context Fixtures (C1..C6)
# ---------------------------------------------------------------------------

TRANCHE_B_CASES: Tuple[LFMQualificationCase, ...] = (
    LFMQualificationCase(
        id="C1",
        text="Bring that file up.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),
            )
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("bring", "open", "file", "display", "retrieve"),
        expected_intent="retrieve",
        expected_requested_ops=("bring", "open", "display", "retrieve"),
        expected_prohibited_ops=(),
        expected_references=("that file",),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="C2",
        text="Do the same thing for them.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_entities=(
                EntityDescriptor(id="e1", name="OH-1 first-year students", category="group"),
            ),
            prior_semantic_operation="draft formal email",
        ),
        expected_resolved_target="e1",
        expected_goal_keywords=("same thing", "draft", "email", "do"),
        expected_intent="execute",
        expected_requested_ops=("draft", "do", "repeat"),
        expected_prohibited_ops=(),
        expected_references=("same thing", "them"),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="C3",
        text="No, I meant the earlier one.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Approval_2025.pdf", artifact_type="document"),
                ArtifactDescriptor(id="x2", name="Approval_2026.pdf", artifact_type="document"),
            )
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("earlier", "approval", "select", "refer"),
        expected_intent="retrieve",
        expected_requested_ops=("select", "retrieve", "refer"),
        expected_prohibited_ops=(),
        expected_references=("earlier one",),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="C4",
        text="Convert this to PDF.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Draft_Letter.docx", artifact_type="document"),
            )
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("convert", "pdf", "draft_letter"),
        expected_intent="modify",
        expected_requested_ops=("convert",),
        expected_prohibited_ops=(),
        expected_references=("this",),
        has_negation=False,
    ),
    LFMQualificationCase(
        id="C5",
        text="Don't send it. Just draft the email.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Complaint_Summary.pdf", artifact_type="document"),
            )
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("draft", "email"),
        expected_intent="create",
        expected_requested_ops=("draft",),
        expected_prohibited_ops=("send",),
        expected_references=("it",),
        has_negation=True,
    ),
    LFMQualificationCase(
        id="C6",
        text="Send it to him after they approve it.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Revised_Order.docx", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="e1", name="Chief Warden", category="person"),
            ),
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("send", "approve"),
        expected_intent="execute",
        expected_requested_ops=("send",),
        expected_prohibited_ops=(),
        expected_references=("it", "him", "they"),
        has_negation=False,
    ),
)


# ---------------------------------------------------------------------------
# Tranche C: RAR Residual Stress Suite (T1..T16)
# ---------------------------------------------------------------------------

TRANCHE_C_CASES: Tuple[LFMQualificationCase, ...] = (
    LFMQualificationCase(
        id="T01",
        text="Don't send it. Just revise it and make it shorter.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Disciplinary_Order.docx", artifact_type="document"),
            )
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("revise", "shorten", "order", "shorter"),
        expected_intent="modify",
        expected_requested_ops=("revise", "shorten", "modify"),
        expected_prohibited_ops=("send",),
        expected_references=("it",),
        expected_operation_bindings=(("revise", "x1"), ("shorten", "x1")),
        has_negation=True,
        notes="Negation with multiple requested operations bound to single anchor",
    ),
    LFMQualificationCase(
        id="T02",
        text="Compare the earlier order with this one and send the summary to him.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Order_2025.docx", artifact_type="document"),
                ArtifactDescriptor(id="x2", name="Order_2026.docx", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="e1", name="Dr. Sharma", category="person"),
            ),
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("compare", "send", "summary", "order"),
        expected_intent="compare",
        expected_requested_ops=("compare", "send"),
        expected_prohibited_ops=(),
        expected_references=("the earlier order", "this one", "him"),
        expected_operation_bindings=(("compare", "x1"), ("send", "e1")),
        has_negation=False,
        notes="Multi-target relational binding: compare x1, x2 and send to e1",
    ),
    LFMQualificationCase(
        id="T03",
        text="Use that file.",
        category=ContextCategory.AMBIGUOUS,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Budget_Sheet_A.xlsx", artifact_type="spreadsheet"),
                ArtifactDescriptor(id="x2", name="Budget_Sheet_B.xlsx", artifact_type="spreadsheet"),
            )
        ),
        expected_goal_keywords=("use", "file", "select"),
        expected_intent="execute",
        expected_requested_ops=("use", "select"),
        expected_prohibited_ops=(),
        expected_references=("that file",),
        expected_ambiguity=True,
        has_negation=False,
        notes="Ambiguity preservation: 2 indistinguishable candidates, model must not invent choice",
    ),
    LFMQualificationCase(
        id="T04",
        text="Do not modify it; only prepare a summary.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Audit_Report.pdf", artifact_type="document"),
            )
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("summary", "prepare", "summarize"),
        expected_intent="create",
        expected_requested_ops=("prepare", "summarize", "summary"),
        expected_prohibited_ops=("modify",),
        expected_references=("it",),
        expected_operation_bindings=(("prepare", "x1"),),
        has_negation=True,
        notes="Negation on modify, requested summarize on anchor x1",
    ),
    LFMQualificationCase(
        id="T05",
        text="Don't delete the spreadsheet, just move it to the archive folder.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="s1", name="Vendor_Accounts.xlsx", artifact_type="spreadsheet"),
            )
        ),
        expected_resolved_target="s1",
        expected_goal_keywords=("move", "archive", "spreadsheet"),
        expected_intent="execute",
        expected_requested_ops=("move", "archive"),
        expected_prohibited_ops=("delete",),
        expected_references=("the spreadsheet", "it"),
        expected_operation_bindings=(("move", "s1"),),
        has_negation=True,
        notes="Prohibited delete, requested move on spreadsheet anchor s1",
    ),
    LFMQualificationCase(
        id="T06",
        text="Do not summarize this; compare the exact figures in a table.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="doc1", name="Fee_Structure.pdf", artifact_type="document"),
            )
        ),
        expected_resolved_target="doc1",
        expected_goal_keywords=("compare", "figures", "table"),
        expected_intent="compare",
        expected_requested_ops=("compare",),
        expected_prohibited_ops=("summarize",),
        expected_references=("this",),
        has_negation=True,
        notes="Prohibited summarize, requested compare with table output preference",
    ),
    LFMQualificationCase(
        id="T07",
        text="Send only after approval; do not email it right now.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="m1", name="Fee_Notice.docx", artifact_type="document"),
            )
        ),
        expected_resolved_target="m1",
        expected_goal_keywords=("send", "email", "approval"),
        expected_intent="communicate",
        expected_requested_ops=("send",),
        expected_prohibited_ops=("email", "send"),
        expected_references=("it",),
        has_negation=True,
        notes="Conditional prohibition: do not email right now, send after approval",
    ),
    LFMQualificationCase(
        id="T08",
        text="Compare x1 with x2 and send the revised summary to e1.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Spec_V1.pdf", artifact_type="document"),
                ArtifactDescriptor(id="x2", name="Spec_V2.pdf", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="e1", name="Registrar Office", category="organization"),
            ),
        ),
        expected_resolved_target="x1",
        expected_goal_keywords=("compare", "send", "summary"),
        expected_intent="compare",
        expected_requested_ops=("compare", "send"),
        expected_prohibited_ops=(),
        expected_references=("x1", "x2", "e1"),
        expected_operation_bindings=(("compare", "x1"), ("send", "e1")),
        has_negation=False,
        notes="Complex multi-target operation binding across multiple artifacts and entity",
    ),
    LFMQualificationCase(
        id="T09",
        text="Draft a formal response to her, but do not share the internal memo.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="doc2", name="Internal_Memo_Dean.docx", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="e2", name="Dr. Anita Roy", category="person"),
            ),
        ),
        expected_resolved_target="e2",
        expected_goal_keywords=("draft", "response", "email"),
        expected_intent="create",
        expected_requested_ops=("draft", "respond"),
        expected_prohibited_ops=("share",),
        expected_references=("her", "the internal memo"),
        expected_operation_bindings=(("draft", "e2"), ("share", "doc2")),
        has_negation=True,
        notes="Operation binding with distinct target per operation: draft to e2, prohibited share doc2",
    ),
    LFMQualificationCase(
        id="T10",
        text="Do not approve it yet, just review the proposed budget.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="p1", name="Project_Proposal.pdf", artifact_type="document"),
                ArtifactDescriptor(id="b1", name="Proposed_Budget.xlsx", artifact_type="spreadsheet"),
            )
        ),
        expected_resolved_target="b1",
        expected_goal_keywords=("review", "budget"),
        expected_intent="analyze",
        expected_requested_ops=("review",),
        expected_prohibited_ops=("approve",),
        expected_references=("it", "the proposed budget"),
        expected_operation_bindings=(("review", "b1"), ("approve", "p1")),
        has_negation=True,
        notes="Prohibited approve on p1, requested review on b1",
    ),
    LFMQualificationCase(
        id="T11",
        text="Open the latest report and extract all action items.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="rep_v1", name="Meeting_Report_Aug.docx", artifact_type="document"),
                ArtifactDescriptor(id="rep_v2", name="Meeting_Report_Sep.docx", artifact_type="document"),
            )
        ),
        expected_resolved_target="rep_v2",
        expected_goal_keywords=("open", "extract", "action items", "report"),
        expected_intent="retrieve",
        expected_requested_ops=("open", "extract"),
        expected_prohibited_ops=(),
        expected_references=("the latest report",),
        expected_operation_bindings=(("open", "rep_v2"), ("extract", "rep_v2")),
        has_negation=False,
        notes="Temporal latest anchor rep_v2 with dual requested operations",
    ),
    LFMQualificationCase(
        id="T12",
        text="Convert that document to Markdown, but do not overwrite the original.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="doc3", name="Policy_Guidelines.docx", artifact_type="document"),
            )
        ),
        expected_resolved_target="doc3",
        expected_goal_keywords=("convert", "markdown"),
        expected_intent="modify",
        expected_requested_ops=("convert",),
        expected_prohibited_ops=("overwrite",),
        expected_references=("that document", "the original"),
        expected_operation_bindings=(("convert", "doc3"), ("overwrite", "doc3")),
        has_negation=True,
        notes="Format conversion with prohibited overwrite constraint",
    ),
    LFMQualificationCase(
        id="T13",
        text="Don't publish the article; send a draft copy to the reviewer.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="art1", name="Research_Article_Final.docx", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="rev1", name="External Reviewer", category="person"),
            ),
        ),
        expected_resolved_target="art1",
        expected_goal_keywords=("send", "draft", "reviewer"),
        expected_intent="communicate",
        expected_requested_ops=("send",),
        expected_prohibited_ops=("publish",),
        expected_references=("the article", "the reviewer"),
        expected_operation_bindings=(("send", "rev1"), ("publish", "art1")),
        has_negation=True,
        notes="Prohibited publish on art1, requested send to rev1",
    ),
    LFMQualificationCase(
        id="T14",
        text="Cancel the meeting notice and draft a postponement email.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="ntc1", name="Senate_Meeting_Notice.pdf", artifact_type="document"),
            )
        ),
        expected_resolved_target="ntc1",
        expected_goal_keywords=("cancel", "draft", "postponement", "email"),
        expected_intent="create",
        expected_requested_ops=("cancel", "draft"),
        expected_prohibited_ops=(),
        expected_references=("the meeting notice",),
        expected_operation_bindings=(("cancel", "ntc1"),),
        has_negation=False,
        notes="Dual operations: cancel existing notice ntc1, draft new postponement email",
    ),
    LFMQualificationCase(
        id="T15",
        text="Find the previous contract and compare it with the current draft, but don't finalize anything.",
        category=ContextCategory.ACTIVE_CONTEXT_REQUIRED,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="c_v1", name="Catering_Contract_2024.pdf", artifact_type="document"),
                ArtifactDescriptor(id="c_v2", name="Catering_Contract_2025_Draft.docx", artifact_type="document"),
            )
        ),
        expected_resolved_target="c_v1",
        expected_goal_keywords=("find", "compare", "contract"),
        expected_intent="compare",
        expected_requested_ops=("find", "compare"),
        expected_prohibited_ops=("finalize",),
        expected_references=("the previous contract", "it", "the current draft"),
        expected_operation_bindings=(("compare", "c_v1"),),
        has_negation=True,
        notes="Temporal offset comparison with prohibited finalization",
    ),
    LFMQualificationCase(
        id="T16",
        text="Which version was accepted by the committee?",
        category=ContextCategory.AMBIGUOUS,
        context=ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="v1", name="Syllabus_RevA.docx", artifact_type="document"),
                ArtifactDescriptor(id="v2", name="Syllabus_RevB.docx", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="comm1", name="Curriculum Committee", category="organization"),
            ),
        ),
        expected_goal_keywords=("which", "version", "accepted", "determine"),
        expected_intent="retrieve",
        expected_requested_ops=("retrieve", "query", "check"),
        expected_prohibited_ops=(),
        expected_references=("version", "the committee"),
        expected_ambiguity=True,
        has_negation=False,
        notes="Ambiguity preservation on multiple version candidates with query goal",
    ),
)


def get_all_qualification_cases() -> Tuple[LFMQualificationCase, ...]:
    """Returns all 40 cases across Tranches A, B, and C."""
    return TRANCHE_A_CASES + TRANCHE_B_CASES + TRANCHE_C_CASES
