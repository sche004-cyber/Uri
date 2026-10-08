"""M35 URIv1 Batch A2.8C — Resolution-Path & Capability-Grounding Scoring Engine.

Executes and rigorously scores model responses across Mode A (Direct) and Mode B (Structured) for:
- Qwen3.5-2B
- Qwen3.5-9B
- LFM2.5-350M (optional lower-bound probe)

Measures all 13 primary dimensions defined in Batch A2.8C governance:
1. Problem Understanding Accuracy
2. Unresolved Requirement Accuracy
3. Resolution Path Sufficiency (RPS)
4. Capability Justification Accuracy (CJA)
5. Capability Selection Accuracy
6. Wrong Capability Rate
7. Unnecessary Capability Invocation Rate
8. Correct NO_TOOL Rate
9. Correct ASK_USER Rate
10. Correct STRATEGY_DISCOVERY_REQUIRED Rate
11. Guessing / Unsupported Assumption Rate
12. Hallucinated Capability Rate
13. Final Task-Path Success

And classifies root causes using the Section 15 Failure Taxonomy.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.arn.a2_8c_benchmark import ResolutionTestCase
from uri_v1.arn.a2_8c_prompts import (
    MODE_A_SCHEMA,
    MODE_A_SCHEMA_NAME,
    MODE_A_SYSTEM_PROMPT,
    MODE_B_SCHEMA,
    MODE_B_SCHEMA_NAME,
    MODE_B_SYSTEM_PROMPT,
    build_mode_a_prompt,
    build_mode_b_prompt,
    wrap_chatml_prompt,
)
from uri_v1.arn.resolution_contracts import (
    AvailableCapability,
    ResolutionRequirementStatus,
)


@dataclass(frozen=True)
class ResolutionExecutionMetric:
    """Telemetry for a single case execution."""

    mode: str  # "MODE_A_DIRECT" or "MODE_B_STRUCTURED"
    model_name: str
    case_id: str
    category: str
    total_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    calls_made: int
    raw_response: Dict[str, Any]
    scores: Dict[str, Any]
    failure_attribution: Optional[str] = None
    error: Optional[str] = None


def score_resolution_result(
    case: ResolutionTestCase,
    mode: str,
    parsed: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Evaluates a model output dictionary against ground truth across all 13 dimensions.

    Returns:
        (scores_dict, failure_attribution)
    """
    scores: Dict[str, Any] = {}
    failure: Optional[str] = None

    valid_caps = {c.value for c in AvailableCapability}

    # Extract chosen capability depending on mode
    if mode == "MODE_A_DIRECT":
        chosen_cap = str(parsed.get("selected_capability", "")).strip()
        justification = str(parsed.get("justification", "")).strip().lower()
        req_status = None
        req_desc = None
        path_exists = None
        step_desc = None
        cap_req = None
        goal = ""
    else:  # MODE_B_STRUCTURED
        goal = str(parsed.get("understood_goal", "")).strip().lower()
        unres = parsed.get("unresolved_requirement", {})
        req_status = str(unres.get("status", "")).strip() if isinstance(unres, dict) else None
        req_desc = str(unres.get("description", "")).strip().lower() if isinstance(unres, dict) else None
        res_path = parsed.get("resolution_path", {})
        path_exists = bool(res_path.get("path_exists", False)) if isinstance(res_path, dict) else None
        step_desc = str(res_path.get("step_description", "")).strip().lower() if isinstance(res_path, dict) else None
        cap_req = str(parsed.get("capability_requirement", "")).strip().lower()
        chosen_cap = str(parsed.get("matched_capability", "")).strip()
        justification = str(parsed.get("justification", "")).strip().lower()

    # 1. Problem Understanding Accuracy
    if mode == "MODE_B_STRUCTURED":
        exp_words = [w.lower() for w in case.expected_goal.split() if len(w) > 3]
        goal_ok = bool(goal) and (any(w in goal for w in exp_words) if exp_words else True)
    else:
        # In Mode A, infer goal alignment from justification
        exp_words = [w.lower() for w in case.expected_goal.split() if len(w) > 3]
        goal_ok = bool(justification) and (any(w in justification for w in exp_words) if exp_words else True)
    scores["problem_understanding_accuracy"] = goal_ok

    # 2. Unresolved Requirement Accuracy
    if mode == "MODE_B_STRUCTURED":
        status_match = (req_status == case.expected_requirement_status.value)
        # Check semantic alignment in description
        exp_desc_words = [w.lower() for w in case.expected_requirement_desc.split() if len(w) > 4]
        desc_ok = bool(req_desc) and (any(w in req_desc for w in exp_desc_words) if exp_desc_words else True)
        unres_ok = status_match and desc_ok
    else:
        # In Mode A, direct selection doesn't isolate requirement, but if correct capability chosen, credit partial
        unres_ok = (chosen_cap == case.expected_matched_capability.value)
    scores["unresolved_requirement_accuracy"] = unres_ok

    # 3. Resolution Path Sufficiency (RPS)
    # «Given the information available, would the proposed path actually be capable of resolving the requirement?»
    if mode == "MODE_B_STRUCTURED":
        path_exists_match = (path_exists == case.expected_path_exists)
        exp_step_words = [w.lower() for w in case.expected_resolution_step.split() if len(w) > 4]
        step_ok = bool(step_desc) and (any(w in step_desc for w in exp_step_words) if exp_step_words else True)
        rps = path_exists_match and step_ok
    else:
        # In Mode A, if chosen capability points to a viable path
        rps = (chosen_cap == case.expected_matched_capability.value)
    scores["resolution_path_sufficiency"] = rps

    # 4. Capability Justification Accuracy (CJA)
    # «Does the selected capability actually satisfy the specific requirement rather than surface words?»
    distractor_words = [case.surface_distractor.value.lower()] if case.surface_distractor else []
    justification_grounded = bool(justification) and not any(f"because {dw}" in justification for dw in distractor_words)
    cja = justification_grounded and (chosen_cap == case.expected_matched_capability.value)
    scores["capability_justification_accuracy"] = cja

    # 5. Capability Selection Accuracy
    cap_ok = (chosen_cap == case.expected_matched_capability.value)
    scores["capability_selection_accuracy"] = cap_ok

    # 6. Wrong Capability Rate
    is_wrong_cap = (chosen_cap != case.expected_matched_capability.value) and (chosen_cap in valid_caps)
    scores["wrong_capability"] = is_wrong_cap

    # 7. Unnecessary Capability Invocation Rate
    # External capability called when NO_TOOL was expected
    is_unnecessary = (case.expected_matched_capability == AvailableCapability.NO_TOOL) and (chosen_cap != AvailableCapability.NO_TOOL.value)
    scores["unnecessary_capability_invocation"] = is_unnecessary

    # 8. Correct NO_TOOL Rate
    if case.expected_matched_capability == AvailableCapability.NO_TOOL:
        scores["correct_no_tool"] = (chosen_cap == AvailableCapability.NO_TOOL.value)
    else:
        scores["correct_no_tool"] = None

    # 9. Correct ASK_USER Rate
    if case.expected_matched_capability == AvailableCapability.ASK_USER:
        scores["correct_ask_user"] = (chosen_cap == AvailableCapability.ASK_USER.value)
    else:
        scores["correct_ask_user"] = None

    # 10. Correct STRATEGY_DISCOVERY_REQUIRED Rate
    if case.expected_matched_capability == AvailableCapability.STRATEGY_DISCOVERY_REQUIRED:
        scores["correct_strategy_discovery"] = (chosen_cap == AvailableCapability.STRATEGY_DISCOVERY_REQUIRED.value)
    else:
        scores["correct_strategy_discovery"] = None

    # 11. Guessing / Unsupported Assumption Rate
    # Model chose an execution tool without resolving missing precondition or ambiguous referent
    is_guessing = False
    if case.category in ("ASK_USER", "STRATEGY_DISCOVERY") and chosen_cap not in (AvailableCapability.ASK_USER.value, AvailableCapability.STRATEGY_DISCOVERY_REQUIRED.value):
        is_guessing = True
    elif case.category == "GROUNDED_PRECONDITION" and chosen_cap == case.surface_distractor.value:
        is_guessing = True
    scores["guessing_unsupported_assumption"] = is_guessing

    # 12. Hallucinated Capability Rate
    is_hallucinated = bool(chosen_cap) and (chosen_cap not in valid_caps)
    scores["hallucinated_capability"] = is_hallucinated

    # 13. Final Task-Path Success
    # Viable, non-destructive path to goal without guessing or wrong capability
    final_success = cap_ok and goal_ok and not is_guessing and not is_hallucinated
    scores["final_task_path_success"] = final_success

    # Failure Attribution Classification
    if not final_success:
        if is_hallucinated:
            failure = "HALLUCINATED_CAPABILITY"
        elif not goal_ok:
            failure = "PROBLEM_MISUNDERSTOOD"
        elif case.category == "NO_TOOL" and is_unnecessary:
            failure = "UNNECESSARY_CAPABILITY"
        elif case.category == "ASK_USER" and chosen_cap != AvailableCapability.ASK_USER.value:
            failure = "FAILED_TO_ASK_USER"
        elif case.category == "STRATEGY_DISCOVERY" and chosen_cap != AvailableCapability.STRATEGY_DISCOVERY_REQUIRED.value:
            failure = "FAILED_STRATEGY_DISCOVERY"
        elif case.surface_distractor and chosen_cap == case.surface_distractor.value:
            if case.category == "GROUNDED_PRECONDITION":
                failure = "PREMATURE_ACTION_UNGROUNDED_PRECONDITION"
            else:
                failure = "SURFACE_LANGUAGE_TRAP"
        elif mode == "MODE_B_STRUCTURED" and not unres_ok:
            failure = "UNRESOLVED_REQUIREMENT_INCORRECT"
        elif mode == "MODE_B_STRUCTURED" and not rps:
            failure = "RESOLUTION_PATH_INCORRECT"
        elif is_wrong_cap:
            failure = "CORRECT_PATH_WRONG_CAPABILITY_MATCH"
        else:
            failure = "MODEL_SEMANTIC_FAILURE"

    return scores, failure


