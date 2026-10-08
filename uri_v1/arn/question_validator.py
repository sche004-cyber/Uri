"""ARN Question Validator (Batch A2.8A).

Enforces neutrality, grounding, atomicity, and non-presupposition on framed questions.

Governing Rule:
    The validator itself must NOT become a hidden semantic decoder.
    It verifies structural grounding and neutrality without evaluating
    the semantic truth of the turn.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Set, Tuple

from uri_v1.arn.uncertainty_contracts import (
    FramedQuestion,
    QuestionValidationFlag,
    QuestionValidationResult,
    SemanticUncertainty,
    UncertaintyType,
)

# Patterns that indicate a question presupposes the semantic answer
_PRESUPPOSITION_PATTERNS = [
    re.compile(r"\bwhy\s+is\s+(\w+)\s+(prohibited|forbidden|disallowed|banned)\b", re.IGNORECASE),
    re.compile(r"\bconfirm\s+that\s+(\w+)\s+is\s+(not|never|prohibited)\b", re.IGNORECASE),
    re.compile(r"\bexplain\s+why\s+the\s+user\s+wants\s+to\s+prohibit\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+prohibited\s+action\b", re.IGNORECASE),
    re.compile(r"\bconfirm\s+that\s+the\s+user\s+does\s+not\s+want\b", re.IGNORECASE),
    re.compile(r"\bwhy\s+should\s+(\w+)\s+be\s+avoided\b", re.IGNORECASE),
]

# Words that often signal non-atomic compound questions
_COMPOUND_QUESTION_PATTERNS = [
    re.compile(r"\band\s+also\s+what\b", re.IGNORECASE),
    re.compile(r"\band\s+furthermore\b", re.IGNORECASE),
    re.compile(r"\?\s+[A-Z].*\?", re.IGNORECASE),  # Two question marks
]


class QuestionValidator:
    """Validates framed semantic questions against neutrality and grounding gates."""

    def validate_question(
        self,
        question: FramedQuestion,
        uncertainty: SemanticUncertainty,
        source_text: str,
        known_entities: Sequence[str] = (),
    ) -> QuestionValidationResult:
        """Validates a single framed question against architectural gates."""
        flags: List[QuestionValidationFlag] = []
        diagnostics: List[str] = []

        q_text = question.question_text.strip()

        # Gate 1: Presupposition & Neutrality Check
        for pat in _PRESUPPOSITION_PATTERNS:
            if pat.search(q_text):
                flags.append(QuestionValidationFlag.PRESUPPOSES_ANSWER)
                diagnostics.append(f"Question presupposes semantic answer: matches leading pattern '{pat.pattern}'.")
                break

        # Gate 2: Atomicity Check (No compound multi-question stuffing)
        for pat in _COMPOUND_QUESTION_PATTERNS:
            if pat.search(q_text):
                flags.append(QuestionValidationFlag.COMBINED_UNCERTAINTIES)
                diagnostics.append("Question combines multiple disjoint inquiries into one (violates atomicity).")
                break

        # Gate 3: Critical Signal Preservation Check
        # If uncertainty is anchored on a specific structural signal, question should reference that marker/concept
        if uncertainty.anchored_signals:
            signal_found = False
            for sig in uncertainty.anchored_signals:
                if sig.span_text.lower() in q_text.lower():
                    signal_found = True
                    break
                # Also check associated verb if signal was action
                if sig.associated_verb and sig.associated_verb.lower() in q_text.lower():
                    signal_found = True
                    break
            if not signal_found and uncertainty.is_critical:
                flags.append(QuestionValidationFlag.LOST_CRITICAL_SIGNAL)
                spans = [s.span_text for s in uncertainty.anchored_signals]
                diagnostics.append(f"Question failed to ground or preserve anchored signal ({', '.join(spans)}).")

        # Gate 4: Grounding & Candidate Invention Check
        # Verify that specific quoted terms in the question appear in source text or known entities
        quoted_terms = re.findall(r'"([^"]+)"', q_text) + re.findall(r"'([A-Za-z0-9_]{3,})'", q_text)
        lower_source = source_text.lower()
        lower_entities = {e.lower() for e in known_entities}

        for term in quoted_terms:
            t_lower = term.lower().strip()
            # If term is a single common functional word (e.g. 'send', 'don't', 'it'), check in text
            if len(t_lower) > 2 and t_lower not in lower_source and t_lower not in lower_entities:
                # Disregard generic grammatical role labels
                if t_lower not in {"requested", "prohibited", "deferred", "boolean", "action", "target"}:
                    flags.append(QuestionValidationFlag.UNGROUNDED_REFERENT)
                    diagnostics.append(f"Question introduces ungrounded referent '{term}' not present in source.")
                    break

        # Gate 5: Relevance to Declared Uncertainty Type
        if uncertainty.uncertainty_type == UncertaintyType.NEGATION_SCOPE:
            if not any(w in q_text.lower() for w in ["not", "negat", "prohibit", "scope", "apply", "govern"]):
                flags.append(QuestionValidationFlag.NOT_ADDRESSING_UNCERTAINTY)
                diagnostics.append("Question does not address negation scope.")
        elif uncertainty.uncertainty_type == UncertaintyType.CONDITIONAL_DEPENDENCY:
            if not any(w in q_text.lower() for w in ["condition", "if", "unless", "contingen", "prereq"]):
                flags.append(QuestionValidationFlag.NOT_ADDRESSING_UNCERTAINTY)
                diagnostics.append("Question does not address conditional dependency.")
        elif uncertainty.uncertainty_type == UncertaintyType.TEMPORAL_DEPENDENCY:
            if not any(w in q_text.lower() for w in ["when", "time", "until", "tempor", "defer", "schedul", "delay"]):
                flags.append(QuestionValidationFlag.NOT_ADDRESSING_UNCERTAINTY)
                diagnostics.append("Question does not address temporal dependency.")
        elif uncertainty.uncertainty_type == UncertaintyType.UNRESOLVED_REFERENCE:
            if not any(w in q_text.lower() for w in ["refer", "which", "bind", "target", "mean", "identity"]):
                flags.append(QuestionValidationFlag.NOT_ADDRESSING_UNCERTAINTY)
                diagnostics.append("Question does not address unresolved reference.")

        if not flags:
            flags.append(QuestionValidationFlag.VALID)
            diag = "Question is grounded, neutral, and atomic."
        else:
            diag = " | ".join(diagnostics)

        is_valid = (flags == [QuestionValidationFlag.VALID])
        return QuestionValidationResult(
            question_id=question.question_id,
            is_valid=is_valid,
            flags=tuple(flags),
            diagnostic_message=diag,
        )

    def validate_batch(
        self,
        questions: Sequence[FramedQuestion],
        uncertainties: Sequence[SemanticUncertainty],
        source_text: str,
        known_entities: Sequence[str] = (),
    ) -> Tuple[QuestionValidationResult, ...]:
        """Validates a collection of questions, including duplicate detection."""
        results: List[QuestionValidationResult] = []
        seen_texts: Set[str] = set()

        u_map = {u.uncertainty_id: u for u in uncertainties}

        for q in questions:
            u = u_map.get(q.uncertainty_id)
            if not u:
                results.append(
                    QuestionValidationResult(
                        question_id=q.question_id,
                        is_valid=False,
                        flags=(QuestionValidationFlag.NOT_ADDRESSING_UNCERTAINTY,),
                        diagnostic_message=f"Question references nonexistent uncertainty ID '{q.uncertainty_id}'.",
                    )
                )
                continue

            # Check duplicate question text
            norm_text = re.sub(r"\s+", " ", q.question_text.lower().strip())
            if norm_text in seen_texts:
                results.append(
                    QuestionValidationResult(
                        question_id=q.question_id,
                        is_valid=False,
                        flags=(QuestionValidationFlag.DUPLICATE_QUESTION,),
                        diagnostic_message=f"Duplicate question detected: '{q.question_text}'.",
                    )
                )
                continue
            seen_texts.add(norm_text)

            res = self.validate_question(
                question=q,
                uncertainty=u,
                source_text=source_text,
                known_entities=known_entities,
            )
            results.append(res)

        return tuple(results)
