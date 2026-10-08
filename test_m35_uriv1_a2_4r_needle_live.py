"""Live integration tests for Batch A2.4R: Needle Single-Pass Semantic Decoder.

Invokes the actual local Needle 3 bridge runtime in single-pass mode.
Verifies structural guarantees:
  - Transport connects cleanly and pings ready.
  - Decoder never raises uncaught exceptions.
  - Yields NeedleSinglePassResult with either a DecodedRequest or typed DecodeError.
  - Handles Mode A and Mode B under the common architecture.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from uri_v1.turn.needle_single_pass import NeedleSinglePassDecoder
from uri_v1.turn.qwen_semantic_decoder import DecoderMode

_VENV_PYTHON = default_venv_python()
_BRIDGE_SCRIPT = Path(__file__).parent / "uri_v1" / "turn" / "needle_bridge_runtime.py"
_NEEDLE_AVAILABLE = _VENV_PYTHON.is_file() and _BRIDGE_SCRIPT.is_file()


@unittest.skipUnless(_NEEDLE_AVAILABLE, "Needle virtualenv not available on this host")
class NeedleSinglePassLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transport = NeedleBridgeTransport(_VENV_PYTHON, _BRIDGE_SCRIPT)
        cls.decoder = NeedleSinglePassDecoder(transport=cls.transport)

    @classmethod
    def tearDownClass(cls):
        cls.decoder.close()

    def test_needle_bridge_ready(self):
        self.transport.load()
        self.assertEqual(self.transport.runtime_info.get("status"), "ready")
        self.assertEqual(self.transport.runtime_info.get("package"), "cactus-needle")

    def test_needle_mode_a_execution(self):
        """Mode A (Raw) execution yields structured result or typed DecodeError, never crash."""
        res = self.decoder.decode_with_result("Convert this to PDF.", mode=DecoderMode.RAW)
        self.assertTrue(res.ok or res.error is not None)
        self.assertIsNotNone(res.latency_ms)

    def test_needle_mode_b_execution(self):
        """Mode B (TurnFrame) execution yields structured result."""
        res = self.decoder.decode_with_result("Don't send it. Just draft the email.", mode=DecoderMode.TURN_FRAME)
        self.assertTrue(res.ok or res.error is not None)
        self.assertIsNotNone(res.latency_ms)
        self.assertIsNotNone(res.turn_frame)


if __name__ == "__main__":
    unittest.main()
