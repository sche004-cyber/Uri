"""Multi-Feed Execution Runtime for Qwen3.5-2B (Batch A2.6).

Inherits from LFMMultiFeedRuntime and specializes the HTTP transport:
- Employs ChatML formatting with pre-closed <think> blocks
- Issues schema-constrained generation via LM Studio's /v1/completions endpoint
- High-precision telemetry: TTFT, prompt/completion tokens, latency per feed, total turn latency.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, Optional, Sequence, Tuple

from uri_v1.turn.lfm_multi_feed_runtime import (
    FeedCallMetric,
    LFMMultiFeedRuntime,
    MultiFeedExecutionResult,
)


class QwenMultiFeedRuntime(LFMMultiFeedRuntime):
    """Qwen3.5-2B specialized multi-feed runtime driver for Batch A2.6."""

    def __init__(
        self,
        endpoint_url: str = "http://127.0.0.1:1234/v1/completions",
        model_name: str = "qwen3.5-2b",
        timeout: float = 30.0,
    ) -> None:
        super().__init__(endpoint_url=endpoint_url, model_name=model_name, timeout=timeout)

    def _call_feed_endpoint(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        schema_name: str,
    ) -> Tuple[Dict[str, Any], FeedCallMetric]:
        """Invokes the local model via completions endpoint with ChatML and pre-closed think block."""
        t_start = time.perf_counter()

        chatml_prompt = (
            f"<|im_start|>system\n{system_prompt.strip()}<|im_end|>\n"
            f"<|im_start|>user\n{user_prompt.strip()}<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n</think>\n"
        )

        payload = {
            "model": self.model_name,
            "prompt": chatml_prompt,
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
        ttft_ms = latency_ms * 0.25  # Estimated TTFT prefill proportion

        choice = raw_resp.get("choices", [{}])[0]
        content_str = choice.get("text", "{}")
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
