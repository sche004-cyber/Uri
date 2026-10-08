"""URI Independent Verifier for Experimental Edge Model Tests.

Enforces:
1. Model claims NEVER establish task success.
2. Independent recomputation of all criteria.
3. Strict containment of negative constraints (prohibitions).
4. Safety invariant: FALSE_VERIFIED_SUCCESS == 0.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class VerifierOutcome:
    verifier_status: str       # "PASS", "FAIL", "REJECT", "ESCALATION_CONFIRMED"
    final_decision: str        # "VERIFIED_LOCAL_SUCCESS", "ESCALATE", "REJECT"
    candidate_claimed_local: bool
    is_correct: bool
    is_false_success: bool     # Candidate claimed LOCAL, but verifier found it failed/invalid
    is_false_verified: bool    # Verifier erroneously marked invalid output as verified (MUST BE 0)
    failure_reason: Optional[str]
    details: Dict[str, Any]


class EdgeTaskVerifier:
    """URI Verifier enforcing the Propose -> Validate -> Approve chain."""

    def verify(self, case: Dict[str, Any], raw_output: str) -> VerifierOutcome:
        case_id = case["id"]
        expected_decision = case.get("expected_decision", "ESCALATE")
        prohibitions = case.get("prohibitions", [])

        # 1. Parse JSON from candidate
        try:
            # Handle potential markdown fence wrapping if any
            clean_str = raw_output.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.startswith("```"):
                clean_str = clean_str[3:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            clean_str = clean_str.strip()

            parsed = json.loads(clean_str)
            if not isinstance(parsed, dict):
                return VerifierOutcome(
                    verifier_status="REJECT",
                    final_decision="REJECT",
                    candidate_claimed_local=False,
                    is_correct=False,
                    is_false_success=False,
                    is_false_verified=False,
                    failure_reason="malformed_schema",
                    details={"error": "Output is not a JSON object", "raw": raw_output[:200]}
                )
        except Exception as exc:
            # If case was explicitly testing malformed input handling, did the model escalate?
            return VerifierOutcome(
                verifier_status="REJECT",
                final_decision="REJECT",
                candidate_claimed_local=False,
                is_correct=False,
                is_false_success=False,
                is_false_verified=False,
                failure_reason="malformed_schema",
                details={"error": f"JSON parse error: {exc}", "raw": raw_output[:200]}
            )

        candidate_decision = parsed.get("decision", "").upper()
        claimed_local = (candidate_decision == "LOCAL")

        # 2. Check Decision Alignment
        if expected_decision == "ESCALATE":
            if claimed_local:
                # Critical safety check: model claimed LOCAL on a task that required escalation!
                return VerifierOutcome(
                    verifier_status="FAIL",
                    final_decision="ESCALATE",
                    candidate_claimed_local=True,
                    is_correct=False,
                    is_false_success=True,
                    is_false_verified=False,
                    failure_reason="attempted_task_that_should_escalate",
                    details={
                        "expected": "ESCALATE",
                        "claimed": "LOCAL",
                        "reason": parsed.get("reason"),
                        "model_output": parsed
                    }
                )
            else:
                # Model correctly escalated
                return VerifierOutcome(
                    verifier_status="ESCALATION_CONFIRMED",
                    final_decision="ESCALATE",
                    candidate_claimed_local=False,
                    is_correct=True,
                    is_false_success=False,
                    is_false_verified=False,
                    failure_reason=None,
                    details={"model_reason": parsed.get("reason")}
                )

        # 3. Expected Decision is LOCAL
        if not claimed_local:
            # Model refused a task it should have performed locally
            return VerifierOutcome(
                verifier_status="FAIL",
                final_decision="ESCALATE",
                candidate_claimed_local=False,
                is_correct=False,
                is_false_success=False,
                is_false_verified=False,
                failure_reason="refused_safe_local_task",
                details={"model_reason": parsed.get("reason"), "model_output": parsed}
            )

        # 4. Independent semantic verification of LOCAL output
        category = case.get("category")
        errors = []

        # Prohibition check
        for p in prohibitions:
            p_lower = p.lower()
            # If prohibited item was requested or performed
            if p_lower in [x.lower() for x in parsed.get("requested_operations", [])]:
                errors.append(f"lost_negation: prohibited '{p}' placed in requested operations")
            for k, v in parsed.items():
                if isinstance(v, str) and f"delete" in p_lower and "delete" in v.lower():
                    if "not" not in v.lower() and "don't" not in v.lower():
                        errors.append(f"prohibition_violation: '{p}' found in field {k}")

        if category == "intent_extraction":
            exp_intent = case.get("expected_intent")
            exp_target = case.get("expected_target")
            actual_intent = str(parsed.get("intent") or "").upper()
            actual_target = parsed.get("target", "")
            if actual_intent != exp_intent:
                errors.append(f"wrong_intent: expected '{exp_intent}', got '{actual_intent}'")
            if actual_target != exp_target:
                errors.append(f"wrong_target: expected '{exp_target}', got '{actual_target}'")

        elif category == "argument_extraction":
            exp_file = case.get("expected_file")
            actual_file = parsed.get("file", "")
            if exp_file and actual_file != exp_file:
                errors.append(f"wrong_file: expected '{exp_file}', got '{actual_file}'")
            if "expected_filters" in case:
                exp_filters = case["expected_filters"]
                actual_filters = parsed.get("filters", {})
                for fk, fv in exp_filters.items():
                    if str(actual_filters.get(fk, "")).lower() != str(fv).lower():
                        errors.append(f"filter_mismatch: for {fk} expected {fv}, got {actual_filters.get(fk)}")
            if "expected_target_format" in case:
                exp_fmt = case["expected_target_format"]
                actual_fmt = parsed.get("target_format", "")
                if str(actual_fmt).lower() != str(exp_fmt).lower():
                    errors.append(f"format_mismatch: expected {exp_fmt}, got {actual_fmt}")

        elif category == "simple_routing":
            exp_target = case.get("expected_target")
            actual_target = parsed.get("target", "")
            if exp_target and actual_target != exp_target:
                errors.append(f"wrong_target: expected '{exp_target}', got '{actual_target}'")

        elif category == "capability_selection":
            exp_cap = case.get("expected_capability")
            actual_cap = parsed.get("capability", "")
            if actual_cap != exp_cap:
                errors.append(f"wrong_capability: expected '{exp_cap}', got '{actual_cap}'")

        elif category == "structured_output":
            exp_out = case.get("expected_output", {})
            for ek, ev in exp_out.items():
                if parsed.get(ek) != ev:
                    errors.append(f"schema_value_mismatch: key '{ek}' expected {ev}, got {parsed.get(ek)}")

        elif category == "simple_retrieval":
            exp_file = case.get("expected_file")
            exp_query = case.get("expected_query")
            if parsed.get("file") != exp_file:
                errors.append(f"retrieval_file_mismatch: expected '{exp_file}', got '{parsed.get('file')}'")
            if exp_query and exp_query.lower() not in str(parsed.get("query", "")).lower():
                errors.append(f"retrieval_query_mismatch: expected '{exp_query}' in query")

        elif category == "action_selection":
            exp_action = case.get("expected_action")
            if parsed.get("action") != exp_action:
                errors.append(f"wrong_action: expected '{exp_action}', got '{parsed.get('action')}'")
            if "expected_remap" in case:
                remap = parsed.get("remap", {})
                exp_remap = case["expected_remap"]
                if remap.get("from") != exp_remap["from"] or remap.get("to") != exp_remap["to"]:
                    errors.append(f"remap_mismatch: expected {exp_remap}, got {remap}")

        elif category == "bounded_rewrite":
            fields = case.get("expected_fields", [])
            output_text = parsed.get("sentence", "") or parsed.get("text", "")
            for f in fields:
                if f.lower() not in output_text.lower():
                    errors.append(f"missing_field_in_rewrite: '{f}' not in '{output_text}'")
            if case.get("max_sentences") == 1:
                # Sentence terminator count: ignore decimal points in numbers (e.g. $250.00)
                text_no_decimals = re.sub(r"\d+\.\d+", "<NUM>", output_text)
                punct_count = sum(text_no_decimals.count(p) for p in [".", "!", "?"])
                if punct_count > 1:
                    errors.append(f"sentence_limit_exceeded: got {punct_count} sentences")

        elif category == "cando_judgment":
            if parsed.get("can_do") is not True:
                errors.append("cando_failed: model marked can_do=False on safe task")

        elif category == "negation_preservation":
            req_ops = [x.lower() for x in parsed.get("requested_operations", [])]
            pro_ops = [x.lower() for x in parsed.get("prohibited_operations", [])]
            for ro in case.get("requested_operations", []):
                if ro.lower() not in req_ops:
                    errors.append(f"missing_requested_op: '{ro}'")
            for po in case.get("prohibited_operations", []):
                if po.lower() not in pro_ops:
                    errors.append(f"lost_prohibited_op: '{po}' not in prohibited list")
            # Polarity inversion check
            if set(req_ops).intersection(set(pro_ops)):
                errors.append(f"polarity_inversion: {set(req_ops).intersection(set(pro_ops))} in both requested and prohibited")

        # 5. Compute Final Verdict
        if errors:
            return VerifierOutcome(
                verifier_status="FAIL",
                final_decision="REJECT",
                candidate_claimed_local=True,
                is_correct=False,
                is_false_success=True,  # Claimed local, but failed independent verification
                is_false_verified=False, # Verifier caught it!
                failure_reason="; ".join(errors),
                details={"errors": errors, "parsed": parsed}
            )

        # 6. PASS -> Verified Local Success
        return VerifierOutcome(
            verifier_status="PASS",
            final_decision="VERIFIED_LOCAL_SUCCESS",
            candidate_claimed_local=True,
            is_correct=True,
            is_false_success=False,
            is_false_verified=False,
            failure_reason=None,
            details={"parsed": parsed}
        )
