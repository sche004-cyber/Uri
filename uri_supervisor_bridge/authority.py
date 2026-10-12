"""Authority verification for the bridge: a signed Phase 1 ExecutionTicket becomes one bounded `AuthorizedWork`.

Everything checked here reuses frozen Phase 1 contracts (`verify_ticket`, `ExecutionTicket`, `digest`,
`public_projection`). The bridge adds checks Phase 1 left to the server envelope: the arguments the executor will
receive must hash to the ticket's `argument_digest`, the approval digest must bind turn/operation/capability/
arguments/confirmed-intent exactly as the server computes it, and every value that reaches argv or a path is
validated as data. Failure is a typed refusal; nothing is partially accepted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from uri_core.client_contracts import digest, public_projection
from uri_core.core.client_execution_control import ExecutionControlError, verify_ticket
from uri_core.execution_contracts import ExecutionTicket, SignedTicket

SUPPORTED_CAPABILITIES = frozenset({"external_harness_task"})
# Server-side verifier identity for harness tasks (paired_coordinator.DEFAULT_VERIFIERS); pinned here so a ticket
# naming any other verifier for this capability is refused instead of being "verified" by the wrong check.
VERIFIER_ID = "uri.client.harness_output_check.v1"
CHECK_NAME = "harness_output_check"

_EXPECTED_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
MAX_INSTRUCTION_BYTES = 64 * 1024


class BridgeRefused(ValueError):
    """Typed refusal. `code` is machine-readable; it never carries private content."""

    def __init__(self, code, detail=None):
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AuthorizedWork:
    """One ticket's worth of authority, fully validated. Immutable; the bridge derives everything else from it."""
    ticket: ExecutionTicket
    ticket_digest: str
    provider: str            # the user's explicit executor selection (reasoning.provider)
    model: str | None
    expected_file: str
    instruction: str
    arguments: dict          # exactly the approved arguments (digest == ticket.argument_digest)
    intent_digest: str | None

    @property
    def task_id(self) -> str:
        return self.ticket.operation_id

    @property
    def principal(self) -> str:
        return self.ticket.principal_id

    @property
    def deadline_us(self) -> int:
        return int(self.ticket.deadline) * 1_000_000

    @property
    def valid_from_us(self) -> int:
        return int(self.ticket.issued_at) * 1_000_000


def approval_digest_for(ticket: ExecutionTicket, intent_digest):
    """The server's binding (paired_coordinator): turn, operation, capability, argument digest, confirmed intent."""
    return digest({"turn": ticket.turn_id, "op": ticket.operation_id, "capability": ticket.capability_id,
                   "args": ticket.argument_digest, "intent": intent_digest})


def verify_authority(signed, *, request, reasoning, binding, server_public_key, generation, now) -> AuthorizedWork:
    """Ticket + approval request + explicit reasoning selection -> AuthorizedWork, or BridgeRefused.

    `request` is the approval_request envelope the user approved (capability_id, arguments, argument_digest,
    approval_digest, intent_digest). `reasoning` is the user's explicit executor selection for this turn.
    """
    if not isinstance(request, dict) or not isinstance(reasoning, dict):
        raise BridgeRefused("REQUEST_SHAPE")
    try:
        signed_model = SignedTicket.model_validate(signed)
    except Exception:
        raise BridgeRefused("TICKET_SHAPE") from None
    ticket = signed_model.ticket
    # 1. Phase 1 verification: signature, binding, generation, freshness window, argument digest, workspace handle.
    try:
        verify_ticket(signed, server_public_key, binding, generation=generation, now=now,
                      argument_digest=request.get("argument_digest"), workspace_handle=ticket.workspace_handle,
                      workspace_version=ticket.workspace_version)
    except ExecutionControlError:
        raise BridgeRefused("TICKET_REFUSED") from None
    if ticket.approval_status != "approved":
        raise BridgeRefused("TICKET_NOT_APPROVED")
    # 2. The arguments that will reach the executor must be the approved ones, not whatever the envelope says now.
    args = request.get("arguments")
    if not isinstance(args, dict) or digest(args) != ticket.argument_digest:
        raise BridgeRefused("ARGUMENT_DIGEST_MISMATCH")
    try:
        public_projection(args)
    except ValueError as exc:
        raise BridgeRefused("ARGUMENTS_NOT_PUBLIC", str(exc)) from None
    # 3. Capability and verifier pinned: this bridge only executes harness tasks checked by the harness verifier.
    if request.get("capability_id") != ticket.capability_id or ticket.capability_id not in SUPPORTED_CAPABILITIES:
        raise BridgeRefused("CAPABILITY_NOT_SUPPORTED", ticket.capability_id)
    if ticket.verifier_id != VERIFIER_ID:
        raise BridgeRefused("VERIFIER_MISMATCH")
    # 4. Approval digest binds turn/op/capability/arguments/confirmed intent. A replayed or edited envelope fails here.
    intent_digest = request.get("intent_digest")
    if intent_digest is not None and not (isinstance(intent_digest, str) and re.fullmatch(r"[0-9a-f]{64}", intent_digest)):
        raise BridgeRefused("INTENT_DIGEST_SHAPE")
    if request.get("approval_digest") != ticket.approval_digest or approval_digest_for(ticket, intent_digest) != ticket.approval_digest:
        raise BridgeRefused("APPROVAL_DIGEST_MISMATCH")
    # 5. Deadline: a ticket whose execution deadline passed grants nothing (the supervisor also enforces it).
    if now > ticket.deadline:
        raise BridgeRefused("TICKET_DEADLINE_PASSED")
    # 6. Executor selection is the user's explicit choice; it is data for an allow-list, never a command.
    if reasoning.get("kind") != "client_external_harness":
        raise BridgeRefused("REASONING_KIND_NOT_HARNESS", str(reasoning.get("kind")))
    provider = reasoning.get("provider")
    if not isinstance(provider, str) or not _PROVIDER.fullmatch(provider):
        raise BridgeRefused("PROVIDER_ID_INVALID")
    model = reasoning.get("model")
    if model is not None and (not isinstance(model, str) or not _MODEL.fullmatch(model)):
        raise BridgeRefused("MODEL_ID_INVALID")
    # 7. Harness inputs: the output name is a bare file name (no path, no reserved device, no dotfile), the
    #    instruction is bounded text that only ever travels on stdin.
    inputs = args.get("inputs")
    if not isinstance(inputs, dict) or args.get("action") is None:
        raise BridgeRefused("ARGUMENT_SHAPE")
    expected = inputs.get("expected_file")
    if (not isinstance(expected, str) or not _EXPECTED_FILE.fullmatch(expected) or expected.lower().split(".")[0] in _RESERVED
            or expected.endswith(".") or expected.endswith(" ")):
        raise BridgeRefused("EXPECTED_FILE_INVALID")
    instruction = inputs.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction.encode("utf-8")) > MAX_INSTRUCTION_BYTES:
        raise BridgeRefused("INSTRUCTION_INVALID")
    return AuthorizedWork(ticket=ticket, ticket_digest=digest(ticket.model_dump()), provider=provider, model=model,
                          expected_file=expected, instruction=instruction, arguments=args, intent_digest=intent_digest)