def call_capability_endpoint(
    endpoint: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: Dict[str, Any],
    is_qwen: bool = True,
    timeout: float = 30.0,
) -> Tuple[Dict[str, Any], int, int, float, Optional[str]]:
    """Invokes LM Studio model endpoint with JSON schema constraint and returns parsed dict + usage."""
    t0 = time.perf_counter()

    if is_qwen:
        chatml = wrap_chatml_prompt(system_prompt, user_prompt)
        payload = {
            "model": model_name,
            "prompt": chatml,
            "temperature": 0.0,
            "max_tokens": 800,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        url = endpoint if "/completions" in endpoint else f"{endpoint.rstrip('/')}/completions"
    else:
        # LFM models use /chat/completions
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 800,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        url = endpoint if "/chat/completions" in endpoint else f"{endpoint.rstrip('/')}/chat/completions"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        lat_ms = (time.perf_counter() - t0) * 1000.0

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        comp_tokens = usage.get("completion_tokens", 0)

        choice = data.get("choices", [{}])[0]
        if is_qwen:
            raw_text = choice.get("text", "{}").strip()
        else:
            raw_text = choice.get("message", {}).get("content", "{}").strip()

        parsed = json.loads(raw_text)
        return parsed, prompt_tokens, comp_tokens, lat_ms, None
    except Exception as e:
        lat_ms = (time.perf_counter() - t0) * 1000.0
        return {}, 0, 0, lat_ms, str(e)


class ResolutionEvaluator:
    """Orchestrates Mode A (Direct) and Mode B (Structured) evaluations across models."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:1234/v1",
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def evaluate_case_mode_a(
        self,
        model_name: str,
        case: ResolutionTestCase,
        is_qwen: bool = True,
    ) -> ResolutionExecutionMetric:
        """Mode A: Direct Capability Selection."""
        prompt = build_mode_a_prompt(case.user_text, case.active_context)
        parsed, p_tok, c_tok, lat, err = call_capability_endpoint(
            endpoint=self.endpoint,
            model_name=model_name,
            system_prompt=MODE_A_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema_name=MODE_A_SCHEMA_NAME,
            schema=MODE_A_SCHEMA,
            is_qwen=is_qwen,
            timeout=self.timeout,
        )
        if not err:
            scores, failure = score_resolution_result(case, "MODE_A_DIRECT", parsed)
        else:
            scores = {"final_task_path_success": False, "capability_selection_accuracy": False, "error": err}
            failure = "API_ERROR"

        return ResolutionExecutionMetric(
            mode="MODE_A_DIRECT",
            model_name=model_name,
            case_id=case.case_id,
            category=case.category,
            total_latency_ms=lat,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            calls_made=1,
            raw_response=parsed,
            scores=scores,
            failure_attribution=failure,
            error=err,
        )

    def evaluate_case_mode_b(
        self,
        model_name: str,
        case: ResolutionTestCase,
        is_qwen: bool = True,
    ) -> ResolutionExecutionMetric:
        """Mode B: Structured Resolution Path."""
        prompt = build_mode_b_prompt(case.user_text, case.active_context)
        parsed, p_tok, c_tok, lat, err = call_capability_endpoint(
            endpoint=self.endpoint,
            model_name=model_name,
            system_prompt=MODE_B_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema_name=MODE_B_SCHEMA_NAME,
            schema=MODE_B_SCHEMA,
            is_qwen=is_qwen,
            timeout=self.timeout,
        )
        if not err:
            scores, failure = score_resolution_result(case, "MODE_B_STRUCTURED", parsed)
        else:
            scores = {"final_task_path_success": False, "capability_selection_accuracy": False, "error": err}
            failure = "API_ERROR"

        return ResolutionExecutionMetric(
            mode="MODE_B_STRUCTURED",
            model_name=model_name,
            case_id=case.case_id,
            category=case.category,
            total_latency_ms=lat,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            calls_made=1,
            raw_response=parsed,
            scores=scores,
            failure_attribution=failure,
            error=err,
        )
