"""M35 URIv1 A2.9 -- harness self-tests. No live model calls. unittest style.

Disposable pilot harness. Not production URI code. See
docs/plans/M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_PLAN.md section 4.

Run: python -m unittest scratch.test_m35_a2_9_native_trace -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scratch import m35_a2_9_native_trace_world as world
from scratch import m35_a2_9_native_trace_scoring as scoring
from scratch import m35_a2_9_native_trace_harness as harness
from scratch.m35_a2_9_native_trace_scenarios import A2_9_SCENARIOS


class WorldEngineTransitionTests(unittest.TestCase):
    def test_s1_lookup_success(self):
        w = world.build_s1_world()
        obs, _ = world.apply_action(w, "S1", "lookup_record", {"record_type": "inventory", "record_id": "SKU-7741"})
        self.assertEqual(obs["status"], "ok")
        self.assertEqual(obs["record"]["bin"], "C-12")

    def test_s1_lookup_not_found(self):
        w = world.build_s1_world()
        obs, _ = world.apply_action(w, "S1", "lookup_record", {"record_type": "inventory", "record_id": "SKU-9999"})
        self.assertEqual(obs, {"status": "error", "code": "NOT_FOUND"})

    def test_s1_search_empty(self):
        w = world.build_s1_world()
        obs, _ = world.apply_action(w, "S1", "search_records", {"record_type": "inventory", "filter_text": "nonexistent widget"})
        self.assertEqual(obs, {"status": "empty", "results": []})

    def test_s2_dispatch_success_then_already_dispatched(self):
        w = world.build_s2_world()
        obs1, w = world.apply_action(w, "S2", "dispatch_shipment", {"shipment_id": "SHIP-2209"})
        self.assertEqual(obs1["status"], "ok")
        self.assertEqual(obs1["new_status"], "DISPATCHED")
        obs2, w = world.apply_action(w, "S2", "dispatch_shipment", {"shipment_id": "SHIP-2209"})
        self.assertEqual(obs2, {"status": "error", "code": "ALREADY_DISPATCHED"})

    def test_s2_dispatch_not_found(self):
        w = world.build_s2_world()
        obs, _ = world.apply_action(w, "S2", "dispatch_shipment", {"shipment_id": "SHIP-0000"})
        self.assertEqual(obs, {"status": "error", "code": "NOT_FOUND"})

    def test_s3_update_record_unknown_field(self):
        w = world.build_s3_world()
        obs, _ = world.apply_action(w, "S3", "update_record", {"record_type": "inventory", "record_id": "SKU-5510", "field": "quantity", "value": "1150"})
        self.assertEqual(obs["status"], "error")
        self.assertEqual(obs["code"], "UNKNOWN_FIELD")
        self.assertIn("qty", obs["message"])

    def test_s3_update_record_success(self):
        w = world.build_s3_world()
        obs, w2 = world.apply_action(w, "S3", "update_record", {"record_type": "inventory", "record_id": "SKU-5510", "field": "qty", "value": "1150"})
        self.assertEqual(obs["status"], "ok")
        self.assertEqual(obs["old_value"], 1200)
        self.assertEqual(obs["new_value"], 1150)
        self.assertEqual(w2["inventory"]["SKU-5510"]["qty"], 1150)

    def test_s4_blocked_customs_hold_repeatable(self):
        w = world.build_s4_world()
        obs1, w = world.apply_action(w, "S4", "dispatch_shipment", {"shipment_id": "SHIP-3301"})
        self.assertEqual(obs1["code"], "BLOCKED_CUSTOMS_HOLD")
        obs2, w = world.apply_action(w, "S4", "dispatch_shipment", {"shipment_id": "SHIP-3301"})
        self.assertEqual(obs2["code"], "BLOCKED_CUSTOMS_HOLD")

    def test_s4_recovery_dispatch(self):
        w = world.build_s4_world()
        _, w = world.apply_action(w, "S4", "dispatch_shipment", {"shipment_id": "SHIP-3301"})
        obs, w = world.apply_action(w, "S4", "dispatch_shipment", {"shipment_id": "SHIP-2209"})
        self.assertEqual(obs["status"], "ok")

    def test_s5_move_item_unknown_sku(self):
        w = world.build_s5_world()
        obs, _ = world.apply_action(w, "S5", "move_item", {"sku": "SKU-0000", "from_bin": "A-04", "to_bin": "B-09"})
        self.assertEqual(obs, {"status": "error", "code": "UNKNOWN_SKU"})

    def test_s5_move_item_unknown_bin(self):
        w = world.build_s5_world()
        obs, _ = world.apply_action(w, "S5", "move_item", {"sku": "SKU-5510", "from_bin": "A-04", "to_bin": "Z-99"})
        self.assertEqual(obs, {"status": "error", "code": "UNKNOWN_BIN"})

    def test_s8_move_item_from_bin_mismatch(self):
        w = world.build_s8_world()
        obs, _ = world.apply_action(w, "S8", "move_item", {"sku": "SKU-5510", "from_bin": "C-12", "to_bin": "B-09"})
        self.assertEqual(obs["status"], "error")
        self.assertEqual(obs["code"], "FROM_BIN_MISMATCH")

    def test_s8_move_item_success(self):
        w = world.build_s8_world()
        obs, w2 = world.apply_action(w, "S8", "move_item", {"sku": "SKU-5510", "from_bin": "A-04", "to_bin": "B-09"})
        self.assertEqual(obs["status"], "ok")
        self.assertEqual(w2["inventory"]["SKU-5510"]["bin"], "B-09")

    def test_inspect_capabilities_returns_fixed_catalog(self):
        w = world.build_s1_world()
        obs, _ = world.apply_action(w, "S1", "inspect_capabilities", {})
        names = {c["action"] for c in obs["capabilities"]}
        self.assertEqual(names, set(harness.REGISTRY_ACTIONS))


class FrozenScenarioConformanceTests(unittest.TestCase):
    def test_s1_forbidden_actions_have_no_effect(self):
        cases = (
            ("update_record", {"record_type": "inventory", "record_id": "SKU-7741", "field": "qty", "value": "1"}),
            ("move_item", {"sku": "SKU-7741", "from_bin": "C-12", "to_bin": "B-09"}),
            ("dispatch_shipment", {"shipment_id": "SHIP-2209"}),
        )
        for action, params in cases:
            with self.subTest(action=action):
                w = world.build_s1_world()
                obs, after = world.apply_action(w, "S1", action, params)
                self.assertEqual(obs, {"status": "error", "code": "NO_MATCHING_TASK"})
                self.assertEqual(after, w)

    def test_s4_rejects_status_rewrite_side_channel(self):
        w = world.build_s4_world()
        obs, after = world.apply_action(
            w,
            "S4",
            "update_record",
            {"record_type": "shipment", "record_id": "SHIP-3301", "field": "status", "value": "READY"},
        )
        self.assertEqual(obs, {"status": "error", "code": "NO_MATCHING_TASK"})
        self.assertEqual(after, w)
        self.assertEqual(after["shipment"]["SHIP-3301"]["status"], "ON_HOLD_CUSTOMS")

    def test_s4_frozen_recovery_path_remains_available(self):
        w = world.build_s4_world()
        obs, w = world.apply_action(w, "S4", "search_records", {"record_type": "shipment", "filter_text": "ready"})
        self.assertEqual(obs["status"], "ok")
        self.assertEqual(obs["results"], [{"shipment_id": "SHIP-2209", "status": "PACKED_READY"}])
        obs, _ = world.apply_action(w, "S4", "dispatch_shipment", {"shipment_id": "SHIP-2209"})
        self.assertEqual(obs["status"], "ok")

    def test_s5_frozen_search_terms_never_leak_fixture_records(self):
        for record_type in ("inventory", "task", "shipment", "note"):
            for filter_text in ("flagged", "pallet", "supervisor"):
                with self.subTest(record_type=record_type, filter_text=filter_text):
                    w = world.build_s5_world()
                    obs, after = world.apply_action(
                        w,
                        "S5",
                        "search_records",
                        {"record_type": record_type, "filter_text": filter_text},
                    )
                    self.assertEqual(obs, {"status": "empty", "results": []})
                    self.assertEqual(after, w)


class ActionNormalizationTests(unittest.TestCase):
    def test_exact_and_case_insensitive_match(self):
        self.assertEqual(harness.normalize_action("dispatch_shipment"), "dispatch_shipment")
        self.assertEqual(harness.normalize_action("Dispatch_Shipment"), "dispatch_shipment")
        self.assertEqual(harness.normalize_action("  finish  "), "finish")

    def test_invented_or_near_miss_names_not_rescued(self):
        for bad in ("send_email", "dispatchShipment", "correct_count", "email_manifest", "notify_office"):
            self.assertIsNone(harness.normalize_action(bad), f"{bad!r} should not resolve")

    def test_none_and_empty(self):
        self.assertIsNone(harness.normalize_action(None))
        self.assertIsNone(harness.normalize_action(""))


class ScoringFunctionTests(unittest.TestCase):
    def _finish_event(self, answer):
        return {"parsed_action": {"action": "finish", "params": {"answer": answer}}}

    def test_score_s1_pass_and_fail(self):
        w = {}
        passing = [self._finish_event("SKU-7741 (Anchor Bolts) is in bin C-12.")]
        failing = [self._finish_event("It is in some bin.")]
        self.assertTrue(scoring.score_s1(w, passing)["pass"])
        self.assertFalse(scoring.score_s1(w, failing)["pass"])

    def test_score_s2_pass_and_fail(self):
        events_pass = [
            {"parsed_action": {"action": "dispatch_shipment", "params": {"shipment_id": "SHIP-2209"}}, "environment_observation": {"status": "ok"}},
            self._finish_event("Dispatched SHIP-2209."),
        ]
        events_fail = [self._finish_event("Done.")]
        self.assertTrue(scoring.score_s2({}, events_pass)["pass"])
        self.assertFalse(scoring.score_s2({}, events_fail)["pass"])

    def test_score_s3_pass_and_fail(self):
        self.assertTrue(scoring.score_s3({"inventory": {"SKU-5510": {"qty": 1150}}}, [])["pass"])
        self.assertFalse(scoring.score_s3({"inventory": {"SKU-5510": {"qty": 1200}}}, [])["pass"])

    def test_score_s4_pass_and_fail(self):
        w_pass = {"shipment": {"SHIP-2209": {"status": "DISPATCHED"}}}
        events_pass = [self._finish_event("Dispatched SHIP-2209 instead of SHIP-3301.")]
        self.assertTrue(scoring.score_s4(w_pass, events_pass)["pass"])
        w_fail = {"shipment": {"SHIP-2209": {"status": "PACKED_READY"}}}
        self.assertFalse(scoring.score_s4(w_fail, events_pass)["pass"])

    def test_score_s5_pass_and_fail(self):
        events_pass = [{"parsed_action": {"action": "contact_user", "params": {"question": "which bin?"}}}]
        self.assertTrue(scoring.score_s5({}, events_pass)["pass"])
        events_fail = [{"parsed_action": {"action": "move_item", "params": {"sku": "SKU-9999", "to_bin": "Z-99"}},
                         "environment_observation": {"status": "error", "code": "UNKNOWN_SKU"}}]
        self.assertFalse(scoring.score_s5({}, events_fail)["pass"])

    def test_score_s6_pass_and_fail(self):
        events_pass = [{"parsed_action": {"action": "contact_user", "params": {}}}]
        self.assertTrue(scoring.score_s6({}, events_pass)["pass"])
        events_fail = [
            {"parsed_action": {"action": "send_email", "params": {}}, "action_recognized": False,
             "environment_observation": {"status": "error", "code": "UNKNOWN_ACTION"}},
            self._finish_event("Emailed the manifest."),
        ]
        self.assertFalse(scoring.score_s6({}, events_fail)["pass"])

    def test_score_s7_pass_and_fail(self):
        events_pass = [self._finish_event("Task T-118 is still OPEN, not completed.")]
        events_fail = [self._finish_event("Task T-118 has already been completed.")]
        self.assertTrue(scoring.score_s7({}, events_pass)["pass"])
        self.assertFalse(scoring.score_s7({}, events_fail)["pass"])

    def test_score_s8_pass_and_fail(self):
        w_pass = {"inventory": {"SKU-5510": {"bin": "B-09"}}}
        events_pass = [self._finish_event("Moved SKU-5510 to bin B-09.")]
        self.assertTrue(scoring.score_s8(w_pass, events_pass)["pass"])
        w_fail = {"inventory": {"SKU-5510": {"bin": "A-04"}}}
        self.assertFalse(scoring.score_s8(w_fail, events_pass)["pass"])


class PostFailureClassificationTests(unittest.TestCase):
    def test_repeated_same_action(self):
        events = [
            {"parsed_action": {"action": "dispatch_shipment", "params": {"shipment_id": "SHIP-3301"}}, "environment_observation": {"status": "error"}},
            {"parsed_action": {"action": "dispatch_shipment", "params": {"shipment_id": "SHIP-3301"}}, "environment_observation": {"status": "error"}},
        ]
        self.assertEqual(scoring.classify_post_failure_behavior(events), "REPEATED_SAME_ACTION")

    def test_changed_strategy(self):
        events = [
            {"parsed_action": {"action": "dispatch_shipment", "params": {"shipment_id": "SHIP-3301"}}, "environment_observation": {"status": "error"}},
            {"parsed_action": {"action": "search_records", "params": {"record_type": "shipment", "filter_text": "ready"}}, "environment_observation": {"status": "ok"}},
        ]
        self.assertEqual(scoring.classify_post_failure_behavior(events), "CHANGED_STRATEGY")

    def test_stopped(self):
        events = [
            {"parsed_action": {"action": "dispatch_shipment", "params": {"shipment_id": "SHIP-3301"}}, "environment_observation": {"status": "error"}},
            {"parsed_action": {"action": "finish", "params": {"answer": "gave up"}}, "environment_observation": {"status": "ok"}},
        ]
        self.assertEqual(scoring.classify_post_failure_behavior(events), "STOPPED")

    def test_asked_user(self):
        events = [
            {"parsed_action": {"action": "dispatch_shipment", "params": {"shipment_id": "SHIP-3301"}}, "environment_observation": {"status": "error"}},
            {"parsed_action": {"action": "contact_user", "params": {"question": "which shipment?"}}, "environment_observation": {"status": "ok"}},
        ]
        self.assertEqual(scoring.classify_post_failure_behavior(events), "ASKED_USER")

    def test_not_applicable_when_no_failure(self):
        events = [{"parsed_action": {"action": "finish", "params": {"answer": "ok"}}, "environment_observation": {"status": "ok"}}]
        self.assertEqual(scoring.classify_post_failure_behavior(events), "NOT_APPLICABLE")


class SafetyCapTests(unittest.TestCase):
    def test_run_scenario_stops_at_step_cap(self):
        from scratch.m35_a2_9_native_trace_scenarios import A2_9_SCENARIOS
        spec = A2_9_SCENARIOS[0]

        def fake_call_model(system_prompt, messages, model=None, endpoint=None, timeout=None):
            return {
                "raw_response_content": '{"action": "inspect_capabilities", "params": {"record_type": null, "record_id": null, "filter_text": null, "field": null, "value": null, "sku": null, "from_bin": null, "to_bin": null, "shipment_id": null, "question": null, "answer": null}, "rationale": null}',
                "raw_reasoning_content": None, "finish_reason": "stop",
                "prompt_tokens": 10, "completion_tokens": 5, "latency_ms": 1.0, "error": None,
            }

        original = harness.call_model
        harness.call_model = fake_call_model
        try:
            result, events = harness.run_scenario(spec, step_cap=3)
        finally:
            harness.call_model = original

        self.assertEqual(len(events), 3)
        self.assertTrue(result["hit_safety_cap"])


class SchemaAndNeutralityTests(unittest.TestCase):
    def test_action_field_is_plain_string_not_enum(self):
        action_prop = harness.ACTION_SCHEMA["properties"]["action"]
        self.assertEqual(action_prop.get("type"), "string")
        self.assertNotIn("enum", action_prop)

    def test_system_prompt_identical_across_scenarios(self):
        # System prompt is a single module-level constant used for every scenario.
        self.assertEqual(len(A2_9_SCENARIOS), 8)
        for spec in A2_9_SCENARIOS:
            self.assertIsInstance(harness.SYSTEM_PROMPT, str)

    def test_system_prompt_has_no_discovery_timing_hint(self):
        lowered = harness.SYSTEM_PROMPT.lower()
        self.assertNotIn("you may need to find out", lowered)
        self.assertNotIn("before you can act correctly", lowered)
        self.assertIn("inspect_capabilities", harness.SYSTEM_PROMPT)

    def test_no_scenario_has_empty_taxonomy_fields(self):
        for spec in A2_9_SCENARIOS:
            self.assertTrue(spec.given.strip())
            self.assertTrue(spec.discover.strip())
            self.assertTrue(spec.execute.strip())
            self.assertTrue(spec.does_not_exist.strip())

    def test_eight_scenarios_unique_ids(self):
        ids = [s.scenario_id for s in A2_9_SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {f"S{i}" for i in range(1, 9)})


if __name__ == "__main__":
    unittest.main()
