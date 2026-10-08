"""Working System Brain host (WS hardening T2): holds the single Runtime v1 instance for the working system.

It replaces `python -m uri_operational_intelligence.host` in the WS launcher and reuses the accepted
`RuntimeManager` unchanged (frozen argv, pinned artifacts, kill-on-close job, identity checks). It adds:

  1. the machine-wide URI GPU lease (`gpu_lease`): no second URI GPU workload (another Brain host, a benchmark that
     uses the lease) can run next to this Brain, and this host waits while another holds it;
  2. a contention check before every start: when foreign GPU processes leave less memory than the measured request,
     the host WAITS and explains who holds the memory. It never stops, suspends or signals another process. Only the
     owner's explicit `--override-contention` starts anyway (recorded, and the result is calibrated like any start);
  3. a release wait before a (re)start: memory that is still committed on the adapter but no longer attributed to a
     process (a server that just exited) must fall below the threshold first. This is a measured signal, not a delay;
  4. a calibration decode right after READY, so the first status already says whether this instance is healthy or
     in the demoted slow state (PERF-W1);
  5. a report file and a request file in the client's `control/oi/` directory: the guarded worker reads the report
     and writes restart / stop / start requests without any change to its guard. Requests are explicit user actions;
     the worker refuses them while a turn runs.

    python scripts/ws_brain_host.py --report-dir <client_root>/control/oi --minutes 240 [--override-contention]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from uri_operational_intelligence import gpu_lease as G  # noqa: E402
from uri_operational_intelligence import runtime_v1 as R  # noqa: E402
from uri_operational_intelligence.brain_health import (ACTIONS, REPORT_FILE, REPORT_SCHEMA, REQUEST_FILE,  # noqa: E402
                                                       REQUEST_SCHEMA, write_host_request)
REQUEST_MAX_AGE_S = 120.0

# Calibration: one fixed decode right after READY. The threshold is the accepted OI value (perf_monitor
# DEGRADED_DECODE_TPS = 60), which lies in the measured gap between healthy instances (96-157 tok/s, freeze record;
# 110-131 in WS runs) and demoted ones (24-42 tok/s: Adaptive Runtime R1 25, OI-PERF-1 35-42, WS PERF-W1 27).
CALIBRATION_PROMPT = "Here is a numbered list of forty everyday household objects, one per line:\n1."
CALIBRATION_TOKENS = 160
DEGRADED_TPS = 60.0
# Release wait: adapter memory not attributed to any process (a just-exited server's allocations) must drop below
# this before a start. Half a 1 GiB demotion block.
RELEASE_UNATTRIBUTED_MIB = 512.0
RELEASE_TIMEOUT_S = 300.0
# Quiet window: after the GPU was seen CONTENDED, it must stay clear this long before a start. A benchmark campaign in
# another session stops and starts servers back to back with gaps of seconds to tens of seconds; starting in such a
# gap would take the GPU from under it. 180 s equals the Adaptive Runtime session's own GPU-owner guard.
QUIET_S = 180.0
GPU_POLL_S = 10.0
RESIDENCY_EVERY_S = 60.0


class Host:
    def __init__(self, report_dir: Path, *, minutes: float, override: bool, cfg=None, state_dir=None,
                 census=G.census, lease_dir=None, now=time.time):
        self.report_dirs = [Path(report_dir)]
        self.cfg = cfg or R.load_config()
        self.state_dir = Path(state_dir or R.DEFAULT_STATE)
        self.report_dirs.append(self.state_dir)
        self.deadline = time.monotonic() + minutes * 60
        self.override = override
        self.census, self.lease_dir, self.now = census, lease_dir, now
        self.lease = None
        self.mgr = None
        self.report = {"schema": REPORT_SCHEMA, "host_pid": os.getpid(), "host_started": round(now(), 3),
                       "state": "STARTING_HOST", "history": [], "override": None}
        if override:
            self.report["override"] = {"by": "--override-contention", "at": round(now(), 3)}
        self.last_request_id = None
        self.stopped_at = None          # wall time the last server stop finished (release measurement)
        self.last_contended = None      # monotonic time the GPU was last seen CONTENDED (quiet window)
        self.stop_file = self.state_dir / "runtime_v1.stop"

    # ---- report ---------------------------------------------------------------------------------------------
    def set(self, state, **fields):
        prev = (self.report.get("state"), self.report.get("detail"))
        self.report.update(fields, state=state, updated_at=round(self.now(), 3))
        if prev != (state, self.report.get("detail")):
            self.report["history"] = (self.report["history"] + [{"t": round(self.now(), 3), "state": state,
                                                                  "detail": fields.get("detail")}])[-20:]
            print("STATE", state, fields.get("detail") or "", flush=True)
        self.write()

    def write(self):
        for d in self.report_dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
                R._atomic_json(d / REPORT_FILE, self.report)
            except OSError:
                pass

    # ---- control --------------------------------------------------------------------------------------------
    def should_exit(self):
        return time.monotonic() >= self.deadline or self.stop_file.exists()

    def take_request(self):
        path = self.report_dirs[0] / REQUEST_FILE
        try:
            req = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        rid = req.get("id")
        if not isinstance(req, dict) or req.get("schema") != REQUEST_SCHEMA or rid == self.last_request_id:
            return None
        self.last_request_id = rid
        age = self.now() - float(req.get("requested_at") or 0)
        if req.get("action") not in ACTIONS or not isinstance(rid, str) or not (0 <= age <= REQUEST_MAX_AGE_S):
            self.report["last_request"] = {"id": rid, "action": req.get("action"), "result": "IGNORED_INVALID_OR_STALE",
                                           "t": round(self.now(), 3)}
            self.write()
            return None
        self.report["last_request"] = {"id": rid, "action": req["action"], "result": "ACCEPTED", "t": round(self.now(), 3)}
        self.write()
        return req["action"]

    # ---- GPU ------------------------------------------------------------------------------------------------
    def owners(self):
        return G.owner_pids(os.getpid())

    def acquire_lease(self):
        while not self.should_exit():
            try:
                self.lease = G.acquire("runtime_v1_brain", label="WS Brain host", session=str(REPO),
                                       expected_vram_mib=G.RUNTIME_V1_DEVICE_MIB, override=self.report["override"],
                                       directory=self.lease_dir)
                self.report["lease"] = {"held": True, "acquired_at": self.lease.record["acquired_at"],
                                        "recovered_from": self.lease.record.get("recovered_from")}
                return True
            except G.GpuBusy as exc:
                h = exc.holder or {}
                self.set("WAITING_FOR_LEASE", detail="GPU_LEASE_HELD",
                         explain="Another URI GPU workload holds the GPU: %s (%s, pid %s). URI waits; it does not stop it."
                         % (h.get("label") or h.get("purpose") or "unknown", h.get("process"), h.get("pid")),
                         lease={"held": False, "holder": h})
                if self.wait_or_request(5.0) == "stop":
                    return False
        return False

    def release_lease(self, reason):
        if self.lease is not None:
            self.lease.release(reason)
            self.lease = None
        self.report["lease"] = {"held": False}

    def wait_for_gpu(self):
        """Contention and release wait. Returns True when a start may proceed."""
        t0 = self.now()
        while not self.should_exit():
            c = self.census()
            fit = G.assess_fit(c, owners=self.owners())
            gpu = {"fit": fit, "explain": G.explain(fit), "census_t": c.get("t"), "census_s": c.get("sample_s")}
            unattr = fit.get("unattributed_mib") or 0.0
            if self.stopped_at is not None:
                gpu["since_stop_s"] = round(self.now() - self.stopped_at, 1)
            if fit["verdict"] == G.UNKNOWN:
                # Cannot measure: proceed (the calibration still classifies the instance) but say so.
                self.set("STARTING", detail="GPU_UNMEASURED", gpu=gpu)
                return True
            if unattr >= RELEASE_UNATTRIBUTED_MIB and self.now() - t0 < RELEASE_TIMEOUT_S:
                self.set("RELEASE_WAIT", detail="VRAM_STILL_RELEASING",
                         explain="Waiting for GPU memory from the previous Brain to be released (%.0f MB left)." % unattr,
                         gpu=gpu)
            elif fit["verdict"] == G.CONTENDED and not self.override:
                self.last_contended = time.monotonic()
                self.set("WAITING_FOR_GPU", detail="GPU_CONTENDED", explain=gpu["explain"], gpu=gpu)
            elif (not self.override and self.last_contended is not None
                  and time.monotonic() - self.last_contended < QUIET_S):
                left = QUIET_S - (time.monotonic() - self.last_contended)
                self.set("WAITING_FOR_GPU", detail="GPU_QUIET_WINDOW", gpu=gpu,
                         explain="The GPU just became free. URI waits %.0f s more to be sure another job has finished." % left)
            else:
                if self.stopped_at is not None:
                    self.report["release_measurement"] = {"since_stop_s": gpu.get("since_stop_s"),
                                                          "unattributed_mib": unattr, "verdict": fit["verdict"]}
                self.report["gpu"] = gpu
                return True
            if self.wait_or_request(GPU_POLL_S) == "stop":
                return False
        return False

    def wait_or_request(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self.should_exit():
            a = self.take_request()
            if a == "stop":
                return "stop"
            time.sleep(0.5)
        return None

    # ---- Brain ----------------------------------------------------------------------------------------------
    def start_brain(self):
        if not self.wait_for_gpu():
            return False
        self.mgr = R.RuntimeManager(self.cfg, state_dir=self.state_dir)
        self.set("STARTING", detail=None, explain="Starting the Brain (Runtime v1).")
        r = self.mgr.ensure_ready(on_state=lambda s: self.set(s) if s in (R.STARTING, R.LOADING) else None)
        if r.state != R.READY:
            self.set("FAILED", detail=r.detail or r.state, explain="The Brain did not become ready (%s)." % (r.detail or r.state),
                     server={"pid": r.pid, "owned": self.mgr.owns_instance})
            self.mgr.stop()
            self.mgr = None
            self.stopped_at = self.now()
            return False
        self.report["server"] = {"pid": r.pid, "owned": self.mgr.owns_instance, "load_seconds": self.mgr.load_seconds,
                                 "model_id": r.model_id}
        if not self.mgr.owns_instance:
            # An authorized instance this host did not start (attach). It is never stopped from here.
            self.set("READY", detail="ATTACHED", explain="Attached to an already running Runtime v1 instance.")
            return True
        self.calibrate(r.pid)
        return True

    def calibrate(self, pid):
        import httpx
        self.set("CALIBRATING", detail=None, explain="Measuring Brain speed.")
        cal = {"t": round(self.now(), 3), "tokens": CALIBRATION_TOKENS, "threshold_tps": DEGRADED_TPS}
        try:
            with httpx.Client(base_url=R.base_url(self.cfg), timeout=httpx.Timeout(120.0, connect=3.0)) as c:
                res = c.post("/completion", json={"prompt": CALIBRATION_PROMPT, "n_predict": CALIBRATION_TOKENS,
                                                  "temperature": 0, "cache_prompt": False, "ignore_eos": True})
                tim = (res.json() or {}).get("timings") or {}
            cal.update(decode_tps=round(float(tim.get("predicted_per_second") or 0), 1),
                       predicted_n=tim.get("predicted_n"), prompt_ms=tim.get("prompt_ms"))
        except Exception as exc:          # a failed probe is reported, never hidden
            cal.update(error=type(exc).__name__)
        res_mem = self.residency(pid)
        cal["residency"] = res_mem
        self.report["calibration"] = cal
        if cal.get("decode_tps") and cal["decode_tps"] >= DEGRADED_TPS:
            self.set("READY", detail=None, explain="Brain ready (%.0f tok/s)." % cal["decode_tps"])
        elif cal.get("decode_tps"):
            self.set("DEGRADED", detail="DECODE_THROUGHPUT_LOW",
                     explain="The Brain is running slowly (%.0f tok/s, healthy is above %.0f). GPU memory was short "
                             "when it loaded. Restart it when the GPU is free." % (cal["decode_tps"], DEGRADED_TPS))
        else:
            self.set("DEGRADED", detail="CALIBRATION_FAILED", explain="The Brain answered READY but the speed check failed.")

    def residency(self, pid):
        c = self.census()
        me = next((p for p in c.get("processes", []) if p["pid"] == pid), None) if c.get("ok") else None
        fit = G.assess_fit(c, owners=self.owners()) if c.get("ok") else {"verdict": G.UNKNOWN}
        out = {"t": c.get("t"), "dedicated_mib": me and me["dedicated_mib"], "non_local_mib": me and me["non_local_mib"],
               "others_mib": fit.get("others_mib"), "verdict_now": fit.get("verdict"),
               "consumers": fit.get("consumers")}
        self.report["residency"] = out
        return out

    def stop_brain(self):
        if self.mgr is None:
            return
        self.set("STOPPING", detail=None, explain="Stopping the Brain.")
        ok = self.mgr.stop() if self.mgr.owns_instance else False
        self.mgr = None
        self.stopped_at = self.now()
        self.report["server"] = {"pid": None, "owned": False, "stopped_clean": ok}

    # ---- main loop ------------------------------------------------------------------------------------------
    def run(self):
        try:
            if not self.acquire_lease():
                self.set("STOPPED", detail="EXIT_BEFORE_LEASE")
                return 0
            self.start_brain()
            last_res = time.monotonic()
            while not self.should_exit():
                if self.mgr is not None and self.mgr._contained is not None and self.mgr._contained.proc.poll() is not None:
                    code = self.mgr._contained.proc.returncode
                    self.mgr.stop()
                    self.mgr = None
                    self.stopped_at = self.now()
                    self.set("FAILED", detail="LOCAL_BRAIN_EXITED:%s" % code,
                             explain="The Brain process exited unexpectedly. Use Restart Brain.")
                action = self.take_request()
                if action == "restart" or (action == "start" and self.mgr is None):
                    self.stop_brain()
                    if self.lease is None and not self.acquire_lease():
                        break
                    self.start_brain()
                elif action == "stop":
                    self.stop_brain()
                    self.release_lease("stop requested")
                    self.set("STOPPED", detail="STOP_REQUESTED", explain="The Brain is stopped. Use Start Brain.")
                if (self.mgr is not None and self.mgr.owns_instance and time.monotonic() - last_res >= RESIDENCY_EVERY_S):
                    self.residency(self.report.get("server", {}).get("pid"))
                    if self.lease is not None:
                        self.lease.heartbeat()
                    self.write()
                    last_res = time.monotonic()
                time.sleep(0.5)
        finally:
            self.stop_brain()
            self.release_lease("host exit")
            self.set("STOPPED", detail="HOST_EXIT", explain="The Brain host has exited.")
            self.stop_file.unlink(missing_ok=True)
        return 0


write_request = write_host_request          # the worker's writer (brain_health), re-exported for tools and tests


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--minutes", type=float, default=240.0)
    ap.add_argument("--override-contention", action="store_true",
                    help="owner-authorized: start next to foreign GPU consumers (recorded; result calibrated)")
    a = ap.parse_args(argv)
    return Host(Path(a.report_dir), minutes=a.minutes, override=a.override_contention).run()


if __name__ == "__main__":
    sys.exit(main())
