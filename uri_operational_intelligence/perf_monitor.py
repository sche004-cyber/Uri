"""Runtime v1 performance health: VRAM residency and observed decode throughput.

Finding OI-PERF-1 (2026-10-08, measured): with the frozen configuration the server's working set can be partly evicted
from dedicated VRAM to shared system memory while it keeps running (dedicated 15,534 -> 14,845 MiB, shared
1,101 -> 1,895 MiB) and decode silently drops ~3x (107-117 -> 35-42 tok/s) with no error. A restart restored it.
This module detects that state; it never restarts anything itself (a restart interrupts the user and is a user/owner
action surfaced as a recovery option).

Signals:
  * residency: per-process GPU dedicated / shared memory of the llama-server pid (Windows performance counters),
    compared with the sample taken when the instance became READY;
  * throughput: rolling median of llama-server's own predicted_per_second for calls that generated >= 64 tokens.
"""
from __future__ import annotations

import statistics
import subprocess
import threading
import time
from collections import deque

DEGRADED_DECODE_TPS = 60.0        # qualified range 96-157 tok/s (freeze record section 6); 3x slowdown measured ~36-42
RESIDENCY_DROP_MIB = 300.0
MIN_TOKENS = 64

HEALTHY, DEGRADED, UNKNOWN = "HEALTHY", "DEGRADED", "UNKNOWN"


def gpu_process_memory(pid, timeout=20):
    """(dedicated_mib, shared_mib) for one process, or (None, None). Windows-only, ~1-2 s (PowerShell counters)."""
    if not pid:
        return None, None
    ps = ("$d=(Get-Counter '\\GPU Process Memory(pid_%d_*)\\Dedicated Usage' -ErrorAction SilentlyContinue).CounterSamples;"
          "$s=(Get-Counter '\\GPU Process Memory(pid_%d_*)\\Shared Usage' -ErrorAction SilentlyContinue).CounterSamples;"
          "'{0} {1}' -f ($d | Measure-Object CookedValue -Sum).Sum, ($s | Measure-Object CookedValue -Sum).Sum") % (pid, pid)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=timeout,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.split()
        return round(float(out[0]) / 2**20, 1), round(float(out[1]) / 2**20, 1)
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None, None


class PerfMonitor:
    def __init__(self, window=12, sampler=gpu_process_memory):
        self._tps = deque(maxlen=window)
        self._lock = threading.Lock()
        self.sampler = sampler
        self.baseline = None        # {"pid", "dedicated_mib", "shared_mib", "t"}
        self.last_sample = None

    def record(self, timings: dict):
        """Feed llama-server timings of a finished call."""
        n, tps = (timings or {}).get("predicted_n"), (timings or {}).get("predicted_per_second")
        if n and tps and n >= MIN_TOKENS:
            with self._lock:
                self._tps.append(float(tps))

    def set_baseline(self, pid):
        d, s = self.sampler(pid)
        self.baseline = {"pid": pid, "dedicated_mib": d, "shared_mib": s, "t": time.time()} if d is not None else None
        return self.baseline

    def sample(self, pid):
        d, s = self.sampler(pid)
        self.last_sample = {"pid": pid, "dedicated_mib": d, "shared_mib": s, "t": time.time()}
        return self.last_sample

    def assess(self, pid=None, sample=True) -> dict:
        with self._lock:
            tps = list(self._tps)
        reasons = []
        out = {"state": UNKNOWN, "reasons": reasons}
        if tps:
            med = statistics.median(tps)
            out["decode_tps_median"] = round(med, 1)
            out["decode_samples"] = len(tps)
            if len(tps) >= 3 and med < DEGRADED_DECODE_TPS:
                reasons.append("DECODE_THROUGHPUT_LOW")
        if sample and pid and self.baseline and self.baseline.get("pid") == pid:
            cur = self.sample(pid)
            out["residency"] = {"baseline": self.baseline, "current": cur}
            if cur["dedicated_mib"] is not None and self.baseline["dedicated_mib"] is not None:
                drop = self.baseline["dedicated_mib"] - cur["dedicated_mib"]
                out["residency"]["dedicated_drop_mib"] = round(drop, 1)
                if drop >= RESIDENCY_DROP_MIB:
                    reasons.append("VRAM_RESIDENCY_EVICTED")
        if reasons:
            out["state"] = DEGRADED
            out["recovery_options"] = ["restart_brain", "close_gpu_heavy_apps", "continue_slow"]
        elif tps or out.get("residency"):
            out["state"] = HEALTHY
        return out
