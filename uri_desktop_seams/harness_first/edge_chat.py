"""Edge text specialist for social turns: a natural, short reply from a local
<=1B model, with URI-owned validation.

The model sees only the user's social message and a bounded instruction. It
gets no tools, no history, no files and no memory. URI validates the reply
(length, no claims of having done anything, no links, no reasoning traces)
and falls back to a deterministic line when the model is slow, unreachable or
its reply fails validation. Transport: local Ollama on loopback only.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

DEFAULT_MODEL = os.environ.get("URI_HARNESS_EDGE_CHAT_MODEL", "qwen3:0.6b")
OLLAMA_URL = os.environ.get("URI_HARNESS_OLLAMA_URL", "http://127.0.0.1:11434")
TIMEOUT_S = float(os.environ.get("URI_HARNESS_EDGE_CHAT_TIMEOUT_S", "4"))

SYSTEM = (
    "You are URI, a friendly desktop assistant that helps with office work: documents, files, email and "
    "research. The user sent a short social message. Reply in one or two short, warm, natural sentences, "
    "in the user's language. Do not claim you did anything, do not mention tools, files or emails unless "
    "the user did, do not ask more than one question, no lists, no emojis."
)

INTENT_HINT = {
    "greeting": "The user is greeting you.",
    "thanks": "The user is thanking you.",
    "farewell": "The user is saying goodbye.",
    "acknowledgement": "The user is acknowledging what you said.",
    "about_uri": "The user is asking who you are or what you can do.",
}

FALLBACK = {
    "greeting": "Hello! What can I help you with today?",
    "thanks": "You're welcome.",
    "farewell": "Goodbye, talk soon.",
    "acknowledgement": "Okay.",
    "about_uri": "I'm URI, your desktop assistant for documents, files, email and research.",
}

_CLAIM = re.compile(r"\bI(?:'ve| have)? (?:sent|saved|created|deleted|searched|opened|uploaded|emailed|drafted|"
                    r"scheduled|booked|read|found|checked|updated|fixed)\b", re.I)
_BAD = re.compile(r"https?://|```|<think>|</think>|\{|\}|\[|\]|\bas an ai\b", re.I)


@dataclass
class ChatResult:
    text: str
    source: str            # "edge_model" or "deterministic_fallback"
    model: Optional[str]
    latency_ms: float
    reject_reason: Optional[str] = None
    prompt_chars: int = 0
    eval_count: Optional[int] = None


def validate(reply: str) -> Optional[str]:
    """Return a rejection reason, or None when the reply is acceptable."""
    r = (reply or "").strip()
    if not r:
        return "empty"
    if len(r) > 240:
        return "too_long"
    if len(re.findall(r"[.!?]+(?:\s|$)", r)) > 3:
        return "too_many_sentences"
    if _BAD.search(r):
        return "forbidden_content"
    if _CLAIM.search(r):
        return "claims_action"
    if r.count("?") > 1:
        return "too_many_questions"
    return None


_EMOJI = re.compile("[🀀-🫿☀-➿️]")


def _clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    text = re.sub(r"\s{2,}", " ", _EMOJI.sub("", text))   # formatting only: the instruction forbids emojis
    return text.strip().strip('"').strip()


def generate(user_text: str, intent: str, model: Optional[str] = None, timeout_s: float = TIMEOUT_S) -> ChatResult:
    model = model or DEFAULT_MODEL
    t0 = time.perf_counter()
    body = {"model": model, "stream": False, "keep_alive": "30m", "think": False,
            "messages": [{"role": "system", "content": SYSTEM + " " + INTENT_HINT.get(intent, "")},
                         {"role": "user", "content": user_text}],
            "options": {"temperature": 0.7, "num_predict": 60, "num_ctx": 1024}}
    prompt_chars = len(SYSTEM) + len(INTENT_HINT.get(intent, "")) + len(user_text)
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # loopback only (OLLAMA_URL)
            raw = json.loads(resp.read().decode("utf-8"))
        text = _clean((raw.get("message") or {}).get("content", ""))
        reason = validate(text)
        ms = (time.perf_counter() - t0) * 1000
        if reason is None:
            return ChatResult(text, "edge_model", model, ms, None, prompt_chars, raw.get("eval_count"))
        return ChatResult(FALLBACK.get(intent, "Okay."), "deterministic_fallback", model, ms, reason, prompt_chars,
                          raw.get("eval_count"))
    except Exception as exc:
        return ChatResult(FALLBACK.get(intent, "Okay."), "deterministic_fallback", model,
                          (time.perf_counter() - t0) * 1000, f"transport:{type(exc).__name__}", prompt_chars)
