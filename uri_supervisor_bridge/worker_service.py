"""Phase 2D worker-side service: the frozen worker protocol, served by the SupervisedTurnRunner.

Same commands and envelopes as the frozen `TurnService` (`turn_start`, `turn_intent`, `turn_decide`), so the
frozen UI client (`uri_ui/lib/services/paired_runtime.dart`) could drive it unchanged, plus strict additions:

  * `turn_decide` MAY carry `approval_digest`: when present it must equal the digest of the approval request the
    worker showed for that turn; a mismatch drops the pending turn and refuses (`APPROVAL_DIGEST_MISMATCH`). A UI
    that echoes the digest it displayed therefore cannot approve a turn whose arguments changed underneath it. The
    worker still binds the approval to its own pending record either way (UI is never the authority).
  * `turn_cancel {turn_id}`: explicit withdrawal of a pending (not yet dispatched) turn. It is sent to the server as
    a denial, so nothing is ever executed for it.
  * Phase 2 UI/operations (`execution.py`): an `approval_required` reply also carries `execution_proposal`;
    `execution_begin {turn_id, approval_digest, proposal_digest}` approves and dispatches in a worker thread and
    returns at once with an `execution_id`; `execution_status {execution_id}`, `execution_cancel {execution_id}` and
    `execution_list {}` read and withdraw that execution while the frame loop stays responsive. While an execution is
    in flight every turn command is refused with `EXECUTION_IN_PROGRESS` (one execution per client at a time).
    `turn_decide` (blocking, frozen semantics) remains available and cannot be cancelled mid-run.

Phase 2 closure, CAP-1: the frozen server lets each (client, session) hold ONE active turn and the whole server FOUR
(`client_service.py:169-174`), and an `approval_required` turn that nobody decides stays active for 15 minutes idle.
Whenever this worker abandons a pending turn on its own (a wrong digest echo, or `close`/stdin EOF with turns still
pending) it now releases it through the frozen server's own cancel route (`POST /client/v1/turns/{id}/cancel`,
version-checked; the server never relabels a dispatched turn). Before this, four abandoned cards blocked every new
turn on the server for up to 15 minutes. A worker that dies without `close` still cannot release (pending state is
memory-only); the server's 15-minute expiry remains the backstop.

Pending state is memory-only, exactly as in the frozen service: a worker restart or reconnect drops every pending
turn (fail closed, `TURN_NOT_PENDING`), and the frozen server's own guards (`INTENT_EXECUTION_UNCERTAIN`,
`INTENT_ALREADY_EXECUTED`, duplicate operation ids) prevent a second execution of the same work. Execution records
(`control/supervisor/executions/`) are durable and are reconciled, never replayed, at the next start.
"""
from __future__ import annotations

from uri_core.client_runtime.turn_runner import TurnError

from .execution import ExecutionController
from .runner import SupervisedTurnService

COMMAND_SCHEMAS = {
    "turn_start": ({"command", "session_id", "text", "reasoning"},),
    "turn_intent": ({"command", "session_id", "text", "reasoning", "intent_decision"},),
    "turn_decide": ({"command", "turn_id", "approve"}, {"command", "turn_id", "approve", "approval_digest"}),
    "turn_cancel": ({"command", "turn_id"},),
    "execution_begin": ({"command", "turn_id", "approval_digest", "proposal_digest"},),
    "execution_status": ({"command", "execution_id"},),
    "execution_cancel": ({"command", "execution_id"},),
    "execution_list": ({"command"},),
}
EXECUTION_COMMANDS = ("execution_begin", "execution_status", "execution_cancel", "execution_list")
TURN_COMMANDS = ("turn_start", "turn_intent", "turn_decide", "turn_cancel")


