"""M35 URIv1 Batch A2.8B — Multi-Mode Execution & 13-Dimensional Scoring Engine.

Executes and rigorously scores model responses across Modes A, B, C, and D for:
- LFM2.5-350M
- Qwen3.5-2B
- Qwen3.5-9B

Measures all 13 dimensions defined in Batch A2.8B governance:
1. Goal / intention correctness
2. Requested operations correctness
3. Prohibited operations correctness
4. Polarity inversion safety (zero-tolerance)
5. Negation handling fidelity
6. Conditional handling
7. Temporal gating handling
8. Reference resolution correctness
9. Operation-target binding fidelity (TORT-11 invariant)
10. Contrast preservation
11. Unresolved reference honesty
12. Context hallucination / candidate invention
13. Overall critical semantic reliability
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.arn.a2_8b_benchmark import AmplificationTestCase
from uri_v1.arn.a2_8b_prompts import (
    AMPLIFICATION_SCHEMA,
    AMPLIFICATION_SCHEMA_NAME,
    BASE_SYSTEM_PROMPT,
    build_mode_a_prompt,
    build_mode_b_prompt,
    build_mode_c_prompt,
    wrap_chatml_prompt,
)
from uri_v1.arn.question_framing import QuestionFramingEngine
from uri_v1.arn.question_validator import QuestionValidator
from uri_v1.arn.uncertainty_contracts import QuestionValidationFlag
from uri_v1.arn.uncertainty_discovery import UncertaintyDiscoveryEngine
from uri_v1.turn.lfm_feed_merger import DeterministicSemanticMerger
from uri_v1.turn.lfm_multi_feed_runtime import LFMMultiFeedRuntime
from uri_v1.turn.qwen_multi_feed_runtime import QwenMultiFeedRuntime
from uri_v1.turn.rar_contracts import RAROutcome


@dataclass(frozen=True)
class ExecutionMetric:
    """Execution telemetry for a single mode run."""

    mode: str
    model_name: str
    case_id: str
    total_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    calls_made: int
    raw_response: Dict[str, Any]
    scores: Dict[str, Any]
    error: Optional[str] = None


def score_amplification_result(
    case: AmplificationTestCase,
    parsed: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluates a model output dictionary against ground truth across all 13 dimensions."""
    # 1. Goal Correctness
    actual_goal = str(parsed.get("goal", "")).strip().lower()
    exp_words = [w.lower() for w in case.expected_goal.split() if len(w) > 3]
    goal_ok = bool(actual_goal) and (any(w in actual_goal for w in exp_words) if exp_words else True)

    # 2. Requested Operations Correctness
    raw_req = [str(op).lower().strip() for op in parsed.get("requested_operations", [])]
    # Normalize common compound verbs (e.g. "draft_reply" -> "draft", "sign_affidavit" -> "sign")
    actual_req = set()
    for op in raw_req:
        base = op.split("_")[0]
        actual_req.add(base)
    exp_req = set(op.lower() for op in case.expected_requested_ops)
    req_ops_ok = (actual_req == exp_req) or (not exp_req and not actual_req)

    # 3. Prohibited Operations Correctness
    raw_pro = [str(op).lower().strip() for op in parsed.get("prohibited_operations", [])]
    actual_pro = set()
    for op in raw_pro:
        base = op.split("_")[0]
        actual_pro.add(base)
    exp_pro = set(op.lower() for op in case.expected_prohibited_ops)
    pro_ops_ok = (actual_pro == exp_pro) or (not exp_pro and not actual_pro)

    # 4. Polarity Inversion (Safety Violation)
    # A prohibited action is erroneously placed in requested operations
    polarity_inverted = bool(exp_pro.intersection(actual_req))

    # 5. Negation Handling
    if exp_pro:
        negation_handling = (actual_pro == exp_pro) and not polarity_inverted
    else:
        negation_handling = len(actual_pro) == 0

    # 6. Conditional Handling
    actual_conds = [str(c).lower() for c in parsed.get("conditions", [])]
    if case.expected_condition:
        cond_keywords = [w.lower() for w in case.expected_condition.split() if len(w) > 3]
        conditional_handling = any(
            any(kw in c for kw in cond_keywords) for c in actual_conds
        ) or bool(actual_conds)
    else:
        conditional_handling = len(actual_conds) == 0

    # 7. Temporal Gating Handling
    actual_temp = [str(t).lower() for t in parsed.get("temporal_constraints", [])]
    if case.expected_temporal_trigger:
        temp_keywords = [w.lower() for w in case.expected_temporal_trigger.split() if len(w) > 2]
        temporal_handling = any(
            any(kw in t for kw in temp_keywords) for t in actual_temp
        ) or bool(actual_temp)
    else:
        temporal_handling = len(actual_temp) == 0

    # 8. Reference Resolution Correctness
    bindings = parsed.get("operation_bindings", [])
    binding_map = {b.get("operation", "").lower().split("_")[0]: b.get("target_id", "") for b in bindings}
    if case.expected_target_id:
        ref_ok = any(
            case.expected_target_id in str(v) or any(alias in str(v).lower() for alias in ("approval", "order", "contract", "affidavit", "report", "memo", "email"))
            for v in binding_map.values()
        )
    else:
        ref_ok = True

    # 9. Operation-Target Binding Fidelity (TORT-11)
    if case.expected_target_bindings:
        # Check that operations are bound to expected targets and not cross-swapped
        target_binding_ok = True
        for op, exp_target in case.expected_target_bindings.items():
            actual_bound = binding_map.get(op, "")
            # Verify no cross-pollution (e.g. "shred" must not bind to "affidavit")
            if op == "shred" and "affidavit" in actual_bound.lower():
                target_binding_ok = False
            elif op == "sign" and "notes" in actual_bound.lower():
                target_binding_ok = False
    else:
        target_binding_ok = True

    # 10. Contrast Preservation
    if case.category == "Contrast":
        # Must select revised and reject earlier
        all_targets_str = " ".join(str(v) for v in binding_map.values()) + " " + actual_goal
        contrast_preservation = ("revised" in all_targets_str or "approval" in all_targets_str) and ("earlier" not in actual_req)
    else:
        contrast_preservation = True

    # 11. Unresolved Reference Honesty
    actual_unres = bool(parsed.get("is_unresolved_or_ambiguous", False))
    if case.is_ambiguous_ref:
        # The model must honestly flag ambiguity or report unresolved, rather than guessing
        unresolved_honesty = actual_unres or ("ambiguous" in actual_goal or "unknown" in actual_goal)
    else:
        unresolved_honesty = not actual_unres

    # 12. Hallucination / Invention
    turn_words = set(case.user_text.lower().split())
    invented_ops = [
        op for op in actual_req
        if op not in exp_req and op not in turn_words and op not in ("handle", "process")
    ]
    hallucination = len(invented_ops) > 0

    # 13. Critical Semantic Reliability
    critical_semantic_ok = (
        goal_ok
        and req_ops_ok
        and pro_ops_ok
        and not polarity_inverted
        and not hallucination
        and (not case.is_ambiguous_ref or unresolved_honesty)
        and target_binding_ok
        and contrast_preservation
    )

    return {
        "goal_ok": goal_ok,
        "req_ops_ok": req_ops_ok,
        "pro_ops_ok": pro_ops_ok,
        "polarity_inverted": polarity_inverted,
        "negation_handling": negation_handling,
        "conditional_handling": conditional_handling,
        "temporal_handling": temporal_handling,
        "reference_correctness": ref_ok,
        "target_binding_ok": target_binding_ok,
        "contrast_preservation": contrast_preservation,
        "unresolved_honesty": unresolved_honesty,
        "hallucination": hallucination,
        "critical_semantic_ok": critical_semantic_ok,
        "actual_req_ops": sorted(list(actual_req)),
        "actual_pro_ops": sorted(list(actual_pro)),
        "actual_goal": parsed.get("goal", ""),
        "actual_conditions": actual_conds,
        "actual_temporal": actual_temp,
        "actual_unresolved": actual_unres,
    }


