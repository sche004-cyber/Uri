import threading

import numpy as np
import pytest

from recording import LEVEL_HISTORY_SIZE, MemoryRecorder, scaled_rms_level


def test_scaled_rms_level_is_silent_at_zero_and_clips_loud_audio():
    assert scaled_rms_level(np.zeros((10, 1), dtype="float32")) == 0.0
    assert scaled_rms_level(np.full((10, 1), .05, dtype="float32")) == pytest.approx(.4)
    assert scaled_rms_level(np.ones((10, 1), dtype="float32")) == 1.0


def test_levels_are_bounded_padded_and_reset_when_recording_starts(monkeypatch):
    recorder = MemoryRecorder()
    for value in range(LEVEL_HISTORY_SIZE + 4):
        recorder._levels.append(float(value))
    assert recorder.levels(3) == [121.0, 122.0, 123.0]
    recorder._levels.clear()
    recorder._levels.extend([.2, .4])
    assert recorder.levels(4) == [0.0, 0.0, .2, .4]

    class Stream:
        def start(self): pass
    stream_options = {}
    monkeypatch.setattr("sounddevice.InputStream", lambda **kwargs: (stream_options.update(kwargs), Stream())[1])
    recorder.start()
    assert stream_options["blocksize"] == 528
    assert recorder.levels(4) == [0.0] * 4


def test_snapshot_keeps_only_latest_requested_audio_during_concurrent_callbacks():
    recorder = MemoryRecorder()
    recorder._callback(np.arange(16000, dtype="float32").reshape(-1, 1), 16000, None, None)
    done = threading.Event()

    def append_more():
        for _ in range(20):
            recorder._callback(np.ones((100, 1), dtype="float32"), 100, None, None)
        done.set()

    thread = threading.Thread(target=append_more)
    thread.start()
    while not done.is_set():
        snapshot = recorder.snapshot(.1)
        assert snapshot.dtype == np.float32
        assert len(snapshot) <= 1600
    thread.join()
    assert np.all(recorder.snapshot(.1) == 1)
