"""Phase 2 UI/operations slice: execution lifecycle, mid-run cancellation and reconnect over the worker protocol.

This module adds NO authority. Core (the frozen server turn record and the client's execution journal) still owns
intent, approval, the ticket and the settlement; the supervisor ledger still owns admission, attempts, containment and
reconciliation. What is added, worker-side (trusted client code, never the UI):

  * `execution_proposal`: the exact proposal a UI approval is bound to (client, session, turn, kind/provider/model,
    capability, argument digest, approval digest). `execution_begin` must echo BOTH the approval digest the server
    issued and this proposal digest; a change of any authority-relevant field (another provider or model, other
    arguments, another turn) yields another digest, so the earlier approval cannot start it.
  * `ExecutionController.begin`: the approved turn is dispatched in a worker thread so the single-threaded frame
    loop keeps answering `execution_status` / `execution_cancel` / `execution_list` while the harness runs. Exactly
    one execution per client at a time (the harness pool is one slot); every other turn command is refused with
    `EXECUTION_IN_PROGRESS` meanwhile.
  * `ExecutionController.cancel`: before the approval is posted the turn is DENIED instead (nothing ever runs);
    after that and before dispatch the bridge refuses the task (`NOT_STARTED:CANCELLED`); while an attempt runs the
    executor is killed through its job object (`SupervisorBridge.cancel` -> `Supervisor.request_cancel`) and the
    outcome is `uncertain` (a kill after dispatch is never a clean close); after a terminal state the request is
    refused (`EXECUTION_TERMINAL`).
  * `ExecutionRegister`: one durable JSON record per execution under `<client_root>/control/supervisor/executions/`
    (worker-owned; the UI holds only ids). `execution_status` always re-reads the record AND the live ledger,
    journal and server turn state, so a reconnecting UI sees what URI knows, never what the UI remembered. A worker
    restart marks every non-terminal record `uncertain` (`WORKER_RESTARTED`) after the frozen journal recovery and
    the bridge's authority revocation have run; nothing is ever re-launched from a record.

Lifecycle: queued -> approving -> starting -> running -> {completed | failed | cancelled | uncertain | quota_paused}.
`completed` is set only from the server's `SETTLED_VERIFIED` (ledger COMPLETE + verified receipt); every unmapped
settlement or exception after dispatch is `uncertain`, never success.
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from uri_core.client_contracts import digest
from uri_core.client_runtime.execution_journal import ExecutionJournal
from uri_core.client_runtime.turn_runner import NOT_STARTED, TurnError
from uri_core.core.runtime_identity import atomic_json

SCHEMA = "uri.phase2ops.execution.v1"
ACTIVE_STATES = ("queued", "approving", "starting", "running")
TERMINAL_STATES = ("completed", "failed", "cancelled", "uncertain", "quota_paused")
AUTHORITY_FIELDS = ("client_id", "session_id", "turn_id", "kind", "provider", "model", "capability_id",
                    "argument_digest", "approval_digest")
_ID = re.compile(r"^[0-9a-f]{32}$")
_LIST_LIMIT = 50


def execution_proposal(client_id, session_id, turn_id, reasoning, approval_request, qualification=None) -> dict:
    """The proposal a UI approval is bound to. `proposal_digest` covers exactly AUTHORITY_FIELDS; the remaining keys
    are display material taken verbatim from the server's approval request (bound through `argument_digest`)."""
    reasoning = reasoning if isinstance(reasoning, dict) else {}
    request = approval_request if isinstance(approval_request, dict) else {}
    arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else {}
    inputs = arguments.get("inputs") if isinstance(arguments.get("inputs"), dict) else {}
    core = {"client_id": client_id, "session_id": session_id, "turn_id": turn_id, "kind": reasoning.get("kind"),
            "provider": reasoning.get("provider"), "model": reasoning.get("model"),
            "capability_id": request.get("capability_id"), "argument_digest": request.get("argument_digest"),
            "approval_digest": request.get("approval_digest")}
    return {**core, "proposal_digest": digest(core), "effect": request.get("effect"), "reversible": request.get("reversible"),
            "action": arguments.get("action"), "arguments": arguments, "instruction": inputs.get("instruction"),
            "expected_file": inputs.get("expected_file"), "qualification": qualification}


def _now():
    return time.time()


