"""Brain health for the working system UI (WS hardening T3): one truthful state with its evidence.

States (UI contract, WS hardening plan H-AC5):
  READY        Runtime v1 answers, its identity and artifacts match, and the latest speed evidence is healthy.
  BUSY         as READY, and a turn is running.
  DEGRADED     the instance answers but the latest speed evidence is below the threshold (the measured demoted
               state, PERF-W1 / OI-PERF-1), or the speed check failed.
  UNAVAILABLE  no usable Brain: stopped, failed, waiting for the GPU, identity problem, or not selected.
  RECOVERING   the Brain host is releasing memory, starting, loading or measuring.

Evidence sources, all existing: the accepted `RuntimeManager.status()` readiness (identity + artifacts), the Brain
host report (`scripts/ws_brain_host.py`: GPU lease, contention, release wait, calibration), and the accepted
`PerfMonitor` fed with llama-server's own timings of real turns. Nothing here is estimated: every number names its
source, and a state without evidence says UNKNOWN in its reasons instead of guessing.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from .perf_monitor import DEGRADED_DECODE_TPS

# Host link: the Brain host writes its report into the client's control/oi directory; the worker writes explicit
# requests there. Both files live inside the client root, so the guarded worker needs no extra permission.
REPORT_SCHEMA = "uri.ws.brain_host.v1"
REQUEST_SCHEMA = "uri.ws.brain_request.v1"
REPORT_FILE, REQUEST_FILE = "brain_host.json", "brain_request.json"
ACTIONS = ("restart", "stop", "start")
# The Brain host rewrites its report at least this often (heartbeat). A report older than HOST_STALE_S whose process
# cannot be inspected is evidence of a dead host; a fresh one is evidence of a live host.
HOST_HEARTBEAT_S = 15.0
HOST_STALE_S = 90.0

READY, BUSY, DEGRADED, UNAVAILABLE, RECOVERING = "READY", "BUSY", "DEGRADED", "UNAVAILABLE", "RECOVERING"
HOST_RECOVERING = {"STARTING", "LOADING", "CALIBRATING", "RELEASE_WAIT", "STOPPING", "STARTING_HOST"}
HOST_WAITING = {"WAITING_FOR_GPU", "WAITING_FOR_LEASE"}
THRESHOLD_SOURCE = ("decode below %.0f tok/s: healthy instances measured 96-157 tok/s (freeze record) and 110-131 "
                    "(WS runs); demoted instances 24-42 tok/s (Adaptive Runtime R1, OI-PERF-1, WS PERF-W1)"
                    % DEGRADED_DECODE_TPS)


def backend(cfg) -> dict:
    rt, model = cfg.get("runtime", {}), cfg.get("model", {})
    return {"provider": "Runtime v1 (local)", "engine": rt.get("engine"), "model_id": model.get("id"),
            "model_repo": model.get("repo"), "context": rt.get("ctx"), "vision": bool(rt.get("vision_enabled")),
            "speculative": "MTP draft" if model.get("mtp_draft") else None,
            "thinking_tiers": sorted((cfg.get("tiers") or {}).keys())}


def assess(*, readiness: dict, host: dict | None, host_alive: bool, perf: dict, busy: bool, selected: dict,
           cfg: dict, now=None, server=None) -> dict:
    """readiness: Readiness.to_dict(); host: the host report (or None); perf: PerfMonitor.assess(sample=False) for the
    current server process; selected: the bridge's Brain selection."""
    now = now or time.time()
    reasons, options = [], []
    r_state = (readiness or {}).get("state", "UNKNOWN")
    h = host if (host and host_alive) else None
    h_state = h.get("state") if h else None
    cal = (h or {}).get("calibration") or {}
    # The host's calibration counts only for the server process readiness just verified (Codex H-r5).
    if cal and not _same_instance(cal, server):
        cal = {}
    out = {"readiness": r_state, "busy": bool(busy), "backend": backend(cfg), "selected": selected,
           "host": {"running": bool(h), "state": h_state, "explain": h and h.get("explain"),
                    "updated_age_s": round(now - h["updated_at"], 1) if h and h.get("updated_at") else None,
                    "override": h and h.get("override")},
           "performance": {"threshold_tps": DEGRADED_DECODE_TPS, "threshold_source": THRESHOLD_SOURCE,
                           "calibration_tps": cal.get("decode_tps"), "calibration_t": cal.get("t"),
                           "calibration_error": cal.get("error"),
                           "decode_tps_median": perf.get("decode_tps_median"),
                           "decode_samples": perf.get("decode_samples", 0)},
           "gpu": _gpu(h)}

    if selected.get("provider") != "llamacpp-runtime-v1":
        out.update(state=UNAVAILABLE, reasons=["NOT_SELECTED"], recovery_options=["select_runtime_v1"],
                   explain="No Brain is selected; open questions are not answered by a model.")
        return out

    if r_state == "READY":
        slow, evidence = _speed(perf, cal)
        if h_state in HOST_RECOVERING:
            state = RECOVERING
            reasons.append("HOST_" + h_state)
        elif slow is True:
            state = DEGRADED
            reasons.append("DECODE_THROUGHPUT_LOW" if evidence != "calibration_failed" else "CALIBRATION_FAILED")
        else:
            state = BUSY if busy else READY
            if slow is None:
                reasons.append("SPEED_NOT_MEASURED")
        if state == DEGRADED:
            if h:
                options.append("restart_brain")
            if any(not c.get("role") for c in out["gpu"].get("consumers") or []):
                options.append("close_gpu_apps")
            options.append("continue_slow")
        out["performance"]["evidence"] = evidence
        explain = (h and h.get("explain")) if state != DEGRADED or evidence == "calibration" else None
        if state == DEGRADED and not explain:
            explain = ("The Brain is running slowly (%s tok/s over the last %d answers; healthy is above %.0f)."
                       % (perf.get("decode_tps_median"), perf.get("decode_samples", 0), DEGRADED_DECODE_TPS))
        out.update(state=state, reasons=reasons, recovery_options=options,
                   explain=explain or ("Brain ready." if state in (READY, BUSY) else None))
        return out

    if r_state in ("STARTING", "LOADING") or h_state in HOST_RECOVERING:
        out.update(state=RECOVERING, reasons=["RUNTIME_" + r_state] + (["HOST_" + h_state] if h_state else []),
                   recovery_options=[], explain=(h and h.get("explain")) or "The Brain is starting.")
        return out
    if h_state in HOST_WAITING:
        out.update(state=UNAVAILABLE, reasons=[h.get("detail") or h_state],
                   recovery_options=["close_gpu_apps", "wait"] if h_state == "WAITING_FOR_GPU" else ["wait"],
                   explain=h.get("explain"))
        return out
    reasons.append("RUNTIME_" + r_state)
    if (readiness or {}).get("detail"):
        reasons.append(str(readiness["detail"]))
    if h:
        options.append("start_brain" if h_state == "STOPPED" else "restart_brain")
    else:
        options.append("start_from_launcher")
    explain = (h and h.get("explain")) or ("The Brain is not running. Start it with the URI Working System launcher."
                                            if not h else None)
    out.update(state=UNAVAILABLE, reasons=reasons, recovery_options=options, explain=explain)
    return out


