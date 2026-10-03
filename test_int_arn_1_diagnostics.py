"""Mocked Brain coverage for privacy-safe INT-ARN-1 decision diagnostics."""

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from uri_core.core import canonical_execution, decision_engine


class Directory:
    def summaries(self):
        return [{"capability_id": "Demo"}]

    def describe(self, capability_id):
        return {"actions": ["open"], "action_schemas": {
            "open": {"parameters": {"file_id": {"type": "string"}}}}}


TEXT = "open that document"


def brain_contract(slot=None):
    contract = {
        "goal": TEXT, "mode": "single_action", "capability": "Demo",
        "actions": [{"name": "open", "inputs": {}}], "clarification": None,
        "unsupported_reason": None, "requires_approval": False,
        "confidence": "high", "reason": "Open file",
    }
    if slot is not None:
        contract["reference_slots"] = [slot]
    return contract


def brain_slot(valid=True):
    return {
        "span": {"start": 5 if valid else 0, "end": 18, "text": "that document"},
        "ref_key": "r1", "target": {"capability_id": "Demo", "action_name": "open",
                                        "argument_name": "file_id"},
        "relation": "direct", "source_class": "file",
    }


class ReferenceDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"URI_INT_ARN_1_ENABLED": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.turn = {"turn": {"user_text": TEXT}, "recent_conversation": [],
                     "active_pointer": None, "capability_summaries": [],
                     "session_facts": [], "attempt_history": []}

    def decide(self, contract):
        return decision_engine.propose_decision(
            turn_state_data=self.turn, capability_directory=Directory(),
            model_callable=lambda _: json.dumps(contract),
        )

    def test_mock_brain_slot_present_absent_invalid(self):
        absent = self.decide(brain_contract())
        self.assertEqual(absent.status, "ok")
        self.assertEqual(absent.reference_diagnostics["raw_reference_slots"], False)
        self.assertEqual(absent.reference_diagnostics["slot_count"], 0)

        present = self.decide(brain_contract(brain_slot()))
        self.assertEqual(present.status, "ok")
        self.assertEqual(present.reference_diagnostics["slot_validation"],
                         [{"passed": True, "reason": None}])

        invalid = self.decide(brain_contract(brain_slot(valid=False)))
        self.assertEqual(invalid.status, "invalid")
        self.assertEqual(invalid.reference_diagnostics["slot_validation"],
                         [{"passed": False, "reason": "SPAN_MISMATCH"}])
        self.assertNotIn(TEXT, json.dumps(invalid.reference_diagnostics))

        with patch.dict(os.environ, {"URI_INT_ARN_1_ENABLED": "0"}):
            off = self.decide(brain_contract())
        self.assertIsNone(off.reference_diagnostics)

    def test_per_decision_row_and_card_summary(self):
        decision = self.decide(brain_contract(brain_slot()))
        path = "user-scoped/reference_clarification/telemetry.jsonl"
        blocked = {"status": "awaiting_user_response", "session_id": "s1",
                   "execution": {"status": "not_executed", "reason": "REFERENCE_UNRESOLVED"},
                   "clarification": {"options": []}}
        rows = []
        with patch.object(canonical_execution, "build_turn_state_and_directory",
                          return_value=(SimpleNamespace(data=self.turn), Directory())), \
             patch.object(canonical_execution, "propose_decision", return_value=decision), \
             patch.object(canonical_execution, "_reference_prepare",
                          return_value=(decision.contract, blocked)), \
             patch.object(canonical_execution, "record_shadow_trace",
                          side_effect=lambda row, path: rows.append((row, path))):
            result = canonical_execution.run_canonical_for_ask(
                orchestrator=SimpleNamespace(), session_id="s1", user_text=TEXT,
                principal=SimpleNamespace(user_id="u1"), log_path=path)
        self.assertEqual(result["_reference_diagnostics"]["outcome"], "card")
        summary = [(row, target) for row, target in rows if row.get("event") == "int_arn_1_decision"]
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0][1], path)
        self.assertTrue(summary[0][0]["clarification_round_built"])
        self.assertNotIn(TEXT, json.dumps(summary[0][0]))


if __name__ == "__main__":
    unittest.main()
