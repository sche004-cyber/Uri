"""Worker-side turn service: lets a UI drive the C5 loop over the framed worker protocol.

The UI never gets credentials, tickets or private state: it sends text plus an explicit reasoning
selection, receives an approval request, and returns approve/deny. Pending state is memory-only;
a worker restart drops it (fail closed). Only a harness the client has qualified (none by
default) can ever execute.
"""
from uri_core.client_runtime.harness import HarnessRegistry
from uri_core.client_runtime.transport import ClientTransport, TransportError
from uri_core.client_runtime.turn_runner import TurnRunner, TurnError


class TurnService:
    def __init__(self, manifest, persistence, harness=None):
        self.manifest, self.persistence = manifest, persistence
        # Core default: no adapters, no harness. The worker composes uri_harness_adapters explicitly.
        self.harness = harness if harness is not None else HarnessRegistry()
        self.transport = ClientTransport(manifest)
        self.runner = None
        self.pending = {}

    def _runner(self):
        if self.runner is None:
            identity = self.transport.verify_server()      # pinned signed identity before any credential
            self.transport.session()

            def call(method, path, body):
                try:
                    return 200, self.transport.request(method, path, body)
                except TransportError as exc:
                    code = str(exc)
                    return (int(code[5:]) if code.startswith("HTTP_") else 599), {"detail": code}
            self.runner = TurnRunner(self.manifest, self.persistence, call, self.manifest.data["server_public_key"],
                                     identity["generation"], harness=self.harness)
        return self.runner

    def handle(self, kind, command):
        runner = self._runner()
        if kind in {"turn_start", "turn_intent"}:
            # turn_intent carries the user's explicit structured confirm/abandon/select decision.
            turn = runner.begin(command["text"], command["session_id"], command["reasoning"],
                                command.get("intent_decision") if kind == "turn_intent" else None)
            if turn["state"] == "approval_required":
                self.pending[turn["turn_id"]] = (command["text"], command["session_id"], command["reasoning"], turn)
                return {"state": "approval_required", "turn_id": turn["turn_id"],
                        "approval_request": turn["approval_request"], "executor_kind": command["reasoning"]["kind"],
                        "intent": turn.get("intent")}
            return self._public(turn)
        entry = self.pending.pop(command["turn_id"], None)
        if entry is None or not isinstance(command["approve"], bool):
            raise TurnError("TURN_NOT_PENDING")
        text, session, reasoning, turn = entry
        return self._public(runner.decide(text, session, reasoning, turn, command["approve"]))

    @staticmethod
    def _public(turn):
        return {k: turn.get(k) for k in ("state", "turn_id", "code", "message", "version", "context",
                                         "clarification", "confirmation", "intent")}
