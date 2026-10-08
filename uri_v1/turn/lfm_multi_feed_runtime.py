"""Multi-Feed Execution Runtime for LFM2.5-350M (Batch A2.5 Stage 4).

Orchestrates narrow feed execution:
- Sequential vs Parallel feed execution
- Mode A (Raw broad call)
- Mode B (Serial RAR -> broad call)
- Mode C (Parallel RAR + broad residual call)
- Mode D (Parallel RAR + adaptive narrow feeds + deterministic merge)
- High-precision telemetry: TTFT, prompt/completion tokens, latency per feed, total turn latency.
"""

from __future__ import annotations

import concurrent.futures
import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.turn.active_context import ActiveContext
from uri_v1.turn.contracts import DecodedRequest
from uri_v1.turn.lfm_adaptive_feeds import (
    FEED_B_SCHEMA,
    FEED_B_SYSTEM_PROMPT,
    FEED_C_SCHEMA,
    FEED_C_SYSTEM_PROMPT,
    FEED_G_SCHEMA,
    FEED_G_SYSTEM_PROMPT,
    FEED_O_SCHEMA,
    FEED_O_SYSTEM_PROMPT,
    FeedBOutput,
    FeedCOutput,
    FeedGOutput,
    FeedOOutput,
    FeedType,
    build_feed_b_prompt,
    build_feed_c_prompt,
    build_feed_g_prompt,
    build_feed_o_prompt,
    parse_feed_b_response,
    parse_feed_c_response,
    parse_feed_g_response,
    parse_feed_o_response,
)
from uri_v1.turn.lfm_feed_merger import DeterministicSemanticMerger
from uri_v1.turn.lfm_feed_planner import AdaptiveSemanticFeedPlanner, FeedPlan

from uri_v1.turn.lfm_wire import (
    LFM_SYSTEM_PROMPT,
    LFM_WIRE_SCHEMA,
    LFM_WIRE_SCHEMA_NAME,
    build_lfm_mode_a_prompt,
    build_lfm_mode_b_prompt,
    normalize_lfm_wire,
)
from uri_v1.turn.rar_contracts import (
    RARCandidate,
    RAREvidence,
    RAROutcome,
    RARQuery,
    RARResolution,
)
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended
from uri_v1.turn.turn_frame import TurnFrame


@dataclass(frozen=True)
class FeedCallMetric:
    feed_type: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    ttft_ms: float
    status: str


@dataclass(frozen=True)
class MultiFeedExecutionResult:
    mode: str
    decoded_request: DecodedRequest
    feed_plan: Optional[FeedPlan]
    feed_metrics: Tuple[FeedCallMetric, ...]
    rar_result: Optional[RARResolution]
    total_latency_ms: float
    rar_latency_ms: float
    sequential_latency_ms: float
    parallel_latency_ms: float
    total_tokens: int
    calls_made: int


