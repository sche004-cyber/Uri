"""Development host: start (or attach to) the single Runtime v1 instance and hold it for a bounded time.

    .venv\\Scripts\\python.exe -m uri_operational_intelligence.host --minutes 120

The server lives in this process' kill-on-close job: it stops when this host exits, when the stop file
`work/oi/state/runtime_v1.stop` appears, or after --minutes. Other processes (tests, benchmarks, the dev server)
ATTACH to it; they never start a second instance. Development use only; not a production service.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from .runtime_v1 import READY, RuntimeManager


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--full-verify", action="store_true")
    a = ap.parse_args(argv)
    mgr = RuntimeManager()
    stop_file = mgr.state_dir / "runtime_v1.stop"
    stop_file.unlink(missing_ok=True)
    t0 = time.monotonic()
    r = mgr.ensure_ready(full_verify=a.full_verify, on_state=lambda s: print("STATE", s, flush=True))
    print(json.dumps({"readiness": r.to_dict(), "owned": mgr.owns_instance, "load_seconds": mgr.load_seconds,
                      "ensure_ready_seconds": round(time.monotonic() - t0, 1)}, default=str), flush=True)
    if r.state != READY or not mgr.owns_instance:
        mgr.stop()
        return 0 if r.state == READY else 2
    deadline = time.monotonic() + a.minutes * 60
    try:
        while time.monotonic() < deadline and not stop_file.exists():
            if mgr._contained.proc.poll() is not None:
                print("SERVER_EXITED", mgr._contained.proc.returncode, flush=True)
                return 3
            time.sleep(1.0)
    finally:
        print("STOPPED_CLEAN", mgr.stop(), flush=True)
        stop_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
