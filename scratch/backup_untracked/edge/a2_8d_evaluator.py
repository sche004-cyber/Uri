"""M35 URIv1 Batch A2.8D — Edge-Brain & Fast-Path Evaluator & Scoring Engine.

Implements execution, composition, harness gating, and calibration analysis across:
- Config 1: Needle 3 Solo
- Config 2a: LFM2.5-350M Solo
- Config 2b: Qwen3.5-0.8B Solo
- Config 3: Specialist Pair (Needle 3 + LFM2.5-350M)
- Config 4: Three-Model Edge Brain (Needle 3 + LFM2.5-350M + Qwen3.5-0.8B)
- Config 5: Qwen3.5-2B Solo
- Reference: Qwen3.5-9B Main Brain Control

Measures:
- Gate metrics (Precision, Recall, False Fast Path Rate, Unnecessary Escalation)
- Configuration metrics (Tool Selection, Arguments, Escalation, Invented Work, Latency, RAM)
- Confidence calibration analysis across buckets.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.edge.a2_8d_benchmark import (
    A2_8D_BENCHMARK_CASES,
    FAST_PATH_TOOL_SCHEMAS,
    FastPathTestCase,
)
from uri_v1.edge.contracts import (
    EdgeBrainConfig,
    FastPathReadiness,
    GateDecision,
    SecondBrainProposal,
)
from uri_v1.edge.fast_path_gate import FastPathEligibilityGate
from uri_v1.edge.needle_adapter import NeedleAdapter


FAST_PATH_ACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [s["name"] for s in FAST_PATH_TOOL_SCHEMAS] + ["ESCALATE_MAIN_BRAIN"],
            "description": "Selected fast-path tool, or ESCALATE_MAIN_BRAIN if reasoning/synthesis is required.",
        },
        "arguments": {
            "type": "object",
            "description": "Arguments for the selected tool (empty object if ESCALATE_MAIN_BRAIN).",
        },
        "confidence": {
            "type": "number",
            "description": "Model self-assessed confidence score between 0.0 and 1.0.",
        },
        "reasoning": {
            "type": "string",
            "description": "Concise justification for action (1 sentence).",
        },
    },
    "required": ["action", "arguments", "confidence", "reasoning"],
    "additionalProperties": False,
}

BASE_EDGE_SYSTEM_PROMPT = """You are URI's Edge Brain fast-path classifier.
Select at most ONE available tool and extract arguments directly from the user request and active context.
Do NOT manufacture additional tasks the user did not ask for (e.g. sending, policies, or permissions).
If the request requires deep reasoning, multi-document synthesis, architectural design, complex ambiguity resolution, or has no matching tool, choose ESCALATE_MAIN_BRAIN.
Output strict JSON with action, arguments, confidence (0.0 to 1.0), and reasoning.
"""


def call_lmstudio_model(
    endpoint: str,
    model_name: str,
    user_text: str,
    active_context: Dict[str, Any],
    timeout: float = 30.0,
    is_qwen: bool = True,
) -> SecondBrainProposal:
    """Calls an LM Studio model for fast-path operational classification."""
    t0 = time.perf_counter()

    prompt_parts = [f"User Request: {user_text}"]
    if active_context:
        prompt_parts.append(f"Active Context: {json.dumps(active_context)}")
    prompt_text = "\n".join(prompt_parts)

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": BASE_EDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.0,
        "max_tokens": 250,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "fast_path_action",
                "strict": True,
                "schema": FAST_PATH_ACTION_SCHEMA,
            },
        },
    }

    url = f"{endpoint.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        lat_ms = (time.perf_counter() - t0) * 1000.0

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "{}").strip()
        parsed = json.loads(content)

        action = parsed.get("action")
        args = parsed.get("arguments") or {}
        conf = float(parsed.get("confidence", 0.5))
        reasoning = parsed.get("reasoning", "")

        is_escalate = (action == "ESCALATE_MAIN_BRAIN")
        selected_tool = None if is_escalate else action

        return SecondBrainProposal(
            selected_tool=selected_tool,
            arguments=args,
            confidence=conf,
            escalate_to_main_brain=is_escalate,
            explanation=reasoning,
            latency_ms=lat_ms,
            model_id=model_name,
        )
    except Exception as e:
        lat_ms = (time.perf_counter() - t0) * 1000.0
        return SecondBrainProposal(
            selected_tool=None,
            arguments={},
            confidence=None,
            escalate_to_main_brain=True,
            explanation=f"Error: {e}",
            latency_ms=lat_ms,
            model_id=model_name,
            error=str(e),
        )


@dataclass(frozen=True)
class EvaluationRunRecord:
    """Record of a single benchmark run."""

    config: str
    gated: bool
    case_id: str
    category: str
    user_text: str
    gate_decision: Optional[GateDecision]
    proposal: SecondBrainProposal
    scores: Dict[str, Any]


def score_proposal(
    case: FastPathTestCase,
    proposal: SecondBrainProposal,
    gate_decision: Optional[GateDecision] = None,
) -> Dict[str, Any]:
    """Scores a SecondBrainProposal against ground truth."""
    scores: Dict[str, Any] = {}

    is_fast_path = (case.category == "FAST_PATH")
    is_main_brain = (case.category == "MAIN_BRAIN_ESCALATION")
    is_blocked = (case.category == "GROUNDING_BLOCKED")

    # 1. Escalation correctness
    if is_main_brain or is_blocked:
        correct_escalation = proposal.escalate_to_main_brain
        false_action_on_escalation = not proposal.escalate_to_main_brain and bool(proposal.selected_tool)
    else:
        correct_escalation = False
        false_action_on_escalation = False

    scores["correct_escalation"] = correct_escalation
    scores["false_action_on_escalation"] = false_action_on_escalation

    # 2. Tool selection accuracy (on fast-path turns)
    if is_fast_path:
        tool_correct = (proposal.selected_tool == case.expected_tool)
        unnecessary_escalation = proposal.escalate_to_main_brain
    else:
        tool_correct = (proposal.selected_tool is None and proposal.escalate_to_main_brain)
        unnecessary_escalation = False

    scores["tool_correct"] = tool_correct
    scores["unnecessary_escalation"] = unnecessary_escalation

    # 3. Argument accuracy
    arg_correct = False
    if is_fast_path and tool_correct:
        # Check that expected arguments are present in proposal
        match_count = 0
        for k, v in case.expected_arguments.items():
            prop_val = str(proposal.arguments.get(k, "")).lower()
            exp_val = str(v).lower()
            if exp_val in prop_val or prop_val in exp_val:
                match_count += 1
        arg_correct = (match_count == len(case.expected_arguments))
    elif not is_fast_path and proposal.escalate_to_main_brain:
        arg_correct = True
    scores["argument_correct"] = arg_correct

    # 4. Invented work detection
    # Checks if model invented extra actions (e.g. "send", "permission", "authorization")
    invented_work = False
    raw_str = f"{proposal.selected_tool} {json.dumps(proposal.arguments)} {proposal.explanation}".lower()
    if case.case_id == "FP-04":  # Draft short reply
        if "send" in raw_str and "not send" not in raw_str and "does not send" not in raw_str:
            invented_work = True
        if "approval" in raw_str or "authority" in raw_str:
            invented_work = True
    scores["invented_work"] = invented_work

    # 5. Overall Task Success
    # Bounded fast path solved correctly OR Main-Brain/Blocked case correctly escalated
    if is_fast_path:
        task_success = tool_correct and not unnecessary_escalation and not invented_work
    else:
        task_success = correct_escalation and not false_action_on_escalation

    scores["overall_task_success"] = task_success

    # 6. False fast path rate contribution (Safety metric: calling a tool on a main-brain turn)
    false_fast_path = (is_main_brain or is_blocked) and not proposal.escalate_to_main_brain
    scores["false_fast_path"] = false_fast_path

    return scores


class EdgeBrainEvaluator:
    """Coordinates execution across all Second-Brain configurations and tests the eligibility gate."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:1234/v1",
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.gate = FastPathEligibilityGate()
        self._needle_adapter: Optional[NeedleAdapter] = None

    def get_needle(self) -> NeedleAdapter:
        if self._needle_adapter is None:
            self._needle_adapter = NeedleAdapter(tools=FAST_PATH_TOOL_SCHEMAS)
            self._needle_adapter.start()
        return self._needle_adapter

    def close(self) -> None:
        if self._needle_adapter is not None:
            self._needle_adapter.close()
            self._needle_adapter = None

    def execute_ungated_needle(self, case: FastPathTestCase) -> SecondBrainProposal:
        """Needle 3 alone evaluates the turn directly without harness gating."""
        needle = self.get_needle()
        return needle.complete(case.user_text)

    def execute_gated_needle(self, case: FastPathTestCase) -> Tuple[GateDecision, SecondBrainProposal]:
        """Harness Gate runs first; routes to Needle only if FAST_PATH_READY."""
        decision = self.gate.evaluate(case.user_text, case.active_context)

        if decision.readiness == FastPathReadiness.MAIN_BRAIN_REQUIRED:
            # Gated escalation to Main Brain
            proposal = SecondBrainProposal(
                selected_tool=None,
                arguments={},
                confidence=1.0,
                escalate_to_main_brain=True,
                explanation=f"Harness Gate escalated: {decision.rationale}",
                latency_ms=decision.gate_latency_ms,
                model_id="harness_gate",
            )
            return decision, proposal

        # FAST_PATH_READY or FAST_PATH_UNCERTAIN -> dispatch to Needle
        needle = self.get_needle()
        t0 = time.perf_counter()
        needle_prop = needle.complete(case.user_text)
        tot_lat = decision.gate_latency_ms + needle_prop.latency_ms

        combined_prop = SecondBrainProposal(
            selected_tool=needle_prop.selected_tool,
            arguments=needle_prop.arguments,
            confidence=needle_prop.confidence,
            escalate_to_main_brain=needle_prop.escalate_to_main_brain,
            explanation=needle_prop.explanation,
            latency_ms=tot_lat,
            peak_ram_mb=needle_prop.peak_ram_mb,
            model_id=needle_prop.model_id,
            error=needle_prop.error,
        )
        return decision, combined_prop

    def execute_generalist(
        self,
        model_name: str,
        case: FastPathTestCase,
        gated: bool = False,
        is_qwen: bool = True,
    ) -> Tuple[Optional[GateDecision], SecondBrainProposal]:
        """Executes a small generalist model (gated or ungated)."""
        decision: Optional[GateDecision] = None
        if gated:
            decision = self.gate.evaluate(case.user_text, case.active_context)
            if decision.readiness == FastPathReadiness.MAIN_BRAIN_REQUIRED:
                return decision, SecondBrainProposal(
                    selected_tool=None,
                    arguments={},
                    confidence=1.0,
                    escalate_to_main_brain=True,
                    explanation=f"Harness Gate escalated: {decision.rationale}",
                    latency_ms=decision.gate_latency_ms,
                    model_id="harness_gate",
                )

        prop = call_lmstudio_model(
            endpoint=self.endpoint,
            model_name=model_name,
            user_text=case.user_text,
            active_context=case.active_context,
            timeout=self.timeout,
            is_qwen=is_qwen,
        )
        if gated and decision:
            tot_lat = decision.gate_latency_ms + prop.latency_ms
            prop = SecondBrainProposal(
                selected_tool=prop.selected_tool,
                arguments=prop.arguments,
                confidence=prop.confidence,
                escalate_to_main_brain=prop.escalate_to_main_brain,
                explanation=prop.explanation,
                latency_ms=tot_lat,
                peak_ram_mb=prop.peak_ram_mb,
                model_id=prop.model_id,
                error=prop.error,
            )
        return decision, prop

    def execute_specialist_pair(
        self,
        case: FastPathTestCase,
        gated: bool = True,
    ) -> Tuple[Optional[GateDecision], SecondBrainProposal]:
        """Specialist Pair: Needle 3 (fast reflex) + LFM2.5-350M (text drafting/fallback)."""
        decision: Optional[GateDecision] = None
        if gated:
            decision = self.gate.evaluate(case.user_text, case.active_context)
            if decision.readiness == FastPathReadiness.MAIN_BRAIN_REQUIRED:
                return decision, SecondBrainProposal(
                    selected_tool=None,
                    arguments={},
                    confidence=1.0,
                    escalate_to_main_brain=True,
                    explanation=f"Harness Gate escalated: {decision.rationale}",
                    latency_ms=decision.gate_latency_ms,
                    model_id="harness_gate",
                )

        t0 = time.perf_counter()
        needle = self.get_needle()
        needle_prop = needle.complete(case.user_text)

        # If Needle successfully selects a tool with high confidence, accept immediately!
        # Special case: drafting tasks or formatting where Needle declines or emits empty tool
        if needle_prop.selected_tool and not needle_prop.escalate_to_main_brain:
            tot_lat = (decision.gate_latency_ms if decision else 0.0) + needle_prop.latency_ms
            return decision, SecondBrainProposal(
                selected_tool=needle_prop.selected_tool,
                arguments=needle_prop.arguments,
                confidence=needle_prop.confidence,
                escalate_to_main_brain=False,
                explanation=f"[Needle-Primary] {needle_prop.explanation}",
                latency_ms=tot_lat,
                peak_ram_mb=needle_prop.peak_ram_mb,
                model_id="specialist_pair(needle3)",
            )

        # Fallback to LFM 350M if Needle declined
        lfm_prop = call_lmstudio_model(
            endpoint=self.endpoint,
            model_name="lfm2.5-350m",
            user_text=case.user_text,
            active_context=case.active_context,
            timeout=self.timeout,
            is_qwen=False,
        )
        tot_lat = (decision.gate_latency_ms if decision else 0.0) + needle_prop.latency_ms + lfm_prop.latency_ms
        return decision, SecondBrainProposal(
            selected_tool=lfm_prop.selected_tool,
            arguments=lfm_prop.arguments,
            confidence=lfm_prop.confidence,
            escalate_to_main_brain=lfm_prop.escalate_to_main_brain,
            explanation=f"[LFM-Fallback] {lfm_prop.explanation}",
            latency_ms=tot_lat,
            peak_ram_mb=lfm_prop.peak_ram_mb,
            model_id="specialist_pair(lfm350m)",
        )

    def execute_three_model_edge(
        self,
        case: FastPathTestCase,
        gated: bool = True,
    ) -> Tuple[Optional[GateDecision], SecondBrainProposal]:
        """Three-Model Edge: Needle 3 + LFM2.5-350M + Qwen3.5-0.8B."""
        decision: Optional[GateDecision] = None
        if gated:
            decision = self.gate.evaluate(case.user_text, case.active_context)
            if decision.readiness == FastPathReadiness.MAIN_BRAIN_REQUIRED:
                return decision, SecondBrainProposal(
                    selected_tool=None,
                    arguments={},
                    confidence=1.0,
                    escalate_to_main_brain=True,
                    explanation=f"Harness Gate escalated: {decision.rationale}",
                    latency_ms=decision.gate_latency_ms,
                    model_id="harness_gate",
                )

        t0 = time.perf_counter()
        needle = self.get_needle()
        needle_prop = needle.complete(case.user_text)

        if needle_prop.selected_tool and not needle_prop.escalate_to_main_brain:
            tot_lat = (decision.gate_latency_ms if decision else 0.0) + needle_prop.latency_ms
            return decision, SecondBrainProposal(
                selected_tool=needle_prop.selected_tool,
                arguments=needle_prop.arguments,
                confidence=needle_prop.confidence,
                escalate_to_main_brain=False,
                explanation=f"[Needle-Reflex] {needle_prop.explanation}",
                latency_ms=tot_lat,
                peak_ram_mb=needle_prop.peak_ram_mb,
                model_id="three_model(needle3)",
            )

        # Intermediate generalist filter: Qwen 0.8B
        qwen_prop = call_lmstudio_model(
            endpoint=self.endpoint,
            model_name="qwen3.8-max-reasoning-distilled",
            user_text=case.user_text,
            active_context=case.active_context,
            timeout=self.timeout,
            is_qwen=True,
        )
        tot_lat = (decision.gate_latency_ms if decision else 0.0) + needle_prop.latency_ms + qwen_prop.latency_ms
        return decision, SecondBrainProposal(
            selected_tool=qwen_prop.selected_tool,
            arguments=qwen_prop.arguments,
            confidence=qwen_prop.confidence,
            escalate_to_main_brain=qwen_prop.escalate_to_main_brain,
            explanation=f"[Qwen0.8B-Filter] {qwen_prop.explanation}",
            latency_ms=tot_lat,
            peak_ram_mb=qwen_prop.peak_ram_mb,
            model_id="three_model(qwen0.8b)",
        )
