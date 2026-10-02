import threading

import numpy as np

from recording import MemoryRecorder


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
