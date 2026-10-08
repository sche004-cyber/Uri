"""Clock seam. Wall time is for recording/validity only; monotonic time only for in-epoch leases."""
import time


class Clock:
    def wall_us(self) -> int:
        return time.time_ns() // 1000

    def mono_ns(self) -> int:
        return time.monotonic_ns()


class FakeClock(Clock):
    """Deterministic clock for tests; wall and monotonic are independently controllable."""

    def __init__(self, wall_us=1_800_000_000_000_000, mono_ns=5_000_000_000_000):
        self._wall, self._mono = wall_us, mono_ns

    def wall_us(self):
        return self._wall

    def mono_ns(self):
        return self._mono

    def advance(self, seconds):
        self._wall += int(seconds * 1_000_000)
        self._mono += int(seconds * 1_000_000_000)

    def set_wall(self, wall_us):  # wall-clock step (NTP/manual); monotonic unaffected
        self._wall = wall_us

    def set_mono(self, mono_ns):  # simulates a new boot/epoch origin
        self._mono = mono_ns
