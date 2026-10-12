"""C4 server ticket control. Not mounted until canonical authority is qualified.

The trusted composition supplies the existing canonical gate/approval and
qualified verifier callbacks. Neither a model nor an HTTP request installs
them. No dispatcher or native adapter is imported here.
"""
import copy
import json
import threading
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from uri_core.client_contracts import Binding, canonical, digest
from uri_core.execution_contracts import ExecutionTicket, SignedTicket, ExecutionReceipt
from uri_core.core.runtime_identity import atomic_json


class ExecutionControlError(ValueError):
    pass


def verify_ticket(value, public_key, binding, *, generation, now, argument_digest,
                  workspace_handle, workspace_version):
    try:
        signed = SignedTicket.model_validate(value)
        ticket = signed.ticket
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(
            bytes.fromhex(signed.signature), canonical(ticket.model_dump()))
        binding = Binding.model_validate(binding)
        if any(getattr(ticket, k) != getattr(binding, k) for k in
               ("server_id", "client_id", "principal_id", "session_id")):
            raise ValueError()
        if ticket.generation != generation or now < ticket.issued_at - 5 or now > ticket.expires_at + 5:
            raise ValueError()
        if (ticket.argument_digest, ticket.workspace_handle, ticket.workspace_version) != (
                argument_digest, workspace_handle, workspace_version):
            raise ValueError()
        return signed
    except Exception:
        raise ExecutionControlError("TICKET_REFUSED") from None


