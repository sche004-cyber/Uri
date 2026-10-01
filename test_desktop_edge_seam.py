"""Harness-first social seam (experimental, default off)."""
import os
import unittest
from unittest.mock import MagicMock, patch

from uri_core.core.edge.settings import EdgeSettings
from uri_desktop_seams.harness_first import edge_chat, seam
from uri_desktop_seams.harness_first.social import social_intent


def _payload(text, override=None):
    return MagicMock(text=text, session_id="s1", model_override=override)


def _context(pending=False, waiting=False):
    ctx = MagicMock()
    ctx.orchestrator.session_manager.get_session.return_value = MagicMock(
        active_workflow=object() if waiting else None, active_workflow_status="waiting_for_input")
    return ctx


class SocialInspectionTests(unittest.TestCase):
    def test_social_turns_admitted(self):
        for t in ["hello", "Hi URI", "hey there", "Thank you so much!", "good night", "ok cool",
                  "who are you?", "are you there?", "see you tomorrow"]:
            self.assertIsNotNone(social_intent(t), t)

    def test_work_turns_not_admitted(self):
        for t in ["hi, how much RAM is this PC using?", "Thanks. Now search the web for NAAC rules.",
                  "hello, read the attached minutes.pdf", "ok send it", "thanks, delete the file",
                  "good morning, check my mail", "hi 21CS042", "what can you do about my slow laptop?",
                  "remember that my extension is 4417", "hello http://x.example",
                  "what can you do?", "can you help me"]:
            self.assertIsNone(social_intent(t), t)


class ValidatorTests(unittest.TestCase):
    def test_rejects_unsafe_replies(self):
        self.assertEqual(edge_chat.validate(""), "empty")
        self.assertEqual(edge_chat.validate("I have sent the email for you."), "claims_action")
        self.assertEqual(edge_chat.validate("See https://x.example"), "forbidden_content")
        self.assertEqual(edge_chat.validate("<think>hm</think>"), "forbidden_content")
        self.assertIsNone(edge_chat.validate("Hello! How can I help you today?"))


class SeamTests(unittest.TestCase):
    def _run(self, text="hello", **kw):
        with patch.object(seam, "_pending_approvals", return_value=kw.get("pending", False)), \
             patch.object(seam, "_user_settings", return_value=kw.get("settings", EdgeSettings())), \
             patch.object(edge_chat, "generate", return_value=edge_chat.ChatResult(
                 "Hi there! What can I do for you?", "edge_model", "m", 300.0, None, 400, 9)) as gen:
            out = seam.try_harness_first(context=_context(waiting=kw.get("waiting", False)), principal=None,
                                         payload=_payload(text, kw.get("override")),
                                         current_turn_attachments=kw.get("att", []))
        return out, gen

    @patch.dict(os.environ, {"URI_HARNESS_FIRST": ""})
    def test_flag_off_does_nothing(self):
        out, gen = self._run()
        self.assertIsNone(out)
        gen.assert_not_called()

    @patch.dict(os.environ, {"URI_HARNESS_FIRST": "1"})
    def test_social_turn_answered_by_edge(self):
        out, gen = self._run()
        self.assertEqual(out["_harness"]["class"], "HARNESS_PLUS_EDGE")
        self.assertEqual(out["narrative"], "Hi there! What can I do for you?")
        self.assertEqual(out["_edge_routing"]["disposition"], "HARNESS_EDGE_CHAT")
        gen.assert_called_once()

    @patch.dict(os.environ, {"URI_HARNESS_FIRST": "1"})
    def test_guards_fall_through(self):
        cases = [dict(text="hi, read report.pdf"), dict(pending=True), dict(waiting=True),
                 dict(att=[{"file_id": "f"}]), dict(override={"provider_id": "p", "model": "m"}),
                 dict(settings=EdgeSettings(intelligence_mode="MAIN_BRAIN_PREFERRED")),
                 dict(settings=EdgeSettings(enabled=False))]
        for kw in cases:
            out, gen = self._run(**kw)
            self.assertIsNone(out, kw)
            gen.assert_not_called()

    @patch.dict(os.environ, {"URI_HARNESS_FIRST": "1"})
    def test_edge_only_mode_answers_social_turn(self):
        out, _ = self._run(settings=EdgeSettings(intelligence_mode="EDGE_ONLY"))
        self.assertIsNotNone(out)

    def test_fallback_on_transport_failure(self):
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            r = edge_chat.generate("hello", "greeting", model="m", timeout_s=0.1)
        self.assertEqual(r.source, "deterministic_fallback")
        self.assertTrue(r.text)


