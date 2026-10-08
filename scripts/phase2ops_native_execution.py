"""Phase 2 UI/operations: drive the REAL native executor through the NEW execution lifecycle frames
(`execution_begin` -> polled `execution_status` -> terminal) over the Phase 2D composition (persisted NATIVE record,
Phase 2 policy file, SupervisedWorkerService, SupervisedTurnRunner, SupervisorBridge, uri_supervisor, REAL CLI), and
then a REAL mid-run cancellation of the same executor (`execution_cancel` while the attempt is RUNNING).

Same authentication posture as Phase 2C/2D: the CLI's own run-scoped login in the shell environment is used as-is.
Nothing here logs in, reads/copies/forwards credentials, edits any configuration, or touches repository files. Writes:
fresh paired-client/server state under <repo>/work/c1 (git-ignored) and the evidence directory. Approval is programmatic
(this harness echoes the digests the worker returned), never a human on the UI.

Usage:  python scripts/phase2ops_native_execution.py --provider codex_cli --model gpt-6-sol --evidence <dir>
        python scripts/phase2ops_native_execution.py --provider claude_code --evidence <dir>      (expected: fail closed)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uri_supervisor import winproc  # noqa: E402
from uri_supervisor.executors import BUILTIN_SPECS  # noqa: E402
from uri_supervisor_bridge.execution import TERMINAL_STATES  # noqa: E402
from uri_supervisor_bridge.qualification import build_record, native_auth_probe, write_record  # noqa: E402
from uri_supervisor_bridge.worker_service import SupervisedWorkerService  # noqa: E402

DETERMINISTIC = ("server_local_model", "uri-deterministic", None)
SHORT_TEXT = "use the harness to write the single word PONG into pong.txt"
LONG_TEXT = ("use the harness to write a detailed essay of at least 2000 words about durable task supervisors, "
             "fencing tokens and write-ahead ledgers into essay.txt")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jdump(obj):
    return json.dumps(obj, indent=1, sort_keys=True, default=str)


def frames_turn(service, text, selection, log):
    session = str(uuid.uuid4())
    start = {"command": "turn_start", "session_id": session, "text": text, "reasoning": selection}
    log.append({"sent": start, "at": time.time()})
    turn = service.handle("turn_start", start)
    log.append({"received": {k: turn.get(k) for k in ("state", "turn_id", "code", "approval_request", "execution_proposal")}, "at": time.time()})
    return turn


def begin(service, turn, log):
    cmd = {"command": "execution_begin", "turn_id": turn["turn_id"], "approval_digest": turn["approval_request"]["approval_digest"],
           "proposal_digest": turn["execution_proposal"]["proposal_digest"]}
    log.append({"sent": cmd, "at": time.time()})
    out = service.handle("execution_begin", cmd)
    log.append({"received": out, "at": time.time()})
    return out["execution_id"]


def poll(service, eid, until, timeout, transitions):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        st = service.handle("execution_status", {"command": "execution_status", "execution_id": eid})
        key = (st["state"], (st.get("ledger") or {}).get("task", {}) and (st.get("ledger") or {}).get("task", {}).get("state"))
        if key != last:
            transitions.append({"at": time.time(), "state": st["state"], "ledger_task": key[1], "reason": st.get("reason")})
            last = key
        if until(st):
            return st
        time.sleep(0.25)
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=sorted(BUILTIN_SPECS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--inactivity", type=float, default=180)
    ap.add_argument("--cancel-after", type=float, default=12.0, help="seconds after RUNNING before execution_cancel")
    ap.add_argument("--skip-cancel", action="store_true")
    a = ap.parse_args()
    p2c, p2d = _load("phase2c_native_qualification"), _load("phase2d_composition_qualification")
    evidence = Path(a.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    tag = f"{a.provider}_lifecycle_{time.strftime('%H%M%S')}"
    report = {"tag": tag, "provider": a.provider, "model": a.model, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "interpreter": sys.executable, "root": str(ROOT),
              "approval_source": "programmatic (this harness echoes the worker's approval + proposal digests), not a human on the UI"}
    base = ROOT / "work/c1" / f"p2ops_{tag}_{uuid.uuid4().hex[:8]}"
    report["base"] = str(base)

    probe = p2c.direct_probe(a.provider, a.model, evidence)
    probe_file = evidence / f"probe_{a.provider}.json"
    probe_file.write_text(p2c.jdump(probe))
    report["direct_probe"] = {k: probe.get(k) for k in ("status", "ok", "exit", "version", "executable", "executable_sha256", "auth_status", "duration_s")}
    exe = probe.get("executable")
    live_auth = native_auth_probe(a.provider, exe) if exe else None
    report["live_auth_status_probe"] = live_auth
    persist = bool(probe.get("ok") and live_auth is True)

    def record_writer(st):
        if not persist:
            return None
        rec = build_record(client_root=st.client_root, client_id=st.trust.client_id, signer=st.client_key, provider=a.provider,
                           level="NATIVE_QUALIFIED", spec_id=a.provider, executable=exe, executable_args=[], version=probe.get("version"),
                           models=[a.model], evidence_path=probe_file, qualified_by="scripts/phase2ops_native_execution.py",
                           notes="direct probe ok + live auth status ok on this machine; containment = Phase 2A job objects")
        write_record(st.client_root, rec)
        report["qualification_record"] = {k: rec[k] for k in ("level", "executable_sha256", "version", "models", "record_sha256", "expires_at")}
        return rec
    report["qualification_record"] = None
    report["qualification_decision"] = "PERSISTED NATIVE_QUALIFIED" if persist else \
        "NOT PERSISTED: direct probe failed or live auth status not ok -> USER INTERACTION REQUIRED (native login); fail closed expected"

    rows = {DETERMINISTIC, ("client_external_harness", a.provider, a.model)}
    stack = p2d.CompositionStack(base, a.provider, a.model, rows, bridge_kwargs={"timeout_s": a.timeout, "inactivity_s": a.inactivity},
                                 record_writer=record_writer)
    service = SupervisedWorkerService(stack.cm, stack.persistence, stack.bridge, harness=stack.client_composition.registry,
                                      composition=stack.client_composition)
    service.runner = stack.runner
    runs = []
    try:
        report["composition_report"] = stack.client_composition.report
        report["registry_discover"] = stack.client_composition.registry.discover()
        selection = {"kind": "client_external_harness", "provider": a.provider, "model": a.model}

        # ---- run 1: lifecycle to a verified receipt ---------------------------------------------------------------
        log, transitions = [], []
        turn = frames_turn(service, SHORT_TEXT, selection, log)
        run = {"name": "lifecycle", "frames": log, "transitions": transitions, "turn_state": turn.get("state"), "code": turn.get("code")}
        if turn.get("state") == "approval_required":
            run["proposal"] = turn["execution_proposal"]
            t0 = time.time()
            eid = begin(service, turn, log)
            run["begin_returned_after_s"] = round(time.time() - t0, 3)
            final = poll(service, eid, lambda s: s["state"] in TERMINAL_STATES, a.timeout + 60, transitions)
            run["duration_s"] = round(time.time() - t0, 1)
            run["final"] = {k: final.get(k) for k in ("execution_id", "state", "reason", "code", "message", "task_id", "bridge_outcome",
                                                       "failure_category", "evidence", "queued_at", "approving_at", "starting_at", "running_at", "ended_at")}
            run["ledger_view"], run["journal_view"] = final.get("ledger"), final.get("journal")
            rec = stack.turn_record(turn["turn_id"])
            run["server_turn_record"] = {k: rec.get(k) for k in ("state", "dispatched", "execution_outcome", "execution_closed", "operation_id")}
            if final.get("task_id") and stack.L.task(final["task_id"]):
                run["ledger"] = p2c.ledger_dump(stack.L, final["task_id"])
            run["result_files"] = [{"path": str(p), "bytes": p.stat().st_size, "sha256": p2c.sha256_file(p), "content": p.read_text(errors="replace")[:200]}
                                   for p in stack.result_files()]
            run["execution_list"] = service.handle("execution_list", {"command": "execution_list"})
        runs.append(run)

        # ---- run 2: REAL mid-run cancellation ----------------------------------------------------------------------
        if not a.skip_cancel and persist and runs[0].get("final", {}).get("state") == "completed":
            log, transitions = [], []
            turn = frames_turn(service, LONG_TEXT, selection, log)
            run = {"name": "mid_run_cancel", "frames": log, "transitions": transitions}
            eid = begin(service, turn, log)
            t0 = time.time()

            def running(s):
                return s["state"] == "running" and any(x["status"] == "RUNNING" and x["pid"] for x in (s.get("ledger") or {}).get("attempts") or [])
            st = poll(service, eid, running, 120, transitions)
            run["reached_running"] = running(st)
            if run["reached_running"]:
                att = st["ledger"]["attempts"][-1]
                run["attempt_pid"] = att["pid"]
                run["pid_state_before_cancel"] = winproc.identity_state(att["pid"], att["pid_create_time"])
                time.sleep(a.cancel_after)
                tc = time.time()
                rep = service.handle("execution_cancel", {"command": "execution_cancel", "execution_id": eid})
                log.append({"sent": {"command": "execution_cancel", "execution_id": eid}, "received": rep, "at": tc})
                run["cancel_reply"] = rep
                final = poll(service, eid, lambda s: s["state"] in TERMINAL_STATES, 120, transitions)
                run["settled_after_cancel_s"] = round(time.time() - tc, 1)
                deadline = time.monotonic() + 20
                while winproc.identity_state(att["pid"], att["pid_create_time"]).startswith("ALIVE") and time.monotonic() < deadline:
                    time.sleep(0.1)
                run["pid_state_after_cancel"] = winproc.identity_state(att["pid"], att["pid_create_time"])
                run["final"] = {k: final.get(k) for k in ("execution_id", "state", "reason", "code", "task_id", "bridge_outcome", "failure_category",
                                                           "cancel_requested", "running_at", "ended_at")}
                run["ledger_view"], run["journal_view"] = final.get("ledger"), final.get("journal")
                rec = stack.turn_record(turn["turn_id"])
                run["server_turn_record"] = {k: rec.get(k) for k in ("state", "dispatched", "execution_outcome", "execution_closed")}
                run["ledger"] = p2c.ledger_dump(stack.L, final["task_id"]) if final.get("task_id") and stack.L.task(final["task_id"]) else None
                run["workspace_files_after_kill"] = sorted(str(p.relative_to(stack.client_root)) for p in (stack.client_root / "workspace").rglob("*")
                                                           if p.is_file() and "results" not in p.parts)[:50]
                run["result_files_total"] = len(stack.result_files())
                run["cancel_after_terminal"] = None
                try:
                    service.handle("execution_cancel", {"command": "execution_cancel", "execution_id": eid})
                except Exception as exc:  # noqa: BLE001
                    run["cancel_after_terminal"] = str(getattr(exc, "code", exc))
            run["duration_s"] = round(time.time() - t0, 1)
            runs.append(run)
        report["runs"] = runs
    except Exception as exc:  # noqa: BLE001
        report["harness_error"] = repr(exc)
        report["runs"] = runs
    finally:
        try:
            service.executions.close(30)
            stack.close()
        except Exception as exc:  # noqa: BLE001
            report["close_error"] = repr(exc)
    report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out = evidence / f"{tag}.json"
    out.write_text(jdump(report), encoding="utf-8")
    summary = {"tag": tag, "direct_cli_status": probe.get("status"), "live_auth": live_auth, "qualification": report["qualification_decision"],
               "runs": [{"name": r["name"], "state": (r.get("final") or {}).get("state"), "reason": (r.get("final") or {}).get("reason"),
                         "code": (r.get("final") or {}).get("code"), "pid_after_cancel": r.get("pid_state_after_cancel")} for r in runs]}
    print(json.dumps(summary, default=str))
    print("REPORT", out)


if __name__ == "__main__":
    main()
