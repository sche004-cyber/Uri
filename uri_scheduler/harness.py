"""Harness gate + supervised execution for scheduled work.

Gate (before every dispatch, nothing cached):
  * the executable resolves (native `claude.exe` behind the npm shim, as Phase 2C/OQ require);
  * qualification: `phase2d` = a persisted, signed Phase 2D record for `claude_code` re-validates for THIS client
    (uri_supervisor_bridge.qualification.compose_client); `probe` = executable + version + live auth only, an explicitly
    weaker mode for isolated qualification runs, labelled in every receipt;
  * authentication: the CLI's own `claude auth status` under the client-profile home (never a credential read, never
    a login). A shared owner login is not used: USERPROFILE/HOME point at the client home (ISO-1).
Any failure returns a stable code (`NOT_INSTALLED`, `NOT_QUALIFIED:<why>`, `NOT_AUTHENTICATED`, `AUTH_UNKNOWN`) and
no task is created.

Execution reuses the accepted Phase 2 supervisor exactly as SupervisorBridge does, with the scheduler's job grant in
place of a Core execution ticket: one supervisor task per scheduler attempt (deterministic id, so the same attempt can
never create two tasks), scope = {read, local_write} inside a fresh per-attempt workspace, the one executor named by the
job's authority, validity bounded by the occurrence deadline. URI-observed postcondition: `scene.json` exists and is a
non-empty regular file. Quota exhaustion is detected by the supervisor from the persisted stream; the per-provider
breaker blocks further admission until the provider's reset. There is no fallback provider.

Fixture mode (`claude_fixture`) runs a SYNTHETIC stand-in that speaks Claude's stream-json dialect. It is never
reported as Claude: every attempt row and receipt carries mode FIXTURE.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from uri_supervisor.executors import CLAUDE_CODE, CLAUDE_RULES, ExecutorSpec
from uri_supervisor.ledger import LedgerError, LedgerRefused
from uri_supervisor.supervisor import Supervisor

POOL = "harness_slot"
CAPABILITY = "harness_task"
FIXTURE_ID = "claude_fixture"
LIVE_ID = "claude_code"
TASK_NS = uuid.UUID("7c0b6a3e-6f53-4c2a-9a55-2f2b7e2d9a10")
FIXTURE_SPEC = ExecutorSpec(FIXTURE_ID, None, (), rules=CLAUDE_RULES, stdin="instructions", rule_set_id="claude_fixture.v1")


@dataclass
class GateResult:
    available: bool
    code: str
    mode: str
    executor_id: str
    executable: str | None = None
    version: str | None = None
    qualification: str | None = None
    detail: dict = field(default_factory=dict)

    def to_json(self):
        return {"available": self.available, "code": self.code, "mode": self.mode, "executor_id": self.executor_id,
                "executable": self.executable, "version": self.version, "qualification": self.qualification,
                "detail": self.detail}


@dataclass
class RunOutcome:
    status: str                  # completed | quota | failed | uncertain | cancelled | not_started
    reason: str
    supervisor_task_id: str
    receipt: dict


def client_environ(client_home: Path | None, base=None) -> dict:
    env = dict(os.environ if base is None else base)
    if client_home is not None:
        h = str(Path(client_home).resolve())
        env["USERPROFILE"] = h
        env["HOME"] = h
    return env


class ClaudeHarness:
    def __init__(self, state_dir, *, mode="live", client_home=None, client_root=None, qualification="phase2d",
                 fixture_script=None, fixture_python=None, timeout_s=900.0, inactivity_s=300.0, gate_probe=None):
        if mode not in ("live", "fixture"):
            raise ValueError("BAD_MODE")
        if qualification not in ("phase2d", "probe"):
            raise ValueError("BAD_QUALIFICATION_MODE")
        self.mode = mode
        self.state_dir = Path(state_dir)
        self.client_home = Path(client_home) if client_home else None
        self.client_root = Path(client_root) if client_root else None
        self.qualification = qualification
        self.fixture_script = Path(fixture_script).resolve() if fixture_script else None
        self.fixture_python = fixture_python or sys.executable
        self.timeout_s, self.inactivity_s = float(timeout_s), float(inactivity_s)
        self._gate_probe = gate_probe              # tests: callable() -> GateResult
        self.executor_id = FIXTURE_ID if mode == "fixture" else LIVE_ID
        self.sup = None
        self.startup_report = []
        self._running: dict[str, int] = {}
        self._cancelled: set[str] = set()       # task ids withdrawn by the owner (bridge discipline, review round 6)
        self._cancel_lock = threading.Lock()

    # ---- lifecycle ------------------------------------------------------------------------------------------------
    def open(self):
        control = self.state_dir / "supervisor"
        control.mkdir(parents=True, exist_ok=True)
        self.sup = Supervisor(control / "ledger.db")            # supervisor startup recovery runs here
        L = self.sup.ledger
        if L.q1("SELECT 1 FROM resource_pool WHERE name=?", (POOL,)) is None:
            self.sup.registry.create_pool(POOL, 1, kind="harness")
        qp = "quota_" + self.executor_id
        if L.q1("SELECT 1 FROM resource_pool WHERE name=?", (qp,)) is None:
            self.sup.registry.create_pool(qp, 1, kind="quota")
        spec = FIXTURE_SPEC if self.mode == "fixture" else CLAUDE_CODE
        current = {r["executor_id"]: r for r in self.sup.registry.current_registrations()}
        row = current.get(spec.executor_id)
        claims = {POOL: 1, qp: 1}
        if row is None or json.loads(row["spec_json"]) != spec.to_json() or json.loads(row["claims_json"]) != claims:
            self.sup.registry.register_executor(spec, capabilities=[CAPABILITY], claims=claims, quota_pools=[qp])
        self.startup_report = self._revoke_unfinished("RESTART")
        return self

    def close(self):
        if self.sup is not None:
            self.sup.close()
            self.sup = None

    def _expire(self, tid):
        L = self.sup.ledger
        row = L.q1("SELECT scope_json FROM authorization WHERE task_id=? AND superseded_at_us IS NULL ORDER BY auth_id DESC LIMIT 1", (tid,))
        scope = json.loads(row[0]) if row else {}
        self.sup.supersede_authorization(tid, scope=scope, valid_until_us=L.now_us(), issued_by="uri_scheduler")

    def _revoke_unfinished(self, why):
        """Same restart discipline as SupervisorBridge: nothing re-launches by itself; the scheduler decides."""
        L = self.sup.ledger
        out = []
        now = L.now_us()
        rows = L.q("SELECT t.task_id,t.state,t.reason_code FROM task t WHERE t.state IN ('QUEUED','RETRY_SAFE') OR EXISTS "
                   "(SELECT 1 FROM authorization a WHERE a.task_id=t.task_id AND a.superseded_at_us IS NULL "
                   "AND (a.valid_until_us IS NULL OR a.valid_until_us>?)) ORDER BY t.task_seq", (now,))
        for t in rows:
            self._expire(t["task_id"])
            state = t["state"]
            if state in ("QUEUED", "RETRY_SAFE"):
                with contextlib.suppress(LedgerError):
                    L.transition(t["task_id"], "FAILED", "AUTHORITY_REVOKED_" + why, t["reason_code"])
                state = L.task(t["task_id"])["state"]
            out.append({"task_id": t["task_id"], "was": t["state"], "state": state})
        return out

    # ---- gate -----------------------------------------------------------------------------------------------------
    def gate(self) -> GateResult:
        if self._gate_probe is not None:
            return self._gate_probe()
        if self.mode == "fixture":
            ok = self.fixture_script is not None and self.fixture_script.is_file()
            return GateResult(ok, "AVAILABLE" if ok else "NOT_INSTALLED", "FIXTURE", FIXTURE_ID,
                              str(self.fixture_script) if self.fixture_script else None, "fixture", "FIXTURE_ONLY")
        from uri_supervisor_bridge import qualification as Q   # noqa: deferred: needs cryptography + Core
        found = shutil.which("claude")
        exe = Q.native_executable("claude_code", found) if found else None
        if exe is None or not Path(exe).is_file():
            return GateResult(False, "NOT_INSTALLED", "LIVE", LIVE_ID, str(found) if found else None)
        exe = str(exe)
        version = CLAUDE_CODE.probe_version() if found else None
        qual = "PROBE_ONLY"
        detail = {}
        if self.qualification == "phase2d":
            if self.client_root is None or not (self.client_root / "client-manifest.json").is_file():
                return GateResult(False, "NOT_QUALIFIED:NO_CLIENT_MANIFEST", "LIVE", LIVE_ID, exe, version, None)
            manifest = json.loads((self.client_root / "client-manifest.json").read_text(encoding="utf-8"))
            try:
                comp = Q.compose_client(self.client_root, trust=Q.RecordTrust.from_manifest(manifest),
                                        auth_probe=lambda _h: True)       # auth is probed below, under the client home
            except Exception as exc:                                   # noqa: BLE001 - any failure is "not qualified"
                return GateResult(False, "NOT_QUALIFIED:" + type(exc).__name__, "LIVE", LIVE_ID, exe, version, None)
            row = next((r for r in comp.report if r["provider"] == LIVE_ID), None)
            if row is None or row["status"] != "QUALIFIED":
                why = "NO_RECORD" if row is None else str(row.get("reason"))
                return GateResult(False, "NOT_QUALIFIED:" + why, "LIVE", LIVE_ID, exe, version, None, {"report": comp.report})
            qual = "PHASE2D:" + row["evidence_sha256"][:16]
            exe = row["executable"]
            detail["record"] = {k: row.get(k) for k in ("version", "executable_sha256", "expires_at", "level")}
        auth = Q.native_auth_probe("claude_code", exe, client_environ(self.client_home))
        if auth is not True:
            return GateResult(False, "NOT_AUTHENTICATED" if auth is False else "AUTH_UNKNOWN", "LIVE", LIVE_ID, exe, version,
                              qual, detail)
        return GateResult(True, "AVAILABLE", "LIVE", LIVE_ID, exe, version, qual, detail)

    # ---- execution ------------------------------------------------------------------------------------------------
    @staticmethod
    def task_id_for(scheduler_attempt_key: str) -> str:
        return str(uuid.uuid5(TASK_NS, scheduler_attempt_key))

    def breaker_reset_us(self):
        """Wall-clock instant (us) when the per-provider quota breaker may reopen, or None when it is not open."""
        L = self.sup.ledger
        row = L.q1("SELECT * FROM resource_pool WHERE name=?", ("quota_" + self.executor_id,))
        if row is None or row["breaker_state"] != "open":
            return None
        if row["breaker_until_wall_us"] is not None:
            return int(row["breaker_until_wall_us"])
        if row["breaker_until_mono_ns"] is not None:
            left_ns = max(0, int(row["breaker_until_mono_ns"]) - L.clock.mono_ns())
            return L.now_us() + left_ns // 1000
        return L.now_us()

    def settlement(self, task_id) -> dict | None:
        """What the supervisor ledger durably knows about one task (used by scheduler restart recovery)."""
        L = self.sup.ledger
        t = L.task(task_id)
        if t is None:
            return None
        atts = L.q("SELECT status, spawned_at_us FROM attempt WHERE task_id=?", (task_id,))
        spawned = any(a["spawned_at_us"] is not None or a["status"] in ("SPAWNING", "RUNNING", "ENDED", "FENCED") for a in atts)
        last = L.q1("SELECT outcome, reason_code, evidence_json FROM recovery_decision WHERE task_id=? ORDER BY decision_id DESC LIMIT 1",
                    (task_id,))
        absence = False
        if last is not None:
            effects = (json.loads(last["evidence_json"]) or {}).get("effects") or []
            activity = L.q1("SELECT COUNT(*) FROM evidence WHERE task_id=? AND source='executor_report' AND kind IN "
                            "('tool_result','tool_result_batch','file_change')", (task_id,))[0]
            absence = bool(effects) and activity == 0 and all(
                e.get("safe") and e.get("reason") == "LOCAL_WRITE_ABSENCE_PROVEN" for e in effects)
        return {"task_id": task_id, "state": t["state"], "spawned": spawned, "absence_proven": absence,
                "last_decision": dict(last) | {"evidence_json": None} if last else None}

    def cancel(self, task_id) -> dict:
        """Withdraw one attempt's task. Before submission/admission it will never spawn; between admission and spawn the
        attempt is ended spawn_failed; while running the executor is killed through its job object (SupervisorBridge
        semantics). Safe from another thread while `run` executes."""
        with self._cancel_lock:
            self._cancelled.add(task_id)
            aid = self._running.get(task_id)
        if aid is None:
            return {"granted": False, "reason": "NOT_RUNNING", "recorded": True}
        r = self.sup.request_cancel(aid)
        if not r.get("granted"):
            # Admitted but not yet active in the supervisor (between our post-admission check and `_supervise`): pre-arm
            # the supervisor's kill set so its FIRST supervision poll kills the executor, milliseconds after the process
            # starts and before Claude Code can initialise (review round 7, R6-1). `request_cancel` itself refuses
            # until the attempt is active; the accepted supervisor is not modified, only its documented kill set is fed.
            # A guarantee that the process is never started at all would need a change to the accepted supervisor.
            self.sup._cancel.add(aid)
            r = {"granted": True, "reason": "PRE_ARMED_BEFORE_ACTIVE"}
        return r

    def _is_cancelled(self, task_id) -> bool:
        with self._cancel_lock:
            return task_id in self._cancelled

    def run(self, *, attempt_key, principal, workspace: Path, instructions: bytes, gate: GateResult,
            valid_until_us=None, expected_file="scene.json") -> RunOutcome:
        L = self.sup.ledger
        tid = self.task_id_for(attempt_key)
        workspace = Path(workspace).resolve()
        request = {"attempt_key": attempt_key, "executor": self.executor_id, "mode": gate.mode,
                   "instructions_sha256": __import__("hashlib").sha256(instructions).hexdigest()}
        scope = {"allowed_op_classes": ["read", "local_write"], "allowed_executors": [self.executor_id],
                 "workspace": str(workspace), "capability": "uri_scheduler.job", "attempt_key": attempt_key}
        if self._is_cancelled(tid):
            return RunOutcome("cancelled", "CANCELLED_BEFORE_SUBMIT", tid, {"supervisor_task": tid})
        try:
            self.sup.submit_task(tid, principal, request,
                                 authorization={"scope": scope, "issued_by": "uri_scheduler.job_grant",
                                                "valid_until_us": valid_until_us},
                                 effects=[{"op_class": "local_write", "operation": "harness_task", "target": str(workspace),
                                           "paths": [str(workspace)], "params": {"expected_file": expected_file}}],
                                 postconditions=[{"kind": "file_regular_nonempty", "spec": {"path": str(workspace / expected_file)},
                                                  "required": True}],
                                 requirements={"capabilities": [CAPABILITY], "executors": [self.executor_id]}, max_attempts=1)
        except LedgerRefused as exc:
            if L.task(tid) is not None:
                return RunOutcome("uncertain", "DUPLICATE_ATTEMPT", tid, {"supervisor_task": tid})
            return RunOutcome("not_started", "SUBMIT_" + str(exc.code), tid, {})
        receipt = {"supervisor_task": tid, "ledger_id": L.ledger_id(), "executor": self.executor_id, "mode": gate.mode,
                   "qualification": gate.qualification, "executable": gate.executable, "version": gate.version}
        try:
            admitted = self.sup.admit_next(only_task_id=tid)
            if admitted is None:
                self._expire(tid)
                with contextlib.suppress(LedgerError):
                    L.transition(tid, "FAILED", "NOT_ADMITTED", None)
                breaker = self.breaker_reset_us()
                status = "quota" if breaker else "not_started"
                return RunOutcome(status, "QUOTA_BREAKER_OPEN" if breaker else "NOT_ADMITTED", tid, receipt | {"reset_us": breaker})
            with self._cancel_lock:
                self._running[tid] = admitted.attempt_id
                cancelled = tid in self._cancelled
            if cancelled:                                   # withdrawn between admission and spawn: never spawn
                self._running.pop(tid, None)
                self.sup._spawn_failed(admitted, "CANCELLED_BEFORE_SPAWN")
                self._expire(tid)
                return RunOutcome("cancelled", "CANCELLED_BEFORE_SPAWN", tid, receipt)
            env = client_environ(self.client_home)
            # Claude Code `dontAsk` denies every un-approved file edit and anything outside its working directory.
            # `Edit(./**)` (relative to the per-attempt workspace, the process cwd) pre-approves edits there; Claude Code
            # applies Edit rules to every built-in file-editing tool including Write (path-scoped Write rules are not
            # consulted), so this one rule is what lets the executor write its output, and only inside the workspace
            # (review rounds 1-2, F2/F4). Reads outside the workspace stay denied by `dontAsk`.
            extra, exe = ["--allowedTools", "Edit(./**)"], gate.executable
            if self.mode == "fixture":
                exe, extra = self.fixture_python, [str(self.fixture_script)]
            try:
                self.sup.run_attempt(admitted, cwd=str(workspace), instructions=instructions, environ=env,
                                     timeout_s=self.timeout_s, inactivity_s=self.inactivity_s, resolved_executable=exe,
                                     extra_argv=extra)
            finally:
                self._running.pop(tid, None)
        except LedgerError as exc:
            with contextlib.suppress(LedgerError):
                self._expire(tid)
            return RunOutcome("uncertain", "SUPERVISOR_ERROR:" + str(exc.code), tid, receipt)
        task = L.task(tid)
        last = L.q1("SELECT * FROM recovery_decision WHERE task_id=? ORDER BY decision_id DESC LIMIT 1", (tid,))
        att = L.q1("SELECT * FROM attempt WHERE task_id=? ORDER BY attempt_id DESC LIMIT 1", (tid,))
        receipt.update({"supervisor_state": task["state"], "supervisor_reason": task["reason_code"],
                        "decision": dict(last) if last else None, "attempt": dict(att) if att else None,
                        "claims": [{"kind": r["kind"], "payload": r["payload"][:2000]} for r in L.q(
                            "SELECT kind, payload FROM evidence WHERE task_id=? AND source='executor_report' AND kind LIKE "
                            "'terminal%' ORDER BY evidence_id", (tid,))]})
        self._expire(tid)
        if task["state"] == "COMPLETE":
            return RunOutcome("completed", "POSTCONDITION_VERIFIED", tid, receipt)
        if last is not None and last["reason_code"] == "PROVIDER_QUOTA_EXHAUSTED":
            with contextlib.suppress(LedgerError):
                L.transition(tid, "FAILED", "QUOTA_DEFERRED_BY_SCHEDULER", last["reason_code"])
            return RunOutcome("quota", "PROVIDER_QUOTA_EXHAUSTED", tid, receipt | {"reset_us": self.breaker_reset_us()})
        if task["state"] in ("QUEUED", "RETRY_SAFE"):
            with contextlib.suppress(LedgerError):
                L.transition(tid, "FAILED", "SCHEDULER_SETTLED", last["reason_code"] if last else None)
        state = L.task(tid)["state"]
        if state in ("UNCERTAIN", "NEEDS_USER"):
            return RunOutcome("uncertain", f"SUPERVISOR_{state}:{last['reason_code'] if last else ''}", tid, receipt)
        return RunOutcome("failed", f"SUPERVISOR_{state}:{(last['reason_code'] if last else task['reason_code']) or ''}", tid, receipt)
