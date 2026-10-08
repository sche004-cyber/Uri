"""Partial escalation interfaces (Stage 2, Slice 2 design, interface-only in Slice 1).

Declares the structural schema for PartialEscalationArtifact without activating
partial dispatch or mutating shared aggregates.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Sequence

from .contracts import CompiledPlan, PartialPlan


@dataclass(frozen=True)
class PartialEscalationArtifact:
    """Extension of the EscalationRequest concept for dynamic DAG remainder."""
    user_id: str
    task_id: str
    run_id: str
    trace_id: str
    proposal_sha256: str
    snapshot_sha256: str
    plan_sha256: str
    source_ids_and_hashes: tuple[tuple[str, str], ...]
    completed_node_receipts: tuple[dict[str, Any], ...]
    unresolved_nodes: tuple[dict[str, Any], ...]
    dependency_closure: tuple[str, ...]
    effects_performed: tuple[str, ...]  # Empty in read-only slice
    requested_role: str  # Role name, never a model name

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "uri.plan.partial_escalation.v1",
            "user_id": self.user_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "proposal_sha256": self.proposal_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "plan_sha256": self.plan_sha256,
            "sources": [{"source_id": s, "content_sha256": h} for s, h in self.source_ids_and_hashes],
            "completed_node_receipts": list(self.completed_node_receipts),
            "unresolved_nodes": list(self.unresolved_nodes),
            "dependency_closure": list(self.dependency_closure),
            "effects_performed": list(self.effects_performed),
            "requested_role": self.requested_role,
        }

    def canonical(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


def build_partial(
    plan: CompiledPlan,
    receipts: Sequence[dict[str, Any]],
    *,
    user_id: str,
    task_id: str,
    run_id: str,
    trace_id: str,
    unresolved_nodes: Sequence[dict[str, Any]],
    requested_role: str = "general_planning_specialist",
) -> PartialEscalationArtifact:
    """Build a PartialEscalationArtifact recording completed receipts and unresolved DAG remainder."""
    sources = tuple((s.source_id, s.content_sha256) for s in plan.sources)
    closure = tuple(n["node_id"] for n in unresolved_nodes if "node_id" in n)
    return PartialEscalationArtifact(
        user_id=user_id,
        task_id=task_id,
        run_id=run_id,
        trace_id=trace_id,
        proposal_sha256=plan.proposal_sha256,
        snapshot_sha256=plan.snapshot_sha256,
        plan_sha256=plan.sha256,
        source_ids_and_hashes=sources,
        completed_node_receipts=tuple(receipts),
        unresolved_nodes=tuple(unresolved_nodes),
        dependency_closure=closure,
        effects_performed=(),  # Zero effects in read-only slice
        requested_role=requested_role,
    )
