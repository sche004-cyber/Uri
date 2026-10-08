"""LFM2.5-350M Wire Schema, Prompt Builder, and Normalizer (Batch A2.5 Stage 3).

Defines:
1. Strict JSON schema for native constrained generation via LM Studio.
2. Mode A prompt builder (Raw / TurnFrame / ActiveContext without RAR).
3. Mode B prompt builder (TurnFrame + ActiveContext + Deterministic RAR facts).
4. Deterministic normalizer mapping raw wire output to immutable DecodedRequest.

Invariants:
- Absolute zero post-hoc semantic repair.
- No polarity inversion or verb substitution in code.
- Truthful representation of model interpretation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from uri_v1.turn.active_context import ActiveContext
from uri_v1.turn.contracts import (
    AmbiguityKind,
    AttachmentReference,
    ConfidenceLevel,
    ConstraintScope,
    ContextDependency,
    ContextDependencyCategory,
    DecodedRequest,
    EntityCategory,
    IntendedOutcome,
    IntentFamily,
    MentionedEntity,
    OperationStatus,
    OutputPreferences,
    ReferenceKind,
    SemanticAmbiguity,
    SemanticConfidence,
    SemanticOperation,
    SemanticReference,
    TemporalReference,
)
from uri_v1.turn.turn_frame import TurnFrame


LFM_WIRE_SCHEMA_NAME = "decoded_request"

LFM_WIRE_SCHEMA: Dict[str, Any] = {
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
            "description": "Broad category of user intent.",
        },
        "requested_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Base verbs of actions requested by the user.",
        },
        "prohibited_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Base verbs of actions explicitly forbidden or negated by the user.",
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
            "description": "Binding of each operation to its target ID if known.",
        },
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                    "target_id": {"type": "string"},
                },
                "required": ["expression", "target_id"],
                "additionalProperties": False,
            },
            "description": "Referring expressions and their resolved target IDs.",
        },
        "temporal_references": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Time words explicitly mentioned in user turn.",
        },
        "constraints": {
            "type": "object",
            "properties": {
                "included_items": {"type": "array", "items": {"type": "string"}},
                "excluded_items": {"type": "array", "items": {"type": "string"}},
                "length_limit": {"type": "string"},
                "language_constraints": {"type": "string"},
            },
            "required": ["included_items", "excluded_items", "length_limit", "language_constraints"],
            "additionalProperties": False,
        },
        "output_preferences": {
            "type": "object",
            "properties": {
                "artifact_type": {"type": "string"},
                "format": {"type": "string"},
                "tone": {"type": "string"},
                "structure": {"type": "string"},
            },
            "required": ["artifact_type", "format", "tone", "structure"],
            "additionalProperties": False,
        },
        "ambiguities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "description": {"type": "string"},
                    "candidates": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["kind", "description", "candidates"],
                "additionalProperties": False,
            },
            "description": "Meaningful ambiguities in user turn.",
        },
        "context_dependencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["category", "description"],
                "additionalProperties": False,
            },
            "description": "External or prior session context required to execute request.",
        },
    },
    "required": [
        "goal",
        "intent_family",
        "requested_operations",
        "prohibited_operations",
        "operation_bindings",
        "references",
        "temporal_references",
        "constraints",
        "output_preferences",
        "ambiguities",
        "context_dependencies",
    ],
    "additionalProperties": False,
}

LFM_SYSTEM_PROMPT = """Step-1 Semantic Decoder for URIv1.
Extract only what is explicitly expressed in the user turn into JSON.
- goal: concise summary of user goal. Never write drafts or body text.
- intent_family: one intent enum.
- requested_operations: base actions requested in user turn. If none, [].
- prohibited_operations: base actions explicitly negated or forbidden in user turn. If none, [].
- operation_bindings: {operation, target_id} for each operation. If target unknown, empty target_id. If none, [].
- references: {expression, target_id} for referring expressions in user turn. If none, [].
- temporal_references: time words present in user turn. If none, [].
- constraints: explicit limitations stated in user turn.
- output_preferences: format, artifact_type, tone, structure if stated.
- ambiguities: {kind, description, candidates} if turn is ambiguous. If none, [].
- context_dependencies: {category, description} if turn requires prior context. If none, [].
Invariants:
Do NOT invent referents, dates, or operations. Empty lists [] for absent fields."""


def build_lfm_mode_a_prompt(
    text: str,
    turn_frame: Optional[TurnFrame] = None,
    active_context: Optional[ActiveContext] = None,
) -> str:
    """Builds the user message for Mode A (without deterministic RAR)."""
    parts = [f"[User Message]\n{text}"]

    if turn_frame is not None:
        tf_lines = ["[TurnFrame]"]
        action_verbs = [a.verb for a in turn_frame.candidate_actions]
        if action_verbs:
            tf_lines.append(f"- Candidate action verbs: {', '.join(action_verbs)}")
        if turn_frame.negation_spans:
            tf_lines.append(f"- Negation spans: {', '.join(turn_frame.negation_spans)}")
        ref_exprs = [r.expression for r in turn_frame.candidate_references]
        if ref_exprs:
            tf_lines.append(f"- Referring expressions: {', '.join(ref_exprs)}")
        if turn_frame.explicit_formats:
            tf_lines.append(f"- Format hints: {', '.join(turn_frame.explicit_formats)}")
        parts.append("\n".join(tf_lines))

    if active_context is not None and (active_context.has_active_artifacts or active_context.has_active_entities or active_context.has_prior_operation):
        ac_lines = ["[Active Context]"]
        if active_context.active_artifacts:
            for art in active_context.active_artifacts:
                ac_lines.append(f"- Artifact: {art.id} ({art.name}, type={art.artifact_type})")
        if active_context.active_entities:
            for ent in active_context.active_entities:
                ac_lines.append(f"- Entity: {ent.id} ({ent.name}, category={ent.category})")
        if active_context.prior_semantic_operation:
            ac_lines.append(f"- Prior operation: {active_context.prior_semantic_operation}")
        parts.append("\n".join(ac_lines))

    return "\n\n".join(parts)


def build_lfm_mode_b_prompt(
    text: str,
    turn_frame: Optional[TurnFrame] = None,
    active_context: Optional[ActiveContext] = None,
    rar_facts: Optional[Dict[str, Any]] = None,
) -> str:
    """Builds the user message for Mode B (with deterministic RAR facts)."""
    parts = [f"[User Message]\n{text}"]

    if turn_frame is not None:
        tf_lines = ["[TurnFrame]"]
        action_verbs = [a.verb for a in turn_frame.candidate_actions]
        if action_verbs:
            tf_lines.append(f"- Candidate action verbs: {', '.join(action_verbs)}")
        if turn_frame.negation_spans:
            tf_lines.append(f"- Negation spans: {', '.join(turn_frame.negation_spans)}")
        ref_exprs = [r.expression for r in turn_frame.candidate_references]
        if ref_exprs:
            tf_lines.append(f"- Referring expressions: {', '.join(ref_exprs)}")
        if turn_frame.explicit_formats:
            tf_lines.append(f"- Format hints: {', '.join(turn_frame.explicit_formats)}")
        parts.append("\n".join(tf_lines))

    if active_context is not None and (active_context.has_active_artifacts or active_context.has_active_entities or active_context.has_prior_operation):
        ac_lines = ["[Active Context]"]
        if active_context.active_artifacts:
            for art in active_context.active_artifacts:
                ac_lines.append(f"- Artifact: {art.id} ({art.name}, type={art.artifact_type})")
        if active_context.active_entities:
            for ent in active_context.active_entities:
                ac_lines.append(f"- Entity: {ent.id} ({ent.name}, category={ent.category})")
        if active_context.prior_semantic_operation:
            ac_lines.append(f"- Prior operation: {active_context.prior_semantic_operation}")
        parts.append("\n".join(ac_lines))

    if rar_facts is not None:
        rar_lines = ["[Deterministic RAR Anchors]"]
        resolved = rar_facts.get("resolved_anchors", {})
        if resolved:
            rar_lines.append("- resolved_anchors:")
            for ref_expr, cand_info in resolved.items():
                rar_lines.append(f"  '{ref_expr}' -> {cand_info}")
        else:
            rar_lines.append("- resolved_anchors: none")

        unresolved = rar_facts.get("unresolved", [])
        if unresolved:
            rar_lines.append(f"- unresolved: {', '.join(unresolved)}")
        else:
            rar_lines.append("- unresolved: none")

        ambiguous = rar_facts.get("ambiguous_candidates", {})
        if ambiguous:
            rar_lines.append("- ambiguous_candidates:")
            for ref_expr, cand_ids in ambiguous.items():
                rar_lines.append(f"  '{ref_expr}' -> [{', '.join(cand_ids)}]")
        else:
            rar_lines.append("- ambiguous: none")

        parts.append("\n".join(rar_lines))

    return "\n\n".join(parts)


def normalize_lfm_wire(
    wire: Dict[str, Any],
    raw_text: str,
) -> DecodedRequest:
    """Deterministically normalizes LFM wire JSON into immutable DecodedRequest.

    CRITICAL INVARIANT:
    No semantic repair is performed. The model's requested vs prohibited
    operations and bindings are preserved exactly as output by the model.
    """
    # 1. Goal & Intent Family
    goal_text = str(wire.get("goal") or "").strip()
    intent_family_str = str(wire.get("intent_family") or "").strip().lower()
    try:
        family = IntentFamily(intent_family_str)
    except ValueError:
        family = IntentFamily.UNSPECIFIED
    intended_outcome = IntendedOutcome(description=goal_text, intent_family=family)

    # 2. Operations & Operation Bindings
    # Build binding lookup: operation_name -> target_id
    op_bindings_wire = wire.get("operation_bindings") or []
    binding_map: Dict[str, str] = {}
    if isinstance(op_bindings_wire, list):
        for b in op_bindings_wire:
            if isinstance(b, dict):
                op_name = str(b.get("operation") or "").strip().lower()
                tgt = str(b.get("target_id") or "").strip()
                if op_name and tgt:
                    binding_map[op_name] = tgt

    operations_list: List[SemanticOperation] = []

    # Requested operations
    req_ops = wire.get("requested_operations") or []
    if isinstance(req_ops, list):
        for op in req_ops:
            op_str = str(op).strip()
            if op_str:
                op_lower = op_str.lower()
                tgt = binding_map.get(op_lower)
                operations_list.append(
                    SemanticOperation(name=op_str, status=OperationStatus.REQUESTED, target=tgt)
                )

    # Prohibited operations (preserved as prohibited without code intervention)
    proh_ops = wire.get("prohibited_operations") or []
    if isinstance(proh_ops, list):
        for op in proh_ops:
            op_str = str(op).strip()
            if op_str:
                op_lower = op_str.lower()
                tgt = binding_map.get(op_lower)
                operations_list.append(
                    SemanticOperation(name=op_str, status=OperationStatus.PROHIBITED, target=tgt)
                )

    # 3. References
    references_list: List[SemanticReference] = []
    refs_wire = wire.get("references") or []
    if isinstance(refs_wire, list):
        for r in refs_wire:
            if isinstance(r, dict):
                expr = str(r.get("expression") or "").strip()
                tid = str(r.get("target_id") or "").strip()
                if expr:
                    is_res = bool(tid and tid.lower() not in ("unknown", "none", ""))
                    references_list.append(
                        SemanticReference(
                            expression=expr,
                            kind=ReferenceKind.OTHER,
                            referent_hint=tid if is_res else None,
                            is_resolved=is_res,
                        )
                    )

    # 4. Temporal References
    temporal_list: List[TemporalReference] = []
    temp_wire = wire.get("temporal_references") or []
    if isinstance(temp_wire, list):
        for t in temp_wire:
            t_str = str(t).strip()
            if t_str:
                temporal_list.append(TemporalReference(expression=t_str, is_relative=True))

    # 5. Constraints
    c_wire = wire.get("constraints") or {}
    included = tuple(str(x).strip() for x in c_wire.get("included_items", []) if str(x).strip())
    excluded = tuple(str(x).strip() for x in c_wire.get("excluded_items", []) if str(x).strip())
    length_lim = str(c_wire.get("length_limit") or "").strip() or None
    lang_lim = str(c_wire.get("language_constraints") or "").strip() or None
    constraints = ConstraintScope(
        included_items=included,
        excluded_items=excluded,
        length_limit=length_lim,
        language_constraints=lang_lim,
    )

    # 6. Output Preferences
    p_wire = wire.get("output_preferences") or {}
    art_type = str(p_wire.get("artifact_type") or "").strip() or None
    fmt = str(p_wire.get("format") or "").strip() or None
    tone = str(p_wire.get("tone") or "").strip() or None
    structure = str(p_wire.get("structure") or "").strip() or None
    output_prefs = OutputPreferences(
        artifact_type=art_type,
        format=fmt,
        tone=tone,
        structure=structure,
    )

    # 7. Ambiguities
    ambiguities_list: List[SemanticAmbiguity] = []
    amb_wire = wire.get("ambiguities") or []
    if isinstance(amb_wire, list):
        for a in amb_wire:
            if isinstance(a, dict):
                kind_str = str(a.get("kind") or "").strip().lower()
                desc = str(a.get("description") or "").strip()
                cands = tuple(str(c).strip() for c in a.get("candidates", []) if str(c).strip())
                try:
                    akind = AmbiguityKind(kind_str)
                except ValueError:
                    akind = AmbiguityKind.OTHER
                if desc or cands:
                    ambiguities_list.append(
                        SemanticAmbiguity(kind=akind, description=desc, candidates=cands)
                    )

    # 8. Context Dependencies
    dependencies_list: List[ContextDependency] = []
    dep_wire = wire.get("context_dependencies") or []
    if isinstance(dep_wire, list):
        for d in dep_wire:
            if isinstance(d, dict):
                cat_str = str(d.get("category") or "").strip().lower()
                desc = str(d.get("description") or "").strip()
                try:
                    dcat = ContextDependencyCategory(cat_str)
                except ValueError:
                    dcat = ContextDependencyCategory.CONTEXT_REQUIRED
                if desc:
                    dependencies_list.append(ContextDependency(description=desc, category=dcat))

    return DecodedRequest(
        raw_text=raw_text,
        goal=intended_outcome,
        operations=tuple(operations_list),
        constraints=constraints,
        output_preferences=output_prefs,
        references=tuple(references_list),
        temporal_references=tuple(temporal_list),
        dependencies=tuple(dependencies_list),
        ambiguities=tuple(ambiguities_list),
    )