class ClientExecutionControl:
    def __init__(self, runtime, authorize=None, verify_receipt=None, clock=time.time):
        self.runtime = runtime
        self.authorize = authorize
        self.verify_receipt = verify_receipt
        self.clock = clock
        self.path = runtime.manifest.path.parent / "control/client_execution_control.json"
        self.lock = threading.RLock()

    def _load(self):
        if not self.path.exists():
            return {"schema_version": "uri.client.v1", "operations": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if set(data) != {"schema_version", "operations"} or data["schema_version"] != "uri.client.v1" or not isinstance(data["operations"], dict):
                raise ValueError()
            return data
        except Exception:
            raise ExecutionControlError("EXECUTION_CONTROL_UNAVAILABLE") from None

    def _authority(self, ticket, identity, phase):
        if any(getattr(ticket, k) != (identity.principal.user_id if k == "principal_id" else getattr(identity, k))
               for k in ("server_id", "client_id", "principal_id")):
            raise ExecutionControlError("EXECUTION_SCOPE")
        # This callback MUST reuse canonical gates, current pairing/grants,
        # current private approval projection and adapter qualification.
        if self.authorize is None or self.authorize(ticket, identity, phase) is not True:
            raise ExecutionControlError("EXECUTION_AUTHORITY_UNAVAILABLE")

    def prepare(self, value, identity):
        ticket = ExecutionTicket.model_validate(value)
        with self.lock:
            self._authority(ticket, identity, "prepare")
            if ticket.generation != self.runtime.generation or ticket.issued_at != int(self.clock()):
                raise ExecutionControlError("TICKET_CLOCK_OR_GENERATION")
            data = self._load()
            if ticket.operation_id in data["operations"]:
                raise ExecutionControlError("OPERATION_ALREADY_PREPARED")
            signed = SignedTicket(ticket=ticket, signature=self.runtime.key.sign(canonical(ticket.model_dump())).hex())
            # Private arguments/evidence/tickets never enter the control ledger.
            data["operations"][ticket.operation_id] = {
                k: ticket.model_dump()[k] for k in ("server_id", "client_id", "principal_id", "session_id", "turn_id",
                    "operation_id", "ticket_id", "generation", "expires_at", "deadline", "verifier_id", "implementation_digest")}
            data["operations"][ticket.operation_id].update(ticket_digest=digest(ticket.model_dump()),
                state="prepared", version=0, receipt_digest=None, claim_digest=None)
            atomic_json(self.path, data)
            return signed.model_dump()

    def _record(self, data, signed, identity):
        try:
            signed = SignedTicket.model_validate(signed)
            self.runtime.key.public_key().verify(bytes.fromhex(signed.signature), canonical(signed.ticket.model_dump()))
        except Exception:
            raise ExecutionControlError("TICKET_REFUSED") from None
        t = signed.ticket
        record = data["operations"].get(t.operation_id)
        if record is None or record["ticket_digest"] != digest(t.model_dump()):
            raise ExecutionControlError("TICKET_UNKNOWN")
        if (t.server_id, t.client_id, t.principal_id) != (identity.server_id, identity.client_id, identity.principal.user_id):
            raise ExecutionControlError("EXECUTION_SCOPE")
        return t, record

    def claim(self, signed, identity, expected_version, idempotency_key):
        if type(expected_version) is not int or not isinstance(idempotency_key, str) or not 16 <= len(idempotency_key) <= 128:
            raise ExecutionControlError("CLAIM_SCHEMA")
        with self.lock:
            data = self._load()
            ticket, record = self._record(data, signed, identity)
            claim_digest = digest({"ticket": record["ticket_digest"], "key": idempotency_key, "version": expected_version})
            if record["state"] != "prepared":
                if record["state"] == "claimed" and record["claim_digest"] == claim_digest:
                    # A replay acknowledges control only; explicitly no dispatch permission.
                    return {"state": "claimed", "version": record["version"], "dispatch": False}
                raise ExecutionControlError("CLAIM_ALREADY_SETTLED_OR_UNCERTAIN")
            if type(expected_version) is not int or expected_version != record["version"]:
                raise ExecutionControlError("EXECUTION_VERSION_CONFLICT")
            if ticket.generation != self.runtime.generation or self.clock() > ticket.expires_at:
                raise ExecutionControlError("TICKET_EXPIRED_OR_RESTARTED")
            self._authority(ticket, identity, "claim")
            record.update(state="claimed", version=record["version"] + 1, claim_digest=claim_digest)
            atomic_json(self.path, data)  # Linearization point BEFORE launch acknowledgement.
            return {"state": "claimed", "version": record["version"], "dispatch": True}

    def cancel(self, signed, identity, expected_version):
        with self.lock:
            data = self._load()
            ticket, record = self._record(data, signed, identity)
            if type(expected_version) is not int or expected_version != record["version"]:
                raise ExecutionControlError("EXECUTION_VERSION_CONFLICT")
            if record["state"] not in {"prepared", "claimed"}:
                raise ExecutionControlError("EXECUTION_TERMINAL")
            record.update(state="cancelled" if record["state"] == "prepared" else "execution_uncertain",
                          version=record["version"] + 1)
            atomic_json(self.path, data)
            return {"state": record["state"], "version": record["version"]}

    def settle(self, signed, value, identity):
        receipt = ExecutionReceipt.model_validate(value)
        with self.lock:
            data = self._load()
            ticket, record = self._record(data, signed, identity)
            if any(getattr(receipt, k) != getattr(ticket, k) for k in
                   ("server_id", "client_id", "principal_id", "session_id", "turn_id", "operation_id", "verifier_id", "implementation_digest")) or receipt.ticket_digest != record["ticket_digest"]:
                raise ExecutionControlError("RECEIPT_SCOPE")
            rd = digest(receipt.model_dump())
            if record["receipt_digest"]:
                if record["receipt_digest"] != rd:
                    raise ExecutionControlError("RECEIPT_CONFLICT")
                return {"state": record["state"], "version": record["version"]}
            if record["state"] not in {"claimed", "execution_uncertain"}:
                raise ExecutionControlError("RECEIPT_WITHOUT_CLAIM")
            if self.verify_receipt is None or self.verify_receipt(ticket, receipt) is not True:
                raise ExecutionControlError("RECEIPT_VERIFIER_UNAVAILABLE")
            record.update(state=receipt.outcome, version=record["version"] + 1, receipt_digest=rd)
            atomic_json(self.path, data)
            return {"state": record["state"], "version": record["version"]}

    def reconcile_restart(self):
        with self.lock:
            data = self._load()
            for record in data["operations"].values():
                if (record["generation"] != self.runtime.generation or self.clock() > record["deadline"]) and record["state"] in {"prepared", "claimed"}:
                    record.update(state="expired" if record["state"] == "prepared" else "execution_uncertain",
                                  version=record["version"] + 1)
            atomic_json(self.path, data)
            return copy.deepcopy(data)
