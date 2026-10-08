"""Unit Tests for M35 URIv1 Batch A2.8C — Resolution-Path Discovery & Capability-Grounding.

Verifies:
1. Benchmark suite integrity & category coverage (16 frozen cases).
2. Mode A and Mode B prompt construction and isolation.
3. Strict JSON schema definitions and constraints.
4. Scoring engine fidelity: NO_TOOL detection, unnecessary invocation, surface traps,
   premature action detection, ASK_USER detection, and STRATEGY_DISCOVERY handling.
"""

from __future__ import annotations

import unittest
from typing import Any, Dict

from uri_v1.arn.a2_8c_benchmark import A2_8C_BENCHMARK_CASES, ResolutionTestCase
from uri_v1.arn.a2_8c_evaluator import score_resolution_result
from uri_v1.arn.a2_8c_prompts import (
    MODE_A_SCHEMA,
    MODE_B_SCHEMA,
    build_mode_a_prompt,
    build_mode_b_prompt,
    format_capability_catalog,
)
from uri_v1.arn.resolution_contracts import (
    CAPABILITY_DESCRIPTIONS,
    AvailableCapability,
    ResolutionRequirementStatus,
)


class TestBatchA28CResolutionSuite(unittest.TestCase):
    """Rigorous verification of Batch A2.8C contracts, prompts, schemas, and scoring."""

    def test_benchmark_suite_integrity(self) -> None:
        """Verifies that all 16 frozen benchmark cases are complete and valid."""
        self.assertEqual(len(A2_8C_BENCHMARK_CASES), 16)
        categories = {c.category for c in A2_8C_BENCHMARK_CASES}
        self.assertEqual(
            categories,
            {"SURFACE_TRAP", "NO_TOOL", "ASK_USER", "STRATEGY_DISCOVERY", "GROUNDED_PRECONDITION"},
        )

        for case in A2_8C_BENCHMARK_CASES:
            self.assertTrue(case.case_id.startswith(("TRAP-", "NOTOOL-", "ASKUSER-", "STRAT-", "PRECOND-")))
            self.assertTrue(len(case.user_text) > 10)
            self.assertTrue(len(case.expected_goal) > 5)
            self.assertIsInstance(case.expected_requirement_status, ResolutionRequirementStatus)
            self.assertIsInstance(case.expected_matched_capability, AvailableCapability)
            self.assertTrue(len(case.expected_resolution_step) > 5)

    def test_prompt_formatting_and_catalog(self) -> None:
        """Verifies that capability catalog and prompt builders output expected structures."""
        catalog = format_capability_catalog()
        for cap in AvailableCapability:
            self.assertIn(cap.value, catalog)

        case = A2_8C_BENCHMARK_CASES[0]
        prompt_a = build_mode_a_prompt(case.user_text, case.active_context)
        self.assertIn("[User Request]", prompt_a)
        self.assertIn(case.user_text, prompt_a)
        self.assertIn("[Active Context & Working State]", prompt_a)
        self.assertIn("Available Capabilities and Meta-Actions:", prompt_a)

        prompt_b = build_mode_b_prompt(case.user_text, case.active_context)
        self.assertIn("Execute Structured Resolution", prompt_b)
        self.assertIn("unresolved requirement", prompt_b)
        self.assertIn("resolution path", prompt_b)

    def test_strict_schemas(self) -> None:
        """Verifies that Mode A and Mode B schemas conform to strict constraints."""
        self.assertEqual(MODE_A_SCHEMA["type"], "object")
        self.assertFalse(MODE_A_SCHEMA["additionalProperties"])
        self.assertIn("selected_capability", MODE_A_SCHEMA["required"])
        self.assertIn("justification", MODE_A_SCHEMA["required"])

        self.assertEqual(MODE_B_SCHEMA["type"], "object")
        self.assertFalse(MODE_B_SCHEMA["additionalProperties"])
        self.assertIn("understood_goal", MODE_B_SCHEMA["required"])
        self.assertIn("unresolved_requirement", MODE_B_SCHEMA["required"])
        self.assertIn("resolution_path", MODE_B_SCHEMA["required"])
        self.assertIn("capability_requirement", MODE_B_SCHEMA["required"])
        self.assertIn("matched_capability", MODE_B_SCHEMA["required"])

    def test_scoring_no_tool_success_and_unnecessary_invocation(self) -> None:
        """Tests scoring on NO_TOOL cases (NOTOOL-01: arithmetic)."""
        case = next(c for c in A2_8C_BENCHMARK_CASES if c.case_id == "NOTOOL-01")

        # 1. Correct NO_TOOL response in Mode B
        correct_parsed = {
            "understood_goal": "Calculate 18% tax on the approved $5000 budget",
            "unresolved_requirement": {
                "status": "ALREADY_GROUNDED",
                "description": "The budget is already known in active context; no data is missing.",
            },
            "resolution_path": {
                "path_exists": True,
                "step_description": "Compute 5000 * 0.18 deterministically in memory.",
            },
            "capability_requirement": "Deterministic arithmetic computation",
            "matched_capability": "NO_TOOL",
            "justification": "All required numbers are grounded in active memory; math requires no external tool.",
        }
        scores, failure = score_resolution_result(case, "MODE_B_STRUCTURED", correct_parsed)
        self.assertTrue(scores["final_task_path_success"])
        self.assertTrue(scores["capability_selection_accuracy"])
        self.assertTrue(scores["correct_no_tool"])
        self.assertFalse(scores["unnecessary_capability_invocation"])
        self.assertIsNone(failure)

        # 2. Unnecessary invocation in Mode A (calling python_repl)
        unnecessary_parsed = {
            "selected_capability": "python_repl",
            "justification": "Need to run python to calculate tax",
        }
        scores, failure = score_resolution_result(case, "MODE_A_DIRECT", unnecessary_parsed)
        self.assertFalse(scores["final_task_path_success"])
        self.assertFalse(scores["capability_selection_accuracy"])
        self.assertTrue(scores["unnecessary_capability_invocation"])
        self.assertEqual(failure, "UNNECESSARY_CAPABILITY")

    def test_scoring_surface_trap_detection(self) -> None:
        """Tests detection when a model falls into a surface-language distractor trap (TRAP-01)."""
        case = next(c for c in A2_8C_BENCHMARK_CASES if c.case_id == "TRAP-01")

        # Model falls into surface trap: web_search
        trap_parsed = {
            "selected_capability": "web_search",
            "justification": "Search the web for Dean's latest requests",
        }
        scores, failure = score_resolution_result(case, "MODE_A_DIRECT", trap_parsed)
        self.assertFalse(scores["final_task_path_success"])
        self.assertFalse(scores["capability_selection_accuracy"])
        self.assertTrue(scores["wrong_capability"])
        self.assertEqual(failure, "SURFACE_LANGUAGE_TRAP")

        # Correct private mailbox selection in Mode B
        correct_b = {
            "understood_goal": "Find what changes the Dean requested in his latest email",
            "unresolved_requirement": {
                "status": "RESOLVABLE_VIA_PATH",
                "description": "Need the recent private email from Dean Harrison",
            },
            "resolution_path": {
                "path_exists": True,
                "step_description": "Search and read authorized mailbox for Dean Harrison",
            },
            "capability_requirement": "Search private authorized email",
            "matched_capability": "email_search_read",
            "justification": "The request concerns a private email from an internal contact, requiring email search.",
        }
        scores_b, failure_b = score_resolution_result(case, "MODE_B_STRUCTURED", correct_b)
        self.assertTrue(scores_b["final_task_path_success"])
        self.assertTrue(scores_b["capability_selection_accuracy"])
        self.assertIsNone(failure_b)

    def test_scoring_premature_action_detection(self) -> None:
        """Tests detection when a model attempts premature execution on ungrounded precondition (PRECOND-01)."""
        case = next(c for c in A2_8C_BENCHMARK_CASES if c.case_id == "PRECOND-01")

        # Premature order submission without verifying approval
        premature_parsed = {
            "selected_capability": "order_submission_system",
            "justification": "Submit the purchase order directly to ERP",
        }
        scores, failure = score_resolution_result(case, "MODE_A_DIRECT", premature_parsed)
        self.assertFalse(scores["final_task_path_success"])
        self.assertTrue(scores["guessing_unsupported_assumption"])
        self.assertEqual(failure, "PREMATURE_ACTION_UNGROUNDED_PRECONDITION")

    def test_scoring_ask_user_detection(self) -> None:
        """Tests detection on genuine ambiguity (ASKUSER-01)."""
        case = next(c for c in A2_8C_BENCHMARK_CASES if c.case_id == "ASKUSER-01")

        # Arbitrary guess
        guess_parsed = {
            "selected_capability": "email_search_read",
            "justification": "Forward to John Davis",
        }
        scores, failure = score_resolution_result(case, "MODE_A_DIRECT", guess_parsed)
        self.assertFalse(scores["final_task_path_success"])
        self.assertTrue(scores["guessing_unsupported_assumption"])
        self.assertEqual(failure, "FAILED_TO_ASK_USER")

        # Correct ASK_USER in Mode B
        correct_ask = {
            "understood_goal": "Forward the milestone brief to John",
            "unresolved_requirement": {
                "status": "UNRESOLVABLE_AMBIGUITY",
                "description": "Multiple Johns exist in contacts with no disambiguating evidence.",
            },
            "resolution_path": {
                "path_exists": False,
                "step_description": "Ask the user which John is the intended recipient.",
            },
            "capability_requirement": "User clarification and disambiguation",
            "matched_capability": "ASK_USER",
            "justification": "Referent is ambiguous; must not guess without user clarification.",
        }
        scores_ask, failure_ask = score_resolution_result(case, "MODE_B_STRUCTURED", correct_ask)
        self.assertTrue(scores_ask["final_task_path_success"])
        self.assertTrue(scores_ask["correct_ask_user"])
        self.assertIsNone(failure_ask)

    def test_scoring_strategy_discovery_detection(self) -> None:
        """Tests detection when a novel method is needed (STRAT-01)."""
        case = next(c for c in A2_8C_BENCHMARK_CASES if c.case_id == "STRAT-01")

        # Incorrect tool invocation
        wrong_tool_parsed = {
            "selected_capability": "web_search",
            "justification": "Search the web for heuristic ideas",
        }
        scores, failure = score_resolution_result(case, "MODE_A_DIRECT", wrong_tool_parsed)
        self.assertFalse(scores["final_task_path_success"])
        self.assertEqual(failure, "FAILED_STRATEGY_DISCOVERY")

        # Correct STRATEGY_DISCOVERY_REQUIRED in Mode B
        correct_strat = {
            "understood_goal": "Develop a better heuristic for ambiguous precedent selection",
            "unresolved_requirement": {
                "status": "UNQUALIFIED_STRATEGY",
                "description": "No qualified automated tool or predetermined execution path exists.",
            },
            "resolution_path": {
                "path_exists": False,
                "step_description": "Initiate strategy discovery workflow to formulate and sandbox new heuristic.",
            },
            "capability_requirement": "Exploratory strategy formulation protocol",
            "matched_capability": "STRATEGY_DISCOVERY_REQUIRED",
            "justification": "This is a novel algorithmic requirement with no existing qualified tool.",
        }
        scores_strat, failure_strat = score_resolution_result(case, "MODE_B_STRUCTURED", correct_strat)
        self.assertTrue(scores_strat["final_task_path_success"])
        self.assertTrue(scores_strat["correct_strategy_discovery"])
        self.assertIsNone(failure_strat)


if __name__ == "__main__":
    unittest.main()