class SupervisedWorkerService(SupervisedTurnService):
    def __init__(self, manifest, persistence, bridge, harness=None, composition=None, executions=True, server_status=None, clock=None):
        super().__init__(manifest, persistence, bridge, harness=harness)
        self.composition = composition
        self.executions = ExecutionController(self, manifest.data["client_root"], bridge=bridge, composition=composition,
                                              server_status=server_status, clock=clock) if executions else None
        self.released = []      # last releases (CAP-1), for diagnostics only: ids, codes, never content

    def release_turn(self, entry, why):
        """CAP-1: release an abandoned, never-dispatched `approval_required` turn on the server. Best effort, never
        raises: a refusal (`VERSION_CONFLICT`, `TURN_TERMINAL`, unreachable server) is recorded and the server's own
        expiry stays the backstop. Nothing is approved, denied or executed by it."""
        turn_id = None
        try:
            text, session, reasoning, turn = entry
            turn_id = turn.get("turn_id")
            runner = self._runner()
            status, data = runner.call("POST", f"/client/v1/turns/{turn_id}/cancel", runner._control(session, turn))
            state = data.get("state") if isinstance(data, dict) else None
            detail = data.get("detail") if isinstance(data, dict) else None
            out = {"turn_id": turn_id, "why": why, "released": status == 200 and state == "cancelled",
                   "status": status, "server_state": state if isinstance(state, str) else None,
                   "code": detail[:64] if isinstance(detail, str) else None}
        except Exception as exc:  # noqa: BLE001  (best effort; reported, never hidden)
            out = {"turn_id": turn_id, "why": why, "released": False, "error": type(exc).__name__}
        self.released = (self.released + [out])[-20:]
        return out

    def _refuse_unusable_harness(self, turn_id):
        """OQ-1 on the blocking `turn_decide approve=true` path too (operational-qualification review round 1, OQ-R1-2):
        an approval for an executor that cannot run NOW never leaves the worker. The pending turn is dropped and released
        on the server (CAP-1 route); nothing is approved. Declining is never gated."""
        entry = self.pending.get(turn_id)
        if entry is None or self.executions is None:
            return
        _, _, reasoning, _ = entry
        reasoning = reasoning if isinstance(reasoning, dict) else {}
        state = self.executions.harness_state(reasoning.get("provider"), reasoning.get("kind"))
        if state is not None and not state["usable"]:
            self.pending.pop(turn_id, None)
            self.release_turn(entry, "HARNESS_NOT_USABLE")
            raise TurnError("HARNESS_NOT_USABLE")

    def release_pending(self, why="WORKER_CLOSED"):
        """Release every turn still pending in this worker (close / stdin EOF)."""
        entries = [self.pending.pop(t, None) for t in list(self.pending)]
        return [self.release_turn(entry, why) for entry in entries if entry is not None]

    @property
    def execution_active(self):
        return self.executions.active if self.executions is not None else None

    def handle(self, kind, command):
        shapes = COMMAND_SCHEMAS.get(kind)
        if shapes is None or set(command) not in shapes:
            raise TurnError("COMMAND_SCHEMA")
        if kind in EXECUTION_COMMANDS:
            if self.executions is None:
                raise TurnError("EXECUTION_NOT_AVAILABLE")
            if kind == "execution_begin":
                return self.executions.begin(command["turn_id"], command["approval_digest"], command["proposal_digest"])
            if kind == "execution_status":
                return self.executions.status(command["execution_id"])
            if kind == "execution_cancel":
                return self.executions.cancel(command["execution_id"])
            return {"executions": self.executions.list(), "active": self.executions.active, "startup": self.executions.startup}
        if self.execution_active is not None:
            raise TurnError("EXECUTION_IN_PROGRESS")
        if kind == "turn_cancel":
            entry = self.pending.pop(command["turn_id"], None)
            if entry is None:
                raise TurnError("TURN_NOT_PENDING")
            text, session, reasoning, turn = entry
            return self._public(self._runner().decide(text, session, reasoning, turn, False))
        if kind == "turn_decide":
            turn_id = command["turn_id"]
            if not isinstance(turn_id, str) or not isinstance(command["approve"], bool):
                dropped = self.pending.pop(turn_id, None) if isinstance(turn_id, str) else None
                if dropped is not None:
                    self.release_turn(dropped, "DECIDE_SCHEMA")
                raise TurnError("TURN_NOT_PENDING")
            if "approval_digest" in command:
                entry = self.pending.get(turn_id)
                shown = ((entry[3].get("approval_request") or {}).get("approval_digest")) if entry else None
                if entry is None or not isinstance(command["approval_digest"], str) or command["approval_digest"] != shown:
                    if self.pending.pop(turn_id, None) is not None:
                        self.release_turn(entry, "APPROVAL_DIGEST_MISMATCH")
                    raise TurnError("APPROVAL_DIGEST_MISMATCH" if entry is not None else "TURN_NOT_PENDING")
                command = {k: v for k, v in command.items() if k != "approval_digest"}
            if command["approve"] is True:
                self._refuse_unusable_harness(command["turn_id"])
        result = super().handle(kind, command)
        if kind in ("turn_start", "turn_intent") and result.get("state") == "approval_required" and self.executions is not None:
            result["execution_proposal"] = self.executions.proposal(result["turn_id"])
        return result
