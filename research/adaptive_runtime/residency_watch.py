"""Residency watchdog prototype (research): samples the GPU memory split of every llama-server
process (local = VRAM, non-local = system memory over PCIe) plus adapter totals, and flags the
"demoted working set" condition that collapses decode throughput. Read-only; never acts.

  python residency_watch.py --seconds 600 --interval 3 --out evidence/residency_<tag>.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import time
from pathlib import Path

import psutil

BS = chr(92)
Q = ("$s=(Get-Counter '@@GPU Process Memory(*)@@Local Usage','@@GPU Process Memory(*)@@Non Local Usage',"
     "'@@GPU Adapter Memory(*)@@Dedicated Usage','@@GPU Adapter Memory(*)@@Shared Usage').CounterSamples;"
     "$s | ForEach-Object { $_.Path + '=' + [int]($_.CookedValue/1MB) }").replace("@@", BS)


def sample():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", Q], capture_output=True, text=True, timeout=30).stdout
    rows = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        path, v = line.rsplit("=", 1)
        rows[path.strip().lower()] = int(v)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold-mib", type=int, default=256, help="non-local MiB on a llama-server that counts as demotion")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t_end = time.monotonic() + args.seconds
    with open(out, "w", encoding="utf-8") as f:
        f.write("ts,pid,local_mib,nonlocal_mib,adapter_dedicated_mib,adapter_shared_mib,flag\n")
        while time.monotonic() < t_end:
            pids = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("llama-server")}
            rows = sample()
            ded = max((v for k, v in rows.items() if "gpu adapter memory" in k and "dedicated" in k), default=0)
            shr = max((v for k, v in rows.items() if "gpu adapter memory" in k and "shared" in k), default=0)
            ts = dt.datetime.now().isoformat(timespec="seconds")
            for pid in sorted(pids):
                loc = sum(v for k, v in rows.items() if f"pid_{pid}_" in k and "local usage" in k and "non local" not in k)
                non = sum(v for k, v in rows.items() if f"pid_{pid}_" in k and "non local usage" in k)
                flag = "DEMOTED" if non >= args.threshold_mib else "ok"
                f.write(f"{ts},{pid},{loc},{non},{ded},{shr},{flag}\n")
                print(f"{ts} pid={pid} local={loc} nonlocal={non} adapter_ded={ded} adapter_shared={shr} {flag}", flush=True)
            if not pids:
                f.write(f"{ts},-,0,0,{ded},{shr},idle\n")
            f.flush()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
