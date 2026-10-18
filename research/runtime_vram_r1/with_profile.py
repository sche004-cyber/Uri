"""Hold one lab profile under the GPU lease while a command runs against it (URL in $URI_LAB_URL), then stop.

    python -I with_profile.py --name suite-c64k --ctx 65536 --vision off [--no-mtp] -- python model_lab/run_bench.py --url ...
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlab  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--ctx", type=int, default=65536)
    ap.add_argument("--vision", default="off")
    ap.add_argument("--no-mtp", action="store_true")
    ap.add_argument("--max-hold", type=float, default=3600)
    ap.add_argument("--cwd", default=str(HERE.parents[1]), help="working directory of the command (default repo root)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    prof = vlab.Profile(a.name, ctx=a.ctx, mtp=not a.no_mtp, vision=a.vision)
    run_dir = vlab.EVIDENCE / "with_profile" / f"{time.strftime('%Y%m%d-%H%M%S')}_{a.name}"
    srv = vlab.Server(prof, run_dir, max_hold_s=a.max_hold)
    rec = srv.record
    rc = None
    try:
        srv.start()
        env = dict(os.environ, URI_LAB_URL=srv.url)
        t0 = time.monotonic()
        # cwd = repo root: Core opens uri_workspace\capabilities_registry.json relative to the working directory (CWD-1)
        rc = subprocess.run([x.replace("{URL}", srv.url) for x in cmd], env=env, cwd=a.cwd).returncode
        rec["command_cwd"] = a.cwd
        rec["command"] = {"argv": cmd, "rc": rc, "seconds": round(time.monotonic() - t0, 1)}
        rec["after"] = srv.memory()
        rec["classification"] = "COMPLETED_WITH_RESULT" if rc == 0 else "FAILED"
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["classification"] = "FAILED"
    finally:
        srv.stop()
        vlab.save(run_dir, "with_profile", rec)
    print("WITH_PROFILE", rec["classification"], rc, run_dir, flush=True)
    return 0 if rec["classification"] == "COMPLETED_WITH_RESULT" else 1


if __name__ == "__main__":
    sys.exit(main())
