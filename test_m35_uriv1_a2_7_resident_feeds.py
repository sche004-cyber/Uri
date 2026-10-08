"""Unit tests for M35 URIv1 Batch A2.7 Resident Main-Brain feeds and metrics."""

from __future__ import annotations

import unittest
from typing import Tuple

from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
    SemanticOperation,
)
from uri_v1.turn.lfm_adaptive_feeds import (
    FeedBOutput,
    FeedCOutput,
    FeedGOutput,
    FeedOOutput,
    FeedType,
)
from uri_v1.turn.lfm_feed_merger import DeterministicSemanticMerger
from uri_v1.turn.qwen9b_torture_battery import build_semantic_torture_battery
from scripts.m35_qwen35_9b_resident_eval import score_decoded_request


class TestBatchA27ResidentMainBrain(unittest.TestCase):
    def setUp(self) -> None:
        self.merger = DeterministicSemanticMerger()
        self.torture_cases = build_semantic_torture_battery()

    def test_semantic_torture_battery_loaded(self) -> None:
        """The torture battery must contain 12 distinct edge-case definitions."""
        self.assertEqual(len(self.torture_cases), 12)
        case_ids = [c.case_id for c in self.torture_cases]
        self.assertIn("TORT-01-SIMPLE-NEG", case_ids)
        self.assertIn("TORT-02-CONTRAST-BASIC", case_ids)
        self.assertIn("TORT-03-DEAN-EMAIL", case_ids)
        self.assertIn("TORT-04-OFFICE-ORDER", case_ids)

    def test_contrastive_negation_scoring_positive(self) -> None:
        """Contrastive negation metric succeeds when both requested and prohibited ops exist."""
        dean_case = [c for c in self.torture_cases if c.case_id == "TORT-03-DEAN-EMAIL"][0]

        # Construct decoded request matching expectations
        feed_g = FeedGOutput(goal="Review Dean's email and reply", intent_family=IntentFamily.COMMUNICATE)
        feed_o = FeedOOutput(requested_operations=("review", "prepare"), prohibited_operations=("send",))
        decoded = self.merger.merge(
            user_text=dean_case.user_text,
            feed_g=feed_g,
            feed_o=feed_o,
        )

        scores = score_decoded_request(dean_case, decoded)
        self.assertTrue(scores["is_contrastive_case"])
        self.assertTrue(scores["contrastive_negation_ok"])
        self.assertTrue(scores["req_ops_ok"])
        self.assertTrue(scores["pro_ops_ok"])

    def test_contrastive_negation_scoring_detects_omission(self) -> None:
        """Contrastive metric fails when negative verb is dropped (the classic 2B failure)."""
        dean_case = [c for c in self.torture_cases if c.case_id == "TORT-03-DEAN-EMAIL"][0]

        # Dropped prohibited operation 'send'
        feed_g = FeedGOutput(goal="Review Dean's email and reply", intent_family=IntentFamily.COMMUNICATE)
        feed_o = FeedOOutput(requested_operations=("review", "prepare"), prohibited_operations=())
        decoded = self.merger.merge(
            user_text=dean_case.user_text,
            feed_g=feed_g,
            feed_o=feed_o,
        )

        scores = score_decoded_request(dean_case, decoded)
        self.assertTrue(scores["is_contrastive_case"])
        self.assertFalse(scores["contrastive_negation_ok"])
        self.assertFalse(scores["pro_ops_ok"])


if __name__ == "__main__":
    unittest.main()
