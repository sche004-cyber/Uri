"""Privacy-preserving per-utterance timing log."""

from __future__ import annotations

import json
from pathlib import Path


def append_timing(path: Path, *, audio_seconds: float, stt_ms: float, cleanup_ms: float, paste_ms: float, device: str, polish_ms: float, polish_model: str | None, polish_used: bool, polish_fallback_reason: str | None, polish_escalated: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "audio_s": round(audio_seconds, 3),
        "stt_ms": round(stt_ms, 1),
        "cleanup_ms": round(cleanup_ms, 1),
        "polish_ms": round(polish_ms, 1),
        "paste_ms": round(paste_ms, 1),
        "device": device,
        "polish_model": polish_model,
        "polish_used": polish_used,
        "polish_fallback_reason": polish_fallback_reason,
        "polish_escalated": polish_escalated,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
