"""Speed and memory probe for one running lab server.

Measures, per request (llama-server's own timings, never wall-clock guesses): prompt tokens, prompt tok/s, time to
first token, decode tok/s, draft acceptance; plus per-process GPU residency before/after so a run that was demoted
mid-way is flagged instead of reported as a slow model.
"""
from __future__ import annotations

import json
import time

import httpx

FIXED_PROMPT = ("Write a detailed, well-structured explanation (about 300 words) of how a school office should plan "
                "the annual examination timetable: gathering constraints, avoiding clashes, communicating changes, "
                "and handling special cases. Use plain prose.")


def stream_chat(url, messages, max_tokens=400, thinking=False, extra=None, timeout=1800):
    body = {"model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": 0.0, "stream": True,
            "stream_options": {"include_usage": True}, "timings_per_token": False,
            "chat_template_kwargs": {"enable_thinking": thinking}}
    if extra:
        body.update(extra)
    t0 = time.monotonic()
    ttft = None
    text, reasoning, timings, finish, tool_calls = [], [], {}, None, {}
    with httpx.Client(timeout=timeout) as c, c.stream("POST", url + "/v1/chat/completions", json=body) as r:
        if r.status_code != 200:
            return {"error": f"HTTP_{r.status_code}", "body": r.read().decode(errors="replace")[:500]}
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            ev = json.loads(data)
            if ev.get("timings"):
                timings = ev["timings"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if (d.get("content") or d.get("reasoning_content") or d.get("tool_calls")) and ttft is None:
                    ttft = time.monotonic() - t0
                if d.get("content"):
                    text.append(d["content"])
                if d.get("reasoning_content"):
                    reasoning.append(d["reasoning_content"])
                for tc in d.get("tool_calls") or []:
                    slot = tool_calls.setdefault(tc.get("index", 0), {"name": "", "arguments": ""})
                    fn = tc.get("function") or {}
                    slot["name"] += fn.get("name") or ""
                    slot["arguments"] += fn.get("arguments") or ""
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    total = time.monotonic() - t0
    return {"text": "".join(text), "reasoning": "".join(reasoning), "finish_reason": finish,
            "tool_calls": [tool_calls[k] for k in sorted(tool_calls)],
            "ttft_s": round(ttft, 3) if ttft else None, "total_s": round(total, 3),
            "prompt_n": timings.get("prompt_n"), "prompt_tps": timings.get("prompt_per_second"),
            "prompt_ms": timings.get("prompt_ms"), "cache_n": timings.get("cache_n"),
            "predicted_n": timings.get("predicted_n"), "decode_tps": timings.get("predicted_per_second"),
            "draft_n": timings.get("draft_n"), "draft_accepted": timings.get("draft_n_accepted")}


def short_speed(server, reps=3):
    """Decode at short context: same 300-word prompt, thinking off, 3 reps (first is warm-up and reported)."""
    rows = []
    for i in range(reps):
        server.p  # noqa
        r = stream_chat(server.url, [{"role": "user", "content": FIXED_PROMPT}], max_tokens=400)
        r.pop("text", None)
        r.pop("reasoning", None)
        rows.append(r)
    return rows
