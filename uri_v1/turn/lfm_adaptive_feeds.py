"""LFM2.5-350M Adaptive Narrow Feeds (Batch A2.5 Stage 4).

Decomposes Step-1 semantic extraction into independent, highly focused narrow feeds:
  - Feed G: Goal / Intent classification
  - Feed O: Action verbs and polarity (requested vs prohibited)
  - Feed C: Constraints and output preferences
  - Feed B: Semantic binding of operations to RAR anchors

Each feed uses a minimal, strict JSON schema and an invariant system prompt
free of contaminating data tokens. Zero post-hoc semantic repair.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from uri_v1.turn.contracts import IntentFamily, OperationStatus


# ---------------------------------------------------------------------------
# Feed Type Enumeration
# ---------------------------------------------------------------------------

class FeedType(str, Enum):
    GOAL = "G"
    OPERATIONS = "O"
    CONSTRAINTS = "C"
    BINDING = "B"


# ---------------------------------------------------------------------------
# Feed G: Goal & Intent
# ---------------------------------------------------------------------------

FEED_G_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "description": "Concise summary of the user's primary intended outcome as an action phrase.",
        },
        "intent_family": {
            "type": "string",
            "enum": [f.value for f in IntentFamily],
            "description": "The broad family of user intent.",
        },
    },
    "required": ["goal", "intent_family"],
    "additionalProperties": False,
}

FEED_G_SYSTEM_PROMPT = """You are a concise intent classifier for user turns in URIv1.
Extract into JSON:
- goal: concise phrase stating user's intended outcome (e.g., 'Draft email to warden', 'Compare financial orders'). Never generate draft content or conversational filler.
- intent_family: broad intent category (retrieve, create, modify, communicate, execute, analyze, compare, research, navigate, converse, unspecified).
Do NOT include references, operations, or constraints."""


@dataclass(frozen=True)
class FeedGOutput:
    goal: str
    intent_family: IntentFamily
    raw_json: Dict[str, Any] = field(default_factory=dict)


def build_feed_g_prompt(user_turn: str, context_cue: Optional[str] = None) -> str:
    parts = [f"[User Message]\n{user_turn.strip()}"]
    if context_cue:
        parts.append(f"[Context Cue]\n{context_cue.strip()}")
    parts.append("[Task]\nIdentify the primary goal phrase and intent family.")
    return "\n\n".join(parts)


def parse_feed_g_response(data: Dict[str, Any]) -> FeedGOutput:
    goal = str(data.get("goal", "")).strip()
    raw_fam = str(data.get("intent_family", "unspecified")).strip().lower()
    try:
        family = IntentFamily(raw_fam)
    except ValueError:
        family = IntentFamily.UNSPECIFIED
    return FeedGOutput(goal=goal, intent_family=family, raw_json=data)


# ---------------------------------------------------------------------------
# Feed O: Operations & Polarity
# ---------------------------------------------------------------------------

FEED_O_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "requested_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Base action verbs requested by the user.",
        },
        "prohibited_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Base action verbs explicitly negated, forbidden, or prohibited.",
        },
    },
    "required": ["requested_operations", "prohibited_operations"],
    "additionalProperties": False,
}

FEED_O_SYSTEM_PROMPT = """You are an action verb and polarity extractor for URIv1.
Extract into JSON:
- requested_operations: base verbs of actions the user explicitly asks to perform (e.g., ['draft', 'compare']).
- prohibited_operations: base verbs of actions the user explicitly says NOT to do, forbids, or negates (e.g., ['send', 'delete']).
Critical rules:
- If a verb is negated ('don't send', 'do not delete'), put it ONLY in prohibited_operations.
- Never place the same verb in both requested and prohibited.
- Use base lowercase verbs only.
- If none, use empty list []."""


@dataclass(frozen=True)
class FeedOOutput:
    requested_operations: Tuple[str, ...]
    prohibited_operations: Tuple[str, ...]
    raw_json: Dict[str, Any] = field(default_factory=dict)


def build_feed_o_prompt(
    clause: str,
    candidate_actions: Optional[Sequence[str]] = None,
    rar_anchors: Optional[Sequence[str]] = None,
    active_context_labels: Optional[Sequence[str]] = None,
    extra_metadata: Optional[str] = None,
    distractors: Optional[Sequence[str]] = None,
) -> str:
    """Builds the Operations feed prompt with progressive width options (O0 to O5)."""
    parts = [f"[Clause]\n{clause.strip()}"]

    # O1: + candidate action spans
    if candidate_actions:
        parts.append(f"[Candidate Action Verbs]\n{', '.join(candidate_actions)}")

    # O2: + resolved RAR anchor IDs
    if rar_anchors:
        parts.append(f"[Resolved Anchors]\n{', '.join(rar_anchors)}")

    # O3: + compact active-context labels
    if active_context_labels:
        parts.append(f"[Active Entities]\n{', '.join(active_context_labels)}")

    # O4: + extra candidate metadata
    if extra_metadata:
        parts.append(f"[Candidate Metadata]\n{extra_metadata.strip()}")

    # O5: + distractors
    if distractors:
        parts.append(f"[Unrelated Background]\n{', '.join(distractors)}")

    parts.append("[Task]\nClassify all action verbs into requested_operations and prohibited_operations.")
    return "\n\n".join(parts)


def parse_feed_o_response(data: Dict[str, Any]) -> FeedOOutput:
    req_raw = data.get("requested_operations", [])
    pro_raw = data.get("prohibited_operations", [])

    req_ops = tuple(str(x).strip().lower() for x in req_raw if str(x).strip())
    pro_ops = tuple(str(x).strip().lower() for x in pro_raw if str(x).strip())

    return FeedOOutput(
        requested_operations=req_ops,
        prohibited_operations=pro_ops,
        raw_json=data,
    )


# ---------------------------------------------------------------------------
# Feed C: Constraints & Output Preferences
# ---------------------------------------------------------------------------

FEED_C_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "constraints": {
            "type": "object",
            "properties": {
                "included_items": {"type": "array", "items": {"type": "string"}},
                "excluded_items": {"type": "array", "items": {"type": "string"}},
                "length_limit": {"type": "string"},
                "language_constraints": {"type": "string"},
                "timing_condition": {"type": "string"},
            },
            "required": [
                "included_items",
                "excluded_items",
                "length_limit",
                "language_constraints",
                "timing_condition",
            ],
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
    },
    "required": ["constraints", "output_preferences"],
    "additionalProperties": False,
}

FEED_C_SYSTEM_PROMPT = """You are a constraints and output preferences extractor for URIv1.
Extract into JSON:
- constraints:
  - included_items: explicit required items/sections
  - excluded_items: explicit items/topics to omit
  - length_limit: explicit length restrictions (e.g. 'shorter', 'under 100 words')
  - language_constraints: language requirements
  - timing_condition: conditional timing (e.g. 'only after approval', 'before 5pm')
- output_preferences:
  - artifact_type: requested artifact (e.g. 'email', 'memo', 'summary')
  - format: requested file format (e.g. 'pdf', 'docx', 'markdown', 'json')
  - tone: requested style/tone (e.g. 'formal', 'brief', 'casual')
  - structure: layout requirements (e.g. 'bullet points', 'table')
Empty string "" or empty list [] if not explicitly stated."""


@dataclass(frozen=True)
class FeedCOutput:
    included_items: Tuple[str, ...]
    excluded_items: Tuple[str, ...]
    length_limit: str
    language_constraints: str
    timing_condition: str
    artifact_type: str
    format: str
    tone: str
    structure: str
    raw_json: Dict[str, Any] = field(default_factory=dict)


def build_feed_c_prompt(user_turn: str) -> str:
    parts = [
        f"[User Message]\n{user_turn.strip()}",
        "[Task]\nExtract explicit constraints and output preferences.",
    ]
    return "\n\n".join(parts)


def parse_feed_c_response(data: Dict[str, Any]) -> FeedCOutput:
    c_raw = data.get("constraints", {})
    op_raw = data.get("output_preferences", {})

    return FeedCOutput(
        included_items=tuple(str(x).strip() for x in c_raw.get("included_items", []) if str(x).strip()),
        excluded_items=tuple(str(x).strip() for x in c_raw.get("excluded_items", []) if str(x).strip()),
        length_limit=str(c_raw.get("length_limit", "")).strip(),
        language_constraints=str(c_raw.get("language_constraints", "")).strip(),
        timing_condition=str(c_raw.get("timing_condition", "")).strip(),
        artifact_type=str(op_raw.get("artifact_type", "")).strip(),
        format=str(op_raw.get("format", "")).strip(),
        tone=str(op_raw.get("tone", "")).strip(),
        structure=str(op_raw.get("structure", "")).strip(),
        raw_json=data,
    )


# ---------------------------------------------------------------------------
# Feed B: Semantic Binding
# ---------------------------------------------------------------------------

FEED_B_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
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
            "description": "Mapping of each operation verb to the resolved anchor target_id it operates on.",
        },
        "unresolved_relations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Operations whose target anchor is unknown or ambiguous.",
        },
    },
    "required": ["operation_bindings", "unresolved_relations"],
    "additionalProperties": False,
}

FEED_B_SYSTEM_PROMPT = """You are an operation-target binder for URIv1.
Given operations and pre-resolved candidate anchors from working memory:
- operation_bindings: map each operation to the target_id of the anchor it semantically applies to.
- unresolved_relations: list operations whose target cannot be determined from the supplied anchors.
Do not rediscover or invent target IDs; use only supplied target_ids or empty string."""


@dataclass(frozen=True)
class OperationBinding:
    operation: str
    target_id: str


@dataclass(frozen=True)
class FeedBOutput:
    bindings: Tuple[OperationBinding, ...]
    unresolved_relations: Tuple[str, ...]
    raw_json: Dict[str, Any] = field(default_factory=dict)


def build_feed_b_prompt(
    clause: str,
    operations: Sequence[str],
    rar_anchors: Sequence[Dict[str, str]],
) -> str:
    """Builds Feed B prompt with operations and pre-resolved RAR anchors."""
    parts = [f"[Clause]\n{clause.strip()}"]

    ops_str = ", ".join(operations) if operations else "(none)"
    parts.append(f"[Operations to Bind]\n{ops_str}")

    anchors_lines = ["[Resolved Working Memory Anchors]"]
    if rar_anchors:
        for a in rar_anchors:
            anchors_lines.append(f"- ID: '{a.get('target_id', '')}', Label: '{a.get('label', '')}', Role: '{a.get('role', '')}'")
    else:
        anchors_lines.append("(no resolved anchors available)")
    parts.append("\n".join(anchors_lines))

    parts.append("[Task]\nBind each operation to its corresponding anchor target_id.")
    return "\n\n".join(parts)


def parse_feed_b_response(data: Dict[str, Any]) -> FeedBOutput:
    b_raw = data.get("operation_bindings", [])
    u_raw = data.get("unresolved_relations", [])

    bindings = tuple(
        OperationBinding(
            operation=str(x.get("operation", "")).strip().lower(),
            target_id=str(x.get("target_id", "")).strip(),
        )
        for x in b_raw
        if str(x.get("operation", "")).strip()
    )
    unresolved = tuple(str(x).strip() for x in u_raw if str(x).strip())

    return FeedBOutput(bindings=bindings, unresolved_relations=unresolved, raw_json=data)
