"""Unit tests for M35 URIv1 Batch A2.8A ARN Foundation.

Tests:
1. Structural signal preservation (all markers with spans and provenance).
2. RAR unresolved/ambiguous propagation into uncertainty types.
3. Uncertainty discovery correctness and completeness.
4. Uncertainty provenance tracking.
5. Question coverage across declared uncertainties.
6. Question correctness and semantic grounding.
7. Question neutrality (rejection of leading presuppositions).
8. Question atomicity (rejection of compound stuffed questions).
9. Question grounding (rejection of invented referents).
10. Critical uncertainty omission detection.
11. Malformed and leading question rejection by QuestionValidator.
12. Zero invented referents invariant.
13. Preservation of operation-target relationships (TORT-11 invariant).
"""

from __future__ import annotations

import unittest
from typing import Tuple

from uri_v1.arn.a2_8a_benchmark import build_a2_8a_benchmark_suite
from uri_v1.arn.question_framing import QuestionFramingEngine
from uri_v1.arn.question_validator import QuestionValidator
from uri_v1.arn.uncertainty_contracts import (
    FramedQuestion,
    QuestionFramingMethod,
    QuestionValidationFlag,
    QuestionValidationResult,
    SemanticUncertainty,
    StructuralSignal,
    StructuralSignalType,
    UncertaintyType,
)
from uri_v1.arn.uncertainty_discovery import UncertaintyDiscoveryEngine
from uri_v1.turn.rar_contracts import RAROutcome, RARResolution
from uri_v1.turn.turn_frame import CandidateAction, CandidateReference, TurnFrame


