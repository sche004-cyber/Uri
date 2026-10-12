"""C2 paired turn lifecycle. Private context is ephemeral, never the ledger."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import threading
import time
import uuid

from uri_core.client_contracts import Binding, ClientStateSnapshot, digest
from uri_core.core.capability_registry import CapabilityRegistry
from uri_core.core.capability_resolver import CapabilityResolver
from uri_core.core.client_pairing import ClientPairingStore, PairingError
from uri_core.core.client_state_ports import ClientStatePorts, NeedsContext, StatePortError
from uri_core.core.runtime_identity import atomic_json


class ClientControlError(ValueError):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.status = status


class PinnedCapabilityRegistry(CapabilityRegistry):
    """The runtime catalogue copy, honoured only while it still matches the manifest-pinned digest.

    CapabilityRegistry re-reads its file on every call. Any later change (drift or tampering) makes this
    registry empty, which permits nothing, instead of silently changing authority mid-run."""

    def __init__(self, registry_path, pinned_sha256):
        super().__init__(registry_path=registry_path)
        self.pinned_sha256 = pinned_sha256

    def _load_raw(self):
        import hashlib
        try:
            data = Path(self.registry_path).read_bytes()
        except OSError:
            return {}
        if hashlib.sha256(data).hexdigest() != self.pinned_sha256:
            return {}
        try:
            value = json.loads(data.decode("utf-8-sig"))
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}


class ExplicitGrants:
    def __init__(self, pairing, identity):
        self.pairing, self.identity = pairing, identity

    def get_grants(self, user_id, registry_ceiling_ids=None):
        if user_id != self.identity.principal.user_id:
            return set()
        return self.pairing.grants(self.identity) & set(registry_ceiling_ids or ())


class ClientService:
    def __init__(self, runtime, clock=time.time):
        self.runtime = runtime
        self.clock = clock
        self.root = Path(runtime.manifest.data["control_root"])
        self.path = self.root / "client_turn_control.json"
        self.pairings = ClientPairingStore(self.root, runtime.manifest.data["server_id"])
        self.registry = PinnedCapabilityRegistry(
            str(Path(runtime.manifest.data["catalogue_root"]) / "capabilities_registry.json"),
            runtime.manifest.data["source_files"]["uri_workspace/capabilities_registry.json"])
        self.lock = threading.RLock()
        self.live = {}
        self.coordinator = None  # C5 supplies the canonical Core composition.

    def _load(self):
        if not self.path.exists():
            return {"schema_version": "uri.client.v1", "turns": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data["schema_version"] != "uri.client.v1" or not isinstance(data["turns"], dict):
                raise ValueError()
            return data
        except (KeyError, TypeError, ValueError, OSError):
            raise ClientControlError("CONTROL_STORE_UNAVAILABLE", 503) from None

    def check_binding(self, value, identity):
        if (value.server_id, value.client_id, value.principal_id) != (
                identity.server_id, identity.client_id, identity.principal.user_id):
            raise ClientControlError("REQUEST_BINDING", 403)

    def capabilities(self, identity):
        allowed = CapabilityResolver.resolve(identity.principal, self.registry,
                                             ExplicitGrants(self.pairings, identity))
        return {"schema_version": "uri.client.v1", "server_id": identity.server_id,
                "client_id": identity.client_id,
                "capabilities": [asdict(d) for d in allowed]}

    def _expire(self, data):
        now = self.clock()
        changed = False
        for turn_id, live in list(self.live.items()):
            record = data["turns"][turn_id]
            if now - record["touched_at"] >= 900 or now - record["created_at"] >= 3600:
                self.live.pop(turn_id)
                if record["state"] in {"executing", "execution_uncertain"}:
                    # Dispatch was authorized: idle expiry must never erase the possibility of an effect
                    # (that would unlock a duplicate dispatch of the same intent). Keep it uncertain.
                    if record["state"] != "execution_uncertain":
                        record.update(state="execution_uncertain", version=record["version"] + 1)
                elif record["state"] not in {"reply", "failed", "cancelled", "waiting_for_model"}:
                    record.update(state="expired", version=record["version"] + 1)
                changed = True
        for turn_id, record in list(data["turns"].items()):
            if record["state"] in {"reply", "failed", "cancelled", "expired"} and now - record["touched_at"] >= 30 * 86400:
                self.live.pop(turn_id, None)
                if record.get("intent_id"):
                    # Keep the intent lineage the C5 replay/duplicate guards depend on (no private content).
                    lineage = data.setdefault("intents", {}).setdefault(record["intent_id"], {"revision": 0, "verified": False})
                    lineage["revision"] = max(lineage["revision"], record.get("intent_revision") or 0)
                    lineage["verified"] = lineage["verified"] or record.get("execution_outcome") == "verified"
                del data["turns"][turn_id]
                changed = True
        if changed:
            atomic_json(self.path, data)

    def _envelope(self, record, **fields):
        return {"schema_version": "uri.client.v1", "server_id": record["server_id"],
                "client_id": record["client_id"], "session_id": record["session_id"],
                "turn_id": record["turn_id"], "operation_id": record["operation_id"],
                "version": record["version"], "state": record["state"], **fields}

    def _advance(self, record, request, identity):
        ports = ClientStatePorts(request.snapshot, Binding(**{
            k: getattr(request, k) for k in ("server_id", "client_id", "principal_id", "session_id")}).model_dump())
        if record["state"] in self.ACTIVE_STATES | {"waiting_for_model", "execution_uncertain"}:
            raise ClientControlError("TURN_NOT_CONTINUABLE")
        needs = []
        for store, method in (("sessions", "get_session"), ("history", "get_session")):
            try:
                ports.read(store, method, request.session_id)
            except NeedsContext as missing:
                needs.append(missing.query.model_dump())
        if needs:
            record["state"] = "needs_context"
            return self._envelope(record, reads=needs)
        if self.coordinator is None:
            record["state"] = "proposal"
            return self._envelope(record, code="CANONICAL_COMPOSITION_PENDING_C5")
        return self.coordinator(record, request, identity, ports)

    def start(self, request, identity):
        self.check_binding(request, identity)
        # Validate all supplied projections before recording a turn.
        ClientStatePorts(request.snapshot, Binding(**{k: getattr(request, k) for k in
                         ("server_id", "client_id", "principal_id", "session_id")}).model_dump())
        payload_digest = digest(request.model_dump())
        with self.lock:
            data = self._load()
            self._expire(data)
            for record in data["turns"].values():
                if record["client_id"] == identity.client_id and record["idempotency_key"] == request.idempotency_key:
                    if record["request_digest"] != payload_digest:
                        raise ClientControlError("IDEMPOTENCY_CONFLICT")
                    live = self.live.get(record["turn_id"])
                    if live is not None:
                        return live["response"]
                    return self._envelope(record, code="CONTEXT_REQUIRED_AFTER_RESTART")
            # A settled execution_uncertain turn can never advance (settle is refused), so it does not hold
            # the session; the ledger's intent guards, not session capacity, prevent its re-dispatch.
            active = [r for r in data["turns"].values() if r["state"] not in
                      {"cancelled", "expired", "failed", "reply", "waiting_for_model", "execution_uncertain"}
                      and r["turn_id"] in self.live]
            if len(active) >= 4 or any(r["client_id"] == identity.client_id and
                                     r["session_id"] == request.session_id for r in active):
                raise ClientControlError("TURN_CAPACITY", 429)
            turn_id, operation_id = str(uuid.uuid4()), str(uuid.uuid4())
            now = self.clock()
            record = {"server_id": identity.server_id, "client_id": identity.client_id,
                "principal_id": identity.principal.user_id, "session_id": request.session_id,
                "turn_id": turn_id, "operation_id": operation_id, "idempotency_key": request.idempotency_key,
                "request_digest": payload_digest, "version": 0, "state": "proposal",
                "created_at": now, "touched_at": now, "continuations": {}}
            response = self._advance(record, request, identity)
            data["turns"][turn_id] = record
            atomic_json(self.path, data)
            self.live[turn_id] = {"request": request, "response": response, "replays": {}}
            return response

    def _record(self, data, turn_id, identity, request=None):
        record = data["turns"].get(turn_id)
        if record is None:
            raise ClientControlError("TURN_UNKNOWN", 404)
        if (record["server_id"], record["client_id"], record["principal_id"]) != (
                identity.server_id, identity.client_id, identity.principal.user_id):
            raise ClientControlError("TURN_SCOPE", 403)
        if request is not None:
            self.check_binding(request, identity)
            if request.session_id != record["session_id"]:
                raise ClientControlError("SESSION_SCOPE", 403)
        return record

    def continue_turn(self, turn_id, continuation, identity):
        with self.lock:
            data = self._load()
            self._expire(data)
            record = self._record(data, turn_id, identity, continuation)
            live = self.live.get(turn_id)
            payload_digest = digest(continuation.model_dump())
            prior = record["continuations"].get(continuation.idempotency_key)
            if prior:
                if prior["digest"] != payload_digest:
                    raise ClientControlError("IDEMPOTENCY_CONFLICT")
                if live and continuation.idempotency_key in live["replays"]:
                    return live["replays"][continuation.idempotency_key]
                return self._envelope(record, code="CONTEXT_REQUIRED_AFTER_RESTART")
            if live is None or record["state"] in {"cancelled", "expired", "reply", "failed"}:
                raise ClientControlError("TURN_NOT_CONTINUABLE")
            if continuation.expected_version != record["version"]:
                raise ClientControlError("VERSION_CONFLICT")
            updated = live["request"].model_copy(update={"snapshot": continuation.snapshot})
            # Revalidate rather than trusting model_copy's unchecked update.
            updated = type(updated).model_validate(updated.model_dump())
            record["version"] += 1
            record["touched_at"] = self.clock()
            response = self._advance(record, updated, identity)
            record["continuations"][continuation.idempotency_key] = {"digest": payload_digest}
            atomic_json(self.path, data)
            live.update(request=updated, response=response)
            live["replays"][continuation.idempotency_key] = response
            return response

    ACTIVE_STATES = {"approval_required", "ticket_issued", "executing"}

    def act(self, turn_id, body, identity, step):
        """Idempotent, version-checked state step used by the trusted coordinator.

        `step(record, live)` returns the response envelope and may set record["state"].
        Replays of an identical request return the stored response; a changed payload
        with the same key conflicts. Nothing here grants authority."""
        with self.lock:
            data = self._load()
            self._expire(data)
            record = self._record(data, turn_id, identity, body)
            live = self.live.get(turn_id)
            payload_digest = digest(body.model_dump())
            prior = record["continuations"].get(body.idempotency_key)
            if prior:
                if prior["digest"] != payload_digest:
                    raise ClientControlError("IDEMPOTENCY_CONFLICT")
                if live and body.idempotency_key in live["replays"]:
                    return live["replays"][body.idempotency_key]
                return self._envelope(record, code="CONTEXT_REQUIRED_AFTER_RESTART")
            if live is None or record["state"] in {"cancelled", "expired", "reply", "failed"}:
                raise ClientControlError("TURN_NOT_CONTINUABLE")
            if body.expected_version != record["version"]:
                raise ClientControlError("VERSION_CONFLICT")
            response = step(record, live)
            record["version"] += 1
            record["touched_at"] = self.clock()
            record["continuations"][body.idempotency_key] = {"digest": payload_digest}
            response = {**response, "version": record["version"]}
            atomic_json(self.path, data)
            live["response"] = response
            live["replays"][body.idempotency_key] = response
            return response

    def cancel(self, turn_id, request, identity):
        with self.lock:
            data = self._load()
            record = self._record(data, turn_id, identity, request)
            payload_digest = digest(request.model_dump())
            prior = record.get("cancellation")
            if record["state"] == "cancelled":
                if prior != {"key": request.idempotency_key, "digest": payload_digest}:
                    raise ClientControlError("IDEMPOTENCY_CONFLICT")
                return self._envelope(record)
            if record["state"] in {"reply", "failed", "expired"}:
                # A settled turn may have external effects; never relabel it.
                raise ClientControlError("TURN_TERMINAL")
            if record["version"] != request.expected_version:
                raise ClientControlError("VERSION_CONFLICT")
            if record["state"] in {"executing", "execution_uncertain"} or (
                    record.get("dispatched") and not record.get("execution_closed")):
                # Dispatch was authorized: the client may be running (or have run) the action. Never relabel
                # it "cancelled" (that would hide a possible effect and defeat the no-duplicate guards).
                # Release the session so the user can continue, but keep the turn execution_uncertain.
                record.update(state="execution_uncertain", version=record["version"] + 1, touched_at=self.clock())
                record["cancellation"] = {"key": request.idempotency_key, "digest": payload_digest}
                self.live.pop(turn_id, None)
                atomic_json(self.path, data)
                return self._envelope(record, code="EXECUTION_UNCERTAIN_NOT_CANCELLED")
            record.update(state="cancelled", version=record["version"] + 1, touched_at=self.clock())
            record["cancellation"] = {"key": request.idempotency_key, "digest": payload_digest}
            self.live.pop(turn_id, None)
            atomic_json(self.path, data)
            return self._envelope(record)

    def status(self, turn_id, identity):
        with self.lock:
            data = self._load()
            self._expire(data)
            record = self._record(data, turn_id, identity)
            return self._envelope(record, context_available=turn_id in self.live)

    def record_provider_wait(self, turn_id, identity, expected_version, checkpoint_digest):
        """C4/C5 quota checkpoint, called by trusted provider composition only.

        No provider substitution or automatic resume. Private context expiry
        leaves the durable wait record intact; a future qualified recovery
        path must supply fresh context and reconcile the exact checkpoint.
        """
        import re
        if type(expected_version) is not int or not isinstance(checkpoint_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", checkpoint_digest):
            raise ClientControlError("PROVIDER_CHECKPOINT_SCHEMA", 400)
        with self.lock:
            data = self._load()
            record = self._record(data, turn_id, identity)
            if record["version"] != expected_version or record["state"] in {"reply", "failed", "cancelled", "expired"}:
                raise ClientControlError("VERSION_CONFLICT")
            live = self.live.get(turn_id)
            if live is None:
                raise ClientControlError("CONTEXT_REQUIRED_AFTER_RESTART")
            record.update(state="waiting_for_model", version=record["version"] + 1,
                touched_at=self.clock(), checkpoint_digest=checkpoint_digest,
                reasoning_digest=digest(live["request"].reasoning.model_dump()))
            response = self._envelope(record, code="WAITING_FOR_MODEL", checkpoint_digest=checkpoint_digest)
            atomic_json(self.path, data)
            live["response"] = response
            return response

    def expire(self):
        with self.lock:
            self._expire(self._load())
