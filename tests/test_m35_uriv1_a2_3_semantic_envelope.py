"""Unit tests for ActiveContext and SemanticInputEnvelope (Batch A2.3).

Verifies:
- ActiveContext properties and immutability.
- SemanticInputEnvelope narrow view derivation.
- Formatting of narrow views for Needle.
"""

from __future__ import annotations

import pytest

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.semantic_envelope import (
    GoalView,
    OperationView,
    OutputScopeView,
    ReferenceView,
    SemanticInputEnvelope,
)
from uri_v1.turn.turn_frame_builder import build_turn_frame


def test_active_context_properties():
    art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document")
    ent = EntityDescriptor(id="e1", name="Prof. Rao", category="person")
    ctx = ActiveContext(
        active_artifacts=(art,),
        active_entities=(ent,),
        prior_semantic_operation="draft",
        active_topic="Hostel Allotment",
    )
    assert ctx.has_active_artifacts
    assert ctx.has_active_entities
    assert ctx.has_prior_operation
    assert ctx.active_topic == "Hostel Allotment"

    with pytest.raises(Exception):
        ctx.active_topic = "other"  # type: ignore[misc]


def test_semantic_input_envelope_derivation():
    raw_text = "Draft an email to Prof. Rao about the meeting tomorrow, but do not send it"
    frame = build_turn_frame(raw_text)
    art = ArtifactDescriptor(id="x1", name="Meeting_Notes.docx")
    ctx = ActiveContext(
        active_artifacts=(art,),
        prior_semantic_operation="compose",
        active_topic="Project Status",
    )
    envelope = SemanticInputEnvelope(current_message=raw_text, turn_frame=frame, active_context=ctx)

    # GoalView
    gv = envelope.goal_view
    assert isinstance(gv, GoalView)
    assert gv.current_message == raw_text
    prompt_g = gv.format_prompt()
    assert "user request:" in prompt_g.lower()
    assert "Active topic: Project Status" in prompt_g

    # OperationView
    ov = envelope.operation_view
    assert isinstance(ov, OperationView)
    prompt_op = ov.format_prompt()
    assert "Candidate action IDs:" in prompt_op
    assert any(act.id in prompt_op for act in frame.candidate_actions)
    assert "Negation cues:" in prompt_op

    # ReferenceView
    rv = envelope.reference_view
    assert isinstance(rv, ReferenceView)
    prompt_ref = rv.format_prompt()
    assert "Candidate reference IDs:" in prompt_ref
    assert "Active session artifacts:" in prompt_ref
    assert "x1: Meeting_Notes.docx" in prompt_ref

    # OutputScopeView
    sv = envelope.output_scope_view
    assert isinstance(sv, OutputScopeView)
    prompt_scope = sv.format_prompt()
    assert "Clauses:" in prompt_scope