def _ro(path):
    con = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True, timeout=2)
    con.row_factory = sqlite3.Row
    return con


def ledger_view(ledger_path, task_id):
    """Read-only view of the supervisor ledger for one task: the authoritative execution facts, never cached."""
    if not task_id or not Path(ledger_path).is_file():
        return None
    try:
        con = _ro(ledger_path)
    except sqlite3.Error as exc:
        return {"error": "LEDGER_UNREADABLE:" + type(exc).__name__}
    try:
        task = con.execute("SELECT state, reason_code, request_json FROM task WHERE task_id=?", (task_id,)).fetchone()
        if task is None:
            return {"task_id": task_id, "task": None}
        try:   # the bridge's own request row: which turn/selection/approval this task was submitted for
            import json
            req = json.loads(task["request_json"] or "{}")
            if not isinstance(req, dict):
                raise TypeError("request_json is not an object")
            request = {k: req.get(k) for k in ("turn_id", "operation_id", "session_id", "capability_id", "provider", "model",
                                               "approval_digest", "argument_digest", "expected_file", "execution_id")}
        except (ValueError, TypeError):
            request = {"error": "REQUEST_UNREADABLE"}
        attempts = [dict(r) for r in con.execute(
            "SELECT attempt_id, status, pid, pid_create_time, end_reason, exit_code, spawned_at_us, ended_at_us "
            "FROM attempt WHERE task_id=? ORDER BY attempt_id", (task_id,))]
        decision = con.execute("SELECT action, reason_code FROM recovery_decision WHERE task_id=? ORDER BY decision_id DESC LIMIT 1",
                               (task_id,)).fetchone()
        now_us = int(time.time() * 1_000_000)
        open_auth = con.execute("SELECT COUNT(*) FROM authorization WHERE task_id=? AND superseded_at_us IS NULL "
                                "AND (valid_until_us IS NULL OR valid_until_us>?)", (task_id, now_us)).fetchone()[0]
        return {"task_id": task_id, "task": {"state": task["state"], "reason_code": task["reason_code"]}, "request": request,
                "attempts": attempts, "decision": dict(decision) if decision else None, "open_authorizations": open_auth}
    except sqlite3.Error as exc:
        return {"error": "LEDGER_QUERY_FAILED:" + type(exc).__name__}
    finally:
        con.close()


def journal_view(journal_path, operation_id):
    """Read-only view of the frozen client execution journal for one operation (= the supervisor task id)."""
    if not operation_id or not Path(journal_path).is_file():
        return None
    try:
        con = _ro(journal_path)
    except sqlite3.Error as exc:
        return {"error": "JOURNAL_UNREADABLE:" + type(exc).__name__}
    try:
        row = con.execute("SELECT state, receipt_digest IS NOT NULL AS receipted FROM operations WHERE id=?", (operation_id,)).fetchone()
        return {"operation_id": operation_id, "state": row["state"], "receipted": bool(row["receipted"])} if row else \
            {"operation_id": operation_id, "state": None}
    except sqlite3.Error as exc:
        return {"error": "JOURNAL_QUERY_FAILED:" + type(exc).__name__}
    finally:
        con.close()


