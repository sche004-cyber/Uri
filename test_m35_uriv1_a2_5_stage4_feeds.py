"""Unit tests for Stage 4 Adaptive Narrow Feeds, Planner, Merger, and Boundaries (Batch A2.5).

Tests:
1. Feed ownership separation
2. Adaptive feed selection logic
3. Deterministic feed merging
4. Omitted feed handling & fallbacks
5. Polarity contradiction detection
6. Parallel-safe feed independence
7. Context envelope fixture integrity (L0 to L7)
8. Noise sensitivity fixture integrity (300 to 1500 tokens)
9. Complexity ladder fixture integrity (C0 to C8)
10. Negation ladder fixture integrity (N1 to N6)
11. Escalation boundary calculations
"""

import unittest
from typing import Tuple

from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
)
from uri_v1.turn.turn_frame import (
    CandidateAction,
    CandidateReference,
    TurnFrame,
)
from uri_v1.turn.lfm_adaptive_feeds import (
    FEED_B_SCHEMA,
    FEED_C_SCHEMA,
    FEED_G_SCHEMA,
    FEED_O_SCHEMA,
    FeedBOutput,
    FeedCOutput,
    FeedGOutput,
    FeedOOutput,
    FeedType,
    OperationBinding,
    build_feed_b_prompt,
    build_feed_c_prompt,
    build_feed_g_prompt,
    build_feed_o_prompt,
    parse_feed_b_response,
    parse_feed_c_response,
    parse_feed_g_response,
    parse_feed_o_response,
)
from uri_v1.turn.lfm_envelope_battery import (
    build_complexity_ladder_battery,
    build_context_envelope_battery,
    build_negation_ladder_battery,
    build_noise_sensitivity_battery,
    build_operation_retention_battery,
    build_progressive_feed_width_battery,
    get_stage4_full_battery,
)
from uri_v1.turn.lfm_feed_merger import DeterministicSemanticMerger
from uri_v1.turn.lfm_feed_planner import (
    AdaptiveSemanticFeedPlanner,
    EscalationDecision,
    SemanticEnvelopeEscalationGuard,
)
from uri_v1.turn.rar_contracts import (
    RARBasis,
    RARDriverRule,
    RAROutcome,
    RARResolution,
)


