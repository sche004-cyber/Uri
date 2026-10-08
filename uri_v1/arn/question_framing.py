"""ARN Question Framing Engine (Batch A2.8A).

Implements and compares three methods for framing semantic questions:
- Method A: Pure deterministic structural synthesis from TurnFrame + RAR.
- Method B: Model-assisted question formulation.
- Method C: Hybrid (Deterministic evidence preservation + Model formulation + Deterministic validation fallback).

Governing Rule:
    Framed questions must be neutral, atomic, grounded, and non-leading.
    They must never presuppose the semantic outcome.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.arn.uncertainty_contracts import (
    FramedQuestion,
    QuestionFramingMethod,
    QuestionValidationFlag,
    SemanticUncertainty,
    StructuralSignal,
    UncertaintyType,
)
from uri_v1.arn.question_validator import QuestionValidator


class QuestionFramingEngine:
    """Engine for synthesizing and validating narrow semantic questions."""

    def __init__(
        self,
        endpoint_url: str = "http://127.0.0.1:1234/v1/completions",
        model_name: str = "qwen3.5-9b",
        timeout_seconds: float = 3.0,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.validator = QuestionValidator()

    # -----------------------------------------------------------------------
    # Method A: Deterministic Structural Framing
    # -----------------------------------------------------------------------
    def frame_method_a(
        self,
        uncertainty: SemanticUncertainty,
        user_text: str,
    ) -> FramedQuestion:
        """Deterministically generates a neutral, atomic question from structural signals."""
        u_type = uncertainty.uncertainty_type
        sig_spans = [s.span_text for s in uncertainty.anchored_signals]
        marker = sig_spans[0] if sig_spans else "indicated marker"

        q_text: str
        ans_type: str

        if u_type == UncertaintyType.NEGATION_SCOPE:
            q_text = f'Which candidate operation, if any, is governed by the negation marker "{marker}"?'
            ans_type = "operation_selection"

        elif u_type == UncertaintyType.OPERATION_POLARITY:
            q_text = f'What is the intended operational polarity for actions associated with "{marker}" (requested, prohibited, or deferred)?'
            ans_type = "polarity_selection"

        elif u_type == UncertaintyType.CONDITIONAL_DEPENDENCY:
            q_text = f'Under what prerequisite condition introduced by "{marker}" is the action contingent?'
            ans_type = "clarification"

        elif u_type == UncertaintyType.TEMPORAL_DEPENDENCY:
            q_text = f'What is the temporal constraint or gating trigger introduced by "{marker}"?'
            ans_type = "clarification"

        elif u_type == UncertaintyType.CONTRAST_RELATIONSHIP:
            q_text = f'How does the directive following "{marker}" qualify or oppose the preceding clause?'
            ans_type = "clarification"

        elif u_type == UncertaintyType.UNRESOLVED_REFERENCE:
            q_text = f'Which known entity or document in context does the reference "{marker}" bind to?'
            ans_type = "candidate_selection"

        elif u_type == UncertaintyType.OPERATION_TARGET:
            verbs = [s.span_text for s in uncertainty.anchored_signals if s.span_text]
            v_desc = f" ({', '.join(verbs)})" if verbs else ""
            q_text = f"Which specific target object is associated with each candidate operation{v_desc}?"
            ans_type = "binding_mapping"

        elif u_type == UncertaintyType.MODIFIER_SCOPE:
            q_text = f'What concrete operations are required by the qualifier "{marker}"?'
            ans_type = "clarification"

        else:
            q_text = f'How should the semantic uncertainty regarding "{marker}" be resolved?'
            ans_type = "clarification"

        return FramedQuestion(
            question_id=f"Q-A-{uncertainty.uncertainty_id}",
            uncertainty_id=uncertainty.uncertainty_id,
            question_text=q_text,
            framing_method=QuestionFramingMethod.METHOD_A_DETERMINISTIC,
            grounded_spans=tuple(sig_spans),
            expected_answer_type=ans_type,
            is_neutral=True,
            is_atomic=True,
            presupposes_answer=False,
            provenance="DeterministicStructuralTemplate",
        )

    # -----------------------------------------------------------------------
    # Method B: Model-Assisted Framing
    # -----------------------------------------------------------------------
    def frame_method_b(
        self,
        uncertainty: SemanticUncertainty,
        user_text: str,
    ) -> FramedQuestion:
        """Formulates question via model call to local endpoint."""
        sig_spans = [s.span_text for s in uncertainty.anchored_signals]
        marker = sig_spans[0] if sig_spans else ""

        chatml_prompt = (
            "<|im_start|>system\n"
            "You are a neutral question-framing module. Formulate exactly one neutral, atomic, non-leading question to clarify the detected semantic uncertainty.\n"
            "Rules:\n"
            "- Do NOT presuppose the answer.\n"
            "- Ground the question directly in the text.\n"
            "- Keep the question concise (under 25 words).\n"
            "- Output only the single question text.\n"
            "<|im_end|>\n"
            "<|im_start|>user\n"
            f"User turn: \"{user_text}\"\n"
            f"Detected uncertainty: {uncertainty.description}\n"
            f"Anchored text span: \"{marker}\"\n\n"
            "Formulate question:\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n</think>\n"
        )

        model_q_text: Optional[str] = None
        try:
            payload = {
                "model": self.model_name,
                "prompt": chatml_prompt,
                "max_tokens": 48,
                "temperature": 0.0,
                "stop": ["<|im_end|>", "\n"],
            }
            req = urllib.request.Request(
                self.endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["choices"][0]["text"].strip()
                if choice:
                    model_q_text = choice.lstrip("Question:").strip().strip('"')
        except Exception:
            model_q_text = None

        if not model_q_text:
            # Fallback to Method A if model endpoint is unreachable
            fallback = self.frame_method_a(uncertainty, user_text)
            return FramedQuestion(
                question_id=f"Q-B-{uncertainty.uncertainty_id}",
                uncertainty_id=uncertainty.uncertainty_id,
                question_text=fallback.question_text,
                framing_method=QuestionFramingMethod.METHOD_B_MODEL_ASSISTED,
                grounded_spans=fallback.grounded_spans,
                expected_answer_type=fallback.expected_answer_type,
                is_neutral=fallback.is_neutral,
                is_atomic=fallback.is_atomic,
                presupposes_answer=False,
                provenance="ModelAssistedEndpointFallback",
            )

        # Validate neutrality of model question
        val_res = self.validator.validate_question(
            question=FramedQuestion(
                question_id="temp",
                uncertainty_id=uncertainty.uncertainty_id,
                question_text=model_q_text,
                framing_method=QuestionFramingMethod.METHOD_B_MODEL_ASSISTED,
            ),
            uncertainty=uncertainty,
            source_text=user_text,
        )

        return FramedQuestion(
            question_id=f"Q-B-{uncertainty.uncertainty_id}",
            uncertainty_id=uncertainty.uncertainty_id,
            question_text=model_q_text,
            framing_method=QuestionFramingMethod.METHOD_B_MODEL_ASSISTED,
            grounded_spans=tuple(sig_spans),
            expected_answer_type="clarification",
            is_neutral=not val_res.has_presupposition,
            is_atomic=QuestionValidationFlag.COMBINED_UNCERTAINTIES not in val_res.flags,
            presupposes_answer=val_res.has_presupposition,
            provenance="ModelAssistedDirect",
        )

    # -----------------------------------------------------------------------
    # Method C: Hybrid Framing (Deterministic Grounding + Model + Validation Gate)
    # -----------------------------------------------------------------------
    def frame_method_c(
        self,
        uncertainty: SemanticUncertainty,
        user_text: str,
        known_entities: Sequence[str] = (),
    ) -> FramedQuestion:
        """Hybrid framing: attempts model framing, validates against neutrality gates, falls back to Method A."""
        # 1. Obtain deterministic candidate
        det_q = self.frame_method_a(uncertainty, user_text)

        # 2. Attempt model framing
        model_q = self.frame_method_b(uncertainty, user_text)

        # 3. Validate model question
        val = self.validator.validate_question(
            question=model_q,
            uncertainty=uncertainty,
            source_text=user_text,
            known_entities=known_entities,
        )

        # 4. If model question is fully valid, adopt it; otherwise enforce deterministic fallback
        if val.is_valid and not model_q.presupposes_answer:
            return FramedQuestion(
                question_id=f"Q-C-{uncertainty.uncertainty_id}",
                uncertainty_id=uncertainty.uncertainty_id,
                question_text=model_q.question_text,
                framing_method=QuestionFramingMethod.METHOD_C_HYBRID,
                grounded_spans=model_q.grounded_spans,
                expected_answer_type=model_q.expected_answer_type,
                is_neutral=True,
                is_atomic=True,
                presupposes_answer=False,
                provenance="HybridValidatedModel",
            )
        else:
            return FramedQuestion(
                question_id=f"Q-C-{uncertainty.uncertainty_id}",
                uncertainty_id=uncertainty.uncertainty_id,
                question_text=det_q.question_text,
                framing_method=QuestionFramingMethod.METHOD_C_HYBRID,
                grounded_spans=det_q.grounded_spans,
                expected_answer_type=det_q.expected_answer_type,
                is_neutral=True,
                is_atomic=True,
                presupposes_answer=False,
                provenance=f"HybridDeterministicFallback({val.flags[0].value if val.flags else 'INVALID'})",
            )
