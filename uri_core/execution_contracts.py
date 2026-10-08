"""C4 bounded ticket/claim/receipt wire contract; no execution authority."""
from typing import Any, Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from uri_core.client_contracts import Binding, Wire, canonical, public_projection


class ExecutionTicket(Binding):
    turn_id: str
    operation_id: str
    ticket_id: str
    generation: str
    capability_id: str = Field(min_length=1, max_length=128)
    argument_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_handle: str
    workspace_version: StrictInt = Field(ge=0)
    approval_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_status: Literal["approved"]
    output_handles: list[str] = Field(default_factory=list, max_length=16)
    verifier_id: str = Field(min_length=1, max_length=128)
    implementation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: StrictInt = Field(ge=0)
    expires_at: StrictInt = Field(ge=0)
    deadline: StrictInt = Field(ge=0)
    cancellation_nonce: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("turn_id", "operation_id", "ticket_id", "generation", "workspace_handle")
    @classmethod
    def ids(cls, value):
        return Binding.opaque_id(value)

    @model_validator(mode="after")
    def bounds(self):
        for handle in self.output_handles:
            Binding.opaque_id(handle)
        if len(set(self.output_handles)) != len(self.output_handles):
            raise ValueError("DUPLICATE_OUTPUT")
        if not 0 < self.expires_at - self.issued_at <= 60 or self.deadline < self.expires_at:
            raise ValueError("TICKET_LIFETIME")
        if self.deadline - self.issued_at > 3600:
            raise ValueError("EXECUTION_DEADLINE")
        public_projection(self.model_dump())
        return self


class SignedTicket(Wire):
    ticket: ExecutionTicket
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")


class ExecutionReceipt(Binding):
    turn_id: str
    operation_id: str
    ticket_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str
    outcome: Literal["verified", "failed", "cancelled", "execution_uncertain"]
    verifier_id: str = Field(min_length=1, max_length=128)
    implementation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_version: StrictInt = Field(ge=0)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=64)
    failure_category: str | None = Field(default=None, max_length=128)

    @field_validator("turn_id", "operation_id", "run_id")
    @classmethod
    def ids(cls, value):
        return Binding.opaque_id(value)

    @model_validator(mode="after")
    def bounded_evidence(self):
        public_projection(self.model_dump())
        if len(canonical(self.model_dump())) > 256 * 1024:
            raise ValueError("RECEIPT_LIMIT")
        if self.outcome == "verified" and (not self.evidence or self.failure_category is not None):
            raise ValueError("VERIFICATION_EVIDENCE_REQUIRED")
        return self
