"""Adapter for Qwen3.5-0.8B candidate via Ollama."""
from __future__ import annotations

import time
from typing import Any, Dict, Tuple
import httpx

from .prompt_builder import build_system_prompt, build_user_prompt


class Qwen08BCandidate:
    def __init__(self, endpoint: str = "http://127.0.0.1:11434/api/generate", model: str = "qwen3.5:0.8b"):
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
            "format": "json",
            "raw": True,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 150
            }
        }
        t0 = time.perf_counter()
        res = httpx.post(self.endpoint, json=payload, timeout=20.0)
        dt = (time.perf_counter() - t0) * 1000
        data = res.json()
        raw_output = data.get("response", "").strip()

        metrics = {
            "inference_duration_ms": round(dt, 1),
            "eval_duration_ms": round(data.get("eval_duration", 0) / 1e6, 1),
            "prompt_eval_duration_ms": round(data.get("prompt_eval_duration", 0) / 1e6, 1),
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "eval_tokens": data.get("eval_count", 0),
        }
        return raw_output, metrics
