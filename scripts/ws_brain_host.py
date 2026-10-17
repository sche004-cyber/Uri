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
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from uri_operational_intelligence import gpu_lease as G  # noqa: E402
from uri_operational_intelligence import runtime_v1 as R  # noqa: E402
from uri_operational_intelligence import runtime_profiles as RP  # noqa: E402
from uri_operational_intelligence.brain_health import (ACTIONS, HOST_HEARTBEAT_S, REPORT_FILE,  # noqa: E402
                                                       REPORT_SCHEMA, REQUEST_FILE, REQUEST_SCHEMA, write_host_request)
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
# Residency alert: the Brain's system-memory share grew by half a demotion block since its calibration (measured live
# 2026-10-09: another session opened ~1 GB of GPU apps after load; non-local rose 1.1 -> 2.75 GB and decode fell from
# 141 to 27-38 tok/s). The host only REPORTS it; it sends no request of its own to the Brain after the start
# calibration, so it never competes with a user turn (Codex H-r7/r8). The slowness verdict comes from the timings of
# real answers (accepted PerfMonitor in the worker).
RESIDENCY_ALERT_GROWTH_MIB = 512.0


class Host:
    def __init__(self, report_dir: Path, *, minutes: float, override: bool, cfg=None, state_dir=None,
                 census=G.census, lease_dir=None, now=time.time):
        self.report_dirs = [Path(report_dir)]
        self.cfg = cfg or R.load_config()
        # Measured device request of this config: the frozen constant, or a resource profile's own measurement.
        self.required_mib = RP.cfg_required_mib(self.cfg, G.RUNTIME_V1_DEVICE_MIB)
        self.state_dir = Path(state_dir or R.DEFAULT_STATE)
        self.report_dirs.append(self.state_dir)
        self.deadline = time.monotonic() + minutes * 60
        self.override = override
        self.census, self.lease_dir, self.now = census, lease_dir, now
        self.lease = None
        self.mgr = None
        self.report = {"schema": REPORT_SCHEMA, "host_pid": os.getpid(), "host_started": round(now(), 3),
                       "state": "STARTING_HOST", "history": [], "override": None,
                       "profile": RP.describe(self.cfg)}
        if override:
            self.report["override"] = {"by": "--override-contention", "at": round(now(), 3)}
        self.last_request_id = None
        self.stopped_at = None          # wall time the last server stop finished (release measurement)
        self.last_contended = None      # monotonic time the GPU was last seen CONTENDED (quiet window)
        self.loaders = []               # (thread, manager) of loads stopped before they finished (Codex H-r1 F1)
        self.stop_requested = False     # a stop request was consumed (possibly inside a wait or a load)
        self._write_lock = threading.Lock()
        self._done = threading.Event()
        seen = G.last_contention(lease_dir)       # also seen by an earlier host or another URI GPU workload
        if seen is not None and 0 <= now() - seen < QUIET_S:
            self.last_contended = time.monotonic() - (now() - seen)
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
        with self._write_lock:            # the load thread reports too
            for d in self.report_dirs:
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    R._atomic_json(d / REPORT_FILE, self.report)
                except OSError:
                    pass

    def _heartbeat(self):
        """The report is rewritten at least every HOST_HEARTBEAT_S, whatever the host is doing (liveness evidence)."""
        while not self._done.wait(HOST_HEARTBEAT_S):
            self.report["heartbeat_at"] = round(self.now(), 3)
            self.write()

    def record_request(self, rid, result):
        reqs = dict(self.report.get("requests") or {})
        reqs[rid] = result
        self.report["requests"] = dict(list(reqs.items())[-16:])

    # ---- control --------------------------------------------------------------------------------------------
    def should_exit(self):
        return time.monotonic() >= self.deadline or self.stop_file.exists()

    def take_request(self, only=None):
        """The next unprocessed request, used once. With `only`, any other action is left for later."""
        path = self.report_dirs[0] / REQUEST_FILE
        try:
            req = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        rid = req.get("id") if isinstance(req, dict) else None
        if not isinstance(req, dict) or req.get("schema") != REQUEST_SCHEMA or rid == self.last_request_id:
            return None
        if only is not None and req.get("action") != only:
            return None
        self.last_request_id = rid
        age = self.now() - float(req.get("requested_at") or 0)
        if req.get("action") not in ACTIONS or not isinstance(rid, str) or not (0 <= age <= REQUEST_MAX_AGE_S):
            self.record_request(rid, "IGNORED_INVALID_OR_STALE")
            self.report["last_request"] = {"id": rid, "action": req.get("action"), "result": "IGNORED_INVALID_OR_STALE",
                                           "t": round(self.now(), 3)}
            self.write()
            return None
        self.record_request(rid, "ACCEPTED")
        self.report["last_request"] = {"id": rid, "action": req["action"], "result": "ACCEPTED", "t": round(self.now(), 3)}
        self.write()
        if req["action"] == "stop":
            self.stop_requested = True
        return req["action"]

    def finish_request(self):
        """Mark the accepted request as done, with the state it left. The worker opens its turn gate on this marker
        only (Codex H-r2), never on an ACCEPTED request or an unreadable report."""
        lr = self.report.get("last_request") or {}
        if lr.get("result") == "ACCEPTED":
            lr.update(result="DONE", done_state=self.report.get("state"), t_done=round(self.now(), 3))
            self.report["last_request"] = lr
            self.record_request(lr.get("id"), "DONE")
            self.write()

    # ---- GPU ------------------------------------------------------------------------------------------------
    def owners(self):
        return G.owner_pids(os.getpid())

    def acquire_lease(self):
        while not self.should_exit():
            try:
                self.lease = G.acquire("runtime_v1_brain", label="WS Brain host", session=str(REPO),
                                       expected_vram_mib=self.required_mib, override=self.report["override"],
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

    def reap_loaders(self):
        """Kill anything a stopped load spawned after the stop, and forget loaders whose thread has ended. True when
        none is left. The accepted ensure_ready() may spawn after a stop that arrived before its spawn."""
        alive = []
        for t, m in self.loaders:
            if m._contained is not None:
                m.stop()
            if t.is_alive():
                alive.append((t, m))
        self.loaders = alive
        return not alive

    def release_lease(self, reason, at_exit=False):
        # Never hand the GPU to another workload while a stopped load could still spawn Runtime v1 (Codex H-r2 F1):
        # wait for the loader to end, however long. When the host itself is exiting, the lease is not released
        # explicitly while a loader lives: process exit closes the lock handle and the kill-on-close job together.
        while not self.reap_loaders():
            if at_exit or self.should_exit():
                self.report["lease"] = {"held": True, "released_by": "process exit (loader still alive)"}
                return
            self.set("STOPPING", detail="WAITING_FOR_STOPPED_LOAD",
                     explain="Waiting for the stopped Brain load to end before freeing the GPU.")
            time.sleep(0.5)
        if self.lease is not None:
            self.lease.release(reason)
            self.lease = None
        self.report["lease"] = {"held": False}

    def wait_for_gpu(self):
        """Contention and release wait. Returns True when a start may proceed."""
        t0 = self.now()
        while not self.should_exit():
            c = self.census()
            fit = G.assess_fit(c, owners=self.owners(), required_mib=self.required_mib)
            gpu = {"fit": fit, "explain": G.explain(fit), "census_t": c.get("t"), "census_s": c.get("sample_s")}
            unattr = fit.get("unattributed_mib") or 0.0
            if self.stopped_at is not None:
                gpu["since_stop_s"] = round(self.now() - self.stopped_at, 1)
            if fit["verdict"] == G.UNKNOWN and not self.override:
                # Cannot measure: wait and retry (Codex H-r1 F3). Only the owner's override starts blind.
                self.set("WAITING_FOR_GPU", detail="GPU_UNMEASURED", gpu=gpu,
                         explain="GPU memory cannot be measured right now (%s); URI waits." % fit.get("reason"))
            elif unattr >= RELEASE_UNATTRIBUTED_MIB and not self.override:
                # Release not finished: keep waiting; after the timeout say so (Codex H-r1 F5), never start anyway.
                late = self.now() - t0 >= RELEASE_TIMEOUT_S
                self.set("WAITING_FOR_GPU" if late else "RELEASE_WAIT",
                         detail="VRAM_RELEASE_TIMEOUT" if late else "VRAM_STILL_RELEASING",
                         explain=("GPU memory (%.0f MB) has not been released after %.0f s. URI keeps waiting." % (unattr, self.now() - t0))
                         if late else "Waiting for GPU memory from the previous Brain to be released (%.0f MB left)." % unattr,
                         gpu=gpu)
            elif fit["verdict"] == G.CONTENDED and not self.override:
                self.last_contended = time.monotonic()
                G.record_contention(self.lease_dir, fit)
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
            a = self.take_request(only="stop")
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
        # The accepted ensure_ready() blocks for the whole load. It runs on a thread so a stop (stop file or request)
        # is honored at once: the owned job is killed and the host does not wait for the load to finish.
        box = {}
        t = threading.Thread(target=lambda: box.update(r=self.mgr.ensure_ready(
            on_state=lambda s: self.set(s) if s in (R.STARTING, R.LOADING) else None)), daemon=True)
        t.start()
        while t.is_alive():
            if self.should_exit() or self.take_request(only="stop") == "stop":
                self.mgr.stop()
                self.loaders.append((t, self.mgr))
                self.mgr = None
                self.stopped_at = self.now()
                self.set("STOPPED", detail="STOPPED_DURING_LOAD", explain="The Brain load was stopped.")
                return False
            t.join(0.5)
        r = box["r"]
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

    def residency_alert(self, now_res):
        """Record (or clear) the alert that GPU memory was taken from the Brain after its calibration."""
        cal = self.report.get("calibration") or {}
        before = (cal.get("residency") or {}).get("non_local_mib")
        now = (now_res or {}).get("non_local_mib")
        if before is None or now is None:
            # Unknown sample: keep what was last measured (Codex H-r9); only a measured value clears the alert.
            return "residency_alert" in self.report
        if now - before >= RESIDENCY_ALERT_GROWTH_MIB:
            self.report["residency_alert"] = {"growth_mib": round(now - before, 1), "non_local_mib": now,
                                              "t": (now_res or {}).get("t"), "server_pid": cal.get("server_pid"),
                                              "server_create_time": cal.get("server_create_time")}
            return True
        self.report.pop("residency_alert", None)
        return False

    def calibrate(self, pid, reason="START", timeout=120.0):
        import httpx
        self.set("CALIBRATING", detail=None, explain="Measuring Brain speed.")
        cal = {"t": round(self.now(), 3), "tokens": CALIBRATION_TOKENS, "threshold_tps": DEGRADED_TPS,
               # The instance this measurement belongs to (Codex H-r5): health uses it only for this process.
               "server_pid": pid, "server_create_time": R._create_time(pid), "reason": reason}
        try:
            with httpx.Client(base_url=R.base_url(self.cfg), timeout=httpx.Timeout(timeout, connect=3.0)) as c:
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
        fit = (G.assess_fit(c, owners=self.owners(), required_mib=self.required_mib) if c.get("ok")
               else {"verdict": G.UNKNOWN})
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
        self.report.pop("calibration", None)          # it described the instance that just stopped
        self.report.pop("residency_alert", None)

    # ---- main loop ------------------------------------------------------------------------------------------
    def run(self):
        threading.Thread(target=self._heartbeat, name="host-heartbeat", daemon=True).start()
        try:
            if not self.acquire_lease():
                self.set("STOPPED", detail="EXIT_BEFORE_LEASE")
                return 0
            self.start_brain()
            last_res = time.monotonic()
            while not self.should_exit():
                self.reap_loaders()
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
                if action == "stop" or self.stop_requested:       # also a stop consumed inside a wait or a load
                    self.stop_requested = False
                    self.stop_brain()
                    self.release_lease("stop requested")
                    self.set("STOPPED", detail="STOP_REQUESTED", explain="The Brain is stopped. Use Start Brain.")
                if action is not None or self.report.get("last_request", {}).get("result") == "ACCEPTED":
                    self.finish_request()
                if (self.mgr is not None and self.mgr.owns_instance and time.monotonic() - last_res >= RESIDENCY_EVERY_S):
                    pid = self.report.get("server", {}).get("pid")
                    self.residency_alert(self.residency(pid))
                    if self.lease is not None:
                        self.lease.heartbeat()
                    self.write()
                    last_res = time.monotonic()
                time.sleep(0.5)
        finally:
            self.stop_brain()
            self.release_lease("host exit", at_exit=True)
            self.set("STOPPED", detail="HOST_EXIT", explain="The Brain host has exited.")
            self.finish_request()
            self._done.set()
            self.stop_file.unlink(missing_ok=True)
        return 0


write_request = write_host_request          # the worker's writer (brain_health), re-exported for tools and tests


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--minutes", type=float, default=240.0)
    ap.add_argument("--override-contention", action="store_true",
                    help="owner-authorized: start next to foreign GPU consumers (recorded; result calibrated)")
    ap.add_argument("--profile", default=None,
                    help="research candidate (URI-RUNTIME-VRAM-R1): ctx,vision,mtp e.g. 65536,off,1; default = frozen")
    a = ap.parse_args(argv)
    cfg = None
    if a.profile:
        ctx, vision, mtp = a.profile.split(",")
        cfg = RP.derive_config(R.load_config(), int(ctx), vision, mtp in ("1", "on", "true"))
    return Host(Path(a.report_dir), minutes=a.minutes, override=a.override_contention, cfg=cfg).run()


if __name__ == "__main__":
    sys.exit(main())
