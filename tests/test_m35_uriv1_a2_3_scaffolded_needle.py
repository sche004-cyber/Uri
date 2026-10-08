"""Unit tests for ScaffoldedNeedleDecoder (Batch A2.3).

Verifies the scaffolded pipeline with mock transport:
- Adaptive view invocation (calling only relevant views).
- Candidate-ID mapping for operations and references.
- Contradiction preservation (zero heuristic semantic repair).
- Unknown / hallucinated ID handling.
- Immutability and conformance to DecodedRequest contract.
- Transport reset invocation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pytest

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_decoder import NeedleBridgeTransport
from uri_v1.turn.needle_scaffolded import ScaffoldedNeedleDecoder, ScaffoldedNeedleResult
from uri_v1.turn.needle_wire import DecodeError


class MockNeedleTransport(NeedleBridgeTransport):
    """Mock transport that simulates Needle bridge responses without running a subprocess."""

    def __init__(self, responses: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.responses = responses or {}
        self.calls: List[Dict[str, Any]] = []
        self.reset_count = 0

    def is_running(self) -> bool:
        return True

    def load(self) -> None:
        pass

    def reset(self) -> None:
        self.reset_count += 1

    def close(self) -> None:
        pass

    def decode(
        self,
        text: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_new_tokens: int = 300,
    ) -> Dict[str, Any]:
        self.calls.append({
            "text": text,
            "system": system,
            "schema": schema,
            "max_new_tokens": max_new_tokens,
        })
        tool_name = schema.get("name") if schema else "unknown"
        if tool_name in self.responses:
            return self.responses[tool_name]
        return {
            "success": True,
            "function_calls": [{"name": tool_name, "arguments": {}}],
        }


def test_adaptive_views_invocation():
    """Verify that when no operations or output cues exist, only goal view is invoked."""
    transport = MockNeedleTransport({
        "select_goal": {
            "success": True,
            "function_calls": [{
                "name": "select_goal",
                "arguments": {"goal": "Check system status", "intent_family": "retrieve"},
            }],
        },
    })
    decoder = ScaffoldedNeedleDecoder(transport=transport)
    # Pure greeting / status without action verbs, negation, or output cues
    result = decoder.decode_with_result("Hello there")
    assert result.error is None
    assert result.decoded_request is not None
    assert "goal" in result.called_views
    assert "operations" in result.skipped_views
    assert "output_scope" in result.skipped_views
    assert transport.reset_count == 1


def test_candidate_id_mapping_operations():
    """Verify that candidate action IDs map correctly to SemanticOperations."""
    transport = MockNeedleTransport({
        "select_goal": {
            "success": True,
            "function_calls": [{
                "name": "select_goal",
                "arguments": {"goal": "Draft email to Prof. Rao", "intent_family": "create"},
            }],
        },
        "select_operations": {
            "success": True,
            "function_calls": [{
                "name": "select_operations",
                "arguments": {
                    "requested_action_ids": ["a1"],
                    "prohibited_action_ids": ["a2"],
                },
            }],
        },
    })
    decoder = ScaffoldedNeedleDecoder(transport=transport)
    text = "Draft an email to Prof. Rao, but do not send it"
    result = decoder.decode_with_result(text)
    assert result.error is None
    req = result.decoded_request
    assert req is not None
    assert req.goal.description == "Draft email to Prof. Rao"
    assert req.goal.intent_family == IntentFamily.CREATE

    # Find requested draft and prohibited send
    req_ops = [op for op in req.operations if op.status == OperationStatus.REQUESTED]
    proh_ops = [op for op in req.operations if op.status == OperationStatus.PROHIBITED]
    assert any(op.name == "draft" for op in req_ops)
    assert any(op.name == "send" for op in proh_ops)
    assert "send" in req.constraints.prohibited_actions
    assert req.confidence.operations == ConfidenceLevel.HIGH


def test_contradiction_handling_zero_heuristic_repair():
    """Verify that if Needle marks an action as both requested and prohibited,

    the contradiction is preserved truthfully without heuristic deletion.
    """
    transport = MockNeedleTransport({
        "select_goal": {
            "success": True,
            "function_calls": [{
                "name": "select_goal",
                "arguments": {"goal": "Process file", "intent_family": "modify"},
            }],
        },
        "select_operations": {
            "success": True,
            "function_calls": [{
                "name": "select_operations",
                "arguments": {
                    "requested_action_ids": ["a1"],
                    "prohibited_action_ids": ["a1"],  # Contradiction!
                },
            }],
        },
    })
    decoder = ScaffoldedNeedleDecoder(transport=transport)
    text = "Draft the document"
    result = decoder.decode_with_result(text)
    assert result.error is None
    req = result.decoded_request
    assert req is not None
    # Both operations are present
    assert any(op.name == "draft" and op.status == OperationStatus.REQUESTED for op in req.operations)
    assert any(op.name == "draft" and op.status == OperationStatus.PROHIBITED for op in req.operations)

    # Contradiction recorded
    assert len(result.contradictions) == 1
    assert "draft" in result.contradictions[0]

    # Ambiguity created
    assert any(amb.kind == AmbiguityKind.MULTIPLE_INTERPRETATIONS for amb in req.ambiguities)

    # Confidence penalty applied
    assert req.confidence.operations == ConfidenceLevel.UNCERTAIN
    assert req.confidence.overall == ConfidenceLevel.UNCERTAIN


def test_unknown_ids_handling():
    """Verify that hallucinated candidate IDs are recorded without crashing."""
    transport = MockNeedleTransport({
        "select_goal": {
            "success": True,
            "function_calls": [{
                "name": "select_goal",
                "arguments": {"goal": "Process file", "intent_family": "modify"},
            }],
        },
        "select_operations": {
            "success": True,
            "function_calls": [{
                "name": "select_operations",
                "arguments": {
                    "requested_action_ids": ["a999"],  # Unknown ID!
                    "prohibited_action_ids": [],
                },
            }],
        },
    })
    decoder = ScaffoldedNeedleDecoder(transport=transport)
    text = "Draft the document"
    result = decoder.decode_with_result(text)
    assert result.error is None
    assert len(result.unknown_ids) == 1
    assert "a999" in result.unknown_ids[0]
    assert result.decoded_request.confidence.operations == ConfidenceLevel.LOW


def test_reference_resolution_with_active_context():
    """Verify that candidate references resolve against active session context."""
    transport = MockNeedleTransport({
        "select_goal": {
            "success": True,
            "function_calls": [{
                "name": "select_goal",
                "arguments": {"goal": "Revise document", "intent_family": "modify"},
            }],
        },
        "select_references": {
            "success": True,
            "function_calls": [{
                "name": "select_references",
                "arguments": {
                    "reference_resolutions": [
                        {
                            "reference_id": "r1",
                            "status": "resolved_candidate",
                            "candidate_target_id": "x1",
                        }
                    ]
                },
            }],
        },
    })
    art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx")
    ctx = ActiveContext(active_artifacts=(art,))
    decoder = ScaffoldedNeedleDecoder(transport=transport)
    text = "Revise it to sound more formal"
    result = decoder.decode_with_result(text, active_context=ctx)
    assert result.error is None
    req = result.decoded_request
    assert req is not None
    # Find resolved reference
    ref = next((r for r in req.references if r.expression == "it"), None)
    assert ref is not None
    assert ref.is_resolved is True
    assert ref.referent_hint == "Hostel_Order_21Sep.docx"
