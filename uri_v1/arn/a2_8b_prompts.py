"""M35 URIv1 Batch A2.8B — RAR + ARN Prompt Builders & Schemas.

Constructs strictly isolated prompts and strict JSON schemas for:
- Mode A (RAW): Minimum semantic extraction prompt, zero external context.
- Mode B (RAR): Raw turn + TurnFrame evidence + RAR-confirmed anchors.
- Mode C (RAR + ARN): Mode B + Preserved structural signals + Discovered uncertainties + Neutral questions.
- Anti-leakage compliance auditing for Mode C questions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.arn.uncertainty_contracts import FramedQuestion, SemanticUncertainty, StructuralSignal
from uri_v1.turn.rar_contracts import RAROutcome, RARResolution
from uri_v1.turn.turn_frame import TurnFrame


AMPLIFICATION_SCHEMA_NAME = "semantic_interpretation"

AMPLIFICATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "description": "User primary intended outcome as a concise phrase.",
        },
        "intent_family": {
            "type": "string",
            "enum": [
                "retrieve", "create", "modify", "communicate",
                "execute", "analyze", "compare", "research",
                "navigate", "converse", "unspecified"
            ],
            "description": "Broad intent category.",
        },
        "requested_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Base verbs of actions explicitly requested to be performed.",
        },
        "prohibited_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Base verbs of actions explicitly forbidden, negated, or prohibited.",
        },
        "operation_bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "target_id": {"type": "string"},
                },
                "required": ["operation", "target_id"],
                "additionalProperties": False,
            },
            "description": "Coupling between each operation verb and its bound target entity/ID.",
        },
        "conditions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Prerequisite or exception conditions governing execution (e.g. 'if Dean approves').",
        },
        "temporal_constraints": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Temporal gating triggers or deferrals (e.g. 'until next Friday').",
        },
        "is_unresolved_or_ambiguous": {
            "type": "boolean",
            "description": "True if an entity or reference in the turn is ambiguous or unresolved and must not be guessed.",
        },
    },
    "required": [
        "goal",
        "intent_family",
        "requested_operations",
        "prohibited_operations",
        "operation_bindings",
        "conditions",
        "temporal_constraints",
        "is_unresolved_or_ambiguous",
    ],
    "additionalProperties": False,
}

BASE_SYSTEM_PROMPT = """You are URIv1's Step-1 Semantic Interpretation Engine.
Analyze the user turn and extract its semantic structure into strict JSON:
- goal: concise summary of user goal. Never output body drafts.
- intent_family: one intent enum.
- requested_operations: list of base verbs requested (e.g. ["draft", "sign"]). If none, [].
- prohibited_operations: list of base verbs explicitly prohibited or negated (e.g. ["send"]). If none, [].
- operation_bindings: list of {operation, target_id} pairing each action with its exact target.
- conditions: explicit conditions or prerequisites (e.g. ["if the Dean approves"]). If none, [].
- temporal_constraints: time triggers or gating deferrals (e.g. ["until next Friday"]). If none, [].
- is_unresolved_or_ambiguous: set to true if any pronoun/reference cannot be conclusively resolved or is ambiguous. Do not invent referents.

