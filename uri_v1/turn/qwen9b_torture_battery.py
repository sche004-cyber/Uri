"""M35 URIv1 Batch A2.7 — Semantic Torture Set.

Designed specifically to stress test contrastive negation preservation,
complex multi-target bindings, nested conditions, and realistic URI workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.contracts import IntentFamily
from uri_v1.turn.lfm_envelope_battery import EnvelopeTestCase
from uri_v1.turn.rar_contracts import RARCandidate
from uri_v1.turn.turn_frame import CandidateAction, CandidateReference, TurnFrame


def build_semantic_torture_battery() -> Tuple[EnvelopeTestCase, ...]:
    cases = []

    # 1. Simple Negation
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-01-SIMPLE-NEG",
            category="Torture_Negation",
            user_text="Do not delete the audit logs.",
            expected_goal="Do not delete audit logs",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=(),
            expected_prohibited_ops=("delete",),
            description="Pure standalone prohibition.",
        )
    )

    # 2. Contrastive Negation (Core A2.6 failure point)
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-02-CONTRAST-BASIC",
            category="Torture_Contrastive",
            user_text="Review the email but do not send it.",
            expected_goal="Review email without sending",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("review",),
            expected_prohibited_ops=("send",),
            description="Basic contrastive: positive requested + negative prohibited.",
        )
    )

    # 3. Realistic URI Example 1: Dean's Email
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-03-DEAN-EMAIL",
            category="Torture_Contrastive",
            user_text="Review the Dean's latest email and prepare a reply, but do not send it.",
            expected_goal="Review Dean's email and prepare reply",
            expected_intent_family=IntentFamily.COMMUNICATE,
            expected_requested_ops=("review", "prepare"),
            expected_prohibited_ops=("send",),
            expected_reference_expression="Dean's latest email",
            expected_target_id="email_dean_latest_2026",
            candidate_pool=(
                RARCandidate(id="email_dean_latest_2026", candidate_type="email", title="Dean's Latest Email", recency_rank=1),
                RARCandidate(id="email_dean_old_2025", candidate_type="email", title="Dean's Prior Email", recency_rank=5),
            ),
            description="Two positive operations + one explicit prohibition + target reference.",
        )
    )

    # 4. Realistic URI Example 2: Office Order
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-04-OFFICE-ORDER",
            category="Torture_Multi_Prohibit",
            user_text="Draft the Office Order using the revised approval, but don't issue or upload anything until I confirm.",
            expected_goal="Draft Office Order",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("draft",),
            expected_prohibited_ops=("issue", "upload"),
            expected_timing_condition="until confirmation",
            description="One requested operation + two prohibited operations + deferred timing.",
        )
    )

    # 5. Multiple positive operations + one prohibition
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-05-MULTI-POS-ONE-NEG",
            category="Torture_Contrastive",
            user_text="Compile the test report, format the charts, but do not publish the document.",
            expected_goal="Compile test report and format charts",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("compile", "format"),
            expected_prohibited_ops=("publish",),
            description="Two positive requested operations + one prohibited operation.",
        )
    )

    # 6. Multiple prohibitions
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-06-MULTI-PROHIBIT",
            category="Torture_Multi_Prohibit",
            user_text="Do not modify or delete the historical archives.",
            expected_goal="Protect historical archives from modification or deletion",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=(),
            expected_prohibited_ops=("modify", "delete"),
            description="Two distinct prohibited operations, zero requested.",
        )
    )

    # 7. "Not X, instead Y" (Inversion / Correction)
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-07-NOT-X-INSTEAD-Y",
            category="Torture_Contrastive",
            user_text="Do not export as PDF; instead generate a Markdown summary.",
            expected_goal="Generate Markdown summary instead of PDF",
            expected_intent_family=IntentFamily.CREATE,
            expected_requested_ops=("generate",),
            expected_prohibited_ops=("export",),
            description="'Not X, instead Y' inversion.",
        )
    )

    # 8. "X but not Y"
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-08-X-BUT-NOT-Y",
            category="Torture_Contrastive",
            user_text="Compile the C++ binaries but do not run them.",
            expected_goal="Compile binaries without running",
            expected_intent_family=IntentFamily.EXECUTE,
            expected_requested_ops=("compile",),
            expected_prohibited_ops=("run",),
            description="Explicit 'X but not Y'.",
        )
    )

    # 9. Conditional Negation ("unless")
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-09-UNLESS-COND",
            category="Torture_Conditional",
            user_text="Archive the session log unless there are critical errors reported.",
            expected_goal="Archive session log conditionally",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("archive",),
            expected_prohibited_ops=(),
            expected_timing_condition="unless critical errors",
            description="Positive action conditional on exception clause.",
        )
    )

    # 10. Temporal / Deferred Action
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-10-DEFERRED-TIMING",
            category="Torture_Temporal",
            user_text="Hold off deploying the patch until tomorrow at 10am.",
            expected_goal="Hold off deploying patch until tomorrow",
            expected_intent_family=IntentFamily.EXECUTE,
            expected_requested_ops=(),
            expected_prohibited_ops=("deploy",),
            expected_timing_condition="tomorrow at 10am",
            description="Deferred action where deployment is prohibited until a specific time.",
        )
    )

    # 11. Multi-Target Disjoint Operations
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-11-MULTI-TARGET-OPS",
            category="Torture_Binding",
            user_text="Sign the affidavit and shred the draft notes.",
            expected_goal="Sign affidavit and shred draft notes",
            expected_intent_family=IntentFamily.MODIFY,
            expected_requested_ops=("sign", "shred"),
            expected_prohibited_ops=(),
            description="Disjoint actions applied to distinct targets.",
        )
    )

    # 12. Realistic URI Example 3: Ledger Protection
    cases.append(
        EnvelopeTestCase(
            case_id="TORT-12-LEDGER-PROTECT",
            category="Torture_Contrastive",
            user_text="Compare the Q3 and Q4 balances and highlight discrepancies, but avoid modifying the ledger.",
            expected_goal="Compare balances and highlight discrepancies",
            expected_intent_family=IntentFamily.COMPARE,
            expected_requested_ops=("compare", "highlight"),
            expected_prohibited_ops=("modify",),
            expected_reference_expression="the ledger",
            expected_target_id="ledger_fiscal_2026",
            candidate_pool=(
                RARCandidate(id="ledger_fiscal_2026", candidate_type="ledger", title="Fiscal Ledger 2026", recency_rank=1),
            ),
            description="Two requested actions + one prohibited action with anchor binding.",
        )
    )

    return tuple(cases)
