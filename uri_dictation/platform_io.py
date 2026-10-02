"""Windows adapters; external UI libraries are imported only when used."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClipboardSnapshot:
    formats: tuple[tuple[int, Any], ...]
    was_empty: bool


class WindowsClipboard:
    def _open(self) -> None:
        import win32clipboard

        last_error = None
        for _ in range(4):
            try:
                win32clipboard.OpenClipboard()
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.03)
        raise last_error  # type: ignore[misc]

    def snapshot(self) -> ClipboardSnapshot:
        import win32clipboard

        self._open()
        try:
            formats: list[tuple[int, Any]] = []
            saw_format = False
            format_id = 0
            while True:
                format_id = win32clipboard.EnumClipboardFormats(format_id)
                if not format_id:
                    break
                saw_format = True
                try:
                    formats.append((format_id, win32clipboard.GetClipboardData(format_id)))
                except Exception:
                    # Some application-defined formats cannot safely be copied.
                    continue
            return ClipboardSnapshot(tuple(formats), was_empty=not saw_format)
        finally:
            win32clipboard.CloseClipboard()

    def set_text(self, text: str) -> None:
        import win32clipboard

        self._open()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

    def restore(self, snapshot: ClipboardSnapshot) -> None:
        import win32clipboard

        self._open()
        try:
            win32clipboard.EmptyClipboard()
            for format_id, value in snapshot.formats:
                try:
                    win32clipboard.SetClipboardData(format_id, value)
                except Exception:
                    continue
        finally:
            win32clipboard.CloseClipboard()


class PynputKeySender:
    def __init__(self) -> None:
        from pynput.keyboard import Controller

        self._keyboard = Controller()

    def paste(self) -> None:
        from pynput.keyboard import Key

        with self._keyboard.pressed(Key.ctrl):
            self._keyboard.press("v")
            self._keyboard.release("v")

    def mark_hotkey_pressed(self) -> None:
        """Prevent a Ctrl+Win release from being interpreted as a bare Win press."""
        from pynput.keyboard import KeyCode

        key = KeyCode.from_vk(0xFF)
        self._keyboard.press(key)
        self._keyboard.release(key)