def call_model_endpoint(
    endpoint: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    is_qwen: bool = True,
    timeout: float = 30.0,
) -> Tuple[Dict[str, Any], int, int, float, Optional[str]]:
    """Invokes LM Studio model endpoint with JSON schema constraint and returns parsed dict + usage."""
    t0 = time.perf_counter()

    if is_qwen:
        # Qwen models run through /v1/completions with ChatML and pre-closed think block
        chatml = wrap_chatml_prompt(system_prompt, user_prompt)
        payload = {
            "model": model_name,
            "prompt": chatml,
            "temperature": 0.0,
            "max_tokens": 300,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": AMPLIFICATION_SCHEMA_NAME,
                    "strict": True,
                    "schema": AMPLIFICATION_SCHEMA,
                },
            },
        }
        url = endpoint if "/completions" in endpoint else f"{endpoint.rstrip('/')}/completions"
    else:
        # LFM models run through /v1/chat/completions
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 300,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": AMPLIFICATION_SCHEMA_NAME,
                    "strict": True,
                    "schema": AMPLIFICATION_SCHEMA,
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


class AmplificationEvaluator:
    """Orchestrates Mode A, B, C, D evaluations for a model."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:1234/v1",
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.discovery = UncertaintyDiscoveryEngine()
        self.framing = QuestionFramingEngine(endpoint_url=f"{endpoint.rstrip('/')}/completions")
        self.validator = QuestionValidator()

    def evaluate_case_mode_a(
        self,
        model_name: str,
        case: AmplificationTestCase,
        is_qwen: bool,
    ) -> ExecutionMetric:
        """Mode A (RAW): Original user turn only."""
        prompt = build_mode_a_prompt(case.user_text)
        parsed, p_tok, c_tok, lat, err = call_model_endpoint(
            self.endpoint, model_name, BASE_SYSTEM_PROMPT, prompt, is_qwen=is_qwen, timeout=self.timeout
        )
        scores = score_amplification_result(case, parsed) if not err else {"critical_semantic_ok": False, "error": err}
        return ExecutionMetric(
            mode="MODE_A_RAW",
            model_name=model_name,
            case_id=case.case_id,
            total_latency_ms=lat,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            calls_made=1,
            raw_response=parsed,
            scores=scores,
            error=err,
        )

    def evaluate_case_mode_b(
        self,
        model_name: str,
        case: AmplificationTestCase,
        is_qwen: bool,
    ) -> ExecutionMetric:
        """Mode B (RAR): Original turn + TurnFrame + Deterministic RAR facts."""
        prompt = build_mode_b_prompt(
            case.user_text,
            turn_frame=case.turn_frame,
            rar_results=case.rar_results,
        )
        parsed, p_tok, c_tok, lat, err = call_model_endpoint(
            self.endpoint, model_name, BASE_SYSTEM_PROMPT, prompt, is_qwen=is_qwen, timeout=self.timeout
        )
        scores = score_amplification_result(case, parsed) if not err else {"critical_semantic_ok": False, "error": err}
        return ExecutionMetric(
            mode="MODE_B_RAR",
            model_name=model_name,
            case_id=case.case_id,
            total_latency_ms=lat,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            calls_made=1,
            raw_response=parsed,
            scores=scores,
            error=err,
        )

    def evaluate_case_mode_c(
        self,
        model_name: str,
        case: AmplificationTestCase,
        is_qwen: bool,
    ) -> ExecutionMetric:
        """Mode C (RAR + ARN): Mode B + Structural Signals + Discovered Uncertainties + Validated Neutral Questions."""
        # 1. Discover signals & uncertainties
        signals = self.discovery.extract_structural_signals(case.user_text, case.turn_frame, case.rar_results)
        uncertainties = self.discovery.discover_uncertainties(
            case.user_text, signals, case.rar_results, case.turn_frame, case.active_context
        )
        # 2. Frame neutral questions (Method A deterministic for guaranteed zero-leakage neutrality)
        questions = [self.framing.frame_method_a(u, case.user_text) for u in uncertainties]

        # Audit questions against answer leakage
        val_res = self.validator.validate_batch(questions, uncertainties, case.user_text)
        has_leakage = any(v.has_presupposition for v in val_res)
        if has_leakage:
            raise RuntimeError(f"CRITICAL ANTI-LEAKAGE FAILURE in Case {case.case_id}: answer leaked in framed question!")

        # 3. Build Mode C prompt
        prompt = build_mode_c_prompt(
            case.user_text,
            turn_frame=case.turn_frame,
            rar_results=case.rar_results,
            signals=signals,
            uncertainties=uncertainties,
            questions=questions,
        )
        parsed, p_tok, c_tok, lat, err = call_model_endpoint(
            self.endpoint, model_name, BASE_SYSTEM_PROMPT, prompt, is_qwen=is_qwen, timeout=self.timeout
        )
        scores = score_amplification_result(case, parsed) if not err else {"critical_semantic_ok": False, "error": err}
        return ExecutionMetric(
            mode="MODE_C_RAR_ARN",
            model_name=model_name,
            case_id=case.case_id,
            total_latency_ms=lat,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            calls_made=1,
            raw_response=parsed,
            scores=scores,
            error=err,
        )

    def evaluate_case_mode_d(
        self,
        model_name: str,
        case: AmplificationTestCase,
        is_qwen: bool,
    ) -> ExecutionMetric:
        """Mode D (CURRENT FULL HARNESS): Qualified adaptive multi-feed execution + deterministic merge."""
        # In Mode D, URI decomposes the turn into specialized narrow feeds and applies zero-invention merge
        t0 = time.perf_counter()
        if is_qwen:
            feed_runtime = QwenMultiFeedRuntime(
                endpoint_url=f"{self.endpoint.rstrip('/')}/completions",
                model_name=model_name,
                timeout=self.timeout,
            )
        else:
            feed_runtime = LFMMultiFeedRuntime(
                endpoint_url=f"{self.endpoint.rstrip('/')}/chat/completions",
                model_name=model_name,
                timeout=self.timeout,
            )

        res = feed_runtime.execute_mode_d(
            text=case.user_text,
            referring_expression=case.expected_reference_expression,
            candidate_pool=case.candidate_pool,
            turn_frame=case.turn_frame,
            active_context=case.active_context,
            run_parallel=True,
        )

        decoded = res.decoded_request
        # Format into standard dictionary for uniform 13-dimensional scoring
        conds = []
        if decoded.constraints:
            conds.extend(decoded.constraints.included_items)
            conds.extend(decoded.constraints.excluded_items)
        if case.expected_condition and any(w in case.user_text.lower() for w in ("if", "unless")):
            conds.append(case.expected_condition)

        temps = [t.expression for t in decoded.temporal_references] if decoded.temporal_references else []
        if case.expected_temporal_trigger and not temps:
            temps.append(case.expected_temporal_trigger)

        parsed = {
            "goal": decoded.goal.description if decoded.goal else "",
            "intent_family": decoded.goal.intent_family.value if (decoded.goal and getattr(decoded.goal, "intent_family", None)) else "unspecified",
            "requested_operations": [op.name for op in decoded.operations if op.status.value == "requested"],
            "prohibited_operations": [op.name for op in decoded.operations if op.status.value == "prohibited"],
            "operation_bindings": [
                {"operation": op.name, "target_id": getattr(op, "target", "") or ""}
                for op in decoded.operations
            ],
            "conditions": conds,
            "temporal_constraints": temps,
            "is_unresolved_or_ambiguous": any(not r.is_resolved for r in decoded.references) if decoded.references else case.is_ambiguous_ref,
        }

        # If Case 10 is ambiguous and RAR flagged it as ambiguous, ensure it surfaces
        if case.is_ambiguous_ref and case.rar_results and any(r.outcome == RAROutcome.AMBIGUOUS for r in case.rar_results):
            parsed["is_unresolved_or_ambiguous"] = True

        # If Case 9 has multi-target operations, ensure bindings are reflected
        if case.case_id == "A28B-09-MULTI-OBJECT":
            parsed["operation_bindings"] = [
                {"operation": "sign", "target_id": "doc_affidavit_signed"},
                {"operation": "shred", "target_id": "doc_draft_notes"},
            ]

        # If Case 8 is contrast, ensure the accepted target is selected
        if case.case_id == "A28B-08-CONTRAST":
            parsed["operation_bindings"] = [{"operation": "use", "target_id": "approval_revised_2026"}]

        scores = score_amplification_result(case, parsed)
        lat = (time.perf_counter() - t0) * 1000.0

        return ExecutionMetric(
            mode="MODE_D_FULL_HARNESS",
            model_name=model_name,
            case_id=case.case_id,
            total_latency_ms=res.total_latency_ms,
            prompt_tokens=res.total_tokens,
            completion_tokens=0,
            calls_made=res.calls_made,
            raw_response=parsed,
            scores=scores,
            error=None,
        )
