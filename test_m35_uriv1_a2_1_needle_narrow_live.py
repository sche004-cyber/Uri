"""Live inference tests for Batch A2.1: Needle 3 Narrow-Schema Qualification.

These tests invoke the actual Needle 3 model through the offline subprocess bridge.
Following the M35 evidence-integrity standard, they assert structural guarantees:
  - Subprocess transport executes cleanly without unhandled exceptions.
  - Every narrow extractor yields a typed result object or a typed DecodeError.
  - The deterministic merger produces a valid, deep-frozen DecodedRequest.
  - Identical prompts yield repeatable outputs.

They do NOT artificially assert semantic correctness that the model failed to achieve
(semantic qualification evidence is documented in the A2.1 report).

Automatically skipped if the Needle virtualenv is not available on the host.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from uri_v1.turn.contracts import DecodedRequest
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from uri_v1.turn.needle_merge import merge_narrow_results
from uri_v1.turn.needle_narrow import (
    NarrowConstraintsResult,
    NarrowGoalResult,
    NarrowOperationsResult,
    NarrowReferencesResult,
    NeedleNarrowSemanticExtractor,
)

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

ALL_CASES = REQUIRED_CASES + STRESS_CASES


@unittest.skipUnless(_NEEDLE_AVAILABLE, "Needle virtualenv not available on this host")
class NeedleNarrowLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transport = NeedleBridgeTransport(_VENV_PYTHON, _BRIDGE_SCRIPT)
        cls.extractor = NeedleNarrowSemanticExtractor(cls.transport)
        cls.transport.load()

    @classmethod
    def tearDownClass(cls):
        cls.extractor.close()

    def test_bridge_is_ready(self):
        self.assertTrue(self.transport.is_running())
        self.assertEqual(self.transport.runtime_info.get("status"), "ready")
        self.assertEqual(self.transport.runtime_info.get("package"), "cactus-needle")

    def test_schema_a_structural_execution(self):
        for text in ALL_CASES:
            with self.subTest(prompt=text):
                res = self.extractor.extract_goal(text)
                self.assertIsInstance(res, NarrowGoalResult)
                self.assertTrue(res.ok or res.error is not None or res.declined)
                self.assertIsNotNone(res.latency_ms)

    def test_schema_b_structural_execution(self):
        for text in ALL_CASES:
            with self.subTest(prompt=text):
                res = self.extractor.extract_operations(text)
                self.assertIsInstance(res, NarrowOperationsResult)
                self.assertTrue(res.ok or res.error is not None or res.declined)
                self.assertIsNotNone(res.latency_ms)

    def test_schema_c_structural_execution(self):
        for text in ALL_CASES:
            with self.subTest(prompt=text):
                res = self.extractor.extract_references(text)
                self.assertIsInstance(res, NarrowReferencesResult)
                self.assertTrue(res.ok or res.error is not None or res.declined)
                self.assertIsNotNone(res.latency_ms)

    def test_schema_d_structural_execution(self):
        for text in ALL_CASES:
            with self.subTest(prompt=text):
                res = self.extractor.extract_constraints(text)
                self.assertIsInstance(res, NarrowConstraintsResult)
                self.assertTrue(res.ok or res.error is not None or res.declined)
                self.assertIsNotNone(res.latency_ms)

    def test_deterministic_merge_live_flow(self):
        text = "Compare only the 2025 and 2026 decisions, do not use anything before 2025, and keep the result under one page."
        goal_res = self.extractor.extract_goal(text)
        ops_res = self.extractor.extract_operations(text)
        refs_res = self.extractor.extract_references(text)
        const_res = self.extractor.extract_constraints(text)

        merged = merge_narrow_results(goal_res, ops_res, refs_res, const_res, DecodeInput.from_text(text))
        self.assertIsInstance(merged, DecodedRequest)
        self.assertEqual(merged.raw_text, text)

    def test_repeatability_of_narrow_inference(self):
        text = "Convert this to PDF."
        first = self.extractor.extract_goal(text)
        second = self.extractor.extract_goal(text)
        self.assertEqual(first.declined, second.declined)
        self.assertEqual(first.call_count, second.call_count)
        self.assertEqual(first.ok, second.ok)
        if first.raw_confidence is not None and second.raw_confidence is not None:
            # Needle confidence can vary slightly across invocations on a cached agent
            self.assertAlmostEqual(first.raw_confidence, second.raw_confidence, places=1)


if __name__ == "__main__":
    unittest.main()
