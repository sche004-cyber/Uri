"""Injectable foreground-window paste operation."""

from __future__ import annotations

import time
from typing import Any, Protocol


class Clipboard(Protocol):
    def snapshot(self) -> Any: ...
    def restore(self, snapshot: Any) -> None: ...
    def set_text(self, text: str) -> None: ...


class KeySender(Protocol):
    def paste(self) -> None: ...


class Toast(Protocol):
    def show(self, message: str) -> None: ...


def paste_text(text: str, clipboard: Clipboard, key_sender: KeySender, *, wait=time.sleep) -> bool:
    """Paste text, always restoring the user's prior clipboard contents."""
    if not text.strip():
        return False
    previous = clipboard.snapshot()
    try:
        clipboard.set_text(text)
        key_sender.paste()
        wait(0.15)
        return True
    finally:
        clipboard.restore(previous)