_OP_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def corroborate(record, ledger, journal, server, task_exists=None, operation_owner=None):
    """The record's own `completed` is never reported on its own word (review round 1, OPS-1). A harness execution
    is `completed` only while the ledger says COMPLETE, the journal says `verified` and the server, when it answers,
    says `reply`; a local (no-task) execution only while the server answers `reply`. Anything less is reported as
    `uncertain` with the exact gap, the recorded state kept beside it. `server=None` means "not consulted" (listing);
    an unreachable server is a gap for a local execution and a non-contradiction for a harness one.
    -> (state, reason, corroboration dict)."""
    recorded = record.get("state")
    if recorded != "completed":
        return recorded, record.get("reason"), {"checked": False}
    gaps = []
    task_id = record.get("task_id")
    # Every execution (harness or local) ran under exactly one ticket operation; the worker claimed that operation for
    # this execution id when the ticket verified (create-once index). A record that names no operation, another
    # record's operation, or an operation this record never claimed is not corroborated (review round 4, OPS-1R).
    op = record.get("operation_id")
    if not isinstance(op, str) or not op:
        gaps.append("OPERATION_MISSING")
    else:
        owner = operation_owner(op) if operation_owner is not None else None
        if owner != record.get("execution_id"):
            gaps.append("OPERATION_NOT_OWNED")
        if task_id and task_id != op:
            gaps.append("OPERATION_TASK_MISMATCH")
        if isinstance(server, dict) and "error" not in server and server.get("operation_id") != op:
            gaps.append("SERVER_OPERATION_MISMATCH")
    if task_id:
        if not isinstance(ledger, dict) or (ledger.get("task") or {}).get("state") != "COMPLETE":
            gaps.append("LEDGER_NOT_COMPLETE")
        else:
            # The COMPLETE task must be THIS execution's: same turn, session, capability, selection and digests as the
            # record's proposal (a record pointing at another execution's finished task is not completed).
            req, prop = ledger.get("request") or {}, record.get("proposal") or {}
            if not isinstance(req, dict) or req.get("turn_id") != record.get("turn_id") or req.get("operation_id") != task_id \
                    or req.get("session_id") != record.get("session_id") \
                    or any(req.get(k) != prop.get(k) for k in ("session_id", "capability_id", "provider", "model",
                                                               "approval_digest", "argument_digest")):
                gaps.append("LEDGER_REQUEST_MISMATCH")
            # The ledger row names the ONE execution record the bridge ran for (review round 2, OPS-1R): a second
            # record copying every field of a genuine execution is still not that execution.
            if isinstance(req, dict) and req.get("execution_id") != record.get("execution_id"):
                gaps.append("LEDGER_EXECUTION_MISMATCH")
        if isinstance(server, dict) and "error" not in server:
            if server.get("state") != "reply":
                gaps.append("SERVER_TURN_NOT_REPLY")
            if server.get("session_id") != record.get("session_id"):
                gaps.append("SERVER_SESSION_MISMATCH")
    else:
        prop = record.get("proposal") or {}
        if prop.get("kind") == "client_external_harness":
            gaps.append("TASK_OMITTED")                   # a harness execution without its supervisor task (OPS-1R)
        if server is None or not isinstance(server, dict) or "error" in server:
            gaps.append("SERVER_UNAVAILABLE")
        else:
            if server.get("state") != "reply":
                gaps.append("SERVER_TURN_NOT_REPLY")
            if server.get("session_id") != record.get("session_id") or prop.get("session_id") != record.get("session_id"):
                gaps.append("SERVER_SESSION_MISMATCH")
            sop = server.get("operation_id")
            if sop and (task_exists(sop) if task_exists is not None else False):
                gaps.append("TASK_OMITTED")               # the server's operation IS a supervisor task: not local
    # The client journal (frozen C4) holds one row per ticket operation, local capabilities included.
    if not isinstance(journal, dict) or journal.get("state") != "verified":
        gaps.append("JOURNAL_NOT_VERIFIED")
    gaps = list(dict.fromkeys(gaps))
    if record.get("code") != "SETTLED_VERIFIED":
        gaps.append("CODE_NOT_SETTLED_VERIFIED")
    if gaps:
        return "uncertain", "UNCORROBORATED_COMPLETION:" + ",".join(gaps), {"checked": True, "gaps": gaps}
    return "completed", record.get("reason"), {"checked": True, "gaps": []}


_STR_OR_NONE = ("turn_id", "session_id", "request_text", "reason", "code", "message", "task_id", "bridge_outcome",
                "failure_category", "decision", "previous_state", "server_state", "operation_id", "operation_owner",
                "approval_retry_reason")
_NUM_OR_NONE = ("queued_at", "approving_at", "starting_at", "running_at", "ended_at", "updated_at", "cancel_requested_at", "worker_pid",
                "approval_retries")
_DICT_OR_NONE = ("proposal", "restart_ledger")
_LIST_OR_NONE = ("evidence",)


