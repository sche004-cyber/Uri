"""Durable Task Supervisor: submit -> admit -> declare intent -> fenced spawn -> stream -> reconcile.

The ledger is the only authority. This class is the single writer for the lifecycle; executors are
workers whose output is recorded as evidence and interpreted only through `recovery.reconcile`.

Mechanical order for one attempt (each step is its own FULL-durability transaction):
  admit      attempt+admission+claims+task RUNNING     (atomic; fencing token = attempt_id)
  intent     effect_intent rows (+ pre-attempt fingerprints for local writes)
  SPAWNING   trigger refuses without admission, intent, held claims, current fence   [rules A, B]
  spawn      suspended -> named kill-on-close job -> identity made durable -> resume
  stream     raw lines persisted BEFORE interpretation, same transaction, never partial lines
  end        attempt ENDED -> reconcile (fence, inspect, postconditions, decide)         [rules C, D]
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import crashpoints, recovery, winproc
from .admission import Admitted, Admitter, Registry
from .clock import Clock
from .executors import ExecutorSpec, ExecutorSpecError, check_final_argv, valid_session_id
from .ledger import Ledger, LedgerError, LedgerRefused, jdump
from .postconditions import fingerprint_paths
from .stream import PARSER_ID, LineSplitter, interpret_line

try:
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None


class SupervisorError(LedgerError):
    pass


def sha(obj) -> str:
    return hashlib.sha256((obj if isinstance(obj, bytes) else jdump(obj).encode("utf-8"))).hexdigest()


@dataclass
class RunResult:
    attempt_id: int
    exit_code: int | None
    end_reason: str
    decision: object


class Supervisor:
    def __init__(self, ledger_path, *, clock: Clock | None = None, lease_s: float = 60.0, reconcilers=None,
                 take_lock: bool = True, run_recovery: bool = True):
        self.clock = clock or Clock()
        # SUP-1: before any executor can be spawned, the hosting process joins a kill-on-close job of its own, so a
        # supervisor death during the suspended-spawn window cannot leave an orphan (winproc.contain_current_process).
        # Review round 1, OQ-R1-3: fail closed. A Windows host that cannot contain itself would keep the window open, so
        # no supervisor is built there (non-Windows hosts cannot spawn at all: winproc refuses). Side effect, by design:
        # when the host process exits, every process it started (not only executors) is killed with it.
        self.self_containment = winproc.contain_current_process() if winproc.IS_WINDOWS else "UNAVAILABLE:NOT_WINDOWS"
        if winproc.IS_WINDOWS and self.self_containment not in ("CONTAINED", "ALREADY_CONTAINED"):
            raise SupervisorError("SELF_CONTAINMENT_UNAVAILABLE", self.self_containment)
        self.ledger = Ledger(ledger_path, self.clock)
        self.registry = Registry(self.ledger)
        self.reconcilers = dict(reconcilers or {})
        self._lock_fh = None
        self._active: set[int] = set()
        self._preempt: set[int] = set()
        self._cancel: set[int] = set()      # Phase 2D: attempts whose caller withdrew the work (kill, never retry here)
        self._safe: dict[int, bool] = {}
        if take_lock:
            self._acquire_lock(str(ledger_path) + ".lock")
        self.epoch, self.instance_id = self.ledger.begin_epoch(os.getpid(), winproc.process_create_time(os.getpid())
                                                               if winproc.IS_WINDOWS else None)
        self.admitter = Admitter(self.ledger, self.epoch, lease_s)
        crashpoints.hit("after_epoch_begin")
        if run_recovery:
            self.recover_all()

    # ---- single-supervisor lock -------------------------------------------------------------
    def _acquire_lock(self, path):
        fh = open(path, "a+b")
        try:
            fh.seek(0)
            if msvcrt is not None:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise SupervisorError("SUPERVISOR_ALREADY_RUNNING", path) from None
        self._lock_fh = fh

    def close(self):
        if self._lock_fh is not None:
            with contextlib.suppress(OSError):
                if msvcrt is not None:
                    self._lock_fh.seek(0)
                    msvcrt.locking(self._lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
            self._lock_fh.close()
            self._lock_fh = None
        self.ledger.close()

    # ---- task intake ------------------------------------------------------------------------
    def submit_task(self, task_id, principal, request: dict, *, authorization: dict, effects: list, postconditions: list,
                    requirements: dict | None = None, priority: int = 0, max_attempts: int = 3, timezone: str | None = None):
        """Durable intake. A task with no effect envelope or no required postcondition is refused: it could never
        be completed (rule C) nor have its effects bounded (rule B)."""
        if not effects:
            raise LedgerRefused("NO_EFFECT_ENVELOPE")
        if not any(p.get("required", True) for p in postconditions):
            raise LedgerRefused("NO_REQUIRED_POSTCONDITION")
        norm = []
        for e in effects:
            if e["op_class"] not in ("read", "idem_write", "local_write", "external"):
                raise LedgerRefused("BAD_OP_CLASS", e["op_class"])
            if e["op_class"] == "idem_write" and not e.get("idempotency_key"):
                raise LedgerRefused("IDEMPOTENT_WRITE_REQUIRES_KEY")
            norm.append({"op_class": e["op_class"], "operation": e["operation"], "target": e.get("target"),
                         "params": e.get("params", {}), "idempotency_key": e.get("idempotency_key"),
                         "paths": [str(p) for p in e.get("paths", [])], "context": e.get("context", {})})
        if any(p["kind"] == "terminal_success" for p in postconditions) and any(e["op_class"] != "read" for e in norm):
            raise LedgerRefused("TERMINAL_SUCCESS_ONLY_FOR_READ_TASKS")
        scope = authorization.get("scope", {}) or {}
        allowed = scope.get("allowed_op_classes")
        if allowed is not None and any(e["op_class"] not in allowed for e in norm):
            raise LedgerRefused("OP_CLASS_NOT_AUTHORIZED")
        ws = scope.get("workspace")
        if ws:
            for e in norm:
                for p in e["paths"] + ([e["target"]] if e["target"] else []):
                    if not _within(ws, p):
                        raise LedgerRefused("EFFECT_OUTSIDE_WORKSPACE", p)
        reqs = dict(requirements or {})
        reqs["effects"] = norm
        now = self.ledger.now_us()
        with self.ledger.tx() as db:
            rnd = int(self.ledger.meta("admission_round", "0"))
            db.execute("INSERT INTO task(task_id,principal,request_json,request_sha256,requirements_json,timezone,base_priority,"
                       "enqueue_round,state,max_attempts,created_at_us,state_changed_at_us,reason_code) "
                       "VALUES (?,?,?,?,?,?,?,?,'QUEUED',?,?,?,'SUBMITTED')",
                       (task_id, principal, jdump(request), sha(request), jdump(reqs), timezone, priority, rnd, max_attempts, now, now))
            db.execute("INSERT INTO authorization(task_id,scope_json,issued_by,valid_from_us,valid_until_us,recorded_at_us) "
                       "VALUES (?,?,?,?,?,?)", (task_id, jdump(authorization.get("scope", {})), authorization.get("issued_by", principal),
                                                authorization.get("valid_from_us", now), authorization.get("valid_until_us"), now))
            for p in postconditions:
                db.execute("INSERT INTO postcondition(task_id,kind,spec_json,required,declared_at_us) VALUES (?,?,?,?,?)",
                           (task_id, p["kind"], jdump(p.get("spec", {})), int(p.get("required", True)), now))
            self.ledger.emit("task.submitted", task_id, payload={"principal": principal, "priority": priority,
                                                                 "request_sha256": sha(request)})
            self.ledger.emit("task.state", task_id, payload={"from": None, "to": "QUEUED", "reason": "SUBMITTED"})
        crashpoints.hit("after_submit")

    def supersede_authorization(self, task_id, *, scope, valid_until_us=None, issued_by=None):
        now = self.ledger.now_us()
        with self.ledger.tx() as db:
            old = db.execute("SELECT auth_id FROM authorization WHERE task_id=? AND superseded_at_us IS NULL ORDER BY auth_id DESC LIMIT 1",
                             (task_id,)).fetchone()
            cur = db.execute("INSERT INTO authorization(task_id,scope_json,issued_by,valid_from_us,valid_until_us,recorded_at_us) "
                             "VALUES (?,?,?,?,?,?)", (task_id, jdump(scope), issued_by or "uri", now, valid_until_us, now))
            if old:
                db.execute("UPDATE authorization SET superseded_at_us=?, superseded_by=? WHERE auth_id=?", (now, cur.lastrowid, old[0]))
            self.ledger.emit("authorization.superseded", task_id, payload={"new": cur.lastrowid})

    # ---- admission passthrough --------------------------------------------------------------
    def admit_next(self, only_task_id=None) -> Admitted | None:
        a = self.admitter.admit_next(only_task_id=only_task_id)
        if a:
            crashpoints.hit("after_admit_commit")
        return a

    # ---- effect intents (rule B) ------------------------------------------------------------
    def declare_intents(self, admitted: Admitted):
        L = self.ledger
        task = L.task(admitted.task_id)
        effects = json.loads(task["requirements_json"])["effects"]
        prev = L.q1("SELECT attempt_id FROM attempt WHERE task_id=? AND attempt_id<? ORDER BY attempt_id DESC LIMIT 1",
                    (admitted.task_id, admitted.attempt_id))
        prev_intents = L.q("SELECT intent_id FROM effect_intent WHERE attempt_id=? ORDER BY intent_id", (prev[0],)) if prev else []
        with L.tx() as db:
            now = L.now_us()
            for i, e in enumerate(effects):
                ctx = dict(e.get("context") or {})
                if e["op_class"] == "local_write":
                    ctx["fingerprints"] = fingerprint_paths(e["paths"] or ([e["target"]] if e.get("target") else []))
                retry_of = prev_intents[i][0] if i < len(prev_intents) else None
                cur = db.execute(
                    "INSERT INTO effect_intent(task_id,attempt_id,op_class,operation,target,params_hash,idempotency_key,retry_of,"
                    "pre_state_json,executor_id,declared_at_us,recorded_at_us) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (admitted.task_id, admitted.attempt_id, e["op_class"], e["operation"], e.get("target"), sha(e["params"]),
                     e.get("idempotency_key"), retry_of, jdump(ctx) if ctx else None, admitted.executor_id, now, now))
                L.emit("effect.intent", admitted.task_id, admitted.attempt_id, ("effect_intent", cur.lastrowid),
                       {"op_class": e["op_class"], "operation": e["operation"]})
        crashpoints.hit("after_intents")

    # ---- running an attempt -----------------------------------------------------------------
    def run_attempt(self, admitted: Admitted, *, cwd, instructions: bytes = b"", model=None, environ=None,
                    timeout_s=900, inactivity_s=300, terminal_grace_s=10, resolved_executable=None, extra_argv=None) -> RunResult:
        L = self.ledger
        aid, tid = admitted.attempt_id, admitted.task_id
        st = L.attempt(aid)
        if st is None or st["status"] != "ADMITTED" or st["task_id"] != tid:
            raise LedgerRefused("ATTEMPT_ALREADY_STARTED", f"attempt {aid} is {st['status'] if st else 'unknown'}")
        reg = L.q1("SELECT * FROM executor_registration WHERE registration_id=?", (admitted.registration_id,))
        spec = ExecutorSpec.from_json(json.loads(reg["spec_json"]))
        self.declare_intents(admitted)
        # resume bookkeeping: honour the previous decision only if it said RESUME_SESSION. Phase 2D (F-C1): a harness
        # session id is resumable execution metadata, never authority. It is reused only when (a) it was recorded on
        # the immediately preceding attempt OF THIS TASK, (b) that attempt's reconciliation decided RESUME_SESSION,
        # (c) the same executor (registration id) runs again, and (d) the id still validates. Anything else runs fresh.
        session, resume_of = None, None
        prev = L.q1("SELECT d.action, a.session_id, a.attempt_id, a.executor_id, a.registration_id FROM recovery_decision d "
                    "JOIN attempt a ON a.attempt_id=d.attempt_id WHERE d.task_id=? AND a.task_id=? AND a.attempt_id<? "
                    "ORDER BY a.attempt_id DESC LIMIT 1", (tid, tid, aid))
        if (prev and prev["action"] == "RESUME_SESSION" and prev["session_id"] and valid_session_id(prev["session_id"])
                and prev["executor_id"] == admitted.executor_id and prev["registration_id"] == admitted.registration_id):
            session, resume_of = prev["session_id"], prev["attempt_id"]
        elif prev and prev["action"] == "RESUME_SESSION":
            L.emit("attempt.resume_refused", tid, aid, ("attempt", aid),
                   {"why": "SESSION_NOT_REUSABLE", "previous_attempt": prev["attempt_id"]})
        scope_row = L.q1("SELECT a.scope_json FROM authorization a JOIN admission d ON d.auth_id=a.auth_id WHERE d.attempt_id=?", (aid,))
        ws = json.loads(scope_row[0]).get("workspace") if scope_row else None
        if ws and not _within(ws, str(cwd)):
            self._spawn_failed(admitted, "CWD_OUTSIDE_WORKSPACE")
            raise LedgerRefused("CWD_OUTSIDE_WORKSPACE", str(cwd))
        try:
            argv = spec.build_argv(workspace=str(cwd), model=model, session=session, resolved_executable=resolved_executable)
            argv = check_final_argv(argv + list(extra_argv or []))
        except ExecutorSpecError as e:
            return self._spawn_failed(admitted, f"BUILD_ARGV:{e}")
        with L.tx() as db:   # rule A/B gate lives in the trigger; this is the durable pre-spawn marker
            db.execute("UPDATE attempt SET status='SPAWNING', argv_sha256=?, resume_of=? WHERE attempt_id=?",
                       (sha(argv), resume_of, aid))
            L.emit("attempt.spawning", tid, aid, ("attempt", aid), {"argv_sha256": sha(argv)})
        crashpoints.hit("after_spawning_marked")
        env = spec.build_env(environ if environ is not None else os.environ)
        env["URI_ATTEMPT_FENCE"] = str(aid)
        env["URI_TASK_ID"] = tid
        name = winproc.job_name_for(L.ledger_id(), aid) + "-" + secrets.token_hex(8)   # unguessable: nobody can squat it

        def durable_identity(ident: winproc.ProcessIdentity):
            with L.tx() as db:
                db.execute("UPDATE attempt SET pid=?, pid_create_time=?, job_name=?, status='RUNNING', spawned_at_us=? "
                           "WHERE attempt_id=? AND status='SPAWNING'", (ident.pid, ident.create_time, ident.job_name, L.now_us(), aid))
                L.emit("attempt.running", tid, aid, ("attempt", aid), {"pid": ident.pid, "create_time": ident.create_time})
            crashpoints.hit("after_pid_record")

        try:
            cp = winproc.spawn_contained(argv, name, before_resume=durable_identity, cwd=str(cwd), env=env, bufsize=0,
                                         stdin=subprocess.PIPE if spec.stdin == "instructions" else subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (winproc.ContainmentError, OSError) as e:
            return self._spawn_failed(admitted, f"SPAWN:{type(e).__name__}:{e}")
        crashpoints.hit("after_spawn_resumed")
        return self._supervise(admitted, spec, cp, instructions, timeout_s, inactivity_s, terminal_grace_s)

    def _spawn_failed(self, admitted, why):
        L = self.ledger
        with L.tx() as db:
            st = L.attempt(admitted.attempt_id)["status"]
            if st == "ADMITTED":
                db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (admitted.attempt_id,))
            db.execute("UPDATE attempt SET status='ENDED', ended_at_us=?, end_reason=? WHERE attempt_id=? AND status IN ('SPAWNING','RUNNING')",
                       (L.now_us(), "spawn_failed", admitted.attempt_id))
            L.emit("attempt.spawn_failed", admitted.task_id, admitted.attempt_id, payload={"why": why})
        d = recovery.reconcile(self, admitted.task_id, admitted.attempt_id, "attempt_end")
        return RunResult(admitted.attempt_id, None, "spawn_failed", d)

    def _supervise(self, admitted, spec, cp: winproc.ContainedProcess, instructions, timeout_s, inactivity_s, grace_s):
        L = self.ledger
        aid, tid = admitted.attempt_id, admitted.task_id
        state = {"last": time.monotonic(), "terminal": None, "terminal_at": None, "events": 0, "error": None}
        counters = {"stdout": 0, "stderr": 0}
        splitters = {"stdout": LineSplitter(), "stderr": LineSplitter()}

        def pump(stream, fh):
            try:
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    state["last"] = time.monotonic()
                    lines = splitters[stream].feed(chunk)
                    if lines:
                        self._record_lines(admitted, spec, stream, lines, counters, state)
                tail = splitters[stream].flush_tail()
                if tail:
                    self._record_lines(admitted, spec, stream, [(tail, False)], counters, state)
            except Exception as e:   # a failing recorder must not be silent: it ends the attempt as interrupted
                state["error"] = f"{type(e).__name__}:{e}"

        def feed_stdin():
            with contextlib.suppress(BrokenPipeError, OSError):
                if cp.proc.stdin:
                    if instructions:
                        cp.proc.stdin.write(instructions)
                    cp.proc.stdin.close()

        threads = [threading.Thread(target=pump, args=("stdout", cp.proc.stdout), daemon=True),
                   threading.Thread(target=pump, args=("stderr", cp.proc.stderr), daemon=True),
                   threading.Thread(target=feed_stdin, daemon=True)]
        for t in threads:
            t.start()
        started, end_reason, killed_ok = time.monotonic(), None, True
        self._active.add(aid)
        last_renew = 0.0
        renew_every = max(1.0, self.admitter.lease_s / 4)
        while cp.proc.poll() is None:
            now = time.monotonic()
            if state["error"]:
                end_reason = "recorder_failed_killed"
            elif now - started > timeout_s:
                end_reason = "timeout_killed"
            elif now - state["last"] > inactivity_s:
                end_reason = "inactivity_killed"
            elif state["terminal"] and now - state["terminal_at"] > grace_s:
                end_reason = "terminal_then_hang_killed"
            elif aid in self._cancel:
                end_reason = "cancelled_killed"
            elif aid in self._preempt and self._safe.get(aid):
                end_reason = "preempted_at_safe_point"
            else:
                if now - last_renew >= renew_every:       # heartbeat at a fraction of the lease, not every poll
                    with contextlib.suppress(LedgerError):
                        self.admitter.renew(aid)
                    last_renew = now
                time.sleep(0.05)
                continue
            killed_ok = cp.kill()
            break
        cp.proc.wait()
        self._active.discard(aid)
        killed_ok = cp.kill() and killed_ok         # sweep descendants
        cp.close()
        for t in threads:
            t.join(timeout=10)
        exit_code = cp.proc.returncode
        if end_reason is None:
            end_reason = {"terminal_success_claim": "exited_after_terminal_success_claim",
                          "terminal_error_claim": "exited_after_terminal_error_claim"}.get(state["terminal"], "exited_without_terminal_event")
        with L.tx() as db:
            db.execute("UPDATE attempt SET status='ENDED', ended_at_us=?, exit_code=?, end_reason=? WHERE attempt_id=? AND status IN ('RUNNING','SPAWNING')",
                       (L.now_us(), exit_code, end_reason, aid))
            L.emit("attempt.ended", tid, aid, ("attempt", aid), {"exit_code": exit_code, "end_reason": end_reason,
                                                                  "contained": killed_ok})
        crashpoints.hit("after_attempt_ended")
        self._preempt.discard(aid)
        self._cancel.discard(aid)
        forced = end_reason if end_reason in ("preempted_at_safe_point", "cancelled_killed") else None
        d = recovery.reconcile(self, tid, aid, "attempt_end", forced_reason=forced)
        return RunResult(aid, exit_code, end_reason, d)

    def request_cancel(self, attempt_id) -> dict:
        """Phase 2D: the caller withdraws a RUNNING attempt. The executor is killed through its job at the next poll;
        reconciliation then records the interruption like any other (absence proofs decide retry safety); it is the
        CALLER's duty not to re-admit a cancelled task. Idempotent; never touches another supervisor's attempts."""
        a = self.ledger.attempt(attempt_id)
        if a is None or a["status"] not in ("SPAWNING", "RUNNING") or attempt_id not in self._active:
            return {"granted": False, "reason": "NOT_RUNNING_HERE"}
        self._cancel.add(attempt_id)
        return {"granted": True, "reason": "CANCEL_REQUESTED"}

    # ---- stream recording: raw first, interpretation second, same transaction -----------------
    def _record_lines(self, admitted, spec, stream, lines, counters, state):
        L, aid, tid = self.ledger, admitted.attempt_id, admitted.task_id
        with L.tx() as db:
            fence_ok = db.execute("SELECT 1 FROM task t JOIN attempt a ON a.attempt_id=? AND a.task_id=t.task_id "
                                  "WHERE t.task_id=? AND t.current_fence=? AND a.status<>'FENCED'", (aid, tid, aid)).fetchone() is not None
            now = L.now_us()
            for raw, complete in lines:
                counters[stream] += 1
                cur = db.execute("INSERT INTO stream_event(task_id,attempt_id,stream,line_no,raw,raw_sha256,complete,received_at_us,fence_current) "
                                 "VALUES (?,?,?,?,?,?,?,?,?)", (tid, aid, stream, counters[stream], raw, hashlib.sha256(raw).hexdigest(),
                                                                 int(complete), now, int(fence_ok)))
                se_id = cur.lastrowid
                if stream != "stdout":
                    db.execute("INSERT INTO stream_interpretation(stream_event_id,parser_id,parse_status,event_type,semantics,extracted) "
                               "VALUES (?,?,'skipped',NULL,'[]','[]')", (se_id, PARSER_ID))
                    continue
                it = interpret_line(raw, spec.rules, complete)
                db.execute("INSERT INTO stream_interpretation(stream_event_id,parser_id,parse_status,event_type,semantics,extracted) "
                           "VALUES (?,?,?,?,?,?)", (se_id, PARSER_ID, it.parse_status, it.event_type,
                                                    jdump([s[0] for s in it.semantics]), jdump([s[1] for s in it.semantics])))
                if not fence_ok:
                    continue            # stale writer: raw is preserved, nothing authoritative is derived
                labels = [s[0] for s in it.semantics]
                self._safe[aid] = "safe_point" in labels or (self._safe.get(aid, False) and not labels)
                for label, ext in it.semantics:
                    if label in ("terminal_success_claim", "terminal_error_claim") and state["terminal"] is None:
                        state["terminal"], state["terminal_at"] = label, time.monotonic()
                    if label == "session" and valid_session_id(ext.get("session_id")):
                        db.execute("UPDATE attempt SET session_id=COALESCE(session_id,?) WHERE attempt_id=?", (ext["session_id"], aid))
                    if label == "safe_point":
                        db.execute("UPDATE attempt SET at_safe_point=1 WHERE attempt_id=?", (aid,))
                        continue
                    ev = db.execute("INSERT INTO evidence(task_id,attempt_id,source,kind,subject,payload,stream_event_id,occurred_at_us,"
                                    "recorded_at_us,recorded_by) VALUES (?,?,'executor_report',?,?,?,?,?,?,'attempt')",
                                    (tid, aid, label, f"attempt:{aid}", jdump(_bounded(ext)), se_id, now, now))
                    L.emit("evidence." + label, tid, aid, ("evidence", ev.lastrowid))
                if labels and "safe_point" not in labels:
                    db.execute("UPDATE attempt SET at_safe_point=0 WHERE attempt_id=?", (aid,))
        state["events"] += len(lines)
        if stream == "stdout":
            crashpoints.hit("mid_stream")
            if state["terminal"]:
                crashpoints.hit("after_terminal_event_recorded")

    # ---- preemption (safe points only) ------------------------------------------------------
    def request_preempt(self, attempt_id) -> dict:
        L = self.ledger
        a = L.attempt(attempt_id)
        if a is None or a["status"] != "RUNNING":
            return {"granted": False, "reason": "NOT_RUNNING"}
        reg = L.q1("SELECT preemptible FROM executor_registration WHERE registration_id=?", (a["registration_id"],))
        if not reg["preemptible"]:
            return {"granted": False, "reason": "EXECUTOR_NOT_PREEMPTIBLE"}
        if L.q1("SELECT 1 FROM effect_intent WHERE attempt_id=? AND op_class IN ('local_write','external')", (attempt_id,)):
            return {"granted": False, "reason": "NON_IDEMPOTENT_EFFECT_DECLARED"}
        if not self._safe.get(attempt_id):
            return {"granted": False, "reason": "NOT_AT_SAFE_POINT"}
        self._preempt.add(attempt_id)
        return {"granted": True, "reason": "AT_SAFE_POINT"}

    # ---- recovery ---------------------------------------------------------------------------
    def recover_all(self):
        """Startup recovery: every task left RUNNING/RECOVERING by a previous epoch is reconciled."""
        L = self.ledger
        out = []
        for t in L.q("SELECT task_id,state,current_fence FROM task WHERE state IN ('RUNNING','RECOVERING') ORDER BY task_seq"):
            aid = t["current_fence"]
            if aid is None:
                row = L.q1("SELECT MAX(attempt_id) FROM attempt WHERE task_id=?", (t["task_id"],))
                aid = row[0]
            if aid is None:
                continue
            a = L.attempt(aid)
            if a["epoch"] == self.epoch and t["state"] == "RUNNING":
                continue          # started by this very epoch; not ours to recover
            out.append(recovery.reconcile(self, t["task_id"], aid, "restart"))
        self.sweep_orphan_claims()
        return out

    def reap_expired_leases(self, skip_active=None):
        """Same-epoch claims past their monotonic lease whose run-loop is gone are reconciled (fence, kill by
        job/identity, postconditions, decide). Attempts this supervisor is actively running are never reaped."""
        L, reaped = self.ledger, []
        active = set(self._active) | set(skip_active or ())
        for c in self.admitter.expired_leases():
            aid = c["attempt_id"]
            if aid in active or aid in reaped:
                continue
            t = L.task(c["task_id"])
            if t["state"] == "RUNNING" and t["current_fence"] == aid:
                recovery.reconcile(self, c["task_id"], aid, "restart")
                reaped.append(aid)
        return reaped

    def sweep_orphan_claims(self):
        """Release held claims of attempts that are FENCED/ENDED AND whose process is proven gone. Never by deadline."""
        L, released = self.ledger, []
        for c in L.q("SELECT DISTINCT c.attempt_id FROM claim c JOIN attempt a ON a.attempt_id=c.attempt_id "
                     "WHERE c.state='held' AND a.status IN ('FENCED','ENDED')"):
            a = L.attempt(c[0])
            state, _ = recovery._inspect_process(self, a)
            if state in ("DEAD_CONFIRMED", "NEVER_STARTED"):
                self.admitter.release(a["attempt_id"], "SWEEP_PROCESS_PROVEN_GONE")
                released.append(a["attempt_id"])
        return released

    # ---- human decisions & new evidence ----------------------------------------------------
    def record_user_decision(self, task_id, choice, principal, rationale=""):
        L = self.ledger
        with L.tx() as db:
            t = L.task(task_id)
            if t["state"] not in ("UNCERTAIN", "NEEDS_USER"):
                raise LedgerRefused("NO_UNRESOLVED_UNCERTAINTY", t["state"])
            now = L.now_us()
            unc = db.execute("SELECT uncertainty_id FROM uncertainty WHERE task_id=? AND resolved_at_us IS NULL "
                             "ORDER BY uncertainty_id DESC LIMIT 1", (task_id,)).fetchone()
            did = db.execute("INSERT INTO user_decision(task_id,uncertainty_id,choice,rationale,principal,decided_at_us,recorded_at_us) "
                             "VALUES (?,?,?,?,?,?,?)", (task_id, unc[0] if unc else None, choice, rationale, principal, now, now)).lastrowid
            basis, kw, completion = ("user_decision", did), {}, None
            if choice == "retry":
                to, kw = "RETRY_SAFE", {"max_attempts": t["max_attempts"] + 1}
            elif choice == "abandon":
                to = "FAILED"
            else:
                to = "COMPLETE"
                completion = db.execute("INSERT INTO completion_record(task_id,attempt_id,kind,basis_json,recorded_at_us) "
                                        "VALUES (?,NULL,'user_accepted',?,?)", (task_id, jdump({"decision": did}), now)).lastrowid
            L.transition(task_id, to, "USER_DECISION_" + choice.upper(), rationale, basis=basis, completion_ref=completion,
                         extra=kw or None)
            if unc:
                db.execute("UPDATE uncertainty SET resolved_at_us=?, resolution_kind='user_decision', resolution_ref=? WHERE uncertainty_id=?",
                           (now, did, unc[0]))
            L.emit("user.decision", task_id, ref=("user_decision", did), payload={"choice": choice, "principal": principal})
        return did

    def reexamine(self, task_id):
        """Fresh observation of an UNCERTAIN/NEEDS_USER task. Leaves the state only on NEW URI-observed evidence."""
        from .postconditions import EvalContext, evaluate_postconditions
        L = self.ledger
        t = L.task(task_id)
        if t["state"] not in ("UNCERTAIN", "NEEDS_USER"):
            return {"changed": False, "reason": "NOT_UNRESOLVED"}
        last = L.q1("SELECT MAX(attempt_id) FROM attempt WHERE task_id=?", (task_id,))[0]
        pcs = evaluate_postconditions(L, task_id, EvalContext(self.reconcilers, last, "recovery"))
        required = [p for p in pcs if p["required"]]
        if required and all(p["status"] == "PASS" for p in required):
            ev = max(p["evidence_id"] for p in required)
            with L.tx() as db:
                comp = db.execute("INSERT INTO completion_record(task_id,attempt_id,kind,basis_json,recorded_at_us) VALUES (?,?,'verified',?,?)",
                                  (task_id, last, jdump({"reexamine": [p["postcondition_id"] for p in required]}), L.now_us())).lastrowid
                L.transition(task_id, "COMPLETE", "NEW_EVIDENCE_POSTCONDITIONS_VERIFIED", basis=("evidence", ev), completion_ref=comp)
                db.execute("UPDATE uncertainty SET resolved_at_us=?, resolution_kind='evidence', resolution_ref=? WHERE task_id=? AND resolved_at_us IS NULL",
                           (L.now_us(), ev, task_id))
            return {"changed": True, "to": "COMPLETE"}
        # an external reconciler now proving ABSENCE of every uncertain external effect, with keys, permits a retry
        verdicts = recovery._classify_effects(self, task_id, last)
        ev = L.q1("SELECT MAX(evidence_id) FROM evidence WHERE task_id=? AND source IN ('uri_observed','uri_verified') "
                  "AND kind IN ('postcondition_check','effect_absent','external_reconcile')", (task_id,))[0]
        if verdicts and all(v["safe"] for v in verdicts) and ev and ev > t["enter_evidence_hwm"]:
            with L.tx() as db:
                L.transition(task_id, "RETRY_SAFE", "NEW_EVIDENCE_EFFECTS_PROVEN_ABSENT_OR_KEYED", basis=("evidence", ev))
                db.execute("UPDATE uncertainty SET resolved_at_us=?, resolution_kind='evidence', resolution_ref=? WHERE task_id=? AND resolved_at_us IS NULL",
                           (L.now_us(), ev, task_id))
            return {"changed": True, "to": "RETRY_SAFE"}
        return {"changed": False, "reason": "STILL_UNPROVEN"}


def _bounded(ext: dict, limit=8192):
    s = jdump(ext)
    if len(s) <= limit:
        return ext
    return {"truncated": True, "sha256": hashlib.sha256(s.encode()).hexdigest(), "bytes": len(s)}


def _within(root, path) -> bool:
    """True if `path` resolves inside `root` (case-insensitive on Windows, `..` and symlinks resolved)."""
    try:
        r = os.path.normcase(os.path.realpath(root))
        p = os.path.normcase(os.path.realpath(path))
        return os.path.commonpath([r, p]) == r
    except ValueError:      # different drives
        return False