if __name__ == "__main__":
    unittest.main()


class FinalizeAttributionTests(unittest.TestCase):
    def test_harness_turn_is_not_attributed_to_an_earlier_main_brain_call(self):
        from uri_core.app import server
        stale = {"provider_id": "ollama", "model": "qwen3.5:9b", "prompt_tokens": 9000, "eval_tokens": 50,
                 "duration_seconds": 19.0, "calls": [{"role": "reasoning"}], "reasoning_ms": 16000,
                 "drafting_ms": 2000, "model_total_ms": 18000}
        result = {"status": "success", "session_id": "s1", "narrative": "Hi!", "response": {"message": "Hi!"},
                  "_harness": {"class": "HARNESS_PLUS_EDGE", "edge_model": "qwen3:0.6b", "edge_ms": 80.0}}
        with patch.object(server, "_serving_model_for_turn", return_value=stale):
            out = server._finalize_ask_response(MagicMock(), None, _payload("hello"), result)
        self.assertEqual(out["serving_model"], "qwen3:0.6b")
        self.assertEqual(out["serving_provider"], "ollama (edge)")
        self.assertIsNone(out["serving_prompt_tokens"])
        self.assertEqual(out["serving_duration_seconds"], 0.08)
        self.assertEqual(out["harness_route"]["class"], "HARNESS_PLUS_EDGE")
        self.assertEqual(out["serving_call_count"], 1)
        self.assertEqual(out["serving_calls"][0]["model"], "qwen3:0.6b")

    def _rec(self, ts, role, dur, pt=100, et=10):
        k = lambda v: {"value": v, "confidence": "KNOWN"}
        return {"ts": ts, "role": role, "provider_id": "ollama", "model": "qwen3.5:9b", "outcome": "success",
                "prompt_tokens": k(pt), "eval_tokens": k(et), "duration_seconds": k(dur)}

    def test_main_brain_turn_reports_every_call_since_turn_start(self):
        from datetime import datetime
        from uri_core.app import server
        start = datetime.fromisoformat("2026-10-01T18:00:00+00:00").timestamp()
        records = [self._rec("2026-10-01T17:59:00+00:00", "drafting", 3.0),   # earlier turn
                   self._rec("2026-10-01T18:00:09+00:00", "reasoning", 9.0, 4000, 90),
                   self._rec("2026-10-01T18:00:11+00:00", "drafting", 2.0, 5000, 20)]
        result = {"status": "success", "session_id": "s1", "narrative": "Hi.", "response": {"message": "Hi."}}
        with patch("uri_core.core.usage_meter.month_records", return_value=records):
            out = server._finalize_ask_response(MagicMock(), "u1", _payload("hello"), result, turn_started=start)
        self.assertEqual(out["serving_call_count"], 2)
        self.assertEqual([c["role"] for c in out["serving_calls"]], ["reasoning", "drafting"])
        self.assertEqual(out["serving_duration_seconds"], 11.0)
        self.assertEqual(out["serving_prompt_tokens"], 9000)
        self.assertEqual(out["serving_model"], "qwen3.5:9b")
        self.assertIsNotNone(out["turn_duration_seconds"])

    def test_turn_without_model_call_is_not_attributed_to_an_earlier_one(self):
        from datetime import datetime
        from uri_core.app import server
        start = datetime.fromisoformat("2026-10-01T18:00:00+00:00").timestamp()
        records = [self._rec("2026-10-01T17:59:00+00:00", "drafting", 3.0)]
        result = {"status": "success", "session_id": "s1", "response": {"message": "Approved."}}
        with patch("uri_core.core.usage_meter.month_records", return_value=records):
            out = server._finalize_ask_response(MagicMock(), "u1", _payload("yes"), result, turn_started=start)
        self.assertIsNone(out["serving_call_count"])  # no usage record: unknown, not 0
        self.assertIsNone(out["serving_model"])
        self.assertIsNone(out["serving_duration_seconds"])


