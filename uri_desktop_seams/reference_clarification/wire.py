"""Bounded, sourced display facts for the later clarification wire adapter."""

from __future__ import annotations

from .evidence import EvidenceEnvelope


def candidate_facts(envelope: EvidenceEnvelope) -> tuple[dict[str, str], ...]:
    """Expose only verified option facts; no raw provider record or locator."""
    if envelope.abstained:
        return ()
    return tuple({
        "candidate_id": item.id,
        "title": item.title,
        "candidate_type": item.candidate_type,
        "source_class": item.source_class,
        "owner": item.owner or "",
    } for item in envelope.inventory)
