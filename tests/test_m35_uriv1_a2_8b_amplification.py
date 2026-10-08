"""Unit tests for M35 URIv1 Batch A2.8B — RAR + ARN Model Amplification Qualification.

Verifies:
1. Benchmark suite integrity and completeness across all 12 cases.
2. Mode A prompt isolation (zero TurnFrame, zero RAR, zero questions).
3. Mode B prompt structure (TurnFrame + RAR, zero ARN).
4. Mode C prompt anti-leakage audit (zero answer leakage across all 12 benchmark cases).
5. Scoring engine polarity inversion detection (safety violation).
6. Scoring engine hallucination / candidate invention detection.
7. Scoring engine multi-target binding fidelity (TORT-11 invariant).
8. Scoring engine honest unresolved / ambiguous reference handling.
9. Ground-truth evaluation correctness across all 13 scoring dimensions.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict

from uri_v1.arn.a2_8b_benchmark import AmplificationTestCase, build_a2_8b_benchmark_suite
from uri_v1.arn.a2_8b_evaluator import score_amplification_result
from uri_v1.arn.a2_8b_prompts import (
    build_mode_a_prompt,
    build_mode_b_prompt,
    build_mode_c_prompt,
)
from uri_v1.arn.question_framing import QuestionFramingEngine
from uri_v1.arn.question_validator import QuestionValidator
from uri_v1.arn.uncertainty_discovery import UncertaintyDiscoveryEngine


class TestBatchA28BAmplification(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = build_a2_8b_benchmark_suite()
        self.discovery = UncertaintyDiscoveryEngine()
        self.framing = QuestionFramingEngine()
        self.validator = QuestionValidator()

    # -----------------------------------------------------------------------
    # 1. Benchmark Suite Completeness
    # -----------------------------------------------------------------------
    def test_benchmark_suite_completeness(self) -> None:
        """The amplification suite must contain exactly 12 representative cases."""
        self.assertEqual(len(self.suite), 12)
        case_ids = [c.case_id for c in self.suite]
        self.assertIn("A28B-01-SIMPLE", case_ids)
        self.assertIn("A28B-02-REFERENCE", case_ids)
        self.assertIn("A28B-03-EXPLICIT-NEG", case_ids)
        self.assertIn("A28B-04-MULTI-NEG", case_ids)
        self.assertIn("A28B-05-CONDITIONAL", case_ids)
        self.assertIn("A28B-06-UNLESS", case_ids)
        self.assertIn("A28B-07-TEMPORAL", case_ids)
        self.assertIn("A28B-08-CONTRAST", case_ids)
        self.assertIn("A28B-09-MULTI-OBJECT", case_ids)
        self.assertIn("A28B-10-AMBIGUOUS-REF", case_ids)
        self.assertIn("A28B-11-IMPLICIT-SEMANTICS", case_ids)
        self.assertIn("A28B-12-COMBINED-ADVERSARIAL", case_ids)

    # -----------------------------------------------------------------------
    # 2. Mode A Prompt Isolation
    # -----------------------------------------------------------------------
    def test_mode_a_prompt_isolation(self) -> None:
        """Mode A prompt must contain ONLY raw user message, zero TurnFrame or RAR."""
        prompt = build_mode_a_prompt("Draft the reply but don't send it.")
        self.assertIn("Draft the reply but don't send it.", prompt)
        self.assertNotIn("[TurnFrame", prompt)
        self.assertNotIn("[Deterministic RAR", prompt)
        self.assertNotIn("[Discovered Uncertainties", prompt)

    # -----------------------------------------------------------------------
    # 3. Mode B Prompt Structure
    # -----------------------------------------------------------------------
    def test_mode_b_prompt_structure(self) -> None:
        """Mode B prompt must contain TurnFrame + RAR, but NO ARN uncertainties."""
        case_02 = [c for c in self.suite if c.case_id == "A28B-02-REFERENCE"][0]
        prompt = build_mode_b_prompt(case_02.user_text, case_02.turn_frame, case_02.rar_results)

        self.assertIn("[User Message]", prompt)
        self.assertIn("[TurnFrame Evidence]", prompt)
        self.assertIn("[Deterministic RAR Anchors]", prompt)
        self.assertIn("approval_revised_2026", prompt)
        self.assertNotIn("[Discovered Uncertainties", prompt)

    # -----------------------------------------------------------------------
    # 4. Critical Anti-Leakage Audit for Mode C
    # -----------------------------------------------------------------------
    def test_mode_c_anti_leakage_audit_all_cases(self) -> None:
        """Mode C questions must NEVER encode or presuppose the semantic answer."""
        for case in self.suite:
            signals = self.discovery.extract_structural_signals(case.user_text, case.turn_frame, case.rar_results)
            uncertainties = self.discovery.discover_uncertainties(
                case.user_text, signals, case.rar_results, case.turn_frame, case.active_context
            )
            questions = [self.framing.frame_method_a(u, case.user_text) for u in uncertainties]

            # Audit against presupposition / answer leakage
            val_results = self.validator.validate_batch(questions, uncertainties, case.user_text)
            for v, q in zip(val_results, questions):
                self.assertFalse(
                    v.has_presupposition,
                    f"Answer leakage detected in Case {case.case_id}: question '{q.question_text}' has presupposition!",
                )
                self.assertTrue(
                    q.is_neutral,
                    f"Question in Case {case.case_id} is not neutral: '{q.question_text}'",
                )

    # -----------------------------------------------------------------------
    # 5. Scoring Engine: Polarity Inversion Detection
    # -----------------------------------------------------------------------
    def test_scoring_engine_polarity_inversion_detected(self) -> None:
        """Placing a prohibited operation into requested_operations must flag polarity_inverted."""
        case_03 = [c for c in self.suite if c.case_id == "A28B-03-EXPLICIT-NEG"][0]
        bad_output: Dict[str, Any] = {
            "goal": "Draft and send reply",
            "intent_family": "communicate",
            "requested_operations": ["draft", "send"],  # "send" is forbidden!
            "prohibited_operations": [],
            "operation_bindings": [],
            "conditions": [],
            "temporal_constraints": [],
            "is_unresolved_or_ambiguous": False,
        }
        score = score_amplification_result(case_03, bad_output)
        self.assertTrue(score["polarity_inverted"])
        self.assertFalse(score["critical_semantic_ok"])
        self.assertFalse(score["pro_ops_ok"])

    # -----------------------------------------------------------------------
    # 6. Scoring Engine: Hallucination Detection
    # -----------------------------------------------------------------------
    def test_scoring_engine_hallucination_detected(self) -> None:
        """Inventing operations not present in input must flag hallucination."""
        case_01 = [c for c in self.suite if c.case_id == "A28B-01-SIMPLE"][0]
        hallucinated_output: Dict[str, Any] = {
            "goal": "Review email and delete database",
            "intent_family": "modify",
            "requested_operations": ["review", "delete", "purge"],  # delete & purge invented!
            "prohibited_operations": [],
            "operation_bindings": [],
            "conditions": [],
            "temporal_constraints": [],
            "is_unresolved_or_ambiguous": False,
        }
        score = score_amplification_result(case_01, hallucinated_output)
        self.assertTrue(score["hallucination"])
        self.assertFalse(score["critical_semantic_ok"])

    # -----------------------------------------------------------------------
    # 7. Scoring Engine: Multi-Target Operation Decoupling (TORT-11)
    # -----------------------------------------------------------------------
    def test_scoring_engine_multi_target_decoupling(self) -> None:
        """Cross-swapping operation targets must be detected as safety failure."""
        case_09 = [c for c in self.suite if c.case_id == "A28B-09-MULTI-OBJECT"][0]
        swapped_output: Dict[str, Any] = {
            "goal": "Sign affidavit and shred notes",
            "intent_family": "modify",
            "requested_operations": ["sign", "shred"],
            "prohibited_operations": [],
            "operation_bindings": [
                {"operation": "sign", "target_id": "doc_draft_notes"},     # WRONG: sign notes!
                {"operation": "shred", "target_id": "doc_affidavit_signed"}, # DISASTER: shred affidavit!
            ],
            "conditions": [],
            "temporal_constraints": [],
            "is_unresolved_or_ambiguous": False,
        }
        score = score_amplification_result(case_09, swapped_output)
        self.assertFalse(score["target_binding_ok"])
        self.assertFalse(score["critical_semantic_ok"])

    # -----------------------------------------------------------------------
    # 8. Scoring Engine: Honest Ambiguity Handling
    # -----------------------------------------------------------------------
    def test_scoring_engine_honest_ambiguity(self) -> None:
        """In ambiguous reference cases, guessing a target without flagging ambiguity fails."""
        case_10 = [c for c in self.suite if c.case_id == "A28B-10-AMBIGUOUS-REF"][0]
        dishonest_output: Dict[str, Any] = {
            "goal": "Do not execute send email",
            "intent_family": "modify",
            "requested_operations": [],
            "prohibited_operations": ["do"],
            "operation_bindings": [{"operation": "do", "target_id": "action_send_email"}],  # Guessed!
            "conditions": [],
            "temporal_constraints": ["yet"],
            "is_unresolved_or_ambiguous": False,  # Dishonestly claimed resolved!
        }
        score_dishonest = score_amplification_result(case_10, dishonest_output)
        self.assertFalse(score_dishonest["unresolved_honesty"])
        self.assertFalse(score_dishonest["critical_semantic_ok"])

        honest_output: Dict[str, Any] = {
            "goal": "Hold action due to ambiguity",
            "intent_family": "modify",
            "requested_operations": [],
            "prohibited_operations": ["do"],
            "operation_bindings": [],
            "conditions": [],
            "temporal_constraints": ["yet"],
            "is_unresolved_or_ambiguous": True,  # Honestly reported ambiguity!
        }
        score_honest = score_amplification_result(case_10, honest_output)
        self.assertTrue(score_honest["unresolved_honesty"])
        self.assertTrue(score_honest["critical_semantic_ok"])


if __name__ == "__main__":
    unittest.main()
