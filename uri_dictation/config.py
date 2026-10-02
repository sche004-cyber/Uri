"""Configuration loading for the standalone URI Dictation helper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_HOTKEY = "ctrl+win"
DEFAULT_MINIMUM_HOLD_SECONDS = 0.3
DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class DictationConfig:
    hotkey: str = DEFAULT_HOTKEY
    minimum_hold_seconds: float = DEFAULT_MINIMUM_HOLD_SECONDS
    language: str = DEFAULT_LANGUAGE


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

    return DictationConfig(hotkey=hotkey.lower(), minimum_hold_seconds=float(minimum), language=language)


def load_dictionary(path: Path) -> dict[str, str]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if isinstance(key, str) and isinstance(value, str)}
