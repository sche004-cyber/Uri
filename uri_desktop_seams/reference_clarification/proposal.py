"""Validate Brain-authored reference slots without detecting references in text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


SOURCE_CLASSES = frozenset({"any", "file", "attachment", "conversation", "gmail", "drive", "memory"})
RELATIONS = frozenset({"direct", "previous", "latest", "revision", "owner", "contrast", "same_as"})


class InvalidReferenceProposal(ValueError):
    """An untrusted proposal is malformed or targets an unavailable action."""


@dataclass(frozen=True)
class ReferenceSlot:
    start: int
    end: int
    expression: str
    ref_key: str
    capability_id: str
    action_name: str
    argument_name: str
    relation: str
    source_class: str


def validate_reference_slots(
    decision: Mapping,
    user_text: str,
    action_arguments: Mapping[tuple[str, str], frozenset[str] | set[str]],
) -> tuple[ReferenceSlot, ...]:
    """Return validated optional slots; an absent field preserves legacy decisions.

    ``action_arguments`` comes from the runtime capability registry, never the
    proposal. Offsets are Python Unicode character offsets into the exact turn.
    """
    if not isinstance(decision, Mapping) or not isinstance(user_text, str):
        raise InvalidReferenceProposal("invalid decision or turn")
    if "reference_slots" not in decision:
        return ()
    raw_slots = decision["reference_slots"]
    if not isinstance(raw_slots, list) or len(raw_slots) > 8:
        raise InvalidReferenceProposal("reference_slots must be a bounded list")
    slots = []
    seen = set()
    required = {"span", "ref_key", "target", "relation", "source_class"}
    for raw in raw_slots:
        if not isinstance(raw, Mapping) or set(raw) != required:
            raise InvalidReferenceProposal("invalid slot shape")
        span, target = raw["span"], raw["target"]
        if not isinstance(span, Mapping) or set(span) != {"start", "end", "text"}:
            raise InvalidReferenceProposal("invalid span shape")
        if not isinstance(target, Mapping) or set(target) != {"capability_id", "action_name", "argument_name"}:
            raise InvalidReferenceProposal("invalid target shape")
        start, end, expression = span["start"], span["end"], span["text"]
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(user_text)
                or not isinstance(expression, str) or not expression.strip()
                or user_text[start:end] != expression):
            raise InvalidReferenceProposal("span does not match the turn")
        if any(not isinstance(target[k], str) or not target[k].strip() for k in target):
            raise InvalidReferenceProposal("invalid action target")
        key = (target["capability_id"], target["action_name"])
        if key not in action_arguments or target["argument_name"] not in action_arguments[key]:
            raise InvalidReferenceProposal("unknown action argument")
        if (not isinstance(raw["ref_key"], str) or not raw["ref_key"].strip()
                or raw["relation"] not in RELATIONS or raw["source_class"] not in SOURCE_CLASSES):
            raise InvalidReferenceProposal("invalid slot metadata")
        identity = (key, target["argument_name"], raw["ref_key"])
        if identity in seen:
            raise InvalidReferenceProposal("duplicate slot")
        seen.add(identity)
        slots.append(ReferenceSlot(start, end, expression, raw["ref_key"],
                                   *key, target["argument_name"], raw["relation"], raw["source_class"]))
    return tuple(slots)