def _well_typed(rec, execution_id) -> bool:
    if not isinstance(rec, dict) or rec.get("schema") != SCHEMA or rec.get("execution_id") != execution_id:
        return False
    if not isinstance(rec.get("state"), str) or rec["state"] not in ACTIVE_STATES + TERMINAL_STATES:
        return False
    for k in _STR_OR_NONE:
        if k in rec and rec[k] is not None and not isinstance(rec[k], str):
            return False
    for k in _NUM_OR_NONE:
        if k in rec and rec[k] is not None and (isinstance(rec[k], bool) or not isinstance(rec[k], (int, float))):
            return False
    for k in _DICT_OR_NONE:
        if k in rec and rec[k] is not None and not isinstance(rec[k], dict):
            return False
    for k in _LIST_OR_NONE:
        if k in rec and rec[k] is not None and not isinstance(rec[k], list):
            return False
    if "cancel_requested" in rec and not isinstance(rec["cancel_requested"], bool):
        return False
    prop = rec.get("proposal")
    if isinstance(prop, dict):
        for k in ("proposal_digest", "approval_digest", "turn_id", "session_id", "kind", "provider", "model", "capability_id",
                  "argument_digest", "effect", "action", "instruction", "expected_file"):
            if k in prop and prop[k] is not None and not isinstance(prop[k], str):
                return False
        if not isinstance(prop.get("proposal_digest"), str):
            return False
        if "reversible" in prop and prop["reversible"] is not None and not isinstance(prop["reversible"], bool):
            return False
        for k in ("arguments", "qualification"):
            if k in prop and prop[k] is not None and not isinstance(prop[k], dict):
                return False
    ev = rec.get("evidence")
    if isinstance(ev, list):
        for e in ev:
            if not isinstance(e, dict):
                return False
            for k in ("check", "output_sha256", "harness", "supervisor_task", "basis"):
                if k in e and e[k] is not None and not isinstance(e[k], str):
                    return False
            for k in ("output_bytes", "supervisor_attempt"):
                if k in e and e[k] is not None and (isinstance(e[k], bool) or not isinstance(e[k], int)):
                    return False
            if "matched" in e and e["matched"] is not None and not isinstance(e["matched"], bool):
                return False
    return True


class ExecutionRegister:
    """Durable, worker-owned execution records. Atomic JSON per execution; never holds tickets, keys or tokens."""

    def __init__(self, client_root):
        self.root = Path(client_root).resolve()
        self.dir = self.root / "control" / "supervisor" / "executions"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def path(self, execution_id) -> Path:
        if not isinstance(execution_id, str) or not _ID.fullmatch(execution_id):
            raise TurnError("EXECUTION_ID_INVALID")
        return self.dir / (execution_id + ".json")

    # ---- operation ownership (review round 4, OPS-1R residual) -------------------------------------
    def _op_path(self, operation_id) -> Path | None:
        if not isinstance(operation_id, str) or not _OP_ID.fullmatch(operation_id):
            return None
        return self.dir / "operations" / (operation_id + ".json")

    def claim_operation(self, operation_id, execution_id):
        """First writer wins: the execution that verified the ticket for `operation_id` owns it for ever. Returns the
        owning execution id (this one, or an earlier claimant), or None when the id is not an operation id."""
        import json
        p = self._op_path(operation_id)
        if p is None:
            return None
        p.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            try:
                with open(p, "x", encoding="utf-8") as f:
                    json.dump({"operation_id": operation_id, "execution_id": execution_id, "claimed_at": _now()}, f)
                    f.flush()
                    import os
                    os.fsync(f.fileno())
            except FileExistsError:
                pass
        return self.operation_owner(operation_id)

    def operation_owner(self, operation_id):
        import json
        p = self._op_path(operation_id)
        if p is None or not p.is_file():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        owner = data.get("execution_id") if isinstance(data, dict) else None
        return owner if isinstance(owner, str) and _ID.fullmatch(owner) and data.get("operation_id") == operation_id else None

    def get(self, execution_id):
        import json
        p = self.path(execution_id)
        with self._lock:
            if not p.is_file():
                return None
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {"schema": SCHEMA, "execution_id": execution_id, "state": "uncertain", "reason": "RECORD_UNREADABLE"}
        # Valid JSON is not yet a valid record (review round 1 OPS-2, round 2 OPS-2R): the id must be the file's and
        # every field the worker reads must have its type. Anything else is an uncertain stub, so listing and restart
        # reconciliation never abort on one damaged row.
        if not _well_typed(rec, execution_id):
            return {"schema": SCHEMA, "execution_id": execution_id, "state": "uncertain", "reason": "RECORD_SCHEMA"}
        return rec

    def write(self, record):
        with self._lock:
            atomic_json(self.path(record["execution_id"]), record)

    def update(self, execution_id, **fields):
        with self._lock:
            rec = self.get(execution_id)
            if rec is None:
                raise TurnError("EXECUTION_UNKNOWN")
            rec.update(fields)
            rec["updated_at"] = _now()
            self.write(rec)
            return rec

    def list(self, limit=_LIST_LIMIT):
        with self._lock:
            ids = sorted(p.stem for p in self.dir.glob("*.json") if _ID.fullmatch(p.stem))
            recs = [self.get(i) for i in ids]
        recs = [r for r in recs if r is not None]
        recs.sort(key=lambda r: (r.get("queued_at") or 0, r["execution_id"]), reverse=True)
        return recs[:limit]

    def reconcile_restart(self, ledger_path, why="WORKER_RESTARTED"):
        """Every non-terminal record belongs to a worker that is gone: the attempt (if any) was killed by its
        kill-on-close job and the bridge has revoked the task's authority. The record becomes `uncertain`; the ledger
        facts are attached. Nothing is re-launched."""
        out = []
        for rec in self.list(limit=10_000):
            if rec.get("state") in TERMINAL_STATES:
                continue
            view = ledger_view(ledger_path, rec.get("task_id"))
            self.update(rec["execution_id"], state="uncertain", reason=why, ended_at=_now(), restart_ledger=view,
                        previous_state=rec.get("state"))
            out.append({"execution_id": rec["execution_id"], "was": rec.get("state"), "state": "uncertain", "reason": why})
        return out


