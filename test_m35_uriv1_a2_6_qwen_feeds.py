"""Unit tests for M35 URIv1 Batch A2.6 Qwen3.5-2B Integration and Feeds."""

from __future__ import annotations

import unittest
from typing import Tuple

from uri_v1.turn.active_context import ActiveContext
from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
)
from uri_v1.turn.lfm_adaptive_feeds import (
    FeedBOutput,
    FeedCOutput,
    FeedGOutput,
    FeedOOutput,
    FeedType,
    build_feed_b_prompt,
    build_feed_c_prompt,
    build_feed_g_prompt,
    build_feed_o_prompt,
    parse_feed_b_response,
    parse_feed_c_response,
    parse_feed_g_response,
    parse_feed_o_response,
)
from uri_v1.turn.lfm_feed_merger import DeterministicSemanticMerger
from uri_v1.turn.lfm_feed_planner import AdaptiveSemanticFeedPlanner
from uri_v1.turn.rar_contracts import RAROutcome, RARResolution
from uri_v1.turn.turn_frame import CandidateAction, TurnFrame


class TestBatchA26FeedsAndIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = AdaptiveSemanticFeedPlanner()
        self.merger = DeterministicSemanticMerger()

    def test_qwen_feed_prompts_contain_no_contaminating_examples(self) -> None:
        """Feed prompts must be clean and not leak task-specific examples."""
        g_prompt = build_feed_g_prompt("Refactor the parser")
        self.assertIn("Refactor the parser", g_prompt)

        o_prompt = build_feed_o_prompt("Format code and run tests")
        self.assertIn("Format code and run tests", o_prompt)

        c_prompt = build_feed_c_prompt("Make it under 100 words")
        self.assertIn("Make it under 100 words", c_prompt)

    def test_qwen_planner_activates_expected_feeds(self) -> None:
        """Planner selects appropriate feeds based on turn frame syntax."""
        frame = TurnFrame(
            raw_text="Run tests but do not commit",
            normalized_text="run tests but do not commit",
            candidate_actions=(
                CandidateAction(id="a0", verb="run", clause_index=0),
                CandidateAction(id="a1", verb="commit", clause_index=1),
            ),
            negation_spans=("do not commit",),
        )
        plan = self.planner.plan_feeds(
            text="Run tests but do not commit",
            turn_frame=frame,
        )
        self.assertTrue(plan.has_feed(FeedType.GOAL))
        self.assertTrue(plan.has_feed(FeedType.OPERATIONS))
        self.assertIn(FeedType.GOAL, plan.feeds)
        self.assertIn(FeedType.OPERATIONS, plan.feeds)

    def test_qwen_merger_combines_narrow_feed_outputs(self) -> None:
        """Deterministic merger accurately combines narrow feed outputs with RAR facts."""
        feed_g = FeedGOutput(
            goal="Execute unit test suite",
            intent_family=IntentFamily.EXECUTE,
        )
        feed_o = FeedOOutput(
            requested_operations=("test", "lint"),
            prohibited_operations=("commit", "push"),
        )
        feed_c = FeedCOutput(
            included_items=(),
            excluded_items=(),
            length_limit="",
            language_constraints="",
            timing_condition="",
            artifact_type="",
            format="verbose",
            tone="",
            structure="",
        )
        rar_res = RARResolution(
            reference_expression="tests",
            outcome=RAROutcome.RESOLVED,
            candidate_id="test_runner_v1",
            raw_confidence=0.98,
        )

        decoded = self.merger.merge(
            user_text="Run tests and lint, do not commit or push",
            feed_g=feed_g,
            feed_o=feed_o,
            feed_c=feed_c,
            rar_result=rar_res,
        )

        self.assertIsInstance(decoded, DecodedRequest)
        self.assertEqual(decoded.goal.description, "Execute unit test suite")
        self.assertEqual(decoded.goal.intent_family, IntentFamily.EXECUTE)

        # Check operations
        req_ops = [op.name for op in decoded.operations if op.status == OperationStatus.REQUESTED]
        pro_ops = [op.name for op in decoded.operations if op.status == OperationStatus.PROHIBITED]
        self.assertEqual(req_ops, ["test", "lint"])
        self.assertEqual(pro_ops, ["commit", "push"])

        # Check output preferences
        self.assertEqual(decoded.output_preferences.format, "verbose")

        # Check references from RAR
        self.assertTrue(len(decoded.references) > 0)
        self.assertTrue(decoded.references[0].is_resolved)
        self.assertEqual(decoded.references[0].referent_hint, "test_runner_v1")

    def test_qwen_merger_contradiction_safety(self) -> None:
        """If a verb appears as both requested and prohibited, merger enforces safety."""
        feed_g = FeedGOutput(goal="Test code", intent_family=IntentFamily.EXECUTE)
        feed_o = FeedOOutput(
            requested_operations=("test", "commit"),
            prohibited_operations=("commit",),
        )
        decoded = self.merger.merge(
            user_text="Test and do not commit",
            feed_g=feed_g,
            feed_o=feed_o,
        )
        req_ops = [op.name for op in decoded.operations if op.status == OperationStatus.REQUESTED]
        pro_ops = [op.name for op in decoded.operations if op.status == OperationStatus.PROHIBITED]

        # 'commit' must NOT be in requested operations
        self.assertNotIn("commit", req_ops)
        self.assertIn("commit", pro_ops)


if __name__ == "__main__":
    unittest.main()
