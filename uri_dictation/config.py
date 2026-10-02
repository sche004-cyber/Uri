"""Configuration loading for the standalone URI Dictation helper."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_HOTKEY = "ctrl+win"
DEFAULT_MINIMUM_HOLD_SECONDS = 0.3
DEFAULT_LANGUAGE = "en"
DEFAULT_PREVIEW_ENABLED = True
DEFAULT_PREVIEW_INTERVAL_SECONDS = 0.8
DEFAULT_PREVIEW_WINDOW_SECONDS = 15.0
DEFAULT_POLISH = True
DEFAULT_POLISH_MODEL = "qwen3.5:9b"
DEFAULT_POLISH_TIMEOUT_SECONDS = 8.0
DEFAULT_POLISH_NUM_CTX = 16384
DEFAULT_POLISH_KEEP_ALIVE = "30m"


@dataclass(frozen=True)
class DictationConfig:
    hotkey: str = DEFAULT_HOTKEY
    minimum_hold_seconds: float = DEFAULT_MINIMUM_HOLD_SECONDS
    language: str = DEFAULT_LANGUAGE
    preview_enabled: bool = DEFAULT_PREVIEW_ENABLED
    preview_interval_seconds: float = DEFAULT_PREVIEW_INTERVAL_SECONDS
    preview_window_seconds: float = DEFAULT_PREVIEW_WINDOW_SECONDS
    polish: bool = DEFAULT_POLISH
    polish_model: str = DEFAULT_POLISH_MODEL
    polish_timeout_s: float = DEFAULT_POLISH_TIMEOUT_SECONDS
    polish_num_ctx: int = DEFAULT_POLISH_NUM_CTX
    polish_keep_alive: str = DEFAULT_POLISH_KEEP_ALIVE


def load_config(path: Path) -> DictationConfig:
    """Load valid fields from JSON, retaining safe defaults for absent/bad fields."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}

    hotkey = raw.get("hotkey", DEFAULT_HOTKEY)
    if not isinstance(hotkey, str) or not hotkey.strip():
        hotkey = DEFAULT_HOTKEY

    minimum = raw.get("minimum_hold_seconds", DEFAULT_MINIMUM_HOLD_SECONDS)
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or minimum < 0:
        minimum = DEFAULT_MINIMUM_HOLD_SECONDS

    language = raw.get("language", DEFAULT_LANGUAGE)
    if not isinstance(language, str) or not language.strip():
        language = DEFAULT_LANGUAGE

    preview_enabled = raw.get("preview_enabled", DEFAULT_PREVIEW_ENABLED)
    if not isinstance(preview_enabled, bool):
        preview_enabled = DEFAULT_PREVIEW_ENABLED

    preview_interval = raw.get("preview_interval_seconds", DEFAULT_PREVIEW_INTERVAL_SECONDS)
    if isinstance(preview_interval, bool) or not isinstance(preview_interval, (int, float)) or preview_interval <= 0:
        preview_interval = DEFAULT_PREVIEW_INTERVAL_SECONDS

    preview_window = raw.get("preview_window_seconds", DEFAULT_PREVIEW_WINDOW_SECONDS)
    if isinstance(preview_window, bool) or not isinstance(preview_window, (int, float)) or preview_window <= 0:
        preview_window = DEFAULT_PREVIEW_WINDOW_SECONDS

    polish = raw.get("polish", DEFAULT_POLISH)
    if not isinstance(polish, bool):
        polish = DEFAULT_POLISH

    polish_model = raw.get("polish_model", DEFAULT_POLISH_MODEL)
    if not isinstance(polish_model, str) or not polish_model.strip():
        polish_model = DEFAULT_POLISH_MODEL
    else:
        polish_model = polish_model.strip()

    polish_timeout = raw.get("polish_timeout_s", DEFAULT_POLISH_TIMEOUT_SECONDS)
    if (isinstance(polish_timeout, bool) or not isinstance(polish_timeout, (int, float))
            or not math.isfinite(polish_timeout) or polish_timeout <= 0):
        polish_timeout = DEFAULT_POLISH_TIMEOUT_SECONDS

    polish_num_ctx = raw.get("polish_num_ctx", DEFAULT_POLISH_NUM_CTX)
    if isinstance(polish_num_ctx, bool) or not isinstance(polish_num_ctx, int) or polish_num_ctx <= 0:
        polish_num_ctx = DEFAULT_POLISH_NUM_CTX

    polish_keep_alive = raw.get("polish_keep_alive", DEFAULT_POLISH_KEEP_ALIVE)
    if not isinstance(polish_keep_alive, str) or not polish_keep_alive.strip():
        polish_keep_alive = DEFAULT_POLISH_KEEP_ALIVE
    else:
        polish_keep_alive = polish_keep_alive.strip()

    return DictationConfig(
        hotkey=hotkey.lower(), minimum_hold_seconds=float(minimum), language=language,
        preview_enabled=preview_enabled, preview_interval_seconds=float(preview_interval),
        preview_window_seconds=float(preview_window), polish=polish, polish_model=polish_model,
        polish_timeout_s=float(polish_timeout), polish_num_ctx=polish_num_ctx,
        polish_keep_alive=polish_keep_alive,
    )


def save_polish_enabled(path: Path, enabled: bool) -> None:
    """Persist only the runtime toggle, retaining all existing config keys."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    raw["polish"] = bool(enabled)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")


def load_dictionary(path: Path) -> dict[str, str]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if isinstance(key, str) and isinstance(value, str)}