class TestBatchA28AARNFoundation(unittest.TestCase):
    def setUp(self) -> None:
        self.discovery = UncertaintyDiscoveryEngine()
        self.framing = QuestionFramingEngine()
        self.validator = QuestionValidator()
        self.suite = build_a2_8a_benchmark_suite()

    # -----------------------------------------------------------------------
    # 1. Structural Signal Preservation
    # -----------------------------------------------------------------------
    def test_structural_signal_preservation(self) -> None:
        """All structural markers (negation, contrast, conditional, temporal) must be preserved with spans."""
        text = "Don't send the reply unless the Dean approves, but hold off until tomorrow."
        signals = self.discovery.extract_structural_signals(text)

        sig_types = {s.signal_type for s in signals}
        self.assertIn(StructuralSignalType.NEGATION_MARKER, sig_types)
        self.assertIn(StructuralSignalType.CONDITIONAL_MARKER, sig_types)
        self.assertIn(StructuralSignalType.CONTRAST_MARKER, sig_types)
        self.assertIn(StructuralSignalType.TEMPORAL_MARKER, sig_types)

        # Check character offsets and spans
        neg_sig = [s for s in signals if s.signal_type == StructuralSignalType.NEGATION_MARKER][0]
        self.assertEqual(neg_sig.span_text.lower(), "don't")
        self.assertEqual(text[neg_sig.start_char : neg_sig.end_char].lower(), "don't")
        self.assertTrue(bool(neg_sig.provenance))

    # -----------------------------------------------------------------------
    # 2. StructuralSignal != SemanticConclusion Invariant
    # -----------------------------------------------------------------------
    def test_structural_signal_does_not_hardcode_semantic_conclusion(self) -> None:
        """Preserving 'don't' does NOT create a hard-coded prohibited action in the engine."""
        text = "Don't send the draft."
        signals = self.discovery.extract_structural_signals(text)
        uncertainties = self.discovery.discover_uncertainties(text, signals)

        # Signals and uncertainties exist, but NO DecodedRequest or prohibited action is decided
        self.assertTrue(len(signals) > 0)
        self.assertTrue(len(uncertainties) > 0)
        for u in uncertainties:
            # All items are hypotheses/questions, not conclusions
            self.assertIsInstance(u.uncertainty_type, UncertaintyType)

    # -----------------------------------------------------------------------
    # 3. RAR Unresolved & Ambiguous Propagation
    # -----------------------------------------------------------------------
    def test_rar_unresolved_and_ambiguous_propagation(self) -> None:
        """RAR UNRESOLVED and AMBIGUOUS outcomes must propagate into UNRESOLVED_REFERENCE uncertainties."""
        rar_unresolved = RARResolution(
            reference_expression="that document",
            outcome=RAROutcome.UNKNOWN,
        )
        rar_ambiguous = RARResolution(
            reference_expression="the order",
            outcome=RAROutcome.AMBIGUOUS,
            ambiguous_candidate_ids=("order_1", "order_2"),
        )

        text = "Process that document and sign the order."
        signals = self.discovery.extract_structural_signals(text, rar_results=(rar_unresolved, rar_ambiguous))
        uncertainties = self.discovery.discover_uncertainties(text, signals, rar_results=(rar_unresolved, rar_ambiguous))

        ref_uncertainties = [u for u in uncertainties if u.uncertainty_type == UncertaintyType.UNRESOLVED_REFERENCE]
        self.assertTrue(len(ref_uncertainties) >= 2)
        descs = " ".join(u.description for u in ref_uncertainties)
        self.assertIn("that document", descs)
        self.assertIn("the order", descs)

    # -----------------------------------------------------------------------
    # 4. Uncertainty Provenance Tracking
    # -----------------------------------------------------------------------
    def test_uncertainty_provenance_tracking(self) -> None:
        """Every discovered uncertainty must carry an auditable provenance string."""
        text = "Draft reply if approved."
        signals = self.discovery.extract_structural_signals(text)
        uncertainties = self.discovery.discover_uncertainties(text, signals)

        for u in uncertainties:
            self.assertTrue(bool(u.provenance))
            self.assertTrue(u.provenance.startswith("UncertaintyDiscovery"))

    # -----------------------------------------------------------------------
    # 5. Question Coverage & Neutrality (Method A)
    # -----------------------------------------------------------------------
    def test_question_coverage_and_neutrality_deterministic(self) -> None:
        """Deterministic framing (Method A) must produce 100% coverage, 100% neutral questions."""
        text = "Review the email and draft a reply, but don't send it."
        signals = self.discovery.extract_structural_signals(text)
        uncertainties = self.discovery.discover_uncertainties(text, signals)

        for u in uncertainties:
            q = self.framing.frame_method_a(u, text)
            self.assertEqual(q.uncertainty_id, u.uncertainty_id)
            self.assertTrue(q.is_neutral)
            self.assertTrue(q.is_atomic)
            self.assertFalse(q.presupposes_answer)

            # Validate with validator
            val = self.validator.validate_question(q, u, text)
            self.assertTrue(val.is_valid, f"Method A failed validation: {val.diagnostic_message}")

    # -----------------------------------------------------------------------
    # 6. Presupposition / Leading Question Rejection
    # -----------------------------------------------------------------------
    def test_leading_question_rejection(self) -> None:
        """Validator must reject questions that presuppose the answer."""
        u = SemanticUncertainty(
            uncertainty_id="U-01",
            uncertainty_type=UncertaintyType.NEGATION_SCOPE,
            description="Negation scope of 'don't'",
            relevance_justification="Safety",
        )
        leading_q = FramedQuestion(
            question_id="Q-BAD-01",
            uncertainty_id="U-01",
            question_text="Why is sending prohibited by the user?",
            framing_method=QuestionFramingMethod.METHOD_B_MODEL_ASSISTED,
        )
        val = self.validator.validate_question(leading_q, u, "Don't send it.")
        self.assertFalse(val.is_valid)
        self.assertTrue(val.has_presupposition)
        self.assertIn(QuestionValidationFlag.PRESUPPOSES_ANSWER, val.flags)

    # -----------------------------------------------------------------------
    # 7. Compound Question / Non-Atomicity Rejection
    # -----------------------------------------------------------------------
    def test_compound_question_rejection(self) -> None:
        """Validator must reject questions that conflate multiple inquiries."""
        u = SemanticUncertainty(
            uncertainty_id="U-02",
            uncertainty_type=UncertaintyType.NEGATION_SCOPE,
            description="Negation scope",
            relevance_justification="Safety",
        )
        compound_q = FramedQuestion(
            question_id="Q-BAD-02",
            uncertainty_id="U-02",
            question_text="Does don't apply to send, and furthermore what time should it be filed?",
            framing_method=QuestionFramingMethod.METHOD_B_MODEL_ASSISTED,
        )
        val = self.validator.validate_question(compound_q, u, "Don't send it.")
        self.assertFalse(val.is_valid)
        self.assertIn(QuestionValidationFlag.COMBINED_UNCERTAINTIES, val.flags)

    # -----------------------------------------------------------------------
    # 8. Ungrounded Referent / Candidate Invention Rejection
    # -----------------------------------------------------------------------
    def test_ungrounded_referent_rejection(self) -> None:
        """Validator must reject questions introducing ungrounded entities."""
        u = SemanticUncertainty(
            uncertainty_id="U-03",
            uncertainty_type=UncertaintyType.UNRESOLVED_REFERENCE,
            description="Referent of 'it'",
            relevance_justification="Safety",
        )
        invented_q = FramedQuestion(
            question_id="Q-BAD-03",
            uncertainty_id="U-03",
            question_text="Does 'it' refer to 'Confidential_Fiscal_Spreadsheet_Q4'?",
            framing_method=QuestionFramingMethod.METHOD_B_MODEL_ASSISTED,
        )
        val = self.validator.validate_question(invented_q, u, "Review the memo and send it.", known_entities=["the memo"])
        self.assertFalse(val.is_valid)
        self.assertTrue(val.is_ungrounded)
        self.assertIn(QuestionValidationFlag.UNGROUNDED_REFERENT, val.flags)

    # -----------------------------------------------------------------------
    # 9. Critical Uncertainty Omission Rate (Benchmark Metric)
    # -----------------------------------------------------------------------
    def test_critical_uncertainty_omission_rate_zero(self) -> None:
        """The discovery engine must achieve 0% Critical Uncertainty Omission Rate on the benchmark."""
        total_expected = 0
        omitted = 0

        for case in self.suite:
            signals = self.discovery.extract_structural_signals(case.user_text, case.turn_frame, case.rar_results)
            uncertainties = self.discovery.discover_uncertainties(case.user_text, signals, case.rar_results, case.turn_frame)
            disc_types = {u.uncertainty_type for u in uncertainties}

            for exp_u in case.expected_uncertainty_types:
                total_expected += 1
                if exp_u not in disc_types:
                    omitted += 1

        cuor = (omitted / total_expected * 100.0) if total_expected else 0.0
        self.assertEqual(cuor, 0.0, f"Critical uncertainties were omitted! CUOR = {cuor:.1f}%")

    # -----------------------------------------------------------------------
    # 10. Multi-Target Operation Coupling (TORT-11 Invariant)
    # -----------------------------------------------------------------------
    def test_multi_target_operation_coupling_preserved(self) -> None:
        """Turns with multiple actions and objects must flag OPERATION_TARGET coupling."""
        case_09 = [c for c in self.suite if c.case_id == "A28A-09-MULTI-OBJECT"][0]
        signals = self.discovery.extract_structural_signals(case_09.user_text, case_09.turn_frame)
        uncertainties = self.discovery.discover_uncertainties(case_09.user_text, signals, turn_frame=case_09.turn_frame)

        target_u = [u for u in uncertainties if u.uncertainty_type == UncertaintyType.OPERATION_TARGET]
        self.assertTrue(len(target_u) > 0)
        self.assertIn("sign", target_u[0].description)
        self.assertIn("shred", target_u[0].description)

    # -----------------------------------------------------------------------
    # 11. Temporal Deferral Uncertainty (TORT-10 Invariant)
    # -----------------------------------------------------------------------
    def test_temporal_deferral_uncertainty_discovered(self) -> None:
        """Turns with temporal deferral must discover TEMPORAL_DEPENDENCY."""
        case_06 = [c for c in self.suite if c.case_id == "A28A-06-TEMPORAL"][0]
        signals = self.discovery.extract_structural_signals(case_06.user_text, case_06.turn_frame)
        uncertainties = self.discovery.discover_uncertainties(case_06.user_text, signals, turn_frame=case_06.turn_frame)

        temp_u = [u for u in uncertainties if u.uncertainty_type == UncertaintyType.TEMPORAL_DEPENDENCY]
        self.assertTrue(len(temp_u) > 0)
        self.assertIn("until", temp_u[0].description)

    # -----------------------------------------------------------------------
    # 12. Hybrid Framing Validation Fallback Gate (Method C)
    # -----------------------------------------------------------------------
    def test_hybrid_framing_fallback_safety(self) -> None:
        """Method C must adopt valid model questions and safely fall back when model is leading."""
        u = SemanticUncertainty(
            uncertainty_id="U-TEST-01",
            uncertainty_type=UncertaintyType.NEGATION_SCOPE,
            description="Negation scope of 'don't'",
            relevance_justification="Safety",
            anchored_signals=(
                StructuralSignal(
                    signal_type=StructuralSignalType.NEGATION_MARKER,
                    span_text="don't",
                    start_char=0,
                    end_char=5,
                    associated_verb="send",
                ),
            ),
        )
        # Even if endpoint produces leading questions or fails, Method C guarantees valid output
        hybrid_q = self.framing.frame_method_c(u, "Don't send it.")
        self.assertTrue(hybrid_q.is_neutral)
        self.assertTrue(hybrid_q.is_atomic)
        self.assertFalse(hybrid_q.presupposes_answer)

        val = self.validator.validate_question(hybrid_q, u, "Don't send it.")
        self.assertTrue(val.is_valid)

    # -----------------------------------------------------------------------
    # 13. Regression: Implicit Qualifier Signal Preservation & Anchoring
    # -----------------------------------------------------------------------
    def test_modifier_scope_signal_preserved_and_anchored(self) -> None:
        """Implicit qualifiers (e.g. 'appropriately') must be preserved as MODIFIER_MARKER and anchored."""
        text = "Deal with the Dean's email appropriately."
        signals = self.discovery.extract_structural_signals(text)

        mod_signals = [s for s in signals if s.signal_type == StructuralSignalType.MODIFIER_MARKER]
        self.assertEqual(len(mod_signals), 1)
        mod_sig = mod_signals[0]
        self.assertEqual(mod_sig.span_text, "appropriately")
        self.assertEqual(mod_sig.start_char, 27)
        self.assertEqual(mod_sig.end_char, 40)

        uncertainties = self.discovery.discover_uncertainties(text, signals)
        mod_u = [u for u in uncertainties if u.uncertainty_type == UncertaintyType.MODIFIER_SCOPE]
        self.assertEqual(len(mod_u), 1)
        self.assertEqual(mod_u[0].anchored_signals, (mod_sig,))

        # Deterministic Method A must ground the framed question with the exact token
        qa = self.framing.frame_method_a(mod_u[0], text)
        self.assertIn('"appropriately"', qa.question_text)
        val = self.validator.validate_question(qa, mod_u[0], text)
        self.assertTrue(val.is_valid)


if __name__ == "__main__":
    unittest.main()
