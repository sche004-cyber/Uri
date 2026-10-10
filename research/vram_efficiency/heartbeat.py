"""Crash-timestamp heartbeat (research only). INC-1 (2026-10-10): the host reset without a bugcheck during a GPU load
and nothing on disk recorded when. This appends one flushed + fsynced JSON line every --every seconds (wall time, CPU
%, RAM available, GPU adapter dedicated MiB, the largest GPU process), so the last line before a reset bounds the
reset time to one interval and shows the load at that moment. Read-only: it starts and stops nothing.

    python heartbeat.py <out.jsonl> [--every 10] [--minutes 120]
"""
import argparse
import json
import os
import subprocess
import time

import psutil

PS = ("$ErrorActionPreference='SilentlyContinue';"
      "$a=((Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples | Measure-Object CookedValue -Maximum).Maximum;"
      "$e=((Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage').CounterSamples | Measure-Object CookedValue -Sum).Sum;"
      "@{a=[int64]$a; e=[double]$e} | ConvertTo-Json -Compress")


def gpu():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", PS], capture_output=True, text=True, timeout=20,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        d = json.loads(out or "{}")
        return round((d.get("a") or 0) / 2**20, 1), round(d.get("e") or 0.0, 1)
    except Exception:
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--every", type=float, default=10.0)
    ap.add_argument("--minutes", type=float, default=120.0)
    a = ap.parse_args()
    end = time.time() + a.minutes * 60
    psutil.cpu_percent(None)
    with open(a.out, "a", encoding="utf-8") as f:
        while time.time() < end:
            ded, eng = gpu()
            rec = {"t": round(time.time(), 1), "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "cpu": psutil.cpu_percent(None), "ram_avail_mib": round(psutil.virtual_memory().available / 2**20),
                   "gpu_dedicated_mib": ded, "gpu_3d_util_sum": eng,
                   "llama": [p.info["pid"] for p in psutil.process_iter(["pid", "name"])
                             if (p.info["name"] or "").lower().startswith("llama-server")]}
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())
            time.sleep(a.every)


if __name__ == "__main__":
    main()
