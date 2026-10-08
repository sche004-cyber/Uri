"""Synthetic unit tests for Batch A2.4: Qwen3-14B Step-1 Semantic Decoder.

These tests run without any external model or HTTP server connection.
They verify:
  - Wire schema contamination checks (schema is strictly semantic, zero tool/capability/routing).
  - Normalizer mapping wire JSON to frozen DecodedRequest across Modes A, B, and C.
  - Operation requested vs. prohibited separation.
  - Reference resolution with and without ActiveContext.
  - Ambiguity and contradiction handling.
  - Prompt construction across Modes A, B, and C in Qwen14BSemanticDecoder.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
import unittest

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.contracts import (
    AmbiguityKind,
    AttachmentReference,
    ConfidenceLevel,
    ContextDependencyCategory,
    DecodedRequest,
    EntityCategory,
    IntentFamily,
    OperationStatus,
    ReferenceKind,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.local_semantic_wire import (
    QWEN14B_WIRE_SCHEMA,
    SYSTEM_PROMPT_MODE_A,
    SYSTEM_PROMPT_MODE_B,
    SYSTEM_PROMPT_MODE_C,
    normalize_qwen14b_wire,
)
from uri_v1.turn.needle_wire import DecodeError, DecodeErrorReason
from uri_v1.turn.qwen_decoder import QwenLocalTransport, QwenTransportError
from uri_v1.turn.qwen_semantic_decoder import (
    DecoderMode,
    Qwen14BDecodeResult,
    Qwen14BSemanticDecoder,
)

PROHIBITED_SUBSTRINGS = (
    "tool",
    "capability",
    "graphify",
    "workflow",
    "provider",
    "decision",
    "plan",
    "route",
    "routing",
    "weather",
    "gmail",
    "calendar",
    "node_id",
    "edge_outcome",
    "escalate",
    "reflex",
)


class Qwen14BWireContaminationTests(unittest.TestCase):
    """Ensures Qwen3-14B wire schema carries zero tool/execution/routing concepts."""

    def test_schema_is_clean(self):
        raw = json.dumps(QWEN14B_WIRE_SCHEMA).lower()
        for forbidden in PROHIBITED_SUBSTRINGS:
            self.assertNotIn(
                forbidden,
                raw,
                f"Forbidden concept {forbidden!r} found in QWEN14B_WIRE_SCHEMA",
            )


class Qwen14BNormalizerTests(unittest.TestCase):
    """Tests deterministic normalization of Qwen3-14B wire dictionaries."""

    def test_valid_basic_wire(self):
        wire = {
            "goal": "Convert this document to PDF",
            "intent_family": "create",
            "requested_operations": ["convert"],
            "prohibited_operations": [],
            "references": [{"expression": "this document", "target_id": ""}],
        }
        inp = DecodeInput.from_text("Convert this document to PDF")
        decoded = normalize_qwen14b_wire(wire, inp)

        self.assertIsInstance(decoded, DecodedRequest)
        self.assertEqual(decoded.goal.description, "Convert this document to PDF")
        self.assertEqual(decoded.goal.intent_family, IntentFamily.CREATE)
        self.assertEqual(len(decoded.operations), 1)
        self.assertEqual(decoded.operations[0].name, "convert")
        self.assertEqual(decoded.operations[0].status, OperationStatus.REQUESTED)
        self.assertEqual(len(decoded.references), 1)
        self.assertEqual(decoded.references[0].expression, "this document")
        self.assertFalse(decoded.references[0].is_resolved)
        self.assertEqual(len(decoded.dependencies), 1)
        self.assertEqual(decoded.dependencies[0].category, ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED)

    def test_requested_vs_prohibited_separation(self):
        wire = {
            "goal": "Draft email without sending",
            "intent_family": "communicate",
            "requested_operations": ["draft"],
            "prohibited_operations": ["send"],
            "references": [{"expression": "it", "target_id": ""}],
        }
        inp = DecodeInput.from_text("Don't send it. Just draft the email.")
        decoded = normalize_qwen14b_wire(wire, inp)

        req_ops = [op.name for op in decoded.operations if op.status == OperationStatus.REQUESTED]
        proh_ops = [op.name for op in decoded.operations if op.status == OperationStatus.PROHIBITED]
        self.assertIn("draft", req_ops)
        self.assertIn("send", proh_ops)
        self.assertNotIn("send", req_ops)
        self.assertEqual(decoded.constraints.prohibited_actions, ("send",))

    def test_contradiction_detection(self):
        wire = {
            "goal": "Send and do not send",
            "intent_family": "communicate",
            "requested_operations": ["send"],
            "prohibited_operations": ["send"],
            "references": [],
        }
        inp = DecodeInput.from_text("Send it, wait don't send it")
        decoded = normalize_qwen14b_wire(wire, inp)

        self.assertEqual(len(decoded.ambiguities), 1)
        self.assertEqual(decoded.ambiguities[0].kind, AmbiguityKind.MULTIPLE_INTERPRETATIONS)
        self.assertEqual(decoded.confidence.overall, ConfidenceLevel.UNCERTAIN)

    def test_reference_resolution_with_active_context(self):
        art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document")
        ent = EntityDescriptor(id="e1", name="Chief Warden", category="role")
        ctx = ActiveContext(active_artifacts=(art,), active_entities=(ent,))

        wire = {
            "goal": "Revise the document for Chief Warden",
            "intent_family": "modify",
            "requested_operations": ["revise"],
            "prohibited_operations": [],
            "references": [
                {"expression": "that file", "target_id": "x1"},
                {"expression": "them", "target_id": "e1"},
                {"expression": "unrelated thing", "target_id": ""},
            ],
        }
        inp = DecodeInput.from_text("Bring that file up for them and an unrelated thing.")
        decoded = normalize_qwen14b_wire(wire, inp, active_context=ctx)

        self.assertEqual(len(decoded.references), 3)
        # x1 resolved
        ref_x1 = decoded.references[0]
        self.assertEqual(ref_x1.expression, "that file")
        self.assertTrue(ref_x1.is_resolved)
        self.assertEqual(ref_x1.referent_hint, "Hostel_Order_21Sep.docx")

        # e1 resolved
        ref_e1 = decoded.references[1]
        self.assertEqual(ref_e1.expression, "them")
        self.assertTrue(ref_e1.is_resolved)
        self.assertEqual(ref_e1.referent_hint, "Chief Warden")

        # unrelated thing unresolved
        ref_un = decoded.references[2]
        self.assertEqual(ref_un.expression, "unrelated thing")
        self.assertFalse(ref_un.is_resolved)
        self.assertIsNone(ref_un.referent_hint)

        # Only unresolved references yield dependencies
        self.assertEqual(len(decoded.dependencies), 1)
        self.assertEqual(decoded.dependencies[0].unresolved_reference, "unrelated thing")

    def test_missing_goal_raises_decode_error(self):
        wire = {
            "intent_family": "create",
            "requested_operations": ["convert"],
            "prohibited_operations": [],
            "references": [],
        }
        with self.assertRaises(DecodeError) as ctx:
            normalize_qwen14b_wire(wire, DecodeInput.from_text("test"))
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)


class MockTransport(QwenLocalTransport):
    """Mock transport for unit testing Qwen14BSemanticDecoder without network calls."""

    def __init__(self, response_payload: Dict[str, Any]) -> None:
        super().__init__()
        self.response_payload = response_payload
        self.recorded_calls = []

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        constrained: bool = True,
        schema: Optional[Dict[str, Any]] = None,
        schema_name: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        self.recorded_calls.append({
            "prompt": prompt,
            "system": system,
            "constrained": constrained,
            "schema": schema,
            "schema_name": schema_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        return self.response_payload


class Qwen14BSemanticDecoderMockTests(unittest.TestCase):
    """Tests Qwen14BSemanticDecoder execution across Modes A, B, and C."""

    def setUp(self):
        self.valid_wire = {
            "goal": "Draft the email",
            "intent_family": "communicate",
            "requested_operations": ["draft"],
            "prohibited_operations": ["send"],
            "references": [{"expression": "it", "target_id": ""}],
            "temporal_references": [],
            "constraints": {"included_items": [], "excluded_items": []},
            "output_preferences": {},
            "entities": [],
        }
        self.mock_resp = {
            "content": json.dumps(self.valid_wire),
            "reasoning_content": "User says don't send it, just draft.",
            "prompt_tokens": 120,
            "completion_tokens": 65,
            "reasoning_tokens": 40,
            "latency_ms": 1250.0,
            "raw_response": {},
        }

    def test_mode_a_raw_prompt_construction(self):
        transport = MockTransport(self.mock_resp)
        decoder = Qwen14BSemanticDecoder(transport=transport, default_mode=DecoderMode.RAW)

        res = decoder.decode_with_result("Don't send it. Just draft the email.")
        self.assertTrue(res.ok)
        self.assertEqual(len(transport.recorded_calls), 1)
        call = transport.recorded_calls[0]
        self.assertEqual(call["prompt"], "Don't send it. Just draft the email.")
        self.assertEqual(call["system"], SYSTEM_PROMPT_MODE_A)
        self.assertEqual(call["schema_name"], "decoded_request")
        self.assertEqual(res.mode, DecoderMode.RAW.value)
        self.assertEqual(res.prompt_tokens, 120)
        self.assertEqual(res.reasoning_tokens, 40)

    def test_mode_b_turn_frame_prompt_construction(self):
        transport = MockTransport(self.mock_resp)
        decoder = Qwen14BSemanticDecoder(transport=transport)

        res = decoder.decode_with_result(
            "Don't send it. Just draft the email.",
            mode=DecoderMode.TURN_FRAME,
        )
        self.assertTrue(res.ok)
        self.assertEqual(len(transport.recorded_calls), 1)
        call = transport.recorded_calls[0]
        self.assertEqual(call["system"], SYSTEM_PROMPT_MODE_B)
        self.assertIn("User message: Don't send it. Just draft the email.", call["prompt"])
        self.assertIn("Pre-semantic surface cues:", call["prompt"])
        self.assertIn("Candidate action verbs:", call["prompt"])
        self.assertIsNotNone(res.turn_frame)
        self.assertEqual(res.mode, DecoderMode.TURN_FRAME.value)

    def test_mode_c_active_context_prompt_construction(self):
        transport = MockTransport(self.mock_resp)
        decoder = Qwen14BSemanticDecoder(transport=transport)
        art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx")
        ctx = ActiveContext(active_artifacts=(art,))

        res = decoder.decode_with_result(
            "Bring that file up.",
            mode=DecoderMode.ACTIVE_CONTEXT,
            active_context=ctx,
        )
        self.assertTrue(res.ok)
        self.assertEqual(len(transport.recorded_calls), 1)
        call = transport.recorded_calls[0]
        self.assertEqual(call["system"], SYSTEM_PROMPT_MODE_C)
        self.assertIn("Active session working memory:", call["prompt"])
        self.assertIn("Hostel_Order_21Sep.docx", call["prompt"])
        self.assertEqual(res.active_context, ctx)
        self.assertEqual(res.mode, DecoderMode.ACTIVE_CONTEXT.value)

    def test_transport_error_returns_decode_result_with_error(self):
        class FailingTransport(QwenLocalTransport):
            def complete(self, *args, **kwargs):
                raise QwenTransportError("Connection refused: 127.0.0.1:1234")

        decoder = Qwen14BSemanticDecoder(transport=FailingTransport())
        res = decoder.decode_with_result("Hello")
        self.assertFalse(res.ok)
        self.assertIsNotNone(res.error)
        self.assertIn("Transport failure", str(res.error))

    def test_empty_content_returns_decode_result_with_error(self):
        empty_resp = {
            "content": "",
            "reasoning_content": "Exhausted tokens in reasoning...",
            "prompt_tokens": 100,
            "completion_tokens": 500,
            "reasoning_tokens": 500,
            "latency_ms": 3000.0,
            "raw_response": {},
        }
        decoder = Qwen14BSemanticDecoder(transport=MockTransport(empty_resp))
        res = decoder.decode_with_result("Hello")
        self.assertFalse(res.ok)
        self.assertEqual(res.error.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)


if __name__ == "__main__":
    unittest.main()
