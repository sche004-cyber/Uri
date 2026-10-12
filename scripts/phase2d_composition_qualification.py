"""Phase 2D: qualify the REAL native executor through the Phase 2 COMPOSITION (persisted qualification record ->
compose_client -> Phase 2 server policy file -> SupervisedWorkerService protocol frames -> SupervisedTurnRunner ->
verify_authority -> SupervisorBridge -> uri_supervisor -> REAL CLI -> ledger COMPLETE -> receipt -> server settle).

Differences from Phase 2C (`phase2c_native_qualification.py`): the qualification is PERSISTED as a record the worker
profile re-validates (binary hash, version, record digest, live auth status), the server rows come from an explicit
policy FILE, and the turn is driven with the exact frames the frozen UI sends (`turn_start`, `turn_decide` with the
approval digest). The approval decision is still supplied by this harness (programmatic), never by a human on the UI.

Nothing here logs in, reads/copies/forwards credentials, edits any configuration, or touches repository files. Writes:
fresh paired-client/server state under <repo>/work/c1 (git-ignored) and the evidence directory.

Usage:  python scripts/phase2d_composition_qualification.py --provider codex_cli --model gpt-6-sol --evidence <dir>
        python scripts/phase2d_composition_qualification.py --provider claude_code --evidence <dir>
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uri_supervisor.executors import BUILTIN_SPECS  # noqa: E402
from uri_supervisor_bridge.composition import phase2_server_composition, policy_path, write_policy  # noqa: E402
from uri_supervisor_bridge.qualification import (build_record, compose_client, load_records, native_auth_probe,  # noqa: E402
                                                 write_record)

DEFAULT_TEXT = "use the harness to write the single word PONG into pong.txt"
DETERMINISTIC = ("server_local_model", "uri-deterministic", None)


def _load_phase2c():
    spec = importlib.util.spec_from_file_location("phase2c_native_qualification", ROOT / "scripts" / "phase2c_native_qualification.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jdump(obj):
    return json.dumps(obj, indent=1, sort_keys=True, default=str)


class CompositionStack:
    """Real server with the Phase 2 policy file, real client, persisted record -> compose_client -> worker service."""

    def __init__(self, base: Path, provider, model, rows, allow_fixture=False, bridge_kwargs=None, record_writer=None):
        from fastapi.testclient import TestClient
        from uri_core.app.paired_server import create_app
        from uri_core.client_runtime.manifest import ClientManifest, provision_client
        from uri_core.client_runtime.persistence import ClientPersistence
        from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, atomic_json, dpapi, provision
        from uri_supervisor_bridge.composition import compose_and_build
        from uri_supervisor_bridge.runner import SupervisedTurnRunner
        from uri_supervisor_bridge.worker_service import SupervisedWorkerService

        server_manifest = provision(ROOT, base / "server", Path(sys.executable), 18236, "c2-paired-core")
        sm = RuntimeManifest(server_manifest)
        self.policy_file = write_policy(policy_path(sm.data["state_root"]), rows)
        self.composition = phase2_server_composition(self.policy_file)
        runtime = RuntimeIdentity(sm)
        self.app = create_app(runtime, composition=self.composition)
        principal = str(uuid.uuid4())
        cm = ClientManifest(provision_client(server_manifest, base / "client", principal, ["remember_fact"]))
        pairings = self.app.state.client_service.pairings
        with pairings.lock:
            data = pairings._load()
            data["clients"][cm.data["client_id"]]["grants"].append("external_harness_task")
            atomic_json(pairings.path, data)
        self.cm, self.client_root = cm, Path(cm.data["client_root"])
        from uri_supervisor_bridge.qualification import RecordTrust
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self.trust = RecordTrust.from_manifest(cm.data)
        self.client_key = Ed25519PrivateKey.from_private_bytes(dpapi((self.client_root / "secure/client-key.dpapi").read_bytes(), True))
        self.record = record_writer(self) if record_writer else None
        self.client_composition, self.bridge = compose_and_build(self.client_root, trust=self.trust, allow_fixture=allow_fixture,
                                                                **(bridge_kwargs or {}))
        cred = json.loads(dpapi((self.client_root / "secure/uri-credentials.dpapi").read_bytes(), True))
        self.http = TestClient(self.app)
        self.http.__enter__()
        s = self.http.post("/client/v1/session", json={"server_id": cred["server_id"], "client_id": cred["client_id"]},
                           headers={"Authorization": "Bearer " + cred["principal_token"], "X-URI-Pairing": cred["pairing_token"]}).json()
        headers = {"Authorization": "Bearer " + s["token"], "X-URI-Client": cred["client_id"]}
        self.calls, self.settle_bodies = [], []

        def call(method, path, body):
            self.calls.append((method, path))
            if path.endswith("/settle") and isinstance(body, dict):
                self.settle_bodies.append(body.get("receipt"))
            r = self.http.request(method, path, json=body, headers=headers)
            return r.status_code, r.json()
        self.persistence = ClientPersistence(cm)
        self.runner = SupervisedTurnRunner(cm, self.persistence, call, cm.data["server_public_key"], runtime.generation,
                                           self.bridge, harness=self.client_composition.registry)
        self.service = SupervisedWorkerService(cm, self.persistence, self.bridge, harness=self.client_composition.registry)
        self.service.runner = self.runner
        self.captured = {}
        real_execute = self.bridge.execute

        def execute(work, **kw):                      # keyword pass-through (UI/operations slice: `context=`)
            self.captured["work"] = work
            return real_execute(work, **kw)
        self.bridge.execute = execute
        real_run = self.runner._run_harness

        def run_harness(session, request, reasoning):
            self.captured["signed"] = self.runner._bridge_signed
            self.captured["request"], self.captured["reasoning"], self.captured["session"] = request, reasoning, session
            return real_run(session, request, reasoning)
        self.runner._run_harness = run_harness

    def close(self):
        self.http.__exit__(None, None, None)
        self.bridge.close()

    @property
    def L(self):
        return self.bridge.L

    def turn_record(self, turn_id):
        return self.app.state.client_service._load()["turns"][turn_id]

    def result_files(self):
        d = self.client_root / "workspace" / "results"
        return [p for p in d.rglob("*") if p.is_file()] if d.exists() else []


def governed_turn(stack: CompositionStack, text, selection, frames_log):
    """Drive one turn with the frozen UI's frames; approval by digest (programmatic)."""
    session = str(uuid.uuid4())
    start = {"command": "turn_start", "session_id": session, "text": text, "reasoning": selection}
    frames_log.append({"sent": start})
    turn = stack.service.handle("turn_start", start)
    frames_log.append({"received": {k: turn.get(k) for k in ("state", "turn_id", "code", "approval_request", "executor_kind")}})
    if turn.get("state") != "approval_required":
        return turn, None
    decide = {"command": "turn_decide", "turn_id": turn["turn_id"], "approve": True,
              "approval_digest": turn["approval_request"]["approval_digest"]}
    frames_log.append({"sent": decide})
    final = stack.service.handle("turn_decide", decide)
    frames_log.append({"received": {k: final.get(k) for k in ("state", "turn_id", "code", "message")}})
    return final, turn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=sorted(BUILTIN_SPECS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--inactivity", type=float, default=150)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    p2c = _load_phase2c()
    evidence = Path(a.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    tag = a.tag or f"{a.provider}_composition_{time.strftime('%H%M%S')}"
    report = {"tag": tag, "provider": a.provider, "model": a.model, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "interpreter": sys.executable, "root": str(ROOT), "approval_source": "programmatic (this harness), not a human on the UI"}
    base = ROOT / "work/c1" / f"p2d_{tag}_{uuid.uuid4().hex[:8]}"
    report["base"] = str(base)

    # ---- 1. direct probe (read-only CLI call; never logs in) -------------------------------------------------------
    probe = p2c.direct_probe(a.provider, a.model, evidence)
    probe_file = evidence / f"probe_{a.provider}.json"
    probe_file.write_text(p2c.jdump(probe))
    report["direct_probe"] = {k: probe.get(k) for k in ("status", "ok", "exit", "version", "executable", "executable_sha256", "stdout_sha256",
                                                        "agent_text", "result", "failures", "auth_status", "forwarded_env_keys", "duration_s")}
    exe = probe.get("executable")
    live_auth = native_auth_probe(a.provider, exe) if exe else None
    report["live_auth_status_probe"] = live_auth

    # ---- 2. persist (or refuse to persist) the qualification record (into the fresh client root, once provisioned) --
    persist = bool(probe.get("ok") and live_auth is True)

    def record_writer(st):
        if not persist:
            return None
        client_root = st.client_root
        rec = build_record(client_root=client_root, client_id=st.trust.client_id, signer=st.client_key, provider=a.provider, level="NATIVE_QUALIFIED", spec_id=a.provider, executable=exe, executable_args=[],
                           version=probe.get("version"), models=[a.model], evidence_path=probe_file,
                           qualified_by="scripts/phase2d_composition_qualification.py",
                           notes="direct probe ok + live auth status ok on this machine; containment = Phase 2A job objects")
        path = write_record(client_root, rec)
        report["qualification_record"] = {"path": str(path), **{k: rec[k] for k in ("level", "executable", "executable_sha256", "version",
                                                                                   "models", "evidence_sha256", "record_sha256", "client_id",
                                                                                   "client_public_key", "qualified_at", "expires_at",
                                                                                   "pinned_files", "resolve_pins", "evidence_file")}}
        return rec
    report["qualification_record"] = None
    report["qualification_decision"] = ("PERSISTED NATIVE_QUALIFIED" if persist else
                                        "NOT PERSISTED: direct probe failed or live auth status not ok -> USER INTERACTION REQUIRED "
                                        "(native login); the composition keeps the provider NATIVE_UNQUALIFIED")

    # ---- 3. compose and run the governed path over worker frames -----------------------------------------------------
    rows = {DETERMINISTIC, ("client_external_harness", a.provider, a.model)}
    if a.provider == "codex_cli":
        rows.add(("client_external_harness", "codex_cli", "gpt-6.1-sol"))     # offered by policy, NOT qualified: must stop at the bridge
    stack = CompositionStack(base, a.provider, a.model, rows, bridge_kwargs={"timeout_s": a.timeout, "inactivity_s": a.inactivity},
                             record_writer=record_writer)
    frames = []
    run = {}
    try:
        report["policy_rows"] = sorted(list(r) for r in stack.composition["policy"].supported)
        report["composition_report"] = stack.client_composition.report
        report["registry_discover"] = stack.client_composition.registry.discover()
        selection = {"kind": "client_external_harness", "provider": a.provider, "model": a.model}
        t0 = time.time()
        final, turn = governed_turn(stack, a.text, selection, frames)
        run["duration_s"] = round(time.time() - t0, 1)
        run["frames"] = frames
        run["final_code"], run["final_state"], run["final_message"] = final.get("code"), final.get("state"), final.get("message")
        run["turn_id"] = final.get("turn_id")
        run["server_calls"] = [p for _, p in stack.calls]
        rec = stack.turn_record(final["turn_id"]) if final.get("turn_id") else None
        run["server_turn_record"] = {k: rec.get(k) for k in ("state", "dispatched", "execution_outcome", "execution_closed", "operation_id",
                                                             "execution_reported")} if rec else None
        op = rec.get("operation_id") if rec else None
        if op and stack.L.task(op):
            run["ledger"] = p2c.ledger_dump(stack.L, op)
            if a.provider == "codex_cli":
                spec = BUILTIN_SPECS["codex_cli"]
                for at in run["ledger"]["attempts"]:
                    ran_exe = stack.client_composition.executors[a.provider].resolved_executable   # the record's resolved path
                    expected = spec.build_argv(workspace=str(stack.client_root.resolve() / "workspace" / json.loads(stack.L.task(op)["request_json"])["run_id"]),
                                               model=a.model, resolved_executable=ran_exe)
                    from uri_supervisor.supervisor import sha as ledger_sha
                    at["argv_sha256_matches_recomputed"] = (ledger_sha(expected) == at["argv_sha256"]
                                                            if at.get("resume_of") is None else "not_recomputed_for_resume")
        run["result_files"] = [{"path": str(p), "bytes": p.stat().st_size, "sha256": p2c.sha256_file(p), "content": p.read_text(errors="replace")[:200]}
                               for p in stack.result_files()]
        run["receipts_sent"] = stack.settle_bodies
        run["receipt_evidence"] = (stack.settle_bodies[-1] or {}).get("evidence") if stack.settle_bodies else None
        run["ledger_task_count"] = stack.L.q1("SELECT COUNT(*) FROM task")[0]
        report["run"] = run

        # ---- 4. post-run adversarial checks, no further executor call unless stated ------------------------------
        checks = []
        main_captured = dict(stack.captured)
        if a.provider == "codex_cli" and report["qualification_record"]:
            # (a) model offered by the server but not qualified on the client: stops at the bridge, zero new tasks
            before = stack.L.q1("SELECT COUNT(*) FROM task")[0]
            f2 = []
            final2, _ = governed_turn(stack, a.text, {"kind": "client_external_harness", "provider": "codex_cli", "model": "gpt-6.1-sol"}, f2)
            after = stack.L.q1("SELECT COUNT(*) FROM task")[0]
            rec2 = stack.turn_record(final2["turn_id"]) if final2.get("turn_id") else {}
            checks.append({"check": "unqualified_model_offered_by_policy", "expected": "SETTLED_FAILED, execution_closed, no new task, no executor call",
                           "observed": {"code": final2.get("code"), "closed": rec2.get("execution_closed"), "tasks": [before, after]},
                           "pass": final2.get("code") == "SETTLED_FAILED" and rec2.get("execution_closed") is True and before == after})
            # (b) tampered record on disk, digest recomputed (the round-1 D1 attack) -> signature refuses it
            from uri_supervisor_bridge.qualification import RecordTrust, record_digest
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            items = load_records(stack.client_root)
            rp = Path(items[0]["path"])
            original = rp.read_text()
            body = json.loads(original)
            body["models"] = [a.model, "gpt-6.1-sol"]
            body["record_sha256"] = record_digest(body)
            rp.write_text(json.dumps(body))
            comp2 = compose_client(stack.client_root, trust=stack.trust)
            checks.append({"check": "tampered_record_with_recomputed_digest_invalidated", "expected": "INVALIDATED RECORD_SIGNATURE_INVALID, nothing usable",
                           "observed": comp2.report, "pass": comp2.report[0].get("reason") == "RECORD_SIGNATURE_INVALID" and comp2.executors == {}
                           and not any(r["usable"] for r in comp2.registry.discover())})
            rp.write_text(original)
            # (c) the same record composed by ANOTHER client identity (copy between clients, round-1 D3)
            other = RecordTrust.from_private_key(str(uuid.uuid4()), Ed25519PrivateKey.generate())
            comp3 = compose_client(stack.client_root, trust=other)
            checks.append({"check": "record_copied_to_another_client_invalidated", "expected": "INVALIDATED RECORD_CLIENT_MISMATCH",
                           "observed": comp3.report, "pass": comp3.report[0].get("reason") == "RECORD_CLIENT_MISMATCH" and comp3.executors == {}})
            # (c2) the persisted launch chain covers the payload behind the npm shim (round-1 D4), and re-checks now
            from uri_supervisor_bridge.qualification import check_launch_chain
            pf = items[0]["record"]["pinned_files"]
            names = sorted({Path(k).name.lower() for k in pf})
            try:
                check_launch_chain(pf, items[0]["record"]["resolve_pins"])
                chain_ok = True
            except Exception as exc:  # noqa: BLE001
                chain_ok = repr(exc)
            checks.append({"check": "launch_chain_pinned_and_intact", "expected": "codex.js + vendor codex.exe + node pinned; chain intact",
                           "observed": {"pinned_names": names, "resolve_pins": items[0]["record"]["resolve_pins"], "intact": chain_ok},
                           "pass": chain_ok is True and "codex.exe" in names and "codex.js" in names and "node.exe" in names})
            # (c3) clean recomposition after restoring the record: still qualified (the checks above changed nothing)
            comp5 = compose_client(stack.client_root, trust=stack.trust)
            checks.append({"check": "restored_record_requalifies", "expected": "QUALIFIED", "observed": comp5.report,
                           "pass": comp5.qualified() == [a.provider]})
            # (d) replay of the same ticket / restart revives nothing (Phase 2C checks, re-run on this real ticket)
            if run.get("ledger"):
                try:
                    stack.captured = main_captured
                    checks += p2c.authority_checks(stack, run)
                except Exception as exc:  # noqa: BLE001
                    checks.append({"check": "phase2c_authority_checks", "pass": None, "error": repr(exc)})
        report["adversarial_checks"] = checks
    except Exception as exc:  # noqa: BLE001
        report["harness_error"] = repr(exc)
        report["run"] = run
    finally:
        try:
            stack.close()
        except Exception as exc:  # noqa: BLE001
            report["close_error"] = repr(exc)
    report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out = evidence / f"{tag}.json"
    out.write_text(jdump(report), encoding="utf-8")
    summary = {"tag": tag, "direct_cli_status": probe.get("status"), "live_auth": live_auth, "qualification": report["qualification_decision"],
               "final_code": run.get("final_code"), "tasks": run.get("ledger_task_count"),
               "checks_failed": [c["check"] for c in report.get("adversarial_checks", []) if c.get("pass") is False]}
    if run.get("ledger"):
        summary["ledger_state"] = run["ledger"]["task"].get("state")
        summary["decisions"] = [(d["outcome"], d["action"], d["reason_code"]) for d in run["ledger"]["decisions"]]
    print(json.dumps(summary, default=str))
    print("REPORT", out)


if __name__ == "__main__":
    main()
