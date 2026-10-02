"""In-memory 16 kHz mono audio recording."""

from __future__ import annotations

import time


class MemoryRecorder:
    def __init__(self) -> None:
        self._chunks = []
        self._stream = None
        self.started_at = 0.0

    def start(self) -> None:
        import sounddevice as sd

        self._chunks = []
        self.started_at = time.perf_counter()
        self._stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        self._chunks.append(indata.copy())

    def stop(self):
        import numpy as np

        if self._stream is None:
            return np.empty((0,), dtype="float32"), 0.0
        self._stream.stop()
        self._stream.close()
        self._stream = None
        duration = time.perf_counter() - self.started_at
        audio = np.concatenate(self._chunks, axis=0).reshape(-1) if self._chunks else np.empty((0,), dtype="float32")
        return audio, duration