class AuditRepairTests(unittest.TestCase):
    """Codex audit of dc5b337 (REPAIR_REQUIRED) repairs."""

    def test_unqualified_edge_model_escalates(self):
        with patch.dict(os.environ, {seam.FLAG: "1"}), patch.object(edge_chat, "DEFAULT_MODEL", "gemma3:270m"),                 patch.object(edge_chat, "generate") as gen:
            out = seam.try_harness_first(context=_context(), principal=None, payload=_payload("hello"),
                                         current_turn_attachments=[])
        self.assertIsNone(out)
        gen.assert_not_called()

    def _rec(self, ts, outcome="success", dur=1.0):
        k = lambda v: {"value": v, "confidence": "KNOWN"}
        return {"ts": ts, "role": "reasoning", "provider_id": "ollama", "model": "qwen3.5:9b", "outcome": outcome,
                "prompt_tokens": k(10), "eval_tokens": k(1), "duration_seconds": k(dur)}

    def test_failed_attempts_are_counted(self):
        from datetime import datetime
        from uri_core.app import server
        start = datetime.fromisoformat("2026-10-01T18:00:00+00:00").timestamp()
        recs = [self._rec("2026-10-01T18:00:05+00:00", "failure", 2.0), self._rec("2026-10-01T18:00:09+00:00")]
        with patch("uri_core.core.usage_meter.month_records", return_value=recs):
            out = server._finalize_ask_response(MagicMock(), "u1", _payload("x"), {"status": "success"}, turn_started=start)
        self.assertEqual(out["serving_call_count"], 2)
        self.assertEqual(out["serving_duration_seconds"], 3.0)
        self.assertEqual(out["serving_model"], "qwen3.5:9b")

    def test_override_without_any_call_is_not_shown_as_executing_model(self):
        from datetime import datetime
        from uri_core.app import server
        start = datetime.fromisoformat("2026-10-01T18:00:00+00:00").timestamp()
        payload = _payload("x", override={"provider_id": "ollama", "model": "gemma4:12b"})
        with patch("uri_core.core.usage_meter.month_records", return_value=[]):
            out = server._finalize_ask_response(MagicMock(), "u1", payload, {"status": "success"}, turn_started=start)
        self.assertIsNone(out["serving_call_count"])  # no usage record: unknown, not 0
        self.assertIsNone(out["serving_model"])

    def test_conversational_draft_keeps_a_length_bound(self):
        from uri_core.core.response_validation import (MAX_CONVERSATIONAL_NARRATIVE_LENGTH, ResponseValidationError,
                                                       validate_drafted_response)
        outcome = {"execution": {"status": "not_applicable", "capability": None}, "response": {"message": "chat"}}
        self.assertTrue(validate_drafted_response("word " * 150, outcome))
        with self.assertRaises(ResponseValidationError):
            validate_drafted_response("word " * (MAX_CONVERSATIONAL_NARRATIVE_LENGTH // 5 + 10), outcome)


class IntentFitTests(unittest.TestCase):
    def test_farewell_answered_with_welcome_is_rejected(self):
        self.assertEqual(edge_chat.validate("You're welcome! Have a great day!", "farewell"), "intent_mismatch")
        self.assertIsNone(edge_chat.validate("Goodbye, take care!", "farewell"))

    def test_thanks_needs_acknowledgement(self):
        self.assertEqual(edge_chat.validate("Hi! Have a great day!", "thanks"), "intent_mismatch")
        self.assertIsNone(edge_chat.validate("You're welcome!", "thanks"))
