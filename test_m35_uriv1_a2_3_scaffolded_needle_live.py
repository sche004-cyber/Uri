"""Live inference tests for Batch A2.3: TurnFrame + Compact Active Context + Adaptive Needle.

These tests invoke the actual Needle 3 model through the offline subprocess bridge.
Following the M35 evidence-integrity standard, they assert structural guarantees:
  - Subprocess transport executes cleanly without unhandled exceptions.
  - ScaffoldedNeedleDecoder adaptively selects views and merges outputs.
  - Produces a valid, deeply frozen DecodedRequest.
  - Reset operation succeeds without error between turns.

Automatically skipped if the Needle virtualenv is not available on the host.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.contracts import DecodedRequest
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from uri_v1.turn.needle_scaffolded import ScaffoldedNeedleDecoder, ScaffoldedNeedleResult

_VENV_PYTHON = default_venv_python()
_BRIDGE_SCRIPT = Path(__file__).parent / "uri_v1" / "turn" / "needle_bridge_runtime.py"
_NEEDLE_AVAILABLE = _VENV_PYTHON.is_file() and _BRIDGE_SCRIPT.is_file()


@unittest.skipUnless(_NEEDLE_AVAILABLE, "Needle 3 venv or bridge runtime not found")
class TestScaffoldedNeedleLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.transport = NeedleBridgeTransport(_VENV_PYTHON, _BRIDGE_SCRIPT)
        cls.transport.load()
        cls.decoder = ScaffoldedNeedleDecoder(transport=cls.transport)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.decoder.close()

    def test_baseline_turn_live(self) -> None:
        prompt = "Convert report.pdf to text format"
        result = self.decoder.decode_with_result(prompt)
        self.assertIsInstance(result, ScaffoldedNeedleResult)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.decoded_request)
        self.assertIsInstance(result.decoded_request, DecodedRequest)
        self.assertIn("goal", result.called_views)
        self.assertGreater(result.total_latency_ms, 0)

        # Frozen immutability check
        with self.assertRaises(Exception):
            result.decoded_request.raw_text = "altered"  # type: ignore[misc]

    def test_negation_turn_live(self) -> None:
        prompt = "Draft an email to Prof. Rao about the meeting tomorrow, but do not send it"
        result = self.decoder.decode_with_result(prompt)
        self.assertIsInstance(result, ScaffoldedNeedleResult)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.decoded_request)
        # Operations view should be called due to actions + negation
        self.assertIn("operations", result.called_views)

    def test_active_context_turn_live(self) -> None:
        prompt = "Revise it to sound more formal and add Dean's approval note"
        art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document")
        ent = EntityDescriptor(id="e1", name="Dean", category="person")
        ctx = ActiveContext(active_artifacts=(art,), active_entities=(ent,))

        result = self.decoder.decode_with_result(prompt, active_context=ctx)
        self.assertIsInstance(result, ScaffoldedNeedleResult)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.decoded_request)
        # Reference view should be called
        self.assertIn("references", result.called_views)

    def test_reset_between_turns_live(self) -> None:
        # Run turn 1
        res1 = self.decoder.decode_with_result("Bring that file up", reset_state=True)
        self.assertIsNotNone(res1.decoded_request)
        # Run turn 2
        res2 = self.decoder.decode_with_result("Draft a short formal email", reset_state=True)
        self.assertIsNotNone(res2.decoded_request)


if __name__ == "__main__":
    unittest.main()