class ExecutionController:
    """Worker-side lifecycle driver. `service` is the SupervisedWorkerService that owns the pending turns and the
    runner; `bridge` the SupervisorBridge whose `cancel` kills running attempts."""

    def __init__(self, service, client_root, *, bridge, composition=None, server_status=None, clock=None):
        self.service, self.bridge, self.composition = service, bridge, composition
        self.clock = clock or _now
        self.root = Path(client_root).resolve()
        self.register = ExecutionRegister(self.root)
        self.ledger_path = self.root / "control" / "supervisor" / "ledger.db"
        self.journal_path = self.root / "control" / "execution-journal.sqlite3"
        self._server_status = server_status
        self._lock = threading.Lock()
        self._active = None
        self._thread = None
        self._cancel = set()
        self._task = {}
        self.startup = self._reconcile_on_start()

    # ---- start-up -----------------------------------------------------------------------------
    def _reconcile_on_start(self):
        journal = None
        if self.journal_path.is_file():
            try:
                # Frozen rule (C4 journal): after a restart every claimed operation is uncertain until reconciled.
                journal = [o for o in ExecutionJournal(self.root).recover() if o["state"] == "execution_uncertain"]
            except Exception as exc:  # noqa: BLE001  (reported, never hidden; the register still reconciles)
                journal = {"error": "JOURNAL_RECOVER_FAILED:" + type(exc).__name__}
        return {"journal": journal, "executions": self.register.reconcile_restart(self.ledger_path)}

    # ---- queries ------------------------------------------------------------------------------
    @property
    def active(self):
        with self._lock:
            return self._active

    def qualification_of(self, provider, kind="client_external_harness"):
        """Qualification row for a harness provider; None for non-harness rows (the deterministic local row)."""
        if self.composition is None or not provider or kind != "client_external_harness":
            return None
        for row in self.composition.report:
            if row.get("provider") == provider:
                keys = ("status", "reason", "level", "models", "version", "expires_at", "qualified_at", "executable_sha256")
                return {k: row.get(k) for k in keys}
        return {"status": "NOT_QUALIFIED", "reason": "NO_RECORD"}

    def proposal(self, turn_id):
        entry = self.service.pending.get(turn_id)
        if entry is None:
            raise TurnError("TURN_NOT_PENDING")
        _, session, reasoning, turn = entry
        return execution_proposal(self.service.manifest.data["client_id"], session, turn_id, reasoning,
                                  turn.get("approval_request"), self.qualification_of(reasoning.get("provider"), reasoning.get("kind")))

    def status(self, execution_id):
        rec = self.register.get(execution_id)
        if rec is None:
            raise TurnError("EXECUTION_UNKNOWN")
        task_id, op = rec.get("task_id"), rec.get("operation_id")
        ledger, journal = ledger_view(self.ledger_path, task_id), journal_view(self.journal_path, op if isinstance(op, str) else task_id)
        server = self._server_turn(rec.get("turn_id"))
        state, reason, corroboration = corroborate(rec, ledger, journal, server, self._task_exists, self.register.operation_owner)
        return {**rec, "state": state, "reason": reason, "recorded_state": rec.get("state"), "corroboration": corroboration,
                "operation_owner": self.register.operation_owner(op) if isinstance(op, str) else None,
                "ledger": ledger, "journal": journal, "server_turn": server}

    def list(self):
        out = []
        for r in self.register.list():
            state, reason = r.get("state"), r.get("reason")
            corroboration = {"checked": False}
            if state == "completed":
                # A listed success is held to exactly the same facts as a status (review rounds 1-2, OPS-1/OPS-1R).
                task_id, op = r.get("task_id"), r.get("operation_id")
                ledger, journal = ledger_view(self.ledger_path, task_id), journal_view(self.journal_path, op if isinstance(op, str) else task_id)
                state, reason, corroboration = corroborate(r, ledger, journal, self._server_turn(r.get("turn_id")), self._task_exists,
                                                           self.register.operation_owner)
            out.append({k: r.get(k) for k in ("execution_id", "turn_id", "session_id", "code", "queued_at", "ended_at",
                                                 "task_id", "cancel_requested")}
                       | {"state": state, "reason": reason, "recorded_state": r.get("state"), "corroboration": corroboration,
                          "provider": (r.get("proposal") or {}).get("provider"), "model": (r.get("proposal") or {}).get("model")})
        return out

    def _task_exists(self, operation_id):
        view = ledger_view(self.ledger_path, operation_id)
        return isinstance(view, dict) and view.get("task") is not None

    def _server_turn(self, turn_id):
        if not turn_id:
            return None
        try:
            if self._server_status is not None:
                data = self._server_status(turn_id)
            else:
                data = self.service.transport.request("GET", f"/client/v1/turns/{turn_id}/status", None)
            return {k: data.get(k) for k in ("state", "version", "operation_id", "session_id")} if isinstance(data, dict) else {"error": "BAD_STATUS"}
        except Exception as exc:  # noqa: BLE001  (the server view is informative; unreachable = reported, not invented)
            return {"error": "SERVER_STATUS_UNAVAILABLE:" + str(getattr(exc, "code", type(exc).__name__))[:64]}

    # ---- begin ----------------------------------------------------------------------------------
    def begin(self, turn_id, approval_digest, proposal_digest):
        with self._lock:
            if self._active is not None:
                raise TurnError("EXECUTION_IN_PROGRESS")
            entry = self.service.pending.get(turn_id)
            if entry is None or not isinstance(turn_id, str):
                raise TurnError("TURN_NOT_PENDING")
            text, session, reasoning, turn = entry
            prop = execution_proposal(self.service.manifest.data["client_id"], session, turn_id, reasoning,
                                      turn.get("approval_request"), self.qualification_of(reasoning.get("provider"), reasoning.get("kind")))
            shown = (turn.get("approval_request") or {}).get("approval_digest")
            if not isinstance(approval_digest, str) or approval_digest != shown:
                self.service.pending.pop(turn_id, None)        # same rule as turn_decide: a wrong echo drops the turn
                self._release(entry, "APPROVAL_DIGEST_MISMATCH")
                raise TurnError("APPROVAL_DIGEST_MISMATCH")
            if not isinstance(proposal_digest, str) or proposal_digest != prop["proposal_digest"]:
                self.service.pending.pop(turn_id, None)
                self._release(entry, "PROPOSAL_DIGEST_MISMATCH")
                raise TurnError("PROPOSAL_DIGEST_MISMATCH")
            self.service.pending.pop(turn_id, None)
            eid = uuid.uuid4().hex
            rec = {"schema": SCHEMA, "execution_id": eid, "turn_id": turn_id, "session_id": session, "request_text": text,
                   "proposal": prop, "state": "queued", "reason": None, "code": None, "message": None, "task_id": None,
                   "bridge_outcome": None, "failure_category": None, "evidence": None, "cancel_requested": False,
                   "operation_id": None, "operation_owner": None,
                   "queued_at": self.clock(), "approving_at": None, "starting_at": None, "running_at": None, "ended_at": None,
                   "worker_pid": None}
            import os
            rec["worker_pid"] = os.getpid()
            self.register.write(rec)
            self._active = eid
            self._thread = threading.Thread(target=self._run, args=(eid, text, session, reasoning, turn), daemon=True,
                                            name="uri-execution-" + eid[:8])
            self._thread.start()
        return {"execution_id": eid, "turn_id": turn_id, "state": "queued", "proposal_digest": prop["proposal_digest"]}

    def _release(self, entry, why):
        """CAP-1: the turn this worker just abandoned is released on the server (see worker_service)."""
        release = getattr(self.service, "release_turn", None)
        return release(entry, why) if release is not None else None

    def _cancel_requested(self, eid):
        with self._lock:
            return eid in self._cancel

    def _run(self, eid, text, session, reasoning, turn):
        runner = None
        try:
            runner = self.service._runner()
            approve = not self._cancel_requested(eid)
            self.register.update(eid, state="approving", approving_at=self.clock(), decision="approve" if approve else "deny")

            def on_dispatch(work):
                with self._lock:
                    self._task[eid] = work.task_id
                    cancelled = eid in self._cancel
                self.register.update(eid, task_id=work.task_id, state="running", running_at=self.clock())
                if cancelled:
                    self.bridge.cancel(work.task_id)          # arrived between approval and dispatch: never spawns

            def on_outcome(work, outcome, evidence, failure):
                public = [{k: e.get(k) for k in ("check", "matched", "output_sha256", "output_bytes", "harness",
                                                  "supervisor_task", "supervisor_attempt", "basis")}
                          for e in (evidence or []) if isinstance(e, dict)]
                self.register.update(eid, bridge_outcome=outcome, failure_category=failure, evidence=public)

            def on_starting(operation_id):
                owner = self.register.claim_operation(operation_id, eid)      # create-once: first execution wins
                self.register.update(eid, state="starting", starting_at=self.clock(), operation_id=operation_id, operation_owner=owner)

            runner.on_dispatch, runner.on_outcome, runner.on_starting = on_dispatch, on_outcome, on_starting
            runner.dispatch_context = {"execution_id": eid}       # the bridge records it in the ledger task row
            final = self._decide(eid, runner, text, session, reasoning, turn, approve)
            rec = self.register.get(eid)
            state, reason = self._classify(final, rec, approve)
            self.register.update(eid, state=state, reason=reason, code=final.get("code"), message=final.get("message"),
                                 server_state=final.get("state"), ended_at=self.clock())
        except Exception as exc:  # noqa: BLE001
            code = str(getattr(exc, "code", type(exc).__name__))[:96]
            rec = self.register.get(eid) or {}
            # Nothing was sent to the server while `queued`; afterwards the approval, claim or settle may have landed,
            # unless the server itself shows the turn still awaiting approval at the version we approved (VAL-1).
            if rec.get("state") == "queued":
                state, reason = "failed", "EXCEPTION:" + code
            elif self._approval_provably_unapplied(rec, turn, session):
                state, reason = "failed", "APPROVAL_REFUSED_NOT_APPLIED:" + code
                self._release((text, session, reasoning, turn), "APPROVAL_REFUSED_NOT_APPLIED")   # CAP-1
            else:
                state, reason = "uncertain", "EXCEPTION:" + code
            self.register.update(eid, state=state, reason=reason, ended_at=self.clock())
        finally:
            if runner is not None:
                runner.on_dispatch = runner.on_outcome = runner.on_starting = runner.dispatch_context = None
            with self._lock:
                if self._active == eid:
                    self._active = None
                self._task.pop(eid, None)
                self._cancel.discard(eid)

    # ---- VAL-1: the frozen ticket clock boundary --------------------------------------------------
    # The frozen coordinator stamps `issued_at = int(clock())` and the frozen control refuses the ticket unless the
    # same whole second is read again after the authority callback (`client_execution_control.py:77`); crossing a
    # second boundary in between is `TICKET_CLOCK_OR_GENERATION`, re-raised as HTTP 403 BEFORE any version bump,
    # idempotency record or operation write (`paired_coordinator.py:314-316`, `client_service.py:256-261`).
    # `tests/phase2ops/test_val1_clock_boundary.py` reproduces it. The worker may resend the user's SAME approval once,
    # and only when nothing can have been applied: no ticket observed, no task, no cancel, and the server's own turn
    # status is still `approval_required` at the version and session the approval was built for. Every server gate
    # runs again on the resend; a second refusal ends the execution `failed` (nothing ran), never `uncertain`.
    APPROVAL_RETRY_CODES = ("SERVER_REFUSED:HTTP_403", "SERVER_REFUSED:TICKET_CLOCK_OR_GENERATION")

    def _approval_provably_unapplied(self, rec, turn, session):
        if not isinstance(rec, dict) or rec.get("state") != "approving":
            return False
        if rec.get("operation_id") or rec.get("task_id") or rec.get("starting_at") or rec.get("running_at"):
            return False
        server = self._server_turn(turn.get("turn_id")) or {}
        return (server.get("state") == "approval_required" and type(server.get("version")) is int
                and server.get("version") == turn.get("version") and server.get("session_id") in (None, session))

    def _decide(self, eid, runner, text, session, reasoning, turn, approve):
        try:
            return runner.decide(text, session, reasoning, turn, approve)
        except TurnError as exc:
            code = str(getattr(exc, "code", ""))
            if (not approve or code not in self.APPROVAL_RETRY_CODES or self._cancel_requested(eid)
                    or not self._approval_provably_unapplied(self.register.get(eid), turn, session)):
                raise
            self.register.update(eid, approval_retries=1, approval_retry_reason=code[:96])
        return runner.decide(text, session, reasoning, turn, approve)

    @staticmethod
    def _classify(final, rec, approve):
        code = final.get("code") if isinstance(final, dict) else None
        failure = (rec or {}).get("failure_category") or ""
        cancel = bool((rec or {}).get("cancel_requested")) or not approve
        if code == "SETTLED_VERIFIED":
            return "completed", None
        if code == "APPROVAL_DENIED":
            return "cancelled", "CANCELLED_BEFORE_APPROVAL" if cancel else "DECLINED"
        if code == "WAITING_FOR_MODEL":
            return "quota_paused", "PROVIDER_QUOTA_EXHAUSTED"
        if code == "SETTLED_EXECUTION_UNCERTAIN":
            return "uncertain", ("CANCELLED_AFTER_DISPATCH" if cancel and failure.startswith("CANCELLED_AFTER_DISPATCH") else failure or code)
        if code == "SETTLED_FAILED":
            if cancel and failure == NOT_STARTED + "CANCELLED":
                return "cancelled", "CANCELLED_BEFORE_START"
            return "failed", failure or code
        return "uncertain", "UNRECOGNISED_SETTLEMENT:" + str(code)[:64]

    # ---- cancel ----------------------------------------------------------------------------------
    def cancel(self, execution_id):
        with self._lock:
            rec = self.register.get(execution_id)
            if rec is None:
                raise TurnError("EXECUTION_UNKNOWN")
            if rec.get("state") in TERMINAL_STATES:
                raise TurnError("EXECUTION_TERMINAL")
            if self._active != execution_id:
                raise TurnError("EXECUTION_NOT_OWNED")       # a record from an earlier worker; restart reconciliation owns it
            self._cancel.add(execution_id)
            task = self._task.get(execution_id)
        self.register.update(execution_id, cancel_requested=True, cancel_requested_at=self.clock())
        kill = self.bridge.cancel(task)["kill"] if task else {"granted": False, "reason": "NOT_DISPATCHED"}
        return {"execution_id": execution_id, "cancel": "requested", "kill": kill, "state": self.register.get(execution_id)["state"]}

    # ---- shutdown ---------------------------------------------------------------------------------
    def close(self, timeout_s=30.0):
        """The owning worker is going away: withdraw the active execution (kill through the job) and wait, bounded,
        for its settlement so the record is terminal. The kill-on-close job covers whatever is left."""
        eid = self.active
        if eid is None:
            return {"active": None}
        try:
            self.cancel(eid)
        except TurnError as exc:
            return {"active": eid, "cancel": str(exc.code)}
        t = self._thread
        if t is not None:
            t.join(timeout_s)
        rec = self.register.get(eid) or {}
        if rec.get("state") not in TERMINAL_STATES:
            self.register.update(eid, state="uncertain", reason="WORKER_CLOSED_DURING_EXECUTION", ended_at=self.clock())
        return {"active": eid, "state": self.register.get(eid)["state"]}
