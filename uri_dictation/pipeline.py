"""Injectable dictation processing pipeline, independent of Windows UI libraries."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from cleanup import cleanup_transcript
from integration import Clipboard, KeySender, Toast, paste_text
from timing import append_timing


class Transcriber(Protocol):
    device: str

    def transcribe(self, audio) -> str: ...


class DictationPipeline:
    def __init__(
        self,
        transcriber: Transcriber,
        clipboard: Clipboard,
        key_sender: KeySender,
        toast: Toast,
        dictionary: Mapping[str, str],
        timing_path: Path,
        *,
        clock: Callable[[], float] = time.perf_counter,
        wait: Callable[[float], None] = time.sleep,
        error_logger: Callable[[BaseException], None] | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._clipboard = clipboard
        self._key_sender = key_sender
        self._toast = toast
        self._dictionary = dictionary
        self._timing_path = timing_path
        self._clock = clock
        self._wait = wait
        self._error_logger = error_logger or (lambda _exc: None)

    def process(self, audio, audio_seconds: float) -> bool:
        stt_start = self._clock()
        try:
            transcript = self._transcriber.transcribe(audio)
        except Exception as exc:
            self._error_logger(exc)
            self._append_timing(audio_seconds, (self._clock() - stt_start) * 1000, 0, 0)
            self._toast.show("Dictation failed")
            return False
        stt_ms = (self._clock() - stt_start) * 1000

        cleanup_start = self._clock()
        text = cleanup_transcript(transcript, self._dictionary)
        cleanup_ms = (self._clock() - cleanup_start) * 1000
        if not text:
            self._append_timing(audio_seconds, stt_ms, cleanup_ms, 0)
            self._toast.show("No speech detected")
            return False

        paste_start = self._clock()
        try:
            paste_text(text, self._clipboard, self._key_sender, wait=self._wait)
        except Exception as exc:
            self._error_logger(exc)
            self._append_timing(audio_seconds, stt_ms, cleanup_ms, (self._clock() - paste_start) * 1000)
            self._toast.show("Could not paste dictation")
            return False
        self._append_timing(audio_seconds, stt_ms, cleanup_ms, (self._clock() - paste_start) * 1000)
        return True

    def _append_timing(self, audio_seconds: float, stt_ms: float, cleanup_ms: float, paste_ms: float) -> None:
        append_timing(
            self._timing_path,
            audio_seconds=audio_seconds,
            stt_ms=stt_ms,
            cleanup_ms=cleanup_ms,
            paste_ms=paste_ms,
            device=getattr(self._transcriber, "label", self._transcriber.device),
        )
