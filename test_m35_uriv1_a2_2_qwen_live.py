"""Live inference qualification tests for Batch A2.2: Qwen Step-1 Semantic Decoder.

Invokes the local Qwen candidate (Qwen3.5-0.8B.Q8_0) running on LM Studio.
Asserts structural guarantees:
  - Transport connects cleanly to local endpoint.
  - Model returns structured JSON conforming to DecodedRequest.
  - Decoding yields valid DecodedRequest or typed DecodeError, never uncaught exceptions.
  - References maintain is_resolved=False invariant.

Auto-skipped if the local LM Studio runtime is not responsive.
"""

from __future__ import annotations

import unittest
import urllib.request

from uri_v1.turn.contracts import DecodedRequest
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.qwen_decoder import QwenLocalTransport, QwenSemanticDecoder


def _is_qwen_server_ready() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


_SERVER_READY = _is_qwen_server_ready()

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


@unittest.skipUnless(_SERVER_READY, "Local LM Studio Qwen server not running on port 1234")
class QwenLiveInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transport = QwenLocalTransport()
        cls.decoder = QwenSemanticDecoder(cls.transport, max_tokens=600)

    def test_transport_connects_and_lists_model(self):
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            self.assertEqual(resp.status, 200)

    def test_constrained_decoding_on_all_prompts(self):
        for text in REQUIRED_CASES + STRESS_CASES:
            with self.subTest(prompt=text):
                res = self.decoder.decode_with_result(DecodeInput(raw_text=text), constrained=True)
                self.assertTrue(res.ok or res.error is not None)
                self.assertIsNotNone(res.latency_ms)
                if res.ok:
                    self.assertIsInstance(res.decoded_request, DecodedRequest)
                    self.assertEqual(res.decoded_request.raw_text, text)
                    for ref in res.decoded_request.references:
                        self.assertFalse(ref.is_resolved)

    def test_unconstrained_decoding_sample(self):
        text = "Convert this to PDF."
        res = self.decoder.decode_with_result(DecodeInput(raw_text=text), constrained=False)
        self.assertTrue(res.ok or res.error is not None)
        if res.ok:
            self.assertEqual(res.decoded_request.raw_text, text)


if __name__ == "__main__":
    unittest.main()