class Stage4FeedArchitectureTests(unittest.TestCase):
    """Test suite verifying Stage 4 feed ownership, planning, and merging."""

    def setUp(self) -> None:
        self.planner = AdaptiveSemanticFeedPlanner()
        self.merger = DeterministicSemanticMerger()
        self.escalation_guard = SemanticEnvelopeEscalationGuard(
            max_context_tokens=400,
            max_operations=3,
            max_candidate_distractors=5,
            max_negation_clauses=2,
        )

    def test_feed_ownership_separation(self) -> None:
        """Feed schemas and outputs must maintain strict separation of concerns."""
        # Feed G owns goal and intent only
        self.assertIn("goal", FEED_G_SCHEMA["properties"])
        self.assertIn("intent_family", FEED_G_SCHEMA["properties"])
        self.assertNotIn("requested_operations", FEED_G_SCHEMA["properties"])
        self.assertNotIn("references", FEED_G_SCHEMA["properties"])

        # Feed O owns requested and prohibited operations only
        self.assertIn("requested_operations", FEED_O_SCHEMA["properties"])
        self.assertIn("prohibited_operations", FEED_O_SCHEMA["properties"])
        self.assertNotIn("goal", FEED_O_SCHEMA["properties"])
        self.assertNotIn("references", FEED_O_SCHEMA["properties"])

        # Feed C owns constraints and output preferences only
        self.assertIn("constraints", FEED_C_SCHEMA["properties"])
        self.assertIn("output_preferences", FEED_C_SCHEMA["properties"])
        self.assertNotIn("goal", FEED_C_SCHEMA["properties"])

        # Feed B owns operation bindings only
        self.assertIn("operation_bindings", FEED_B_SCHEMA["properties"])
        self.assertNotIn("goal", FEED_B_SCHEMA["properties"])

    def test_adaptive_feed_selection_simple_turn(self) -> None:
        """Simple turn 'Open calculator' selects Goal and Operations feeds only."""
        plan = self.planner.plan_feeds("Open calculator.")
        self.assertTrue(plan.has_feed(FeedType.GOAL))
        self.assertTrue(plan.has_feed(FeedType.OPERATIONS))
        self.assertFalse(plan.has_feed(FeedType.CONSTRAINTS))
        self.assertFalse(plan.has_feed(FeedType.BINDING))
        self.assertFalse(plan.is_complex)

    def test_adaptive_feed_selection_with_constraints(self) -> None:
        """Turn with constraint keyword 'shorter' activates Feed C."""
        plan = self.planner.plan_feeds("Make that email shorter.")
        self.assertTrue(plan.has_feed(FeedType.GOAL))
        self.assertTrue(plan.has_feed(FeedType.CONSTRAINTS))

    def test_adaptive_feed_selection_complex_turn(self) -> None:
        """Complex turn with multiple operations and resolved anchors selects G, O, C, B."""
        raw_t = "Compare the earlier order with this one, don't send it yet, and draft a shorter reply."
        tf = TurnFrame(
            raw_text=raw_t,
            normalized_text=raw_t.lower(),
            candidate_actions=(
                CandidateAction(id="act1", verb="compare"),
                CandidateAction(id="act2", verb="send"),
                CandidateAction(id="act3", verb="draft"),
            ),
        )
        rar = RARResolution(
            reference_expression="the earlier order",
            outcome=RAROutcome.RESOLVED,
            candidate_id="doc_order_01",
            basis=RARBasis.DETERMINISTIC_ANCHOR,
            rule_used=RARDriverRule.TEMPORAL_RELATION,
        )
        plan = self.planner.plan_feeds(tf.raw_text, turn_frame=tf, rar_result=rar)
        self.assertTrue(plan.has_feed(FeedType.GOAL))
        self.assertTrue(plan.has_feed(FeedType.OPERATIONS))
        self.assertTrue(plan.has_feed(FeedType.CONSTRAINTS))
        self.assertTrue(plan.has_feed(FeedType.BINDING))
        self.assertTrue(plan.is_complex)

    def test_deterministic_merge_full_stack(self) -> None:
        """Merger combines G, O, C, B and RAR into an immutable DecodedRequest."""
        g = FeedGOutput(goal="Draft email to warden", intent_family=IntentFamily.COMMUNICATE)
        o = FeedOOutput(requested_operations=("draft",), prohibited_operations=("send",))
        c = FeedCOutput(
            included_items=(),
            excluded_items=(),
            length_limit="under 100 words",
            language_constraints="",
            timing_condition="",
            artifact_type="email",
            format="markdown",
            tone="formal",
            structure="bullet points",
        )
        b = FeedBOutput(
            bindings=(OperationBinding(operation="draft", target_id="doc_warden_notes"),),
            unresolved_relations=(),
        )
        rar = RARResolution(
            reference_expression="the notes",
            outcome=RAROutcome.RESOLVED,
            candidate_id="doc_warden_notes",
            basis=RARBasis.DETERMINISTIC_ANCHOR,
            rule_used=RARDriverRule.EXACT_ID,
        )

        decoded = self.merger.merge(
            user_text="Draft an email using the notes under 100 words, don't send it.",
            feed_g=g,
            feed_o=o,
            feed_c=c,
            feed_b=b,
            rar_result=rar,
        )

        self.assertEqual(decoded.goal.description, "Draft email to warden")
        self.assertEqual(decoded.goal.intent_family, IntentFamily.COMMUNICATE)

        # Operations
        req_ops = [op for op in decoded.operations if op.status == OperationStatus.REQUESTED]
        pro_ops = [op for op in decoded.operations if op.status == OperationStatus.PROHIBITED]
        self.assertEqual(len(req_ops), 1)
        self.assertEqual(req_ops[0].name, "draft")
        self.assertEqual(req_ops[0].target, "doc_warden_notes")
        self.assertEqual(len(pro_ops), 1)
        self.assertEqual(pro_ops[0].name, "send")

        # References from RAR
        self.assertEqual(len(decoded.references), 1)
        self.assertTrue(decoded.references[0].is_resolved)
        self.assertEqual(decoded.references[0].referent_hint, "doc_warden_notes")

        # Constraints
        self.assertEqual(decoded.output_preferences.tone, "formal")
        self.assertEqual(decoded.output_preferences.artifact_type, "email")
        self.assertEqual(decoded.confidence.overall, ConfidenceLevel.HIGH)

    def test_omitted_feed_handling_and_fallback_binding(self) -> None:
        """When Feed B is omitted, single operation mechanically binds to single RAR target."""
        g = FeedGOutput(goal="Review document", intent_family=IntentFamily.MODIFY)
        o = FeedOOutput(requested_operations=("review",), prohibited_operations=())
        rar = RARResolution(
            reference_expression="that document",
            outcome=RAROutcome.RESOLVED,
            candidate_id="doc_hostel_rules",
            basis=RARBasis.DETERMINISTIC_ANCHOR,
            rule_used=RARDriverRule.CURRENT_ATTACHMENT,
        )

        # Feed B and Feed C are omitted
        decoded = self.merger.merge(
            user_text="Review that document.",
            feed_g=g,
            feed_o=o,
            feed_c=None,
            feed_b=None,
            rar_result=rar,
        )

        self.assertEqual(len(decoded.operations), 1)
        self.assertEqual(decoded.operations[0].name, "review")
        self.assertEqual(decoded.operations[0].target, "doc_hostel_rules")

    def test_contradiction_detection_safety(self) -> None:
        """If Feed O emits contradictory polarity for a verb, merger flags contradiction."""
        g = FeedGOutput(goal="Process document", intent_family=IntentFamily.MODIFY)
        # Model erroneously put 'send' into both requested and prohibited
        o = FeedOOutput(
            requested_operations=("draft", "send"),
            prohibited_operations=("send",),
        )

        decoded = self.merger.merge(
            user_text="Draft it but don't send.",
            feed_g=g,
            feed_o=o,
        )

        # Contradiction recorded in ambiguities
        conflict_ambiguities = [a for a in decoded.ambiguities if a.kind == AmbiguityKind.MULTIPLE_INTERPRETATIONS]
        self.assertEqual(len(conflict_ambiguities), 1)
        self.assertIn("send", conflict_ambiguities[0].candidates)

        # 'send' is removed from requested operations for safety
        req_verbs = [op.name for op in decoded.operations if op.status == OperationStatus.REQUESTED]
        self.assertNotIn("send", req_verbs)
        self.assertIn("draft", req_verbs)

    def test_parallel_safe_feed_independence(self) -> None:
        """Prompts for G, O, and C do not depend on each other and can execute concurrently."""
        turn = "Review the order but do not send it."
        prompt_g = build_feed_g_prompt(turn)
        prompt_o = build_feed_o_prompt(turn, candidate_actions=["review", "send"])
        prompt_c = build_feed_c_prompt(turn)

        self.assertIn(turn, prompt_g)
        self.assertIn(turn, prompt_o)
        self.assertIn(turn, prompt_c)
        # All three prompts are cleanly formed without inter-feed state
        self.assertIsInstance(prompt_g, str)
        self.assertIsInstance(prompt_o, str)
        self.assertIsInstance(prompt_c, str)

    def test_context_envelope_fixtures_integrity(self) -> None:
        """All 8 levels of the Context Envelope battery must be well-formed."""
        cases = build_context_envelope_battery()
        self.assertEqual(len(cases), 8)
        expected_ids = [f"ENV-L{i}" for i in range(8)]
        self.assertEqual([c.case_id for c in cases], expected_ids)

        # Tokens must be ascending across context levels
        token_counts = [c.context_tokens_approx for c in cases]
        self.assertEqual(token_counts, sorted(token_counts))
        self.assertGreater(cases[-1].context_tokens_approx, 1000)

    def test_noise_sensitivity_fixtures_integrity(self) -> None:
        """Noise sensitivity pairs must have identical semantic targets and ascending noise."""
        cases = build_noise_sensitivity_battery()
        self.assertEqual(len(cases), 4)
        for c in cases:
            self.assertEqual(c.expected_requested_ops, ("draft",))
            self.assertEqual(c.expected_prohibited_ops, ("send",))
        noise_counts = [c.noise_tokens_approx for c in cases]
        self.assertEqual(noise_counts, [0, 300, 600, 1200])

    def test_complexity_ladder_fixtures_integrity(self) -> None:
        """Complexity ladder must span C0 through C8."""
        cases = build_complexity_ladder_battery()
        self.assertEqual(len(cases), 9)
        self.assertEqual([c.case_id for c in cases], [f"CMPLX-C{i}" for i in range(9)])

    def test_negation_ladder_fixtures_integrity(self) -> None:
        """Negation ladder must span N1 through N6."""
        cases = build_negation_ladder_battery()
        self.assertEqual(len(cases), 6)
        self.assertEqual([c.case_id for c in cases], [f"NEG-N{i}" for i in range(1, 7)])

    def test_escalation_boundary_calculation(self) -> None:
        """Escalation guard must trigger when envelope thresholds are exceeded."""
        # Within envelope
        d1 = self.escalation_guard.evaluate(
            estimated_tokens=250,
            num_operations=2,
            num_candidates=3,
            negation_clause_count=1,
        )
        self.assertFalse(d1.should_escalate)

        # Exceeds tokens (>400)
        d2 = self.escalation_guard.evaluate(
            estimated_tokens=550,
            num_operations=2,
            num_candidates=3,
            negation_clause_count=1,
        )
        self.assertTrue(d2.should_escalate)
        self.assertIn("Context tokens", d2.reason)

        # Exceeds operations (>3)
        d3 = self.escalation_guard.evaluate(
            estimated_tokens=200,
            num_operations=5,
            num_candidates=2,
            negation_clause_count=1,
        )
        self.assertTrue(d3.should_escalate)
        self.assertIn("Operation count", d3.reason)

        # Cross-target relational dependency
        d4 = self.escalation_guard.evaluate(
            estimated_tokens=200,
            num_operations=2,
            num_candidates=2,
            negation_clause_count=1,
            has_cross_target_dependency=True,
        )
        self.assertTrue(d4.should_escalate)
        self.assertIn("Cross-target relational dependency", d4.reason)


if __name__ == "__main__":
    unittest.main()
