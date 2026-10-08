"""Adapter for Qwen3.5-9B resident Main Brain candidate via LM Studio."""
from __future__ import annotations

import time
from typing import Any, Dict, Tuple
import httpx

from .prompt_builder import build_system_prompt, build_user_prompt


class Qwen9BResidentCandidate:
    def __init__(self, endpoint: str = "http://127.0.0.1:1234/v1/completions", model: str = "qwen3.5-9b"):
        self.endpoint = endpoint
        self.model = model

    def run_case(self, case: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        sys_p = build_system_prompt()
        user_p = build_user_prompt(case)
        full_prompt = (
            f"<|im_start|>system\n{sys_p}\n<|im_end|>\n"
            f"<|im_start|>user\n{user_p}\n<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n</think>\n"
        )
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "temperature": 0.0,
            "max_tokens": 150,
            "stop": ["<|im_end|>"]
        }
        t0 = time.perf_counter()
        res = httpx.post(self.endpoint, json=payload, timeout=30.0)
        dt = (time.perf_counter() - t0) * 1000
        data = res.json()
        choices = data.get("choices", [])
        raw_output = choices[0].get("text", "").strip() if choices else ""
        usage = data.get("usage", {})

        metrics = {
            "inference_duration_ms": round(dt, 1),
            "eval_duration_ms": round(dt, 1),
            "prompt_eval_duration_ms": 0.0,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "eval_tokens": usage.get("completion_tokens", 0),
        }
        return raw_output, metrics
