"""Synthetic unit tests for Batch A2.4R: Needle Single-Pass Semantic Decoder.

Tests run without external model or bridge subprocess execution.
Verifies:
  - NEEDLE_TOOL_SCHEMA contamination cleanliness
  - Prompt construction across Modes A, B, C, and D
  - Normalization of single-pass function call arguments
  - Contradiction handling and ambiguity flagging
  - Missing call and transport failure handling
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
import unittest

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor
from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.local_semantic_wire import (
    SYSTEM_PROMPT_MODE_A,
    SYSTEM_PROMPT_MODE_B,
    SYSTEM_PROMPT_MODE_C,
    SYSTEM_PROMPT_MODE_D,
)
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, NeedleTransportError
from uri_v1.turn.needle_single_pass import (
    NEEDLE_TOOL_SCHEMA,
    NeedleSinglePassDecoder,
    NeedleSinglePassResult,
)
from uri_v1.turn.needle_wire import DecodeError, DecodeErrorReason
from uri_v1.turn.qwen_semantic_decoder import DecoderMode

PROHIBITED_SUBSTRINGS = (
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


class NeedleToolSchemaContaminationTests(unittest.TestCase):
    """Ensures NEEDLE_TOOL_SCHEMA carries zero execution/routing concepts."""

    def test_schema_is_clean(self):
        raw = json.dumps(NEEDLE_TOOL_SCHEMA["parameters"]).lower()
        for forbidden in PROHIBITED_SUBSTRINGS:
            self.assertNotIn(
                forbidden,
                raw,
                f"Forbidden concept {forbidden!r} found in NEEDLE_TOOL_SCHEMA parameters",
            )


class MockNeedleTransport(NeedleBridgeTransport):
    """Mock bridge transport for unit testing NeedleSinglePassDecoder without subprocess."""

    def __init__(self, response_payload: Dict[str, Any]) -> None:
        self.response_payload = response_payload
        self.recorded_calls = []

    def load(self) -> None:
        pass

    def decode(
        self,
        text: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_new_tokens: int = 300,
    ) -> Dict[str, Any]:
        self.recorded_calls.append({
            "text": text,
            "system": system,
            "schema": schema,
            "max_new_tokens": max_new_tokens,
        })
        return self.response_payload

    def reset(self) -> None:
        pass

    def close(self) -> None:
        pass


class NeedleSinglePassDecoderMockTests(unittest.TestCase):
    """Tests NeedleSinglePassDecoder execution across Modes A, B, C, and D."""

    def setUp(self):
        self.valid_args = {
            "goal": "Draft the email without sending",
            "intent_family": "communicate",
            "requested_operations": ["draft"],
            "prohibited_operations": ["send"],
            "references": [{"expression": "it", "target_id": ""}],
        }
        self.mock_resp = {
            "type": "call",
            "success": True,
            "function_calls": [{"name": "decode_request", "arguments": self.valid_args}],
            "reasoning": "Drafting requested, sending prohibited.",
            "prefill_tps": 900.0,
            "decode_tps": 350.0,
            "peak_ram_mb": 105.0,
            "_bridge_latency_ms": 450.0,
        }

    def test_mode_a_raw_prompt_construction(self):
        transport = MockNeedleTransport(self.mock_resp)
        decoder = NeedleSinglePassDecoder(transport=transport, default_mode=DecoderMode.RAW)

        res = decoder.decode_with_result("Don't send it. Just draft the email.")
        self.assertTrue(res.ok)
        self.assertEqual(len(transport.recorded_calls), 1)
        call = transport.recorded_calls[0]
        self.assertEqual(call["text"], "Don't send it. Just draft the email.")
        self.assertEqual(call["system"], SYSTEM_PROMPT_MODE_A)
        self.assertEqual(call["schema"]["name"], "decode_request")
        self.assertEqual(res.mode, DecoderMode.RAW.value)

    def test_mode_b_turn_frame_prompt_construction(self):
        transport = MockNeedleTransport(self.mock_resp)
        decoder = NeedleSinglePassDecoder(transport=transport)

        res = decoder.decode_with_result(
            "Don't send it. Just draft the email.",
            mode=DecoderMode.TURN_FRAME,
        )
        self.assertTrue(res.ok)
        self.assertEqual(len(transport.recorded_calls), 1)
        call = transport.recorded_calls[0]
        self.assertEqual(call["system"], SYSTEM_PROMPT_MODE_B)
        self.assertIn("User message: Don't send it. Just draft the email.", call["text"])
        self.assertIn("Pre-semantic surface cues:", call["text"])
        self.assertNotIn("Active session working memory:", call["text"])
        self.assertIsNotNone(res.turn_frame)
        self.assertEqual(res.mode, DecoderMode.TURN_FRAME.value)

    def test_mode_c_active_context_prompt_construction(self):
        transport = MockNeedleTransport(self.mock_resp)
        decoder = NeedleSinglePassDecoder(transport=transport)
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
        self.assertIn("User message: Bring that file up.", call["text"])
        self.assertIn("Active session working memory:", call["text"])
        self.assertNotIn("Pre-semantic surface cues:", call["text"])  # No TurnFrame in Mode C!
        self.assertEqual(res.active_context, ctx)
        self.assertIsNone(res.turn_frame)
        self.assertEqual(res.mode, DecoderMode.ACTIVE_CONTEXT.value)

    def test_mode_d_turn_frame_active_context_prompt_construction(self):
        transport = MockNeedleTransport(self.mock_resp)
        decoder = NeedleSinglePassDecoder(transport=transport)
        art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx")
        ctx = ActiveContext(active_artifacts=(art,))

        res = decoder.decode_with_result(
            "Bring that file up.",
            mode=DecoderMode.TURN_FRAME_ACTIVE_CONTEXT,
            active_context=ctx,
        )
        self.assertTrue(res.ok)
        self.assertEqual(len(transport.recorded_calls), 1)
        call = transport.recorded_calls[0]
        self.assertEqual(call["system"], SYSTEM_PROMPT_MODE_D)
        self.assertIn("User message: Bring that file up.", call["text"])
        self.assertIn("Pre-semantic surface cues:", call["text"])
        self.assertIn("Active session working memory:", call["text"])
        self.assertEqual(res.active_context, ctx)
        self.assertIsNotNone(res.turn_frame)
        self.assertEqual(res.mode, DecoderMode.TURN_FRAME_ACTIVE_CONTEXT.value)

    def test_missing_function_call_yields_decode_error(self):
        empty_resp = {
            "type": "call",
            "success": True,
            "function_calls": [],
            "reasoning": "No tools available",
            "_bridge_latency_ms": 100.0,
        }
        decoder = NeedleSinglePassDecoder(transport=MockNeedleTransport(empty_resp))
        res = decoder.decode_with_result("Convert this to PDF.")
        self.assertFalse(res.ok)
        self.assertEqual(res.error.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)

    def test_contradiction_handling_in_wire(self):
        contradictory_args = {
            "goal": "Send and draft",
            "intent_family": "communicate",
            "requested_operations": ["draft", "send"],
            "prohibited_operations": ["send"],
            "references": [],
        }
        resp = {
            "type": "call",
            "success": True,
            "function_calls": [{"name": "decode_request", "arguments": contradictory_args}],
            "reasoning": "Contradictory",
            "_bridge_latency_ms": 200.0,
        }
        decoder = NeedleSinglePassDecoder(transport=MockNeedleTransport(resp))
        res = decoder.decode_with_result("Send it wait don't send it.")
        self.assertTrue(res.ok)
        self.assertIsNotNone(res.decoded_request)
        self.assertEqual(len(res.decoded_request.ambiguities), 1)
        self.assertEqual(res.decoded_request.ambiguities[0].kind, AmbiguityKind.MULTIPLE_INTERPRETATIONS)
        self.assertEqual(res.decoded_request.confidence.overall, ConfidenceLevel.UNCERTAIN)


if __name__ == "__main__":
    unittest.main()