def _same_instance(cal, server) -> bool:
    if not server or server.get("pid") is None or cal.get("server_pid") != server.get("pid"):
        return False
    a, b = cal.get("server_create_time"), server.get("create_time")
    return a is not None and b is not None and abs(float(a) - float(b)) < 1.0


def _speed(perf, cal):
    """(slow?, evidence). Real-turn evidence (>= 3 samples of the current instance) is newer than the calibration
    taken when the instance became READY, so it decides when present."""
    if perf.get("decode_samples", 0) >= 3 and perf.get("decode_tps_median") is not None:
        return perf["decode_tps_median"] < DEGRADED_DECODE_TPS, "turns"
    if cal.get("decode_tps"):
        return cal["decode_tps"] < DEGRADED_DECODE_TPS, "calibration"
    if cal.get("error"):
        return True, "calibration_failed"
    return None, "none"


def _gpu(h):
    if not h:
        return {"measured": False}
    res, gpu = h.get("residency") or {}, h.get("gpu") or {}
    fit = gpu.get("fit") or {}
    return {"measured": bool(res or fit), "verdict_at_start": fit.get("verdict"), "verdict_now": res.get("verdict_now"),
            "free_mib_at_start": fit.get("free_mib"), "server_dedicated_mib": res.get("dedicated_mib"),
            "server_non_local_mib": res.get("non_local_mib"), "others_mib": res.get("others_mib", fit.get("others_mib")),
            "consumers": res.get("consumers") or fit.get("consumers") or [], "sampled_t": res.get("t"),
            "release": h.get("release_measurement"), "lease": h.get("lease")}


def read_host_report(report_dir) -> tuple[dict | None, bool]:
    """(report, host_alive). Alive means the report's host process still exists with the recorded start time."""
    try:
        rep = json.loads((Path(report_dir) / REPORT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, False
    if not isinstance(rep, dict) or rep.get("schema") != REPORT_SCHEMA:
        return None, False
    return rep, host_alive(rep)


def host_alive(rep, now=None) -> bool:
    """Positive evidence only (Codex H-r3): the process is gone or its start time differs (pid reused) means dead;
    a successful inspection means alive. When the process cannot be inspected (access denied, transient error), the
    heartbeat decides: fresh means alive, stale means dead."""
    try:
        import psutil
        p = psutil.Process(int(rep.get("host_pid")))
        return p.is_running() and abs(p.create_time() - float(rep.get("host_started") or 0)) < 5.0
    except (ImportError, ValueError, TypeError):
        pass
    except Exception as exc:
        if type(exc).__name__ in ("NoSuchProcess", "ZombieProcess"):
            return False
    beat = max(float(rep.get("updated_at") or 0), float(rep.get("heartbeat_at") or 0))
    return ((now or time.time()) - beat) < HOST_STALE_S


def write_host_request(report_dir, action) -> dict:
    """One explicit request for the Brain host (restart / stop / start)."""
    if action not in ACTIONS:
        raise ValueError("ACTION_INVALID")
    req = {"schema": REQUEST_SCHEMA, "id": str(uuid.uuid4()), "action": action, "requested_at": round(time.time(), 3)}
    path = Path(report_dir) / REQUEST_FILE
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(req), encoding="utf-8")
    os.replace(tmp, path)
    return req
