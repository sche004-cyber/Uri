"""Client-side composition: the frozen TurnRunner with harness execution routed through the SupervisorBridge.

Only `_run_harness` changes. The frozen order is kept exactly (journal.intent -> online claim ->
journal.acknowledge -> execute -> receipt -> journal.settle -> online settle -> persist): the bridge runs
strictly after the server's claim authorized dispatch, and it returns the same (outcome, evidence, failure)
triple the frozen `_execute` already turns into an ExecutionReceipt. The signed ticket is captured at the one
place the frozen runner already verifies it (`_validate_ticket`, invoked by the journal) and consumed once.
"""
from __future__ import annotations

from uri_core.client_contracts import digest
from uri_core.client_runtime.turn_runner import NOT_STARTED, TurnRunner
from uri_core.client_runtime.turn_service import TurnService

from .authority import BridgeRefused, verify_authority
from .bridge import SupervisorBridge


class SupervisedTurnRunner(TurnRunner):
    def __init__(self, manifest, persistence, call, server_public_key, generation, bridge: SupervisorBridge,
                 journal=None, clock=None, harness=None):
        super().__init__(manifest, persistence, call, server_public_key, generation, journal=journal, clock=clock, harness=harness)
        self.bridge = bridge
        self._bridge_signed = None
        # turn_id -> digest of the reasoning selection the approval was requested under. The frozen ticket binds
        # turn/operation/capability/arguments/intent but not the executor selection; the user approved the task
        # *for the selection shown at begin*, so a different provider/model at decide time is refused (Phase 2C, D-C1).
        self._selection = {}
        # Phase 2 UI/operations: lifecycle observers set by the ExecutionController for the ONE execution it drives
        # (`on_starting(operation_id)` once the ticket verified, `on_dispatch(work)` just before the bridge runs it,
        # `on_outcome(work, outcome, evidence, failure)` when the bridge returns). Observation only: they cannot change
        # the outcome, the receipt or the order of the frozen loop.
        self.on_starting = self.on_dispatch = self.on_outcome = None
        self.dispatch_context = None      # {'execution_id': ...} recorded by the bridge in the ledger task row (OPS-1R)

    def begin(self, text, session, reasoning, intent_decision=None):
        turn = super().begin(text, session, reasoning, intent_decision)
        if isinstance(turn, dict) and turn.get("state") == "approval_required" and turn.get("turn_id"):
            self._selection[turn["turn_id"]] = digest(reasoning)
        return turn

    def _validate_ticket(self, value):
        ok = super()._validate_ticket(value)          # frozen: signature, binding, generation, window, argument digest
        self._bridge_signed = value if ok is True else None
        if ok is True and self.on_starting is not None:
            # The server issued a ticket for the approved turn and it verified: the execution is now "starting"
            # (journal intent -> claim -> dispatch follow). Observed here so no further frozen method is overridden.
            self.on_starting(value["ticket"]["operation_id"])
        return ok

    def _run_harness(self, session, request, reasoning):
        signed, self._bridge_signed = self._bridge_signed, None       # one ticket, one run
        if signed is None:
            return "failed", [], NOT_STARTED + "TICKET_NOT_VERIFIED"
        bound = self._selection.pop(signed["ticket"]["turn_id"], None)
        if bound is None or bound != digest(reasoning):
            return "failed", [], NOT_STARTED + "AUTHORITY_SELECTION_MISMATCH"
        try:
            work = verify_authority(signed, request=request, reasoning=reasoning, binding=self._binding(session),
                                    server_public_key=self.server_public_key, generation=self.generation, now=self.clock())
        except BridgeRefused as exc:
            return "failed", [], (NOT_STARTED + "AUTHORITY_" + exc.code)[:128]
        if self.on_dispatch is not None:
            self.on_dispatch(work)
        result = self.bridge.execute(work, context=self.dispatch_context)
        if self.on_outcome is not None:
            self.on_outcome(work, *result)
        return result


class SupervisedTurnService(TurnService):
    """Worker-side TurnService that builds a SupervisedTurnRunner. Composition only; same protocol."""

    def __init__(self, manifest, persistence, bridge: SupervisorBridge, harness=None):
        super().__init__(manifest, persistence, harness=harness)
        self.bridge = bridge

    def _runner(self):
        if self.runner is None:
            identity = self.transport.verify_server()
            self.transport.session()
            from uri_core.client_runtime.transport import TransportError

            def call(method, path, body):
                try:
                    return 200, self.transport.request(method, path, body)
                except TransportError as exc:
                    code = str(exc)
                    return (int(code[5:]) if code.startswith("HTTP_") else 599), {"detail": code}
            self.runner = SupervisedTurnRunner(self.manifest, self.persistence, call, self.manifest.data["server_public_key"],
                                               identity["generation"], self.bridge, harness=self.harness)
        return self.runner
