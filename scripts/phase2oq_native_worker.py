"""Phase 2 operational qualification, EXE-1: the NATIVE Codex binary under the REAL worker profile.

What runs for real: a fresh paired server (`scripts/run_uri_phase2_server.py`, Phase 2 policy file) and client
(`scripts/run_uri_supervised_worker.py`, NO fixture flag), the npm-vendored native `codex.exe` qualified with its pinned
launch chain, the client profile's own Codex home (CODEX_HOME pin), the Windows sandbox, the supervisor's job objects,
and the frozen framed protocol.

What does NOT run for real: the model. The client profile's Codex home points Codex at the scripted local endpoint
(`scripts/phase2oq_scripted_endpoint.py`, 127.0.0.1). No login exists in that profile, by design.

Phases
  W   real worker process: preflight, harness_discover, a Codex turn. Expected: the native record COMPOSES (launch
      chain, version, CODEX_HOME, sandbox mode all hold) and the harness is NOT usable because the client profile is
      not logged in -> the turn is refused before any approval (fail closed, PA-8 is the owner's login).
  W2  real worker process, client Codex home without a Windows sandbox mode -> record INVALIDATED
      (CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED), harness not usable.
  W3  real worker process, a record for the npm `codex.CMD` launcher -> INVALIDATED (the worker PATH has no `node`).
  L   worker-ENVIRONMENT lifecycle: a child process with exactly the worker's sanitized environment and CODEX_HOME pin
      composes the same record with ONE substitution, the live auth gate answers True for codex_cli, and drives the
      real lifecycle frames: (1) a run to a verified receipt (pong.txt written inside the sandboxed workspace),
      (2) a real mid-run cancellation while a sandboxed child command runs (no process of the run may survive).
      This is NOT PA-10: PA-10 needs the owner's client-profile login and the real worker process.

Writes only: <repo>/work/c1/p2oq_native_* (git-ignored) and the evidence directory. Never logs in, never reads or
copies a credential, never touches the owner's Codex home.

Usage: .venv/Scripts/python.exe -I scripts/phase2oq_native_worker.py --evidence <dir> [--phases W,W2,W3,L]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SERVER = ROOT / "scripts/run_uri_phase2_server.py"
WORKER = ROOT / "scripts/run_uri_supervised_worker.py"
PONG_TEXT = "use the harness to write the single word PONG into pong.txt"
ESSAY_TEXT = ("use the harness to write a detailed essay of at least 2000 words about durable task supervisors "
              "into essay.txt")
CODEX_SELECTION = {"kind": "client_external_harness", "provider": "codex_cli", "model": None}


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jdump(obj):
    return json.dumps(obj, indent=1, sort_keys=True, default=str)


def run_processes(marker):
    """Processes whose command line or image path contains `marker` (psutil; read-only)."""
    import psutil
    out = []
    for p in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            text = " ".join(p.info["cmdline"] or []) + " " + (p.info["exe"] or "")
        except Exception:  # noqa: BLE001
            continue
        if marker.lower() in text.lower():
            out.append({"pid": p.info["pid"], "name": p.info["name"], "cmdline": " ".join(p.info["cmdline"] or [])[:300]})
    return out


# ---- worker process helpers ---------------------------------------------------------------------------------------

class Worker:
    def __init__(self, client):
        from uri_core.core.runtime_identity import child_environment
        m = client.data
        self.root = Path(m["client_root"])
        self.proc = subprocess.Popen([m["interpreter"], "-B", "-I", str(WORKER), "--manifest", str(client.path)], cwd=m["client_root"],
                                     env=child_environment(self.root, Path(m["interpreter"])), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def cmd(self, value):
        from uri_core.client_runtime.frames import read_frame, write_frame
        write_frame(self.proc.stdin, value)
        return read_frame(self.proc.stdout)

    def close(self):
        out = None
        if self.proc.poll() is None:
            try:
                out = self.cmd({"command": "close"})
                self.proc.stdin.close()
                self.proc.wait(30)
            except Exception as exc:  # noqa: BLE001
                out = {"error": repr(exc)}
                self.proc.kill()
        err = self.proc.stderr.read().decode("utf-8", "replace")[-2000:] if self.proc.stderr else ""
        return {"close": out, "exit": self.proc.returncode, "stderr_tail": err}


def worker_phase(client, name, expect_turn=True):
    w = Worker(client)
    rep = {"phase": name}
    try:
        rep["preflight"] = w.cmd({"command": "preflight"})
        found = w.cmd({"command": "harness_discover"})
        v = found.get("value") or {}
        rep["harness_discover"] = {"result": found.get("result"), "code": found.get("code"),
                                   "codex_cli": next((h for h in v.get("harnesses", []) if h.get("harness_id") == "codex_cli"), None),
                                   "qualification": v.get("qualification"), "qualification_live": v.get("qualification_live")}
        inst = json.loads((Path(client.data["client_root"]) / "control/worker-instance.json").read_text(encoding="utf-8"))
        rep["worker_instance"] = {k: inst.get(k) for k in ("profile", "qualified", "cli_homes_pinned", "fixture_allowed", "pid")}
        if expect_turn:
            turn = w.cmd({"command": "turn_start", "session_id": str(uuid.uuid4()), "text": PONG_TEXT, "reasoning": CODEX_SELECTION})
            val = turn.get("value") or {}
            rep["turn_start"] = {"result": turn.get("result"), "code": turn.get("code") or val.get("code"), "state": val.get("state"),
                                 "approval_request": bool(val.get("approval_request")), "execution_proposal": bool(val.get("execution_proposal"))}
            prop = val.get("execution_proposal") or {}
            rep["proposal_harness"] = prop.get("harness")
            rep["proposal_qualification"] = prop.get("qualification")
            if val.get("state") == "approval_required":
                # The owner would press Approve here: OQ-1 must refuse before the approval leaves the worker.
                rep["execution_begin"] = w.cmd({"command": "execution_begin", "turn_id": val["turn_id"],
                                                "approval_digest": val["approval_request"]["approval_digest"],
                                                "proposal_digest": prop.get("proposal_digest")})
                rep["execution_list"] = w.cmd({"command": "execution_list"})
                rep["server_turn"] = w.cmd({"command": "server_request", "method": "GET",
                                            "path": f"/client/v1/turns/{val['turn_id']}/status", "body": {}})
    finally:
        rep["shutdown"] = w.close()
    return rep


# ---- worker-environment lifecycle (child process) ---------------------------------------------------------------

def child_lifecycle(a):
    """Runs INSIDE the worker's sanitized environment (set by the parent). Mirrors run_uri_supervised_worker.main up to
    the frame loop, with the live auth gate substituted for codex_cli only."""
    from uri_core.client_runtime.manifest import ClientManifest
    from uri_core.client_runtime.persistence import ClientPersistence
    from uri_supervisor import winproc
    from uri_supervisor_bridge.composition import compose_and_build
    from uri_supervisor_bridge.execution import TERMINAL_STATES
    from uri_supervisor_bridge.qualification import RecordTrust, client_cli_homes
    from uri_supervisor_bridge.worker_service import SupervisedWorkerService
    manifest = ClientManifest(a.manifest)
    m = manifest.data
    root = Path(m["client_root"])
    rep = {"mode": "worker-environment lifecycle; auth gate substituted for codex_cli (client profile is NOT logged in)",
           "environment_keys": sorted(os.environ), "path": os.environ.get("PATH"), "codex_home": os.environ.get("CODEX_HOME"),
           "cwd_is_client_root": Path.cwd().resolve() == root.resolve()}
    pins = client_cli_homes(root, create=False)
    assert os.environ.get("CODEX_HOME") == pins["CODEX_HOME"], "CODEX_HOME_NOT_PINNED"
    comp, bridge = compose_and_build(root, trust=RecordTrust.from_manifest(m), codex_home=pins["CODEX_HOME"],
                                     auth_probe=lambda h: True if h == "codex_cli" else None,
                                     timeout_s=a.timeout, inactivity_s=a.timeout)
    rep["composition_report"] = comp.report
    service = SupervisedWorkerService(manifest, ClientPersistence(manifest), bridge, harness=comp.registry, composition=comp)
    rep["discover_codex"] = next((h for h in comp.registry.discover() if h["harness_id"] == "codex_cli"), None)

    def poll(eid, until, timeout, transitions):
        deadline, last, st = time.monotonic() + timeout, None, None
        while time.monotonic() < deadline:
            st = service.handle("execution_status", {"command": "execution_status", "execution_id": eid})
            task = ((st.get("ledger") or {}).get("task") or {}).get("state")
            if (st["state"], task) != last:
                transitions.append({"at": time.time(), "state": st["state"], "ledger_task": task, "reason": st.get("reason")})
                last = (st["state"], task)
            if until(st):
                return st
            time.sleep(0.25)
        return st

    def start(text):
        turn = service.handle("turn_start", {"command": "turn_start", "session_id": str(uuid.uuid4()), "text": text,
                                             "reasoning": CODEX_SELECTION})
        if turn.get("state") != "approval_required":
            return turn, None
        eid = service.handle("execution_begin", {"command": "execution_begin", "turn_id": turn["turn_id"],
                                                 "approval_digest": turn["approval_request"]["approval_digest"],
                                                 "proposal_digest": turn["execution_proposal"]["proposal_digest"]})["execution_id"]
        return turn, eid

    keep = ("execution_id", "state", "reason", "code", "task_id", "bridge_outcome", "failure_category", "cancel_requested",
            "running_at", "ended_at")
    runs = []
    try:
        # (1) lifecycle to a verified receipt
        transitions = []
        turn, eid = start(PONG_TEXT)
        run = {"name": "lifecycle", "turn_state": turn.get("state"), "turn_code": turn.get("code"),
               "proposal": turn.get("execution_proposal"), "transitions": transitions}
        if eid:
            final = poll(eid, lambda s: s["state"] in TERMINAL_STATES, a.timeout + 60, transitions)
            run["final"] = {k: final.get(k) for k in keep}
            run["ledger_view"] = final.get("ledger")
            run["result_files"] = [{"path": str(p.relative_to(root)), "content": p.read_text(errors="replace")[:100]}
                                   for p in (root / "workspace/results").rglob("pong.txt")]
        runs.append(run)
        # (2) mid-run cancellation while a sandboxed child command runs
        transitions = []
        turn, eid = start(ESSAY_TEXT)
        run = {"name": "mid_run_cancel", "turn_state": turn.get("state"), "transitions": transitions}
        if eid:
            def running(s):
                return s["state"] == "running" and any(x["status"] == "RUNNING" and x["pid"] for x in (s.get("ledger") or {}).get("attempts") or [])
            st = poll(eid, running, 120, transitions)
            run["reached_running"] = running(st)
            if run["reached_running"]:
                att = st["ledger"]["attempts"][-1]
                run["attempt_pid"] = att["pid"]
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline and not run_processes("Start-Sleep -Seconds 600"):
                    time.sleep(0.5)
                run["sandboxed_child_before_cancel"] = run_processes("Start-Sleep -Seconds 600")
                time.sleep(a.cancel_after)
                run["cancel_reply"] = service.handle("execution_cancel", {"command": "execution_cancel", "execution_id": eid})
                final = poll(eid, lambda s: s["state"] in TERMINAL_STATES, 120, transitions)
                run["final"] = {k: final.get(k) for k in keep}
                run["ledger_view"] = final.get("ledger")
                deadline = time.monotonic() + 20
                while winproc.identity_state(att["pid"], att["pid_create_time"]).startswith("ALIVE") and time.monotonic() < deadline:
                    time.sleep(0.1)
                run["pid_state_after_cancel"] = winproc.identity_state(att["pid"], att["pid_create_time"])
                time.sleep(2)
                run["survivors_sleep_child"] = run_processes("Start-Sleep -Seconds 600")
                run["survivors_vendor_codex"] = [p for p in run_processes(str(Path(a.native).parent.parent))
                                                 if p["pid"] != os.getpid() and p["name"].lower() != "python.exe"]
        runs.append(run)
    finally:
        rep["runs"] = runs
        rep["executions_close"] = service.executions.close(30)
        bridge.close()
        Path(a.out).write_text(jdump(rep), encoding="utf-8")
    return 0


# ---- parent ---------------------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence")
    ap.add_argument("--phases", default="W,W2,W3,L")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--cancel-after", type=float, default=6.0)
    ap.add_argument("--child-lifecycle", action="store_true")
    ap.add_argument("--manifest")
    ap.add_argument("--out")
    ap.add_argument("--native")
    a = ap.parse_args()
    if a.child_lifecycle:
        return child_lifecycle(a)

    from phase2d.conftest import client_identity
    from scripts.uri_server_launcher import listener
    from uri_core.client_runtime.manifest import ClientManifest, provision_client
    from uri_core.core.client_pairing import ClientPairingStore
    from uri_core.core.runtime_identity import RuntimeManifest, atomic_json, child_environment, provision
    from uri_supervisor_bridge import qualification as q
    from uri_supervisor_bridge.composition import DETERMINISTIC_ROW, policy_path, write_policy
    from scripts.phase2oq_scripted_endpoint import ScriptedEndpoint
    if Path(sys.executable).resolve() != (ROOT / ".venv/Scripts/python.exe").resolve():
        raise SystemExit("RUN_WITH_THE_WORKTREE_VENV")
    phases = [p.strip() for p in a.phases.split(",") if p.strip()]
    evidence = Path(a.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    tag = "native_worker_" + time.strftime("%H%M%S")
    base = ROOT / "work/c1" / f"p2oq_{tag}_{uuid.uuid4().hex[:8]}"
    report = {"tag": tag, "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "base": str(base), "phases": {},
              "model": "SCRIPTED LOCAL ENDPOINT (scripts/phase2oq_scripted_endpoint.py) - not a provider, not a login"}
    native = q.native_executable("codex_cli")
    report["native_executable"] = str(native)
    port = next(p for p in range(18340, 18380) if listener(p) is None)
    server = RuntimeManifest(provision(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core"))
    write_policy(policy_path(server.data["state_root"]), {DETERMINISTIC_ROW, ("client_external_harness", "codex_cli", None)})
    client = ClientManifest(provision_client(server.path, base / "client", str(uuid.uuid4()), ["remember_fact"]))
    store = ClientPairingStore(server.data["control_root"], server.data["server_id"])
    with store.lock:
        data = store._load()
        data["clients"][client.data["client_id"]]["grants"].append("external_harness_task")
        atomic_json(store.path, data)
    client_root = Path(client.data["client_root"])
    codex_home = Path(q.client_cli_homes(client_root)["CODEX_HOME"])
    worker_env = {**child_environment(client_root, Path(client.data["interpreter"])), **q.client_cli_homes(client_root)}
    sp = None
    with ScriptedEndpoint() as ep:
        cfg = codex_home / "config.toml"
        cfg.write_text(ep.codex_config("unelevated"), encoding="utf-8")
        report["client_codex_config"] = cfg.read_text(encoding="utf-8")
        # Qualification probe of the native binary under the worker's environment (client-profile Codex home).
        p2c = _load("phase2c_native_qualification")
        saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(worker_env)
        try:
            probe = p2c.direct_probe("codex_cli", None, evidence / "probe", executable=native)
            live = q.native_auth_probe("codex_cli", str(native))
        finally:
            os.environ.clear()
            os.environ.update(saved)
        probe_file = evidence / "probe_codex_cli.json"
        probe_file.write_text(jdump(probe), encoding="utf-8")
        report["direct_probe"] = {k: probe.get(k) for k in ("status", "ok", "exit", "version", "executable", "executable_sha256",
                                                            "agent_text", "forwarded_env_keys")}
        report["client_profile_logged_in"] = live
        cid, key = client_identity(client_root)
        rec = q.build_record(client_root=client_root, client_id=cid, signer=key, provider="codex_cli", level="NATIVE_QUALIFIED",
                             spec_id="codex_cli", executable=native, executable_args=[], version=probe.get("version"), models=[None],
                             evidence_path=probe_file, qualified_by="scripts/phase2oq_native_worker.py",
                             notes="SYNTHETIC: scripted local endpoint, not a provider/model qualification; client profile not logged in")
        q.write_record(client_root, rec)
        report["record"] = {k: rec[k] for k in ("level", "executable", "executable_sha256", "version", "models", "record_sha256")} | {
            "pinned_files": len(rec["pinned_files"]), "resolve_pins": rec["resolve_pins"]}
        sm = server.data
        log = Path(sm["state_root"]) / "logs" / "phase2-server.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        sp = subprocess.Popen([sm["interpreter"], "-B", "-I", str(SERVER), "--manifest", str(server.path)], cwd=sm["state_root"],
                              env=child_environment(Path(sm["state_root"]), Path(sm["interpreter"])), stdin=subprocess.DEVNULL,
                              stdout=open(log, "ab"), stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 40
            while listener(port) is None and time.monotonic() < deadline:
                time.sleep(0.2)
            if "W" in phases:
                report["phases"]["W"] = worker_phase(client, "W real worker, native record, client profile not logged in")
            if "W2" in phases:
                cfg.write_text(ep.codex_config(None), encoding="utf-8")
                try:
                    report["phases"]["W2"] = worker_phase(client, "W2 real worker, no Windows sandbox mode", expect_turn=False)
                finally:
                    cfg.write_text(ep.codex_config("unelevated"), encoding="utf-8")
            if "W3" in phases:
                shim = shutil.which("codex")
                rec_path = q.qualification_dir(client_root) / "codex_cli.json"
                native_bytes = rec_path.read_bytes()
                shim_ev = evidence / "probe_codex_cli_shim_negative_control.json"
                shim_ev.write_text(jdump({**probe, "executable": shim, "executable_sha256": q._file_sha256(shim),
                                          "note": "negative control: the probe result re-labelled for the npm launcher"}), encoding="utf-8")
                try:
                    shim_rec = q.build_record(client_root=client_root, client_id=cid, signer=key, provider="codex_cli",
                                              level="NATIVE_QUALIFIED", spec_id="codex_cli", executable=shim, executable_args=[],
                                              version=probe.get("version"), models=[None], evidence_path=shim_ev,
                                              qualified_by="scripts/phase2oq_native_worker.py (W3 negative control)",
                                              notes="SYNTHETIC negative control: npm .cmd launcher")
                    q.write_record(client_root, shim_rec)
                    report["phases"]["W3"] = worker_phase(client, "W3 real worker, npm codex.CMD record", expect_turn=False)
                    report["phases"]["W3"]["record_resolve_pins"] = shim_rec["resolve_pins"]
                except q.QualificationError as exc:
                    report["phases"]["W3"] = {"phase": "W3", "build_record_refused": exc.code}
                finally:
                    rec_path.write_bytes(native_bytes)
            if "L" in phases:
                out = evidence / "lifecycle_child.json"
                cp = subprocess.run([client.data["interpreter"], "-B", "-I", str(Path(__file__).resolve()), "--child-lifecycle",
                                     "--manifest", str(client.path), "--out", str(out), "--native", str(native),
                                     "--timeout", str(a.timeout), "--cancel-after", str(a.cancel_after)],
                                    cwd=str(client_root), env=worker_env, capture_output=True, timeout=a.timeout * 3)
                report["phases"]["L"] = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
                report["phases"]["L"]["child_exit"] = cp.returncode
                report["phases"]["L"]["child_stderr_tail"] = cp.stderr.decode("utf-8", "replace")[-3000:]
        finally:
            report["endpoint_requests"] = ep.requests
            if sp is not None and sp.poll() is None:
                sp.kill()
                sp.wait(15)
    report["client_home_codex_auth_files"] = sorted(str(p.relative_to(codex_home)) for p in codex_home.glob("auth*"))
    report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out = evidence / f"{tag}.json"
    out.write_text(jdump(report), encoding="utf-8")
    ph = report["phases"]
    lc = {r["name"]: r for r in ph.get("L", {}).get("runs", [])}
    summary = {"tag": tag, "probe": report["direct_probe"].get("status"), "logged_in": live,
               "W": ((ph.get("W") or {}).get("turn_start") or {}), "W_begin": (ph.get("W") or {}).get("execution_begin"),
               "W_harness": (ph.get("W") or {}).get("proposal_harness"),
               "W_codex_row": [r for r in ((ph.get("W") or {}).get("harness_discover") or {}).get("qualification") or [] if r.get("provider") == "codex_cli"],
               "W2": [(r.get("status"), r.get("reason")) for r in ((ph.get("W2") or {}).get("harness_discover") or {}).get("qualification") or []],
               "W3": [(r.get("status"), r.get("reason")) for r in ((ph.get("W3") or {}).get("harness_discover") or {}).get("qualification") or []]
               or (ph.get("W3") or {}).get("build_record_refused"),
               "L": {n: {"state": (r.get("final") or {}).get("state"), "code": (r.get("final") or {}).get("code"),
                         "reason": (r.get("final") or {}).get("reason"), "pid_after": r.get("pid_state_after_cancel"),
                         "survivors": len(r.get("survivors_sleep_child") or []) + len(r.get("survivors_vendor_codex") or []) if "survivors_sleep_child" in r else None,
                         "files": r.get("result_files")} for n, r in lc.items()}}
    print(json.dumps(summary, default=str))
    print("REPORT", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
