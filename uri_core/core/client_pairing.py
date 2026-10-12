"""C2 developer-local pairing; persisted records never contain raw tokens."""
from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import secrets
from pathlib import Path
import threading
import time
import uuid
import json

from uri_core.core.auth_session import AuthSessionStore
from uri_core.core.principal_context import PrincipalContext
from uri_core.core.runtime_identity import atomic_json


class PairingError(ValueError):
    def __init__(self, code, status=401):
        super().__init__(code)
        self.status = status


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class PairedPrincipal:
    server_id: str
    client_id: str
    principal: PrincipalContext


class ClientPairingStore:
    def __init__(self, control_root, server_id):
        self.root = Path(control_root).resolve()
        self.server_id = server_id
        self.path = self.root / "client_pairings.json"
        self.thread_lock = threading.RLock()
        self.principal_sessions = AuthSessionStore(storage_path=str(self.root / "principal_sessions.json"))
        self.sessions = AuthSessionStore(storage_path=str(self.root / "paired_sessions.json"))

    @property
    def lock(self):
        return self._locked()

    @contextmanager
    def _locked(self):
        # Provisioning controller and live HTTP process share this ledger.
        # Thread-only JSON locks would lose bindings across those processes.
        from scripts.uri_server_launcher import NamedMutex
        with self.thread_lock, NamedMutex("Local\\URI_Pairings_" + self.server_id, 10):
            yield

    def _load(self):
        if not self.path.exists():
            return {"version": 1, "server_id": self.server_id, "clients": {}, "bindings": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data["version"] != 1 or data["server_id"] != self.server_id:
                raise ValueError()
            return data
        except (OSError, KeyError, ValueError, TypeError):
            raise PairingError("PAIRING_STORE_UNAVAILABLE", 503) from None

    def provision(self, principal_id, *, grants, mode, client_id=None):
        """Called only by the local controller, never by an HTTP/model route."""
        if str(uuid.UUID(principal_id)) != principal_id:
            raise PairingError("PRINCIPAL_INVALID", 400)
        client_id = client_id or str(uuid.uuid4())
        if str(uuid.UUID(client_id)) != client_id:
            raise PairingError("CLIENT_INVALID", 400)
        with self.lock:
            data = self._load()
            if client_id in data["clients"]:
                raise PairingError("CLIENT_ALREADY_PAIRED", 409)
            pairing_token = secrets.token_urlsafe(32)
            principal_token = self.principal_sessions.create(principal_id)
            data["clients"][client_id] = {"principal_id": principal_id, "role": "USER", "mode": mode,
                "pairing_hash": token_hash(pairing_token), "active": True, "grants": sorted(set(grants))}
            atomic_json(self.path, data)
        return {"server_id": self.server_id, "client_id": client_id, "principal_id": principal_id,
                "principal_token": principal_token, "pairing_token": pairing_token}

    def acquire(self, server_id, client_id, principal_token, pairing_token):
        if server_id != self.server_id:
            raise PairingError("SERVER_BINDING", 403)
        with self.lock:
            principal_id = self.principal_sessions.resolve(principal_token)
            data = self._load()
            pair = data["clients"].get(client_id)
            if not pair or not pair["active"] or not pairing_token or not secrets.compare_digest(
                    pair["pairing_hash"], token_hash(pairing_token)):
                raise PairingError("PAIRING_INVALID")
            if principal_id is None:
                raise PairingError("PRINCIPAL_SESSION_INVALID")
            if principal_id != pair["principal_id"]:
                raise PairingError("PRINCIPAL_BINDING", 403)
            token = self.sessions.create(principal_id)
            data["bindings"][token_hash(token)] = {"client_id": client_id, "expires_at": time.time() + 86400}
            atomic_json(self.path, data)
            return {"schema_version": "uri.client.v1", "server_id": self.server_id, "client_id": client_id,
                    "token": token, "expires_in": 86400}

    def resolve(self, token, claimed_client_id):
        with self.lock:
            principal_id = self.sessions.resolve(token)
            if not principal_id:
                raise PairingError("SESSION_INVALID")
            data = self._load()
            binding = data["bindings"].get(token_hash(token))
            if not binding or binding["expires_at"] <= time.time():
                raise PairingError("SESSION_EXPIRED")
            if binding["client_id"] != claimed_client_id:
                raise PairingError("CLIENT_BINDING", 403)
            pair = data["clients"].get(claimed_client_id)
            if not pair or not pair["active"] or pair["principal_id"] != principal_id:
                raise PairingError("PAIRING_REVOKED")
            return PairedPrincipal(self.server_id, claimed_client_id, PrincipalContext(
                user_id=principal_id, role=pair["role"], device_id=None, mode=pair["mode"]))

    def grants(self, identity):
        with self.lock:
            pair = self._load()["clients"].get(identity.client_id)
            if not pair or not pair["active"] or pair["principal_id"] != identity.principal.user_id:
                raise PairingError("PAIRING_REVOKED")
            return set(pair["grants"])

    def revoke(self, client_id):
        with self.lock:
            data = self._load()
            if client_id not in data["clients"]:
                raise PairingError("CLIENT_UNKNOWN", 404)
            data["clients"][client_id]["active"] = False
            atomic_json(self.path, data)
