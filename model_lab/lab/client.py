"""Streaming OpenAI-compatible chat client that records first-token and total latency.

Works against llama-server and Ollama's /v1 endpoint. "First token" is the first streamed
delta of any kind (reasoning or answer); "first answer token" is the first answer delta, which
is what a user actually waits for when thinking is enabled.
"""
from __future__ import annotations

import json
import time

import httpx


class ChatResult(dict):
    @property
    def text(self):
        return self.get("content") or ""


def chat(base_url, messages, *, model="local", max_tokens=1024, temperature=0.0, top_p=None,
         top_k=None, json_schema=None, response_format=None, template_kwargs=None,
         extra=None, timeout=900.0, seed=7):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
            "stream": True, "seed": seed, "stream_options": {"include_usage": True}}
    if top_p is not None:
        body["top_p"] = top_p
    if top_k is not None:
        body["top_k"] = top_k
    if json_schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": json_schema, "strict": True}}
    elif response_format is not None:
        body["response_format"] = response_format
    if template_kwargs:
        template_kwargs = dict(template_kwargs)
        budget = template_kwargs.pop("_budget", None)
        if budget is not None:
            body["thinking_budget_tokens"] = budget   # per-request reasoning budget (llama-server)
        if template_kwargs:
            body["chat_template_kwargs"] = template_kwargs
    if extra:
        body.update(extra)
    t0 = time.monotonic()
    first_any = first_answer = None
    content, reasoning = [], []
    timings, usage, finish = None, None, None
    err = None
    try:
        with httpx.stream("POST", base_url.rstrip("/") + "/v1/chat/completions", json=body, timeout=timeout) as r:
            if r.status_code != 200:
                err = f"HTTP {r.status_code}: {r.read().decode(errors='replace')[:500]}"
            else:
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    if chunk.get("timings"):
                        timings = chunk["timings"]
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    for ch in chunk.get("choices") or []:
                        d = ch.get("delta") or {}
                        rc = d.get("reasoning_content") or d.get("reasoning")
                        c = d.get("content")
                        now = time.monotonic()
                        if (rc or c) and first_any is None:
                            first_any = now
                        if rc:
                            reasoning.append(rc)
                        if c:
                            if first_answer is None:
                                first_answer = now
                            content.append(c)
                        if ch.get("finish_reason"):
                            finish = ch["finish_reason"]
    except Exception as exc:  # network / timeout
        err = f"{type(exc).__name__}: {exc}"
    t1 = time.monotonic()
    res = ChatResult(content="".join(content), reasoning="".join(reasoning), finish_reason=finish, error=err,
                     ttft_s=round(first_any - t0, 3) if first_any else None,
                     ttfa_s=round(first_answer - t0, 3) if first_answer else None,
                     total_s=round(t1 - t0, 3), timings=timings, usage=usage)
    if timings:
        res["prompt_tokens"] = timings.get("prompt_n")
        res["cached_tokens"] = timings.get("cache_n")
        res["prefill_tps"] = round(timings.get("prompt_per_second") or 0, 1)
        res["gen_tokens"] = timings.get("predicted_n")
        res["gen_tps"] = round(timings.get("predicted_per_second") or 0, 1)
    elif usage:
        res["prompt_tokens"] = usage.get("prompt_tokens")
        res["gen_tokens"] = usage.get("completion_tokens")
    return res


def extract_json(text):
    """Lenient JSON extraction for scoring (fences, leading prose). Returns (obj|None, strict_ok)."""
    t = (text or "").strip()
    try:
        return json.loads(t), True
    except ValueError:
        pass
    if t.startswith("```"):
        t2 = t.strip("`")
        t2 = t2[4:] if t2.lower().startswith("json") else t2
        try:
            return json.loads(t2.strip()), False
        except ValueError:
            pass
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(t[s:e + 1]), False
        except ValueError:
            pass
    return None, False

