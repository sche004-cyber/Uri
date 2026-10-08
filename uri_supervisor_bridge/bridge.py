"""SupervisorBridge: one verified ticket -> one durable supervisor task -> one Phase 1 receipt outcome.

Ownership: Core (frozen) owns intent, confirmation, approval, the ticket and the settlement. The supervisor
(Phase 2A) owns admission, fenced attempts, containment and reconciliation. This bridge owns only the
translation between them, and it is deliberately narrow:

  * the task id IS the ticket's operation id (canonical UUID): the same ticket can never create two tasks;
  * the authorization row is derived from the ticket (op classes, the user's explicit executor, the per-run
    workspace, validity = [issued_at, deadline)); the supervisor re-checks that scope at every admission;
  * admission is restricted to that one task (`only_task_id`), so a ticket can never run queued foreign work;
  * when the bridge returns, the task's authority is closed: a settled ticket never leaves re-admittable work;
  * on construction (= restart) every unfinished task's authority is revoked and nothing is re-launched,
    matching Phase 1 (`ExecutionJournal.recover`: claimed work becomes execution_uncertain, never a relaunch);
  * `verified` is returned only when the supervisor's ledger says COMPLETE, i.e. URI itself observed the
    required postcondition; executor claims never reach the receipt as success.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from uri_core.client_runtime.harness import HarnessError, resolve_command
from uri_supervisor.executors import ExecutorSpec
from uri_supervisor.ledger import LedgerError, LedgerRefused
from uri_supervisor.supervisor import Supervisor

from .authority import CHECK_NAME, AuthorizedWork, BridgeRefused

# Same prefix the frozen client runtime / server use: "nothing effect-capable was started".
NOT_STARTED = "NOT_STARTED:"
POOL = "harness_slot"
CAPABILITY = "harness_task"
TOOL_ACTIVITY = ("tool_result", "tool_result_batch", "file_change")


@dataclass(frozen=True)
class ExecutorBinding:
    """How one user-selectable provider is run by the supervisor. `spec.executor_id` must equal the provider id."""
    spec: ExecutorSpec
    resolved_executable: str | None = None
    extra_argv: tuple = ()
    version: str | None = None
    # Optional pin (Phase 2C): SHA-256 of the executable FILE the qualification evidence was produced with. When set,
    # the bridge hashes the resolved file before every run and refuses a different one (`EXECUTOR_BINARY_HASH_MISMATCH`).
    # Note the limit: for a launcher shim (npm `codex.CMD`) this pins the shim, not the interpreter it starts.
    executable_sha256: str | None = None
    # Optional pin (Phase 2D): the models this provider was qualified with. When set, a ticket whose bound selection
    # names another model (or none) is refused before any task exists (`MODEL_NOT_QUALIFIED`). Qualification is
    # evidence about one (provider, executable, model) triple; a different model never inherits it silently.
    qualified_models: tuple | None = None
    # Launch-chain pins (independent review round 1, D4): ((abs path, sha256), ...) every file the launcher executes,
    # and ((name, abs path), ...) names the launcher resolves on PATH (e.g. `node` for the npm `codex.cmd` shim). Both are
    # re-checked before every run; a replaced payload behind an unchanged shim is refused before any task exists.
    pinned_files: tuple = ()
    resolve_pins: tuple = ()
    # Re-validation hook (independent review round 2, R2-1): called before EVERY execution; returns None when the
    # persisted qualification (record bytes, signature, expiry, evidence, launch chain, version) still holds, else a
    # reason code. Without it a long-lived worker kept honouring a record that had expired or lost its evidence.
    revalidate: object = None


def _fit(s, n=128):
    return s if len(s) <= n else s[:n]


def _file_sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _same_file(a, b):
    """True only when both paths resolve to the same existing file (case-insensitive on Windows)."""
    try:
        ra, rb = os.path.realpath(a), os.path.realpath(b)
        if not (os.path.isfile(ra) and os.path.isfile(rb)):
            return False
        return os.path.normcase(ra) == os.path.normcase(rb) or os.path.samefile(ra, rb)
    except OSError:
        return False


class SupervisorBridge:
    def __init__(self, client_root, *, registry=None, executors: dict | None = None, clock=time.time,
                 max_attempts: int = 2, timeout_s: float = 120, inactivity_s: float = 60):
        self.root = Path(client_root).resolve()
        self.registry = registry                      # Phase 1 HarnessRegistry: install/auth/qualification gate
        self.executors = dict(executors or {})
        self.clock = clock
        self.max_attempts, self.timeout_s, self.inactivity_s = int(max_attempts), float(timeout_s), float(inactivity_s)
        self._lock = threading.RLock()
        self._cancel_lock = threading.Lock()
        self._cancelled: set[str] = set()        # task ids whose caller withdrew the work (Phase 2D)
        self._running: dict[str, int] = {}       # task id -> attempt id currently supervised by this bridge
        for provider, b in self.executors.items():
            if b.spec.executor_id != provider:
                raise BridgeRefused("EXECUTOR_BINDING_ID_MISMATCH", provider)
        control = self.root / "control" / "supervisor"
        control.mkdir(parents=True, exist_ok=True)
        self.sup = Supervisor(control / "ledger.db")   # startup recovery runs here (new epoch)
        self.L = self.sup.ledger
        self.startup_report = self._revoke_unfinished_authority("RESTART")
        self._ensure_pool()
        self._ensure_registrations()

    # ---- composition ----------------------------------------------------------------------
    @staticmethod
    def quota_pool(provider):
        """One breaker per provider: a quota hit on one provider never blocks the user's explicit choice of another."""
        return "quota_" + provider

    def _ensure_pool(self):
        if self.L.q1("SELECT 1 FROM resource_pool WHERE name=?", (POOL,)) is None:
            self.sup.registry.create_pool(POOL, 1, kind="harness")
        for provider in self.executors:
            if self.L.q1("SELECT 1 FROM resource_pool WHERE name=?", (self.quota_pool(provider),)) is None:
                self.sup.registry.create_pool(self.quota_pool(provider), 1, kind="quota")

    def _ensure_registrations(self):
        current = {r["executor_id"]: r for r in self.sup.registry.current_registrations()}
        for provider, b in self.executors.items():
            row = current.get(provider)
            want = json.dumps(b.spec.to_json(), sort_keys=True, separators=(",", ":"))
            qp = [self.quota_pool(provider)]
            # The quota pool is also CLAIMED: Phase 2A consults breakers only on claimed pools (admission.admit_next),
            # so an open per-provider breaker must sit on a pool the attempt claims to actually block admission.
            claims = {POOL: 1, self.quota_pool(provider): 1}
            if row is not None and json.dumps(json.loads(row["spec_json"]), sort_keys=True, separators=(",", ":")) == want \
                    and json.loads(row["quota_pools_json"]) == qp and json.loads(row["claims_json"]) == claims:
                continue
            self.sup.registry.register_executor(b.spec, capabilities=[CAPABILITY], claims=claims, quota_pools=qp,
                                                version=b.version)

    def close(self):
        self.sup.close()

    # ---- restart discipline --------------------------------------------------------------
    def _revoke_unfinished_authority(self, why):
        """Every task that is not COMPLETE loses its authorization; QUEUED/RETRY_SAFE become FAILED. Nothing is
        re-launched. Returns a public report (ids and states only)."""
        out = []
        now = self.L.now_us()
        rows = self.L.q("SELECT t.task_id,t.state,t.reason_code FROM task t WHERE t.state IN ('QUEUED','RETRY_SAFE') OR EXISTS "
                        "(SELECT 1 FROM authorization a WHERE a.task_id=t.task_id AND a.superseded_at_us IS NULL "
                        "AND (a.valid_until_us IS NULL OR a.valid_until_us>?)) ORDER BY t.task_seq", (now,))
        for t in rows:
            tid, state = t["task_id"], t["state"]
            self._expire_authorization(tid)
            new_state = state
            if state in ("QUEUED", "RETRY_SAFE"):
                try:
                    self.L.transition(tid, "FAILED", "AUTHORITY_REVOKED_" + why, t["reason_code"])
                    new_state = "FAILED"
                except LedgerError:
                    new_state = self.L.task(tid)["state"]
            out.append({"task_id": tid, "was": state, "state": new_state, "authority": "revoked"})
        return out

    def _expire_authorization(self, tid):
        row = self.L.q1("SELECT scope_json FROM authorization WHERE task_id=? AND superseded_at_us IS NULL ORDER BY auth_id DESC LIMIT 1", (tid,))
        scope = json.loads(row[0]) if row else {}
        now = self.L.now_us()
        # [now, now) is empty: no admission can ever find this authorization valid again.
        self.sup.supersede_authorization(tid, scope=scope, valid_until_us=now, issued_by="uri_supervisor_bridge")

    def reconcile_restart(self):
        """Public view of what construction did: recovered decisions are in the ledger; this lists revocations."""
        return list(self.startup_report)

    # ---- execution ------------------------------------------------------------------------
    def execute(self, work: AuthorizedWork, *, context=None):
        """-> (outcome, evidence, failure_category) in the frozen TurnRunner/ExecutionReceipt vocabulary
        ('verified' | 'failed' | 'quota' | 'execution_uncertain').

        `context` (UI/operations slice, review round 2 OPS-1R): the caller's own execution id, recorded durably in the
        task's request row so the ledger itself binds the supervisor task to exactly one worker-side execution record.
        It carries no authority and changes nothing the supervisor decides."""
        with self._lock:
            return self._execute(work, context)

    def _execute(self, work: AuthorizedWork, context=None):
        L, tid = self.L, work.task_id
        if L.task(tid) is not None:
            # The ticket's operation already exists in the ledger: dispatch may already have happened. Never
            # a second task, never NOT_STARTED.
            return "execution_uncertain", [], "DUPLICATE_OPERATION"
        if self.registry is None:
            return "failed", [], NOT_STARTED + "NO_HARNESS_REGISTRY"
        try:
            self.registry.selectable(work.provider)        # Phase 1 gate: installed + authenticated + qualified, no fallback
        except HarnessError as exc:
            return "failed", [], _fit(NOT_STARTED + "HARNESS_" + str(exc))
        binding = self.executors.get(work.provider)
        if binding is None:
            return "failed", [], NOT_STARTED + "EXECUTOR_NOT_REGISTERED"
        # One executable per provider: the binary Phase 1 qualified is the only one the supervisor may run.
        cmd = resolve_command(self.registry.executables.get(work.provider))
        qualified_exe = cmd[0] if cmd else None
        exe = binding.resolved_executable or qualified_exe
        if exe is None or qualified_exe is None or _same_file(exe, qualified_exe) is not True:
            return "failed", [], NOT_STARTED + "EXECUTOR_BINARY_MISMATCH"
        if binding.executable_sha256 is not None and _file_sha256(exe) != binding.executable_sha256:
            return "failed", [], NOT_STARTED + "EXECUTOR_BINARY_HASH_MISMATCH"
        if not self._launch_chain_intact(binding):
            return "failed", [], NOT_STARTED + "EXECUTOR_LAUNCH_CHAIN_MISMATCH"
        if binding.qualified_models is not None and work.model not in binding.qualified_models:
            return "failed", [], NOT_STARTED + "MODEL_NOT_QUALIFIED"
        if binding.revalidate is not None:
            try:
                why = binding.revalidate()
            except Exception as exc:  # noqa: BLE001  (any failure to re-establish qualification fails closed)
                why = "REVALIDATION_ERROR:" + type(exc).__name__
            if why is not None:
                return "failed", [], _fit(NOT_STARTED + "QUALIFICATION_NO_LONGER_VALID:" + str(why))
        if self._is_cancelled(tid):
            return "failed", [], NOT_STARTED + "CANCELLED"
        run_id = uuid.uuid4().hex
        work_dir = self.root / "workspace" / run_id
        work_dir.mkdir(parents=True)                       # fresh, empty: the pre-attempt fingerprint of an empty dir
        out_path = work_dir / work.expected_file
        request = {"capability_id": work.ticket.capability_id, "action": work.arguments.get("action"),
                   "argument_digest": work.ticket.argument_digest, "approval_digest": work.ticket.approval_digest,
                   "intent_digest": work.intent_digest, "ticket_digest": work.ticket_digest, "turn_id": work.ticket.turn_id,
                   "operation_id": work.ticket.operation_id, "session_id": work.ticket.session_id, "provider": work.provider,
                   "model": work.model, "expected_file": work.expected_file, "run_id": run_id,
                   "execution_id": context.get("execution_id") if isinstance(context, dict) else None}
        scope = {"allowed_op_classes": ["read", "local_write"], "allowed_executors": [work.provider], "workspace": str(work_dir),
                 "capability": work.ticket.capability_id, "ticket_digest": work.ticket_digest,
                 "approval_digest": work.ticket.approval_digest, "argument_digest": work.ticket.argument_digest}
        try:
            self.sup.submit_task(
                tid, work.principal, request,
                authorization={"scope": scope, "issued_by": "uri_core.execution_ticket",
                               "valid_from_us": work.valid_from_us, "valid_until_us": work.deadline_us},
                effects=[{"op_class": "local_write", "operation": "harness_task", "target": str(work_dir), "paths": [str(work_dir)],
                          "params": {"expected_file": work.expected_file, "argument_digest": work.ticket.argument_digest}}],
                postconditions=[{"kind": "file_regular_nonempty", "spec": {"path": str(out_path)}, "required": True}],
                requirements={"capabilities": [CAPABILITY], "executors": [work.provider]},
                max_attempts=self.max_attempts)
        except LedgerRefused as exc:
            if L.task(tid) is not None:
                return "execution_uncertain", [], "DUPLICATE_OPERATION"
            return "failed", [], _fit(NOT_STARTED + "SUBMIT_" + str(exc.code))
        instructions = (work.instruction + "\nWrite the result to a file named " + work.expected_file
                        + " in the working directory.").encode("utf-8")
        stop = "SETTLED"
        guard = 0
        try:
            while True:
                state = L.task(tid)["state"]
                if state not in ("QUEUED", "RETRY_SAFE"):
                    break
                remaining = work.ticket.deadline - self.clock()
                if remaining <= 0:
                    stop = "DEADLINE"
                    break
                if self._is_cancelled(tid):
                    stop = "CANCELLED"
                    break
                guard += 1
                if guard > self.max_attempts + 1:
                    stop = "GUARD"
                    break
                admitted = self.sup.admit_next(only_task_id=tid)
                if admitted is None:
                    stop = "NOT_ADMITTED"
                    break
                if admitted.task_id != tid:                # unreachable with only_task_id; fail closed if it ever is
                    self.sup._spawn_failed(admitted, "FOREIGN_TASK_ADMITTED")
                    raise BridgeRefused("FOREIGN_TASK_ADMITTED", admitted.task_id)
                with self._cancel_lock:
                    self._running[tid] = admitted.attempt_id
                    if tid in self._cancelled:            # cancelled between admission and spawn: never spawn
                        self.sup._spawn_failed(admitted, "CANCELLED_BEFORE_SPAWN")
                        stop = "CANCELLED"
                        break
                try:
                    self.sup.run_attempt(admitted, cwd=str(work_dir), instructions=instructions, model=work.model,
                                         timeout_s=max(1.0, min(self.timeout_s, remaining)),
                                         inactivity_s=max(1.0, min(self.inactivity_s, remaining)),
                                         resolved_executable=exe, extra_argv=list(binding.extra_argv))
                finally:
                    with self._cancel_lock:
                        self._running.pop(tid, None)
                if self._is_cancelled(tid):
                    stop = "CANCELLED"
                    break
        except LedgerError as exc:
            # The ledger refused or failed mid-run (busy, disk, invariant). Dispatch was authorized, an attempt may
            # have run: uncertain, never failed/retry. Close the ticket's authority as far as the ledger allows.
            with contextlib.suppress(LedgerError):
                self._expire_authorization(tid)
            return "execution_uncertain", [], _fit("SUPERVISOR_ERROR:" + str(exc.code))
        return self._settle(work, run_id, work_dir, out_path, stop)

    @staticmethod
    def _launch_chain_intact(binding):
        for path, digest in binding.pinned_files:
            if _file_sha256(path) != digest:
                return False
        if binding.resolve_pins:
            env_path = binding.spec.build_env(os.environ).get("PATH", "")
            for name, path in binding.resolve_pins:
                found = shutil.which(name, path=env_path)
                if not found or _same_file(found, path) is not True:
                    return False
        return True

    # ---- cancellation (Phase 2D) ---------------------------------------------------------------
    def _is_cancelled(self, tid):
        with self._cancel_lock:
            return tid in self._cancelled

    def cancel(self, task_id) -> dict:
        """Withdraw the work for one ticket's task. Safe from another thread while `execute` runs.

        Before admission: the task never spawns (`NOT_STARTED:CANCELLED`). Between admission and spawn: the attempt is
        ended as spawn_failed and the task is not re-admitted. While an attempt runs: the executor is killed through its
        job object and the task is not re-admitted; whatever it may have done is reported as `execution_uncertain`
        (absence proofs are recorded in the ledger but a cancellation never re-runs the work). A cancelled task id can
        never be executed again by this bridge (same ticket = same task id)."""
        with self._cancel_lock:
            self._cancelled.add(task_id)
            aid = self._running.get(task_id)
        granted = self.sup.request_cancel(aid) if aid is not None else {"granted": False, "reason": "NOT_RUNNING"}
        return {"task_id": task_id, "recorded": True, "kill": granted}

    # ---- settlement -----------------------------------------------------------------------
    def _settle(self, work, run_id, work_dir, out_path, stop):
        L, tid = self.L, work.task_id
        state = L.task(tid)["state"]
        last = L.q1("SELECT * FROM recovery_decision WHERE task_id=? ORDER BY decision_id DESC LIMIT 1", (tid,))
        attempts = L.q("SELECT attempt_id FROM attempt WHERE task_id=? ORDER BY attempt_id", (tid,))
        if state == "COMPLETE":
            self._expire_authorization(tid)              # the ticket is spent whatever the copy-out says
            # Ledger says URI verified the required postcondition. Defence in depth: look once more, then copy out.
            try:
                if out_path.is_symlink() or not out_path.is_file() or out_path.stat().st_size == 0:
                    raise OSError("OUTPUT_NOT_REGULAR_NONEMPTY")
                data = out_path.read_bytes()
                dest = self.root / "workspace" / "results" / run_id
                dest.mkdir(parents=True)
                shutil.copyfile(out_path, dest / work.expected_file)
            except OSError as exc:
                return "execution_uncertain", [], _fit("OUTPUT_COPY_OUT_FAILED:" + type(exc).__name__)
            evidence = [{"check": CHECK_NAME, "argument_digest": work.ticket.argument_digest, "verifier_id": work.ticket.verifier_id,
                         "matched": True, "output_sha256": hashlib.sha256(data).hexdigest(), "output_bytes": len(data),
                         "harness": work.provider, "supervisor_task": tid, "supervisor_attempt": attempts[-1][0] if attempts else None,
                         "supervisor_decision": last["decision_id"] if last else None, "ledger_id": L.ledger_id(),
                         "basis": "uri_supervisor_postcondition_verified"}]
            return "verified", evidence, None
        # Not verified: close this ticket's authority so the ledger never holds re-admittable work for it.
        self._expire_authorization(tid)
        if L.task(tid)["state"] in ("QUEUED", "RETRY_SAFE"):
            try:
                L.transition(tid, "FAILED", "BRIDGE_SETTLED_" + stop, last["reason_code"] if last else None)
            except LedgerError:
                pass
        state = L.task(tid)["state"]
        reason = (last["reason_code"] if last else L.task(tid)["reason_code"]) or stop
        proc_states = [json.loads(e["payload"]).get("state") for e in L.q(
            "SELECT payload FROM evidence WHERE task_id=? AND kind='process_identity' ORDER BY evidence_id", (tid,))]
        never_started = not attempts or (len(proc_states) == len(attempts) and all(s == "NEVER_STARTED" for s in proc_states))
        if state in ("UNCERTAIN", "NEEDS_USER"):
            return "execution_uncertain", [], _fit(f"SUPERVISOR_{state}:{reason}")
        if stop == "CANCELLED":
            # A cancellation after dispatch is never a clean close: the executor may have acted before it was killed.
            if never_started:
                return "failed", [], NOT_STARTED + "CANCELLED"
            return "execution_uncertain", [], _fit("CANCELLED_AFTER_DISPATCH:" + reason)
        if self._clean_quota_pause(tid, last):
            return "quota", [], "QUOTA"
        if never_started:
            return "failed", [], _fit(NOT_STARTED + ("EXECUTOR_NOT_ADMITTED" if not attempts else "SPAWN_FAILED") + ":" + reason)
        return "failed", [], _fit(f"SUPERVISOR_{state}:{reason}")

    def _clean_quota_pause(self, tid, last):
        """Quota pause may close a ticket 'without effect' only when: the last decision is a quota decision, every
        declared effect was proven absent (workspace fingerprint equal), and the executor reported no tool activity
        in any attempt (Phase 1 rule: any tool action before the limit makes the attempt uncertain)."""
        if last is None or last["reason_code"] != "PROVIDER_QUOTA_EXHAUSTED":
            return False
        steps = json.loads(last["evidence_json"])
        effects = steps.get("effects") or []
        if not effects or not all(e.get("safe") and e.get("reason") == "LOCAL_WRITE_ABSENCE_PROVEN" for e in effects):
            return False
        activity = self.L.q1("SELECT COUNT(*) FROM evidence WHERE task_id=? AND source='executor_report' AND kind IN (?,?,?)",
                             (tid, *TOOL_ACTIVITY))[0]
        return activity == 0
