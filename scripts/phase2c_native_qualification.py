"""Phase 2C: qualify the REAL native execution path through the full governed chain.

confirmed intent -> approval -> server-signed Phase 1 ExecutionTicket -> SupervisedTurnRunner -> verify_authority
-> SupervisorBridge -> uri_supervisor (targeted admission, contained spawn, raw stream, reconciliation) -> REAL
installed executor (Codex CLI / Claude Code) -> ledger COMPLETE -> bridge receipt -> frozen server settle.

Nothing here logs in, reads or forwards credentials, edits configuration, or touches repository files: the only
writes are the fresh paired-client state under <repo>/work/c1 (git-ignored) and the evidence directory.

Usage (from the Phase 2 worktree, .venv interpreter):
  python scripts/phase2c_native_qualification.py --provider codex_cli --model gpt-6-sol --evidence <dir> [--mode run]
Modes:
  run           full governed run + post-run authority checks (no further executor calls)
  swap          begin under one selection, decide under another: must refuse before any executor runs
  crash         run in a child that is killed (os._exit) at --crash-at while the REAL executor streams, then restart
  restart-only  construct a bridge on an existing client root and report what startup recovery/revocation did
The direct CLI probe (step B of the report) always runs first unless --skip-probe is given.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uri_supervisor.executors import CLAUDE_CODE, CODEX_CLI  # noqa: E402
from uri_supervisor_bridge.authority import BridgeRefused, verify_authority  # noqa: E402
from uri_supervisor_bridge.bridge import ExecutorBinding, SupervisorBridge  # noqa: E402

SPECS = {"codex_cli": CODEX_CLI, "claude_code": CLAUDE_CODE}
PROBE_PROMPT = "Reply with exactly the word OK and nothing else."
DEFAULT_TEXT = "use the harness to write the single word PONG into pong.txt"


def sha256_file(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jdump(obj):
    return json.dumps(obj, indent=1, sort_keys=True, default=str)


# ---- step B/C/D: direct CLI probe under the URI-filtered environment ----------------------------------------
def direct_probe(provider, model, evidence: Path, executable=None):
    """Harmless read-only CLI call with a deterministic expected answer. Records the raw stream. Never logs in.
    `executable` (operational qualification, EXE-1): probe exactly this file instead of the PATH lookup."""
    spec = SPECS[provider]
    exe = str(executable) if executable else shutil.which(spec.executable)
    if executable:
        from uri_core.client_runtime.harness import probe_version as _probe_version
        version = _probe_version([exe]).get("version") if Path(exe).is_file() else None
    else:
        version = spec.probe_version()
    out = {"provider": provider, "executable": exe, "version": version, "model": model, "ok": False}
    if exe is None:
        out["status"] = "NOT_INSTALLED"
        return out
    out["executable_sha256"] = sha256_file(Path(exe))
    env = spec.build_env(os.environ)           # exactly what the supervisor would forward (allow-list, no API keys)
    out["forwarded_env_keys"] = sorted(env)
    probe_dir = evidence / f"probe_{provider}"
    probe_dir.mkdir(parents=True, exist_ok=True)
    if provider == "codex_cli":
        argv = [exe, "exec", "--json", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(probe_dir)]
        if model:
            argv += ["-m", model]
        argv.append(PROBE_PROMPT)
        stdin = None
    else:
        status = subprocess.run([exe, "auth", "status"], capture_output=True, timeout=60, env=env, stdin=subprocess.DEVNULL)
        out["auth_status_exit"] = status.returncode
        try:
            out["auth_status"] = json.loads(status.stdout.decode("utf-8", "replace"))
        except ValueError:
            out["auth_status_raw"] = status.stdout.decode("utf-8", "replace")[:500]
        argv = [exe, "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--setting-sources", "",
                "--permission-mode", "dontAsk", "--tools", "", "--strict-mcp-config", "--max-budget-usd", "0.5"]
        if model:
            argv += ["--model", model]
        stdin = (PROBE_PROMPT + "\n").encode()
    out["argv"] = argv
    t0 = time.time()
    p = subprocess.run(argv, input=stdin, capture_output=True, timeout=240, cwd=str(probe_dir), env=env,
                       stdin=None if stdin is not None else subprocess.DEVNULL)
    out["duration_s"] = round(time.time() - t0, 2)
    out["exit"] = p.returncode
    raw = probe_dir / "stdout.ndjson"
    raw.write_bytes(p.stdout)
    (probe_dir / "stderr.txt").write_bytes(p.stderr[-4000:])
    out["stdout_sha256"], out["stdout_lines"] = sha256_file(raw), len(p.stdout.splitlines())
    events = []
    for line in p.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    if provider == "codex_cli":
        done = any(e.get("type") == "turn.completed" for e in events)
        failed = [e for e in events if e.get("type") in ("turn.failed", "error")]
        text = next((e["item"].get("text") for e in events if e.get("type") == "item.completed"
                     and (e.get("item") or {}).get("type") == "agent_message"), None)
        out.update(terminal_completed=done, failures=[str(f)[:300] for f in failed], agent_text=text,
                   ok=bool(done and not failed and p.returncode == 0 and text == "OK"))
    else:
        res = next((e for e in events if e.get("type") == "result"), None)
        out.update(result={k: res.get(k) for k in ("subtype", "is_error", "result", "num_turns")} if res else None,
                   ok=bool(res and res.get("subtype") == "success" and not res.get("is_error") and p.returncode == 0
                           and str(res.get("result", "")).strip() == "OK"))
    out["status"] = "OK" if out["ok"] else ("AUTH_REQUIRED" if _looks_like_auth(out) else "FAILED")
    return out


def _looks_like_auth(out):
    blob = json.dumps(out).lower()
    return "authenticate" in blob or "oauth" in blob or '"loggedin": false' in blob or "login" in blob


# ---- the real paired stack (mirrors tests/phase2b/conftest.bridge_stack, no pytest) --------------------------------
class Stack:
    def __init__(self, base: Path, provider, model, registry, bridge_kwargs):
        from fastapi.testclient import TestClient
        from uri_core.app.paired_server import create_app
        from uri_core.client_runtime.manifest import ClientManifest, provision_client
        from uri_core.client_runtime.persistence import ClientPersistence
        from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
        from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, atomic_json, dpapi, provision
        from uri_supervisor_bridge.runner import SupervisedTurnRunner

        self.provider, self.model = provider, model
        server_manifest = provision(ROOT, base / "server", Path(sys.executable), 18234, "c2-paired-core")
        runtime = RuntimeIdentity(RuntimeManifest(server_manifest))
        # Exact (kind, provider, model) rows: the user's explicit selection must match one verbatim.
        rows = {("client_external_harness", "claude_code", None), ("client_external_harness", "codex_cli", None),
                ("client_external_harness", provider, model), ("server_local_model", "uri-deterministic", None)}
        self.app = create_app(runtime, composition={"policy": ReasoningSelectionPolicy(rows),
                                                    "qualified": ("remember_fact", "external_harness_task")})
        principal = str(uuid.uuid4())
        cm = ClientManifest(provision_client(server_manifest, base / "client", principal, ["remember_fact"]))
        pairings = self.app.state.client_service.pairings
        with pairings.lock:
            data = pairings._load()
            data["clients"][cm.data["client_id"]]["grants"].append("external_harness_task")
            atomic_json(pairings.path, data)
        self.cm, self.client_root = cm, Path(cm.data["client_root"])
        cred = json.loads(dpapi((self.client_root / "secure/uri-credentials.dpapi").read_bytes(), True))
        self.bridge = SupervisorBridge(self.client_root, registry=registry, **bridge_kwargs)
        self.http = TestClient(self.app)
        self.http.__enter__()
        s = self.http.post("/client/v1/session", json={"server_id": cred["server_id"], "client_id": cred["client_id"]},
                           headers={"Authorization": "Bearer " + cred["principal_token"], "X-URI-Pairing": cred["pairing_token"]}).json()
        headers = {"Authorization": "Bearer " + s["token"], "X-URI-Client": cred["client_id"]}
        self.calls = []

        self.settle_bodies = []

        def call(method, path, body):
            self.calls.append((method, path))
            if path.endswith("/settle") and isinstance(body, dict):
                self.settle_bodies.append(body.get("receipt"))      # the receipt the frozen runner built
            r = self.http.request(method, path, json=body, headers=headers)
            return r.status_code, r.json()
        self.persistence = ClientPersistence(cm)
        self.runner = SupervisedTurnRunner(cm, self.persistence, call, cm.data["server_public_key"], runtime.generation,
                                           self.bridge, harness=registry)
        # capture the AuthorizedWork the runner hands to the bridge (for post-run authority checks)
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


def ledger_dump(L, task_id):
    rows = lambda sql, *a: [dict(r) for r in L.q(sql, a)]
    out = {"task": dict(L.task(task_id) or {}),
           "attempts": rows("SELECT attempt_id,status,epoch,pid,pid_create_time,job_name,argv_sha256,session_id,resume_of,"
                            "executor_version,exit_code,end_reason,spawned_at_us,ended_at_us FROM attempt WHERE task_id=? ORDER BY attempt_id", task_id),
           "admissions": rows("SELECT attempt_id,auth_id,registration_id,round FROM admission WHERE task_id=? ORDER BY admission_id", task_id),
           "authorizations": rows("SELECT auth_id,issued_by,valid_from_us,valid_until_us,superseded_at_us,scope_json FROM authorization "
                                  "WHERE task_id=? ORDER BY auth_id", task_id),
           "decisions": rows("SELECT decision_id,attempt_id,outcome,action,reason_code,evidence_json FROM recovery_decision WHERE task_id=? "
                             "ORDER BY decision_id", task_id),
           "evidence": rows("SELECT evidence_id,attempt_id,source,kind,payload FROM evidence WHERE task_id=? ORDER BY evidence_id", task_id),
           "postcondition_results": rows("SELECT * FROM postcondition_result WHERE task_id=? ORDER BY result_id", task_id),
           "completion_records": rows("SELECT * FROM completion_record WHERE task_id=?", task_id),
           "stream": [{"attempt_id": r["attempt_id"], "stream": r["stream"], "line_no": r["line_no"], "complete": r["complete"],
                       "fence_current": r["fence_current"], "raw": bytes(r["raw"]).decode("utf-8", "replace")[:2000]}
                      for r in L.q("SELECT attempt_id,stream,line_no,complete,fence_current,raw FROM stream_event WHERE task_id=? "
                                   "ORDER BY stream_event_id", (task_id,))]}
    for a in out["admissions"]:
        pass
    return out


def authority_checks(stack: Stack, run):
    """Post-run checks that need NO further executor call. Each entry: expectation vs observed."""
    from uri_core.client_contracts import digest
    w, signed, request, reasoning = (stack.captured.get(k) for k in ("work", "signed", "request", "reasoning"))
    checks = []
    if w is None:
        return [{"check": "captured_work", "observed": "none (bridge never executed)", "pass": None}]
    tid = w.task_id
    L = stack.L

    def add(name, expect, observed, ok):
        checks.append({"check": name, "expected": expect, "observed": observed, "pass": bool(ok)})
    # 1. replay of the very same operation: never a second task, never NOT_STARTED
    before = L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (tid,))[0]
    r = stack.bridge.execute(w)
    after = L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (tid,))[0]
    add("replay_same_ticket", "execution_uncertain / DUPLICATE_OPERATION, no new attempt", {"result": r, "attempts": [before, after]},
        r[0] == "execution_uncertain" and r[2] == "DUPLICATE_OPERATION" and before == after)
    # 2. authority closed after settlement: latest authorization row has an empty validity
    row = L.q1("SELECT valid_from_us,valid_until_us,issued_by FROM authorization WHERE task_id=? AND superseded_at_us IS NULL "
               "ORDER BY auth_id DESC LIMIT 1", (tid,))
    add("authority_closed_after_settlement", "valid_until_us <= now, issued_by uri_supervisor_bridge",
        dict(row) if row else None, row is not None and row["valid_until_us"] is not None and row["valid_until_us"] <= L.now_us())
    binding, pk, gen = stack.runner._binding(stack.captured["session"]), stack.runner.server_public_key, stack.runner.generation
    now = signed["ticket"]["issued_at"]

    def refused(**kw):
        req = kw.pop("request", request)
        rs = kw.pop("reasoning", reasoning)
        try:
            verify_authority(signed, request=req, reasoning=rs, binding=binding, server_public_key=pk, generation=kw.pop("generation", gen),
                             now=kw.pop("now", now))
            return "ACCEPTED"
        except BridgeRefused as exc:
            return exc.code
    # 3. changed task arguments
    tampered = json.loads(json.dumps(request))
    tampered["arguments"]["inputs"]["instruction"] += " and also delete everything"
    add("tampered_arguments", "ARGUMENT_DIGEST_MISMATCH", refused(request=tampered), refused(request=tampered) == "ARGUMENT_DIGEST_MISMATCH")
    # 4. changed confirmed-intent binding
    other_intent = {**request, "intent_digest": digest({"other": 1})}
    add("other_confirmed_intent", "APPROVAL_DIGEST_MISMATCH", refused(request=other_intent), refused(request=other_intent) == "APPROVAL_DIGEST_MISMATCH")
    # 5. provider substitution at the ticket level is NOT bound by the frozen ticket (documented); the runner binds it
    other = {**reasoning, "provider": "claude_code" if reasoning["provider"] != "claude_code" else "codex_cli", "model": None}
    add("provider_change_at_ticket_level", "ACCEPTED by verify_authority (ticket has no provider field); refused by SupervisedTurnRunner "
        "selection binding (see swap mode) and by registry/allowed_executors", refused(reasoning=other), True)
    # 6. server generation change / deadline
    add("generation_change", "TICKET_REFUSED", refused(generation=str(uuid.uuid4())), refused(generation=str(uuid.uuid4())) == "TICKET_REFUSED")
    late = refused(now=signed["ticket"]["deadline"] + 1)
    add("after_deadline", "TICKET_REFUSED or TICKET_DEADLINE_PASSED", late, late in ("TICKET_REFUSED", "TICKET_DEADLINE_PASSED"))
    # 7. the verified receipt cites ledger facts, not executor words
    ev = run.get("receipt_evidence") or []
    add("receipt_basis_is_ledger", "basis uri_supervisor_postcondition_verified, supervisor_task == operation id",
        ev, bool(ev) and all(e.get("basis") == "uri_supervisor_postcondition_verified" and e.get("supervisor_task") == tid for e in ev)
        if run.get("final_code") == "SETTLED_VERIFIED" else True)
    # 8. restart does not revive anything: a fresh bridge on the same root launches nothing, state unchanged
    state_before = L.task(tid)["state"]
    stack.bridge.close()
    b2 = SupervisorBridge(stack.client_root, registry=stack.bridge.registry, executors=stack.bridge.executors)
    rep = b2.reconcile_restart()
    attempts_after = b2.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (tid,))[0]
    open_auth = b2.L.q1("SELECT COUNT(*) FROM authorization WHERE task_id=? AND superseded_at_us IS NULL AND (valid_until_us IS NULL OR valid_until_us>?)",
                        (tid, b2.L.now_us()))[0]
    add("restart_revives_nothing", "same state, same attempt count, zero open authorizations",
        {"startup_report": rep, "state": [state_before, b2.L.task(tid)["state"]], "attempts": [after, attempts_after], "open_auth": open_auth},
        b2.L.task(tid)["state"] == state_before and attempts_after == after and open_auth == 0)
    b2.close()
    stack.bridge = b2
    return checks


def build_registry(provider, probe, evidence_file: Path):
    """Phase 1 HarnessRegistry composed exactly as the worker does, plus run-scoped auth evidence and qualification.
    The probe result is trusted composition input (it was observed by this process); nothing is persisted."""
    from uri_harness_adapters import default_registry
    verdict = {provider: bool(probe.get("ok"))}
    reg = default_registry(auth_probe=lambda hid: verdict.get(hid))   # None for other providers = AUTH_UNVERIFIED
    if probe.get("ok"):
        # C7 gate 4 inputs: live smoke run (the probe) + containment evidence (Phase 2A job objects). Run-scoped:
        # the production worker still composes default_registry() with nothing qualified.
        reg.qualify(provider, "NATIVE_QUALIFIED", sha256_file(evidence_file))
    return reg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=sorted(SPECS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--mode", default="run", choices=["run", "swap", "crash", "restart-only", "crash-child"])
    ap.add_argument("--base", default=None, help="client/server state dir under work/c1 (default: fresh)")
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--attempt1-timeout", type=float, default=None, help="induced supervisor timeout for attempt 1 only")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--inactivity", type=float, default=150)
    ap.add_argument("--crash-at", default="mid_stream")
    ap.add_argument("--skip-probe", action="store_true")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    evidence = Path(a.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    tag = a.tag or f"{a.provider}_{a.mode}_{time.strftime('%H%M%S')}"
    report = {"tag": tag, "provider": a.provider, "model": a.model, "mode": a.mode, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "interpreter": sys.executable, "root": str(ROOT)}
    probe_file = evidence / f"probe_{a.provider}.json"
    if a.skip_probe and probe_file.exists():
        probe = json.loads(probe_file.read_text())
    else:
        probe = direct_probe(a.provider, a.model, evidence)
        probe_file.write_text(jdump(probe))
    report["direct_probe"] = {k: probe.get(k) for k in ("status", "ok", "exit", "version", "executable", "stdout_sha256", "agent_text",
                                                        "result", "failures", "auth_status", "forwarded_env_keys", "duration_s")}
    report["direct_cli_status"] = probe["status"]
    base = Path(a.base) if a.base else ROOT / "work/c1" / f"p2c_{tag}"
    report["base"] = str(base)

    if a.mode == "restart-only":
        reg = build_registry(a.provider, probe, probe_file)
        client_root = base / "client"
        b = SupervisorBridge(client_root, registry=reg, executors={a.provider: ExecutorBinding(spec=SPECS[a.provider])})
        report["startup_report"] = b.reconcile_restart()
        report["tasks"] = [dict(r) for r in b.L.q("SELECT task_id,state,reason_code,attempt_count FROM task")]
        report["attempt_identities"] = [dict(r) for r in b.L.q("SELECT attempt_id,status,pid,pid_create_time,end_reason FROM attempt")]
        b.close()
        _finish(evidence, tag, report)
        return

    if a.mode == "crash":
        # child: full stack + real executor, killed by the supervisor's crash point while the executor streams
        child_tag = tag + "_child"
        cmd = [sys.executable, __file__, "--provider", a.provider, "--evidence", str(evidence), "--mode", "crash-child",
               "--base", str(base), "--skip-probe", "--tag", child_tag, "--timeout", str(a.timeout), "--inactivity", str(a.inactivity)]
        if a.model:
            cmd += ["--model", a.model]
        env = {**os.environ, "URI_SUPERVISOR_CRASH_AT": a.crash_at}
        t0 = time.time()
        p = subprocess.run(cmd, env=env, capture_output=True, timeout=a.timeout + 120)
        report["child"] = {"exit": p.returncode, "duration_s": round(time.time() - t0, 1), "crash_at": a.crash_at,
                           "stdout_tail": p.stdout.decode("utf-8", "replace")[-1500:], "stderr_tail": p.stderr.decode("utf-8", "replace")[-1500:]}
        # before restart: is the real executor still alive? (job object is kill-on-close: it must not be)
        import sqlite3
        import psutil
        db = base / "client/control/supervisor/ledger.db"
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        atts = [dict(r) for r in con.execute("SELECT attempt_id,task_id,status,pid,pid_create_time,end_reason FROM attempt")]
        tasks = [dict(r) for r in con.execute("SELECT task_id,state,reason_code FROM task")]
        con.close()
        alive = []
        for at in atts:
            if at["pid"]:
                try:
                    pr = psutil.Process(at["pid"])
                    alive.append({"pid": at["pid"], "name": pr.name(), "create_time": pr.create_time(), "same_identity":
                                  abs(pr.create_time() * 1e6 - (at["pid_create_time"] or 0)) < 2e6})
                except psutil.NoSuchProcess:
                    pass
        report["before_restart"] = {"attempts": atts, "tasks": tasks, "executor_processes_alive": alive}
        reg = build_registry(a.provider, probe, probe_file)
        t1 = time.time()
        b = SupervisorBridge(base / "client", registry=reg, executors={a.provider: ExecutorBinding(spec=SPECS[a.provider])})
        report["restart"] = {"duration_s": round(time.time() - t1, 2), "startup_report": b.reconcile_restart()}
        tid = tasks[0]["task_id"] if tasks else None
        if tid:
            report["after_restart"] = ledger_dump(b.L, tid)
            report["after_restart"]["open_authorizations"] = b.L.q1(
                "SELECT COUNT(*) FROM authorization WHERE task_id=? AND superseded_at_us IS NULL AND (valid_until_us IS NULL OR valid_until_us>?)",
                (tid, b.L.now_us()))[0]
        b.close()
        _finish(evidence, tag, report)
        return

    # ---- run / swap / crash-child: the governed chain -------------------------------------------------------------
    reg = build_registry(a.provider, probe, probe_file)
    report["registry_discover"] = reg.discover()
    spec = SPECS[a.provider]
    binding = ExecutorBinding(spec=spec, version=spec.probe_version(), executable_sha256=probe.get("executable_sha256"))
    stack = Stack(base, a.provider, a.model, reg, {"executors": {a.provider: binding}, "timeout_s": a.timeout, "inactivity_s": a.inactivity})
    if a.attempt1_timeout:
        real_run_attempt, n = stack.bridge.sup.run_attempt, {"i": 0}

        def run_attempt(admitted, **kw):
            n["i"] += 1
            if n["i"] == 1:
                kw["timeout_s"], kw["inactivity_s"] = a.attempt1_timeout, a.attempt1_timeout
            return real_run_attempt(admitted, **kw)
        stack.bridge.sup.run_attempt = run_attempt
        report["induced"] = f"attempt 1 supervisor timeout {a.attempt1_timeout}s (interruption injected by the qualification harness)"
    selection = {"kind": "client_external_harness", "provider": a.provider, "model": a.model}
    approvals = []
    run = {}
    try:
        session = str(uuid.uuid4())
        t0 = time.time()
        if a.mode == "swap":
            other = {"kind": "client_external_harness", "provider": "claude_code" if a.provider != "claude_code" else "codex_cli", "model": None}
            turn = stack.runner.begin(a.text, session, selection)
            run["begin_state"] = turn.get("state")
            final = stack.runner.decide(a.text, session, other, turn, True) if turn.get("state") == "approval_required" else turn
            run["swapped_to"] = other
        else:
            final = stack.runner.run(a.text, session, selection, lambda req: approvals.append({k: req.get(k) for k in
                                                                                             ("capability_id", "arguments", "approval_digest", "intent_digest")}) or True)
        run["duration_s"] = round(time.time() - t0, 1)
        run["approval_requests_shown"] = approvals
        run["final_code"], run["final_state"] = final.get("code"), final.get("state")
        run["final_message"] = final.get("message")
        run["turn_id"] = final.get("turn_id")
        run["server_calls"] = [p for _, p in stack.calls]
        rec = stack.turn_record(final["turn_id"]) if final.get("turn_id") else None
        run["server_turn_record"] = {k: rec.get(k) for k in ("state", "dispatched", "execution_outcome", "execution_closed", "operation_id",
                                                             "execution_reported")} if rec else None
        op = rec.get("operation_id") if rec else None
        if op and stack.L.task(op):
            run["ledger"] = ledger_dump(stack.L, op)
        run["result_files"] = [{"path": str(p), "bytes": p.stat().st_size, "sha256": sha256_file(p), "content": p.read_text(errors="replace")[:200]}
                               for p in stack.result_files()]
        rec_exec = (rec or {}).get("execution") or {}
        # the receipt the frozen runner built is journaled on the client
        j = stack.client_root / "control" / "execution_journal.json"
        if j.exists():
            try:
                jd = json.loads(j.read_text())
                for key in ("settled", "receipts"):
                    pass
                run["client_journal_keys"] = sorted(jd) if isinstance(jd, dict) else type(jd).__name__
            except ValueError:
                pass
        run["receipts_sent"] = stack.settle_bodies
        run["receipt_evidence"] = (stack.settle_bodies[-1] or {}).get("evidence") if stack.settle_bodies else None
        report["run"] = run
        if a.mode == "run" and run.get("ledger"):
            report["authority_checks"] = authority_checks(stack, run)
    finally:
        try:
            stack.close()
        except Exception as exc:  # noqa: BLE001
            report["close_error"] = repr(exc)
    _finish(evidence, tag, report)


def _receipt_evidence(stack, turn_id):
    """Evidence list of the receipt as the server stored it (settle result), if present."""
    try:
        data = stack.app.state.client_service._load()
        rec = data["turns"].get(turn_id) or {}
        ex = rec.get("execution") or {}
        if isinstance(ex, dict) and ex.get("evidence"):
            return ex["evidence"]
        ctrl = getattr(stack.app.state, "coordinator", None)
        return (rec.get("receipt") or {}).get("evidence")
    except Exception:  # noqa: BLE001
        return None


def _finish(evidence: Path, tag, report):
    report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out = evidence / f"{tag}.json"
    out.write_text(jdump(report), encoding="utf-8")
    summary = {k: report.get(k) for k in ("tag", "direct_cli_status")}
    run = report.get("run") or {}
    summary.update({k: run.get(k) for k in ("final_code", "final_state")})
    if run.get("ledger"):
        t = run["ledger"]["task"]
        summary["ledger_state"], summary["attempts"] = t.get("state"), len(run["ledger"]["attempts"])
        summary["decisions"] = [(d["outcome"], d["action"], d["reason_code"]) for d in run["ledger"]["decisions"]]
    if report.get("authority_checks"):
        summary["authority_checks_failed"] = [c["check"] for c in report["authority_checks"] if c["pass"] is False]
    if "child" in report:
        summary["child_exit"] = report["child"]["exit"]
        summary["executor_alive_before_restart"] = report["before_restart"]["executor_processes_alive"]
        summary["after_restart_state"] = (report.get("after_restart") or {}).get("task", {}).get("state")
    print(json.dumps(summary, default=str))
    print("REPORT", out)


if __name__ == "__main__":
    main()
