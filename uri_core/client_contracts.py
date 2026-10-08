"""C2 shared wire shapes. No HTTP, providers, processes or account discovery."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

VERSION = "uri.client.v1"
CONTEXT_LIMIT = 256 * 1024
FRAME_LIMIT = 2 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def public_projection(value, depth=0):
    if depth > 32:
        raise ValueError("PROJECTION_DEPTH")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in {
                "password", "token", "api_key", "credentials", "secret", "access_token",
                "refresh_token", "storage_path", "absolute_path", "native_profile", "path",
            }:
                raise ValueError("PRIVATE_FIELD")
            public_projection(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            public_projection(item, depth + 1)
    elif isinstance(value, str):
        from uri_core.core.security_guards import looks_like_credential_value
        if looks_like_credential_value(value):
            raise ValueError("CREDENTIAL_VALUE")
        if re.match(r"^(?:[a-zA-Z]:[\\/]|\\\\|/)", value):
            raise ValueError("ABSOLUTE_PATH")
    elif value is not None and type(value) not in (bool, int, float):
        raise ValueError("JSON_REQUIRED")
    canonical(value)
    return value


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["uri.client.v1"] = VERSION


class Binding(Wire):
    server_id: str
    client_id: str
    principal_id: str
    session_id: str

    @field_validator("server_id", "client_id", "principal_id", "session_id")
    @classmethod
    def opaque_id(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("CANONICAL_UUID_REQUIRED")
        return value


class ReadQuery(Wire):
    store: str = Field(min_length=1, max_length=48)
    method: str = Field(min_length=1, max_length=48)
    args: list[Any] = Field(default_factory=list, max_length=32)
    kwargs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_arguments(self):
        public_projection(self.args)
        public_projection(self.kwargs)
        if len(canonical(self.model_dump())) > 16 * 1024:
            raise ValueError("QUERY_LIMIT")
        return self

    def key(self):
        return digest(self.model_dump())


class ReadProjection(Wire):
    query: ReadQuery
    result: Any
    store_version: StrictInt = Field(ge=0)
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validated_result(self):
        public_projection(self.result)
        if digest(self.result) != self.result_digest:
            raise ValueError("RESULT_DIGEST")
        return self


class ClientStateSnapshot(Binding):
    reads: list[ReadProjection] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def bounded_snapshot(self):
        if len(canonical(self.model_dump())) > CONTEXT_LIMIT:
            raise ValueError("CONTEXT_LIMIT")
        keys = [r.query.key() for r in self.reads]
        if len(keys) != len(set(keys)):
            raise ValueError("DUPLICATE_QUERY")
        versions = {}
        for read in self.reads:
            if read.query.store in versions and versions[read.query.store] != read.store_version:
                raise ValueError("MIXED_STORE_VERSION")
            versions[read.query.store] = read.store_version
        return self


class Mutation(Wire):
    query: ReadQuery
    base_version: StrictInt = Field(ge=0)
    previous_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    replacement: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validated_payload(self):
        if self.replacement is not None:
            public_projection(self.replacement)
            if (self.query.store, self.query.method) != ("sessions", "save_session"):
                raise ValueError("REPLACEMENT_NOT_ALLOWED")
        payload = self.query.model_dump() if self.replacement is None else {
            "query": self.query.model_dump(), "replacement": self.replacement}
        if digest(payload) != self.payload_digest:
            raise ValueError("MUTATION_DIGEST")
        return self


class ClientMutationSet(Binding):
    operation_id: str
    idempotency_key: str = Field(min_length=16, max_length=128)
    mutations: list[Mutation] = Field(max_length=128)

    @field_validator("operation_id")
    @classmethod
    def valid_operation(cls, value):
        return Binding.opaque_id(value)


class ReasoningSelection(Wire):
    kind: Literal["server_local_model", "client_cloud_model", "client_external_harness"]
    provider: str = Field(min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    allowed_fallbacks: list[str] = Field(default_factory=list, max_length=8)


class IntentDecision(Wire):
    """Structured user decision on a pending C5 intent (confirm / abandon / select a displayed option).
    Text never confirms an intent; only this explicit, digest-bound decision does."""
    intent_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    revision: StrictInt = Field(ge=1)
    decision: Literal["confirm", "abandon", "select"]
    digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidate_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def decision_fields(self):
        if (self.decision == "confirm") != (self.digest is not None):
            raise ValueError("CONFIRM_REQUIRES_DIGEST")
        if (self.decision == "select") != (self.candidate_id is not None):
            raise ValueError("SELECT_REQUIRES_CANDIDATE")
        return self


class TurnRequest(Binding):
    request_id: str
    idempotency_key: str = Field(min_length=16, max_length=128)
    text: str = Field(min_length=1, max_length=65536)
    snapshot: ClientStateSnapshot
    reasoning: ReasoningSelection
    intent_decision: IntentDecision | None = None

    @field_validator("request_id")
    @classmethod
    def valid_request(cls, value):
        return Binding.opaque_id(value)

    @model_validator(mode="after")
    def snapshot_binding(self):
        for name in ("server_id", "client_id", "principal_id", "session_id"):
            if getattr(self, name) != getattr(self.snapshot, name):
                raise ValueError("SNAPSHOT_BINDING")
        return self


class Continuation(Binding):
    expected_version: StrictInt = Field(ge=0)
    idempotency_key: str = Field(min_length=16, max_length=128)
    snapshot: ClientStateSnapshot


class ControlRequest(Binding):
    expected_version: StrictInt = Field(ge=0)
    idempotency_key: str = Field(min_length=16, max_length=128)


class SessionRequest(Wire):
    server_id: str
    client_id: str

    @field_validator("server_id", "client_id")
    @classmethod
    def valid_id(cls, value):
        return Binding.opaque_id(value)