Invariants:
- Never invert polarity: do not put prohibited actions in requested_operations.
- Never invent operations or entities not present in input or context.
- Output valid JSON only."""


# ---------------------------------------------------------------------------
# Mode A Prompt: RAW
# ---------------------------------------------------------------------------
def build_mode_a_prompt(user_text: str) -> str:
    """Mode A: Only the raw user message with minimal output contract."""
    return f"[User Message]\n{user_text}\n\nTask: Extract semantic structure into JSON."


# ---------------------------------------------------------------------------
# Mode B Prompt: RAR
# ---------------------------------------------------------------------------
def build_mode_b_prompt(
    user_text: str,
    turn_frame: Optional[TurnFrame] = None,
    rar_results: Sequence[RARResolution] = (),
) -> str:
    """Mode B: Raw turn + TurnFrame evidence + Deterministic RAR facts."""
    parts = [f"[User Message]\n{user_text}"]

    if turn_frame is not None:
        tf_lines = ["[TurnFrame Evidence]"]
        verbs = [a.verb for a in turn_frame.candidate_actions]
        if verbs:
            tf_lines.append(f"- Candidate action verbs: {', '.join(verbs)}")
        if turn_frame.negation_spans:
            tf_lines.append(f"- Negation spans: {', '.join(turn_frame.negation_spans)}")
        refs = [r.expression for r in turn_frame.candidate_references]
        if refs:
            tf_lines.append(f"- Referring expressions: {', '.join(refs)}")
        if turn_frame.temporal_surface_spans:
            tf_lines.append(f"- Temporal mentions: {', '.join(turn_frame.temporal_surface_spans)}")
        parts.append("\n".join(tf_lines))

    if rar_results:
        rar_lines = ["[Deterministic RAR Anchors]"]
        for rar in rar_results:
            if rar.outcome == RAROutcome.RESOLVED:
                rar_lines.append(f"- Confirmed Anchor: '{rar.reference_expression}' -> {rar.candidate_id}")
            elif rar.outcome == RAROutcome.UNKNOWN:
                rar_lines.append(f"- Unresolved Reference: '{rar.reference_expression}' (target unknown in active context)")
            elif rar.outcome == RAROutcome.AMBIGUOUS:
                cands = ", ".join(rar.ambiguous_candidate_ids)
                rar_lines.append(f"- Ambiguous Reference: '{rar.reference_expression}' (tied candidates: {cands})")
        parts.append("\n".join(rar_lines))

    parts.append("Task: Extract semantic structure into JSON using confirmed anchors where resolved.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Mode C Prompt: RAR + ARN
# ---------------------------------------------------------------------------
def build_mode_c_prompt(
    user_text: str,
    turn_frame: Optional[TurnFrame] = None,
    rar_results: Sequence[RARResolution] = (),
    signals: Sequence[StructuralSignal] = (),
    uncertainties: Sequence[SemanticUncertainty] = (),
    questions: Sequence[FramedQuestion] = (),
) -> str:
    """Mode C: Mode B + Preserved Structural Signals + ARN Uncertainties + Neutral Questions."""
    parts = [f"[User Message]\n{user_text}"]

    if turn_frame is not None:
        tf_lines = ["[TurnFrame Evidence]"]
        verbs = [a.verb for a in turn_frame.candidate_actions]
        if verbs:
            tf_lines.append(f"- Candidate action verbs: {', '.join(verbs)}")
        if turn_frame.negation_spans:
            tf_lines.append(f"- Negation spans: {', '.join(turn_frame.negation_spans)}")
        refs = [r.expression for r in turn_frame.candidate_references]
        if refs:
            tf_lines.append(f"- Referring expressions: {', '.join(refs)}")
        parts.append("\n".join(tf_lines))

    if rar_results:
        rar_lines = ["[Deterministic RAR Anchors]"]
        for rar in rar_results:
            if rar.outcome == RAROutcome.RESOLVED:
                rar_lines.append(f"- Confirmed Anchor: '{rar.reference_expression}' -> {rar.candidate_id}")
            elif rar.outcome == RAROutcome.UNKNOWN:
                rar_lines.append(f"- Unresolved Reference: '{rar.reference_expression}' (target unknown in active context)")
            elif rar.outcome == RAROutcome.AMBIGUOUS:
                cands = ", ".join(rar.ambiguous_candidate_ids)
                rar_lines.append(f"- Ambiguous Reference: '{rar.reference_expression}' (tied candidates: {cands})")
        parts.append("\n".join(rar_lines))

    if signals:
        sig_lines = ["[Preserved Structural Signals]"]
        for s in signals:
            sig_lines.append(f"- {s.signal_type.value}: \"{s.span_text}\" (chars {s.start_char}-{s.end_char})")
        parts.append("\n".join(sig_lines))

    if uncertainties and questions:
        arn_lines = ["[Discovered Uncertainties & Clarification Framing]"]
        for u, q in zip(uncertainties, questions):
            arn_lines.append(f"- Uncertainty: {u.description}")
            arn_lines.append(f"  Clarification Question: {q.question_text}")
        parts.append("\n".join(arn_lines))

    parts.append("Task: Resolve the semantic uncertainties and extract final semantic structure into JSON.")
    return "\n\n".join(parts)


def wrap_chatml_prompt(system_prompt: str, user_prompt: str) -> str:
    """Formats prompt with ChatML and pre-closed think block for Qwen models."""
    return (
        f"<|im_start|>system\n{system_prompt.strip()}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt.strip()}<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n</think>\n"
    )
