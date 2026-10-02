"""In-memory 16 kHz mono audio recording."""

from __future__ import annotations

import time
import threading
from collections import deque


LEVEL_HISTORY_SIZE = 120
LEVEL_GAIN = 8.0


def scaled_rms_level(block) -> float:
    """Return a clipped display level for one float32 input block."""
    import numpy as np

    if not len(block):
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float32))))
    return min(1.0, rms * LEVEL_GAIN)


class MemoryRecorder:
    def __init__(self) -> None:
        self._chunks = []
        self._chunks_lock = threading.Lock()
        self._levels = deque(maxlen=LEVEL_HISTORY_SIZE)
        self._stream = None
        self.started_at = 0.0

    def start(self) -> None:
        import sounddevice as sd

        with self._chunks_lock:
            self._chunks = []
            self._levels.clear()
        self.started_at = time.perf_counter()
        self._stream = sd.InputStream(
            samplerate=16000, channels=1, dtype="float32", blocksize=528, callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        level = scaled_rms_level(indata)
        with self._chunks_lock:
            self._chunks.append(indata.copy())
            self._levels.append(level)

    def levels(self, n: int) -> list[float]:
        """Return the latest display levels, left-padded with silence."""
        if n <= 0:
            return []
        with self._chunks_lock:
            recent = list(self._levels)[-n:]
        return [0.0] * (n - len(recent)) + recent

    def snapshot(self, max_seconds: float):
        """Return up to the latest ``max_seconds`` of captured mono audio."""
        import numpy as np

        sample_count = max(0, int(max_seconds * 16000))
        with self._chunks_lock:
            chunks = tuple(self._chunks)
        audio = np.concatenate(chunks, axis=0).reshape(-1) if chunks else np.empty((0,), dtype="float32")
        return audio[-sample_count:].astype("float32", copy=False) if sample_count else np.empty((0,), dtype="float32")

    def is_window_truncated(self, max_seconds: float) -> bool:
        with self._chunks_lock:
            return sum(chunk.shape[0] for chunk in self._chunks) > int(max_seconds * 16000)

    def stop(self):
        import numpy as np

        if self._stream is None:
            return np.empty((0,), dtype="float32"), 0.0
        self._stream.stop()
        self._stream.close()
        self._stream = None
        duration = time.perf_counter() - self.started_at
        with self._chunks_lock:
            chunks = tuple(self._chunks)
        audio = np.concatenate(chunks, axis=0).reshape(-1) if chunks else np.empty((0,), dtype="float32")
        return audio, duration
