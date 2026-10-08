"""Live integration tests for Batch A2.4: Qwen3-14B Step-1 Semantic Decoder.

Invokes the local Qwen3-14B model running on LM Studio.
Asserts structural guarantees and empirical behavior across Modes A, B, and C.
Auto-skipped if the local LM Studio runtime is not responsive or qwen3-14b is not loaded.
"""

from __future__ import annotations

import unittest
import urllib.request

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor
from uri_v1.turn.contracts import DecodedRequest, OperationStatus
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.qwen_decoder import QwenLocalTransport
from uri_v1.turn.qwen_semantic_decoder import (
    DecoderMode,
    Qwen14BSemanticDecoder,
)


def _is_qwen14b_ready() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


_SERVER_READY = _is_qwen14b_ready()


@unittest.skipUnless(_SERVER_READY, "Local LM Studio server not running on port 1234")
class Qwen14BLiveInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transport = QwenLocalTransport(model_id="qwen3-14b", timeout=120.0)
        cls.decoder = Qwen14BSemanticDecoder(transport=cls.transport, max_tokens=800)

    def test_live_mode_a_raw_negation(self):
        """Mode A (Raw) must correctly separate requested vs. prohibited on R4."""
        text = "Don't send it. Just draft the email."
        res = self.decoder.decode_with_result(text, mode=DecoderMode.RAW)
        self.assertTrue(res.ok, f"Mode A failed on R4: {res.error}")
        self.assertIsNotNone(res.decoded_request)
        decoded = res.decoded_request

        req_ops = [op.name.lower() for op in decoded.operations if op.status == OperationStatus.REQUESTED]
        proh_ops = [op.name.lower() for op in decoded.operations if op.status == OperationStatus.PROHIBITED]

        # Verify draft is requested, send is prohibited
        self.assertTrue(any("draft" in op for op in req_ops), f"Expected 'draft' in requested ops: {req_ops}")
        self.assertTrue(any("send" in op for op in proh_ops), f"Expected 'send' in prohibited ops: {proh_ops}")
        self.assertFalse(any("send" in op for op in req_ops), f"Did not expect 'send' in requested ops: {req_ops}")

    def test_live_mode_b_turn_frame(self):
        """Mode B (TurnFrame) receives surface cues and produces valid DecodedRequest."""
        text = "Find the previous approval, compare it with this one and draft a revised order."
        res = self.decoder.decode_with_result(text, mode=DecoderMode.TURN_FRAME)
        self.assertTrue(res.ok, f"Mode B failed on R5: {res.error}")
        self.assertIsNotNone(res.decoded_request)
        self.assertIsNotNone(res.turn_frame)

    def test_live_mode_c_active_context_resolution(self):
        """Mode C (Active Context) resolves referring expression 'that file' to x1."""
        text = "Bring that file up."
        art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document")
        ctx = ActiveContext(active_artifacts=(art,))

        res = self.decoder.decode_with_result(
            text,
            mode=DecoderMode.ACTIVE_CONTEXT,
            active_context=ctx,
        )
        self.assertTrue(res.ok, f"Mode C failed on C1: {res.error}")
        self.assertIsNotNone(res.decoded_request)
        decoded = res.decoded_request

        # Find reference
        file_refs = [r for r in decoded.references if "file" in r.expression.lower() or "that" in r.expression.lower()]
        self.assertTrue(len(file_refs) > 0, f"Expected reference to 'that file': {decoded.references}")
        resolved_refs = [r for r in file_refs if r.is_resolved]
        self.assertTrue(len(resolved_refs) > 0, f"Expected resolved reference to x1: {file_refs}")
        self.assertEqual(resolved_refs[0].referent_hint, "Hostel_Order_21Sep.docx")


if __name__ == "__main__":
    unittest.main()
