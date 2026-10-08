"""M35 Batch A2: REAL Needle 3 inference qualification tests.

These are NOT deterministic unit tests: they invoke the actual Needle 3
model through the offline subprocess bridge and assert only on structural
guarantees the code must hold regardless of model quality (the transport
works, decoding never crashes, output is either a valid DecodedRequest or a
DecodeError -- never a fabricated one). They deliberately do NOT assert
Needle produced semantically correct output, because A2's qualification
evidence (see docs/plans/M35_URIV1_A2_NEEDLE_DECODER_REPORT.md) found base
Needle 3 (generation 3) frequently declines to call the tool at all or
emits degraded fields for this schema. Semantic accuracy is qualified in
the report from the same live probe data, not asserted here as pass/fail.

Skipped automatically (not failed) if the Needle virtualenv is unavailable,
so normal unit-test discovery / CI stays green without local Needle
infrastructure. Requires no internet access: HF_HUB_OFFLINE=1 is set by the
bridge runtime itself.
"""

import unittest
from pathlib import Path

from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, NeedleSemanticDecoder, default_venv_python

_VENV_PYTHON = default_venv_python()
_BRIDGE_SCRIPT = Path(__file__).parent / "uri_v1" / "turn" / "needle_bridge_runtime.py"
_NEEDLE_AVAILABLE = _VENV_PYTHON.is_file() and _BRIDGE_SCRIPT.is_file()

REQUIRED_CASES = [
    "Convert this to PDF.",
    "Bring that file up.",
    "Do the same thing for them.",
    "Don't send it. Just draft the email.",
    "Find the previous approval, compare it with this one and draft a revised order.",
    (
        "The committee has already changed its view twice and the latest letter doesn't "
        "seem to match what was decided earlier. I need something I can put up tomorrow."
    ),
    "Compare only the 2025 and 2026 decisions, do not use anything before 2025, and keep the result under one page.",
    "Draft a short formal email in Indian English to the Chief Warden.",
    "Do not summarize this; compare the exact figures in a table.",
    "What was approved yesterday?",
]

STRESS_CASES = [
    "Hello",
    "Thanks",
    "Open calculator.",
    "Don't open it yet.",
    "Send it to him after they approve it.",
    "Compare the attached PDF with this spreadsheet.",
    "Make something I can submit tomorrow.",
    "No, I meant the earlier one.",
]


@unittest.skipUnless(_NEEDLE_AVAILABLE, "Needle virtualenv not available on this host")
class NeedleLiveTransportTests(unittest.TestCase):
    def setUp(self):
        self.transport = NeedleBridgeTransport(_VENV_PYTHON, _BRIDGE_SCRIPT)
        self.decoder = NeedleSemanticDecoder(self.transport)

    def tearDown(self):
        self.decoder.close()

    def test_bridge_loads_and_pings_ready(self):
        self.transport.load()
        self.assertEqual(self.transport.runtime_info.get("status"), "ready")
        self.assertEqual(self.transport.runtime_info.get("package"), "cactus-needle")

    def test_decode_never_raises_uncaught_and_always_yields_result_or_typed_error(self):
        for text in REQUIRED_CASES + STRESS_CASES:
            with self.subTest(text=text):
                result = self.decoder.decode_with_result(DecodeInput(raw_text=text))
                self.assertTrue(result.ok or result.error is not None)
                if result.ok:
                    self.assertEqual(result.decoded_request.raw_text, text)

    def test_required_cases_batch_for_report_evidence(self):
        """Runs the full required qualification battery once; does not assert
        semantic correctness (see module docstring). Evidence is captured in
        the A2 report from a dedicated live probe run, not from this test's
        pass/fail state."""
        outcomes = []
        for text in REQUIRED_CASES:
            result = self.decoder.decode_with_result(DecodeInput(raw_text=text))
            outcomes.append((text, result.ok, result.error.reason.value if result.error else None))
        self.assertEqual(len(outcomes), len(REQUIRED_CASES))

    def test_repeatability_of_identical_prompt(self):
        text = "Convert this to PDF."
        first = self.decoder.decode_with_result(DecodeInput(raw_text=text))
        second = self.decoder.decode_with_result(DecodeInput(raw_text=text))
        self.assertEqual(first.ok, second.ok)
        if first.raw_confidence is not None and second.raw_confidence is not None:
            self.assertAlmostEqual(first.raw_confidence, second.raw_confidence, places=4)


if __name__ == "__main__":
    unittest.main()