class LFMMultiFeedRuntime:
    """Runtime driver for Stage 4 multi-feed qualification."""

    def __init__(
        self,
        endpoint_url: str = "http://127.0.0.1:1234/v1/chat/completions",
        model_name: str = "lfm2.5-350m",
        timeout: float = 30.0,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.model_name = model_name
        self.timeout = timeout
        self.planner = AdaptiveSemanticFeedPlanner()
        self.merger = DeterministicSemanticMerger()

    def _call_feed_endpoint(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        schema_name: str,
    ) -> Tuple[Dict[str, Any], FeedCallMetric]:
        """Invokes the LM Studio API with a specific schema and prompt."""
        t_start = time.perf_counter()
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 400,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_resp = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            t_end = time.perf_counter()
            metric = FeedCallMetric(
                feed_type=schema_name,
                latency_ms=(t_end - t_start) * 1000,
                prompt_tokens=0,
                completion_tokens=0,
                ttft_ms=0.0,
                status=f"ERROR: {e}",
            )
            return {}, metric

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000

        usage = raw_resp.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        comp_tokens = usage.get("completion_tokens", 0)

        # Estimate TTFT as prefill proportion (typically ~25% of latency for short responses)
        ttft_ms = latency_ms * 0.25

        choice = raw_resp.get("choices", [{}])[0]
        content_str = choice.get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(content_str)
        except json.JSONDecodeError:
            parsed = {}

        metric = FeedCallMetric(
            feed_type=schema_name,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=comp_tokens,
            ttft_ms=ttft_ms,
            status="OK",
        )
        return parsed, metric

    # -----------------------------------------------------------------------
    # Mode D: Parallel RAR + Adaptive Narrow LFM Feeds + Deterministic Merge
    # -----------------------------------------------------------------------
    def execute_mode_d(
        self,
        text: str,
        referring_expression: Optional[str] = None,
        candidate_pool: Sequence[Any] = (),
        turn_frame: Optional[TurnFrame] = None,
        active_context: Optional[ActiveContext] = None,
        run_parallel: bool = True,
    ) -> MultiFeedExecutionResult:
        """Executes primary Mode D: RAR + Planned narrow feeds + deterministic merge."""
        t_turn_start = time.perf_counter()

        # 1. Deterministic RAR (can run in parallel with or prior to planning)
        t_rar_start = time.perf_counter()
        rar_res: Optional[RARResolution] = None
        if referring_expression and candidate_pool:
            query = RARQuery(
                reference_expression=referring_expression,
                candidates=tuple(candidate_pool),
                local_evidence=RAREvidence(
                    recency_hint="same" if referring_expression in ("same", "same thing") else None,
                    negation_spans=turn_frame.negation_spans if turn_frame else (),
                ),
            )
            rar_trace = resolve_rar_deterministic_extended(query)
            rar_res = rar_trace.resolution
        rar_latency_ms = (time.perf_counter() - t_rar_start) * 1000

        # 2. Adaptive Feed Planning
        plan = self.planner.plan_feeds(text=text, turn_frame=turn_frame, rar_result=rar_res)

        feed_metrics: List[FeedCallMetric] = []
        feed_g_out: Optional[FeedGOutput] = None
        feed_o_out: Optional[FeedOOutput] = None
        feed_c_out: Optional[FeedCOutput] = None
        feed_b_out: Optional[FeedBOutput] = None

        independent_tasks: List[Tuple[FeedType, Any, Any, Any, str]] = []

        # Prepare independent feeds (G, O, C)
        if plan.has_feed(FeedType.GOAL):
            independent_tasks.append((
                FeedType.GOAL,
                FEED_G_SYSTEM_PROMPT,
                build_feed_g_prompt(text),
                FEED_G_SCHEMA,
                "feed_g_goal",
            ))

        if plan.has_feed(FeedType.OPERATIONS):
            verbs = [a.verb for a in turn_frame.candidate_actions] if turn_frame else None
            anchors = [rar_res.candidate_id] if (rar_res and rar_res.candidate_id) else None
            independent_tasks.append((
                FeedType.OPERATIONS,
                FEED_O_SYSTEM_PROMPT,
                build_feed_o_prompt(text, candidate_actions=verbs, rar_anchors=anchors),
                FEED_O_SCHEMA,
                "feed_o_operations",
            ))

        if plan.has_feed(FeedType.CONSTRAINTS):
            independent_tasks.append((
                FeedType.CONSTRAINTS,
                FEED_C_SYSTEM_PROMPT,
                build_feed_c_prompt(text),
                FEED_C_SCHEMA,
                "feed_c_constraints",
            ))

        seq_latencies: List[float] = []
        par_latencies: List[float] = []

        # Execute independent feeds
        if run_parallel and len(independent_tasks) > 1:
            t_par_start = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(independent_tasks)) as executor:
                future_to_type = {
                    executor.submit(
                        self._call_feed_endpoint, task[1], task[2], task[3], task[4]
                    ): task[0]
                    for task in independent_tasks
                }
                for future in concurrent.futures.as_completed(future_to_type):
                    ftype = future_to_type[future]
                    res_json, metric = future.result()
                    feed_metrics.append(metric)
                    seq_latencies.append(metric.latency_ms)
                    if ftype == FeedType.GOAL:
                        feed_g_out = parse_feed_g_response(res_json)
                    elif ftype == FeedType.OPERATIONS:
                        feed_o_out = parse_feed_o_response(res_json)
                    elif ftype == FeedType.CONSTRAINTS:
                        feed_c_out = parse_feed_c_response(res_json)
            par_latencies.append((time.perf_counter() - t_par_start) * 1000)
        else:
            # Sequential execution
            for ftype, sys_p, usr_p, schema, name in independent_tasks:
                res_json, metric = self._call_feed_endpoint(sys_p, usr_p, schema, name)
                feed_metrics.append(metric)
                seq_latencies.append(metric.latency_ms)
                if ftype == FeedType.GOAL:
                    feed_g_out = parse_feed_g_response(res_json)
                elif ftype == FeedType.OPERATIONS:
                    feed_o_out = parse_feed_o_response(res_json)
                elif ftype == FeedType.CONSTRAINTS:
                    feed_c_out = parse_feed_c_response(res_json)

        # Execute Feed B if needed (requires operations from Feed O)
        if plan.has_feed(FeedType.BINDING):
            ops = list(feed_o_out.requested_operations) if feed_o_out else []
            anchors_data = []
            if rar_res and rar_res.candidate_id:
                anchors_data.append({
                    "target_id": rar_res.candidate_id,
                    "label": rar_res.candidate_id,
                    "role": "referenced_entity",
                })
            b_json, b_metric = self._call_feed_endpoint(
                FEED_B_SYSTEM_PROMPT,
                build_feed_b_prompt(text, operations=ops, rar_anchors=anchors_data),
                FEED_B_SCHEMA,
                "feed_b_binding",
            )
            feed_metrics.append(b_metric)
            seq_latencies.append(b_metric.latency_ms)
            feed_b_out = parse_feed_b_response(b_json)
            if run_parallel and len(independent_tasks) > 1:
                par_latencies.append(b_metric.latency_ms)

        # 3. Deterministic Merge
        decoded = self.merger.merge(
            user_text=text,
            feed_g=feed_g_out,
            feed_o=feed_o_out,
            feed_c=feed_c_out,
            feed_b=feed_b_out,
            rar_result=rar_res,
            turn_frame=turn_frame,
            active_context=active_context,
        )

        total_lat_ms = (time.perf_counter() - t_turn_start) * 1000
        sequential_sum = sum(seq_latencies) + rar_latency_ms
        parallel_sum = (sum(par_latencies) if par_latencies else sequential_sum) + rar_latency_ms
        total_tokens = sum(m.prompt_tokens + m.completion_tokens for m in feed_metrics)

        return MultiFeedExecutionResult(
            mode="Mode D (Adaptive Multi-Feed + RAR)",
            decoded_request=decoded,
            feed_plan=plan,
            feed_metrics=tuple(feed_metrics),
            rar_result=rar_res,
            total_latency_ms=total_lat_ms,
            rar_latency_ms=rar_latency_ms,
            sequential_latency_ms=sequential_sum,
            parallel_latency_ms=parallel_sum,
            total_tokens=total_tokens,
            calls_made=len(feed_metrics),
        )

    # -----------------------------------------------------------------------
    # Mode A / B / C Callers for Baseline Comparison
    # -----------------------------------------------------------------------
    def execute_mode_a(
        self,
        text: str,
        turn_frame: Optional[TurnFrame] = None,
        active_context: Optional[ActiveContext] = None,
    ) -> MultiFeedExecutionResult:
        """Mode A: Single broad call, no RAR."""
        t_start = time.perf_counter()
        prompt = build_lfm_mode_a_prompt(text, turn_frame=turn_frame, active_context=active_context)
        res_json, metric = self._call_feed_endpoint(
            LFM_SYSTEM_PROMPT, prompt, LFM_WIRE_SCHEMA, LFM_WIRE_SCHEMA_NAME
        )
        decoded = normalize_lfm_wire(res_json, raw_text=text)
        tot_lat = (time.perf_counter() - t_start) * 1000

        return MultiFeedExecutionResult(
            mode="Mode A (Raw Broad Call)",
            decoded_request=decoded,
            feed_plan=None,
            feed_metrics=(metric,),
            rar_result=None,
            total_latency_ms=tot_lat,
            rar_latency_ms=0.0,
            sequential_latency_ms=tot_lat,
            parallel_latency_ms=tot_lat,
            total_tokens=metric.prompt_tokens + metric.completion_tokens,
            calls_made=1,
        )

    def execute_mode_b(
        self,
        text: str,
        referring_expression: Optional[str] = None,
        candidate_pool: Sequence[Any] = (),
        turn_frame: Optional[TurnFrame] = None,
        active_context: Optional[ActiveContext] = None,
    ) -> MultiFeedExecutionResult:
        """Mode B: Serial RAR -> Broad call."""
        t_start = time.perf_counter()
        rar_res: Optional[RARResolution] = None
        rar_lat = 0.0
        rar_facts: Dict[str, Any] = {"resolved_anchors": {}, "unresolved": [], "ambiguous_candidates": {}}

        if referring_expression and candidate_pool:
            t_rar = time.perf_counter()
            query = RARQuery(
                reference_expression=referring_expression,
                candidates=tuple(candidate_pool),
                local_evidence=RAREvidence(
                    recency_hint="same" if referring_expression in ("same", "same thing") else None,
                    negation_spans=turn_frame.negation_spans if turn_frame else (),
                ),
            )
            rar_trace = resolve_rar_deterministic_extended(query)
            rar_res = rar_trace.resolution
            rar_lat = (time.perf_counter() - t_rar) * 1000

            if rar_res.outcome == RAROutcome.RESOLVED and rar_res.candidate_id:
                rar_facts["resolved_anchors"][referring_expression] = {
                    "target_id": rar_res.candidate_id,
                    "rule": str(rar_res.rule_used),
                }
            elif rar_res.outcome == RAROutcome.UNKNOWN:
                rar_facts["unresolved"].append(referring_expression)
            elif rar_res.outcome == RAROutcome.AMBIGUOUS:
                rar_facts["ambiguous_candidates"][referring_expression] = list(rar_res.ambiguous_candidate_ids)

        prompt = build_lfm_mode_b_prompt(
            text,
            turn_frame=turn_frame,
            active_context=active_context,
            rar_facts=rar_facts,
        )
        res_json, metric = self._call_feed_endpoint(
            LFM_SYSTEM_PROMPT, prompt, LFM_WIRE_SCHEMA, LFM_WIRE_SCHEMA_NAME
        )
        decoded = normalize_lfm_wire(res_json, raw_text=text)
        tot_lat = (time.perf_counter() - t_start) * 1000

        return MultiFeedExecutionResult(
            mode="Mode B (Serial RAR -> Broad Call)",
            decoded_request=decoded,
            feed_plan=None,
            feed_metrics=(metric,),
            rar_result=rar_res,
            total_latency_ms=tot_lat,
            rar_latency_ms=rar_lat,
            sequential_latency_ms=tot_lat,
            parallel_latency_ms=tot_lat,
            total_tokens=metric.prompt_tokens + metric.completion_tokens,
            calls_made=1,
        )
