"""Durable, bounded S1 round journal. Paths are always server-owned user paths."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import types
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import get_args, get_origin, get_type_hints, Union
from uuid import uuid4

from uri_core.core.portable_paths import DEFAULT_USER_STATE_ROOT, user_scoped_path
from uri_v1.reference_clarification.safeguards import ClarificationSafeguards
from uri_v1.reference_clarification.store import BindingRecord, InMemoryClarificationStore, StoredRound
from uri_v1.turn.rar_clarification_contract import ClarificationContract, BindingState, validate_contract
from uri_v1.turn.rar_contracts import RARQuery

from .evidence import EvidenceCandidate

SCHEMA_VERSION = 1
MAX_BYTES = 1_048_576
MAX_RECORDS = 64
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _decode(kind, value):
    """Strictly materialize only the frozen dataclass/enum schema, never arbitrary types."""
    origin = get_origin(kind)
    args = get_args(kind)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        choices = [arg for arg in args if arg is not type(None)]
        if len(choices) != 1:
            raise ValueError("unsupported journal union")
        return _decode(choices[0], value)
    if origin is tuple:
        if not isinstance(value, list) or len(value) > MAX_RECORDS:
            raise ValueError("invalid journal tuple")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(args[0], item) for item in value)
        if len(args) != len(value):
            raise ValueError("invalid journal tuple width")
        return tuple(_decode(arg, item) for arg, item in zip(args, value))
    if isinstance(kind, type) and issubclass(kind, Enum):
        if type(value) is not str:
            raise ValueError("invalid journal enum")
        return kind(value)
    if isinstance(kind, type) and is_dataclass(kind):
        if not isinstance(value, dict) or set(value) != {f.name for f in fields(kind)}:
            raise ValueError("invalid journal object")
        hints = get_type_hints(kind)
        return kind(**{f.name: _decode(hints[f.name], value[f.name]) for f in fields(kind)})
    if kind in (str, int, bool, float):
        if type(value) is not kind:
            raise ValueError("invalid journal scalar")
        return value
    raise ValueError("unsupported journal field")


def _stamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("journal timestamp lacks timezone")
    return result.astimezone(timezone.utc)


@dataclass
class Journal:
    user_id: str
    session_id: str
    store: InMemoryClarificationStore = field(default_factory=InMemoryClarificationStore)
    # Round and binding provenance are distinct because a confirmed click can
    # outlive its displayed round. No serialized source is an authority by itself.
    sources: dict[str, tuple[EvidenceCandidate, ...]] = field(default_factory=dict)
    impacts: dict[str, str] = field(default_factory=dict)
    guards: dict[str, ClarificationSafeguards] = field(default_factory=dict)
    origins: dict[str, str] = field(default_factory=dict)
    binding_expires: dict[str, str] = field(default_factory=dict)


class ClarificationJournal:
    def __init__(self, *, root: str = DEFAULT_USER_STATE_ROOT) -> None:
        self.root = root

    def path(self, user_id: str, session_id: str) -> Path:
        if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
            raise ValueError("invalid session ID")
        name = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
        return Path(user_scoped_path(user_id, f"reference_clarification/{name}", root=self.root))

    @contextmanager
    def transaction(self, user_id: str, session_id: str):
        path = self.path(user_id, session_id)
        with _locks_guard:
            lock = _locks.setdefault(str(path), threading.RLock())
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = path.with_suffix(".lock")
            with open(lock_path, "a+b") as lock_file:
                # This lock spans service instances and processes, including reload.
                lock_file.seek(0)
                if os.name == "nt":
                    import msvcrt
                    if lock_file.seek(0, 2) == 0:
                        lock_file.write(b"\0")
                        lock_file.flush()
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    journal = self._load(path, user_id, session_id)
                    yield journal
                    self._save(path, journal)
                finally:
                    if os.name == "nt":
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load(self, path: Path, user_id: str, session_id: str) -> Journal:
        journal = Journal(user_id, session_id)
        if not path.exists():
            return journal
        try:
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("journal size exceeded")
            raw = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(raw, dict) or set(raw) != {"schema", "user_id", "session_id", "rounds", "bindings", "binding_queries", "sources", "impacts", "guards", "origins", "binding_expires"}
                    or raw["schema"] != SCHEMA_VERSION or raw["user_id"] != user_id or raw["session_id"] != session_id):
                raise ValueError("journal schema or scope mismatch")
            for key in ("rounds", "bindings", "binding_queries", "sources", "impacts", "guards", "origins", "binding_expires"):
                if not isinstance(raw[key], dict) or len(raw[key]) > MAX_RECORDS:
                    raise ValueError("journal collection invalid")
            for key, item in raw["rounds"].items():
                if not isinstance(key, str) or set(item) != {"contract", "query", "state", "used"}:
                    raise ValueError("round shape invalid")
                contract = _decode(ClarificationContract, item["contract"])
                query = _decode(RARQuery, item["query"])
                validate_contract(contract, query)
                if key != contract.ambiguity_id or contract.session_id != session_id or type(item["used"]) is not bool:
                    raise ValueError("round identity invalid")
                journal.store.rounds[key] = StoredRound(contract, query, _decode(BindingState, item["state"]), item["used"])
            for key, item in raw["bindings"].items():
                binding = _decode(BindingRecord, item)
                if key != binding.ambiguity_id or binding.session_id != session_id:
                    raise ValueError("binding identity invalid")
                journal.store.bindings[key] = binding
            journal.store.binding_queries = {key: _decode(RARQuery, item) for key, item in raw["binding_queries"].items()}
            if any(not isinstance(items, list) or len(items) > MAX_RECORDS for items in raw["sources"].values()):
                raise ValueError("source collection invalid")
            journal.sources = {key: tuple(_decode(EvidenceCandidate, item) for item in items) for key, items in raw["sources"].items()}
            journal.impacts = {key: _decode(str, item) for key, item in raw["impacts"].items()}
            journal.guards = {key: _decode(ClarificationSafeguards, item) for key, item in raw["guards"].items()}
            journal.origins = {key: _decode(str, item) for key, item in raw["origins"].items()}
            journal.binding_expires = {key: _decode(str, item) for key, item in raw["binding_expires"].items()}
            if (set(journal.store.bindings) != set(journal.store.binding_queries)
                    or set(journal.store.bindings) != set(journal.binding_expires)
                    or not set(journal.sources) <= set(journal.store.rounds) | set(journal.store.bindings)
                    or any(item.user_id != user_id for items in journal.sources.values() for item in items)):
                raise ValueError("journal references invalid")
            self._prune(journal)
            return journal
        except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError):
            os.replace(path, path.with_name(path.name + f".corrupt.{uuid4().hex}"))
            return Journal(user_id, session_id)

    @staticmethod
    def _prune(journal: Journal) -> None:
        now = datetime.now(timezone.utc)
        expired = {key for key, record in journal.store.rounds.items() if _stamp(record.contract.expires_at) <= now}
        for key in expired:
            journal.store.rounds.pop(key, None)
            journal.sources.pop(key, None)
            journal.impacts.pop(key, None)
        for key, expires_at in tuple(journal.binding_expires.items()):
            if _stamp(expires_at) <= now:
                journal.store.bindings.pop(key, None)
                journal.store.binding_queries.pop(key, None)
                journal.sources.pop(key, None)
                journal.impacts.pop(key, None)
                journal.origins.pop(key, None)
                journal.binding_expires.pop(key, None)

    def _save(self, path: Path, journal: Journal) -> None:
        if len(journal.store.rounds) > MAX_RECORDS or len(journal.store.bindings) > MAX_RECORDS:
            raise ValueError("journal record budget exceeded")
        raw = {
            "schema": SCHEMA_VERSION, "user_id": journal.user_id, "session_id": journal.session_id,
            "rounds": {key: {"contract": asdict(item.contract), "query": asdict(item.query), "state": item.state.value, "used": item.used} for key, item in journal.store.rounds.items()},
            "bindings": {key: asdict(item) for key, item in journal.store.bindings.items()},
            "binding_queries": {key: asdict(item) for key, item in journal.store.binding_queries.items()},
            "sources": {key: [asdict(item) for item in items] for key, items in journal.sources.items()},
            "impacts": journal.impacts, "guards": {key: asdict(item) for key, item in journal.guards.items()},
            "origins": journal.origins, "binding_expires": journal.binding_expires,
        }
        data = json.dumps(raw, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(data) > MAX_BYTES:
            raise ValueError("journal size exceeded")
        fd, temporary = tempfile.mkstemp(prefix=".journal-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
