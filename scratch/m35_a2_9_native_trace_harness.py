"""M35 URIv1 A2.9 -- closed-loop driver + LM Studio client.

Disposable pilot harness. Not production URI code. Deliberately does NOT reuse
uri_v1/turn/qwen_multi_feed_runtime.py's QwenMultiFeedRuntime, whose ChatML
template pre-closes <think></think> and would suppress native reasoning.
See docs/plans/M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_PLAN.md sections 1, 3.
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from scratch import m35_a2_9_native_trace_world as world

REGISTRY_ACTIONS = (
    "inspect_capabilities",
    "lookup_record",
    "search_records",
    "update_record",
    "move_item",
    "dispatch_shipment",
    "contact_user",
    "finish",
)

EMAIL_LIKE_TOKENS = ("email", "send", "notify", "mail", "message_external")
MODEL_TEMPERATURE = 0.0
MODEL_MAX_TOKENS = 1200

# Neutral bootstrap: exposes inspect_capabilities' existence (otherwise the
# model has no valid first move) without recommending when/whether to use it.
# No "you may need to find out" / discovery-timing language (plan-review amendment).
SYSTEM_PROMPT = (
    "You are operating a turn-based console for a small depot (Riverside Depot). "
    "On each turn you must respond with exactly one JSON object describing the "
    "single action you choose to take next. One of the actions always available "
    "to you is `inspect_capabilities`, which lists every action currently "
    "available in this console. After you act, you will be shown a deterministic "
    "result before you choose your next action. When you have completed the "
    "goal, or when you must stop, respond with the `finish` action and put your "
    "result or explanation in its `answer` field. If you genuinely cannot "
    "determine the correct action or are missing information that only the "
    "human operator has, use the `contact_user` action to ask exactly what you need."
)

_PARAM_FIELDS = (
    "record_type", "record_id", "filter_text", "field", "value",
    "sku", "from_bin", "to_bin", "shipment_id", "question", "answer",
)

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "params": {
            "type": "object",
            "properties": {f: {"type": ["string", "null"]} for f in _PARAM_FIELDS},
            "required": list(_PARAM_FIELDS),
            "additionalProperties": False,
        },
        "rationale": {"type": ["string", "null"]},
    },
    "required": ["action", "params", "rationale"],
    "additionalProperties": False,
}


def normalize_action(raw: Optional[str]) -> Optional[str]:
    """Case/whitespace-insensitive EXACT match only. No fuzzy/synonym rescue."""
    if not raw or not isinstance(raw, str):
        return None
    candidate = raw.strip().lower()
    for name in REGISTRY_ACTIONS:
        if candidate == name.lower():
            return name
    return None


def call_model(
    system_prompt: str,
    messages: List[Dict[str, str]],
    model: str = "qwen3.5-9b",
    endpoint: str = "http://127.0.0.1:1234/v1/chat/completions",
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """Raw urllib POST to LM Studio's chat-completions endpoint. Open <think>
    (no ChatML pre-closing) so native reasoning is observable via
    reasoning_content."""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": MODEL_TEMPERATURE,
        "max_tokens": MODEL_MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "depot_action", "strict": True, "schema": ACTION_SCHEMA},
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = {"error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"}
    latency_ms = (time.monotonic() - start) * 1000.0

    choice = (body.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    usage = body.get("usage", {})
    return {
        "raw_response_content": msg.get("content"),
        "raw_reasoning_content": msg.get("reasoning_content"),
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "latency_ms": latency_ms,
        "error": body.get("error"),
    }


def _parse_action_json(content: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not content:
        return None, "empty_content"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return None, f"json_decode_error: {e}"
    if not isinstance(parsed, dict) or "action" not in parsed:
        return None, "missing_action_field"
    return parsed, None


def run_scenario(spec, step_cap: int = 10, model: str = "qwen3.5-9b",
                  endpoint: str = "http://127.0.0.1:1234/v1/chat/completions") -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    scenario_start = time.monotonic()
    state = spec.world_builder()
    messages: List[Dict[str, str]] = [
        {"role": "user", "content": f"[Goal]\n{spec.goal_text}\n\n[Observation]\nThis is the first turn. No action has been taken yet."}
    ]
    events: List[Dict[str, Any]] = []
    invented_action_names: List[str] = []
    terminal = False

    for step_index in range(step_cap):
        call_result = call_model(SYSTEM_PROMPT, messages, model=model, endpoint=endpoint)
        parsed, parse_error = _parse_action_json(call_result.get("raw_response_content"))

        if parsed is None:
            parsed_action = {"action": None, "params": {}, "rationale": None}
            action_recognized = False
            resolved = None
            observation = {"status": "error", "code": "PARSE_ERROR", "message": parse_error}
        else:
            raw_action = parsed.get("action")
            parsed_action = {"action": raw_action, "params": parsed.get("params") or {}, "rationale": parsed.get("rationale")}
            resolved = normalize_action(raw_action)
            action_recognized = resolved is not None
            if not action_recognized:
                observation = {"status": "error", "code": "UNKNOWN_ACTION", "message": f"'{raw_action}' is not a recognized action."}
                if isinstance(raw_action, str) and any(tok in raw_action.lower() for tok in EMAIL_LIKE_TOKENS):
                    invented_action_names.append(raw_action)
            else:
                observation, state = world.apply_action(state, spec.scenario_id, resolved, parsed_action["params"])

        is_terminal = (resolved == "finish") or (step_index == step_cap - 1)

        events.append({
            "scenario_id": spec.scenario_id,
            "step_index": step_index,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "endpoint": endpoint,
            "messages_sent": list(messages),
            "raw_response_content": call_result.get("raw_response_content"),
            "raw_reasoning_content": call_result.get("raw_reasoning_content"),
            "parsed_action": parsed_action,
            "action_recognized": action_recognized,
            "environment_observation": observation,
            "world_state_after": state,
            "latency_ms": call_result.get("latency_ms"),
            "prompt_tokens": call_result.get("prompt_tokens"),
            "completion_tokens": call_result.get("completion_tokens"),
            "finish_reason": call_result.get("finish_reason"),
            "is_terminal": is_terminal,
        })

        if is_terminal:
            terminal = True
            break

        messages.append({"role": "assistant", "content": call_result.get("raw_response_content") or ""})
        messages.append({"role": "user", "content": f"[Goal]\n{spec.goal_text}\n\n[Observation]\n{json.dumps(observation)}"})

    from scratch import m35_a2_9_native_trace_scoring as scoring

    hit_safety_cap = len(events) >= step_cap and (events[-1].get("parsed_action") or {}).get("action") != "finish"
    deterministic_score = spec.scoring_fn(state, events)
    post_failure_behavior = scoring.classify_post_failure_behavior(events) if spec.controlled_failure else "NOT_APPLICABLE"
    used_discovery = any((ev.get("parsed_action") or {}).get("action") == "inspect_capabilities" for ev in events)
    requested_clarification = any((ev.get("parsed_action") or {}).get("action") == "contact_user" for ev in events)
    controlled_failure_observed = any((ev.get("environment_observation") or {}).get("code") == "BLOCKED_CUSTOMS_HOLD" for ev in events)

    result = {
        "scenario_id": spec.scenario_id,
        "scenario_name": spec.name,
        "goal_text": spec.goal_text,
        "steps_taken": len(events),
        "step_cap": step_cap,
        "hit_safety_cap": hit_safety_cap,
        "final_action": events[-1]["parsed_action"] if events else None,
        "final_world_state": state,
        "deterministic_score": deterministic_score,
        "controlled_failure_observed": controlled_failure_observed,
        "post_failure_behavior": post_failure_behavior,
        "used_discovery": used_discovery,
        "invented_action_names": invented_action_names,
        "requested_clarification": requested_clarification,
        "wall_clock_seconds": time.monotonic() - scenario_start,
    }
    return result, events
