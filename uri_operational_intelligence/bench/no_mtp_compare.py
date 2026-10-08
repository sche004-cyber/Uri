"""MTP vs no-MTP comparison on the OI task suite (research-only instance; Runtime v1 config is not changed).

Starts a SEPARATE, contained llama-server on port 18472 with the frozen argv minus the four MTP arguments
(`-md`, `--spec-type`, `--spec-draft-n-max`, `-otd`), runs the OI task suite against it, and stops it. Refuses to run
while the frozen instance (18470) is up: two resident copies do not fit in 16 GB.

    .venv\\Scripts\\python.exe -m uri_operational_intelligence.bench.no_mtp_compare --label no_mtp
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import uuid

from .. import runtime_v1 as R

PORT = 18472
MTP_ARGS = {"-md": 1, "--spec-type": 1, "--spec-draft-n-max": 1, "-otd": 1}


def no_mtp_argv(cfg):
    argv, out, skip = R.expected_argv(cfg), [], 0
    for a in argv:
        if skip:
            skip -= 1
            continue
        if a in MTP_ARGS:
            skip = MTP_ARGS[a]
            continue
        out.append(a)
    out[out.index("--port") + 1] = str(PORT)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="no_mtp")
    ap.add_argument("--parts", default="tasks,latency")
    a = ap.parse_args(argv)
    cfg = R.load_config()
    if R.RuntimeManager(cfg).status().state != R.STOPPED:
        sys.exit("FROZEN_INSTANCE_RUNNING: stop it first (two copies do not fit in VRAM)")
    if R.verify_artifacts(cfg)["overall"] != "MATCH":
        sys.exit("ARTIFACT_MISMATCH")
    from uri_supervisor.winproc import spawn_contained
    log = open(R.DEFAULT_STATE / "logs" / ("llama-server-nomtp-%s.log" % time.strftime("%Y%m%d-%H%M%S")), "wb")
    argv_ = no_mtp_argv(cfg)
    proc = spawn_contained(argv_, "uri-oi-nomtp-" + uuid.uuid4().hex, stdout=log, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL)
    url = "http://127.0.0.1:%d" % PORT
    try:
        t0 = time.monotonic()
        while time.monotonic() - t0 < 400:
            if proc.proc.poll() is not None:
                sys.exit("NOMTP_EXITED")
            if R.probe_server(url).get("health_status") == 200:
                break
            time.sleep(1)
        else:
            sys.exit("NOMTP_START_TIMEOUT")
        print("no-MTP instance ready in %.1f s; argv has -md: %s" % (time.monotonic() - t0, "-md" in argv_), flush=True)
        from . import reasoning
        reasoning.main(["--label", a.label, "--url", url, "--parts", a.parts])
    finally:
        print("STOPPED_CLEAN", proc.kill(), flush=True)
        proc.close()


if __name__ == "__main__":
    main()
