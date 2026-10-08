"""C3 reuse of private stores with one-writer CAS and recoverable journal."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from contextlib import contextmanager
import inspect
import json
from pathlib import Path
import shutil
import sqlite3
import uuid

from uri_core.client_contracts import Binding, ClientMutationSet, ClientStateSnapshot, ReadProjection, ReadQuery, digest, public_projection
from uri_core.core.client_state_ports import ClientStatePorts, StatePortError, method_contract
from scripts.uri_server_launcher import NamedMutex


class PersistenceError(ValueError):
    pass


def projection(value):
    if hasattr(value, "to_reference"):
        value = value.to_reference()
    elif is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {k: projection(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [projection(v) for v in value]
    return value


class ClientPersistence:
    def __init__(self, manifest):
        self.manifest = manifest
        self.m = manifest.data
        self.root = Path(self.m["client_root"])
        self.private = self.root / "private"
        self.journal = self.root / "control/journal"
        self.journal.mkdir(exist_ok=True)
        self.database = self.root / "control/state-journal.sqlite3"
        self.contract = method_contract()
        with self._db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS versions(store TEXT PRIMARY KEY, version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS views(session TEXT, store TEXT, version INTEGER, digest TEXT, reads TEXT,
                    PRIMARY KEY(session,store,version,digest));
                CREATE TABLE IF NOT EXISTS transactions(operation TEXT PRIMARY KEY, digest TEXT NOT NULL,
                    state TEXT NOT NULL, backup TEXT NOT NULL, receipt TEXT);
                CREATE TABLE IF NOT EXISTS consents(digest TEXT PRIMARY KEY);""")
        with self.writer():
            self._recover()
            self._construct_stores()

    def writer(self):
        return NamedMutex("Local\\URI_Client_Writer_" + self.m["client_id"], 10)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.database)
        db.execute("PRAGMA synchronous=FULL")
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _construct_stores(self):
        self._check_private_tree()
        # Imports and constructors stay exclusively in this client package.
        from uri_core.core.user_profile import UserProfileStore
        from uri_core.core.user_memory import MemoryStore
        from uri_core.core.memory_settings import MemorySettingsStore
        from uri_core.core.growth_ledger import GrowthLedgerStore
        from uri_core.core.approval_store import ApprovalStore
        from uri_core.core.state import SessionManager
        from uri_core.core.experience_store import ExperienceStore
        from uri_core.core.skill_memory import SkillMemory
        from uri_core.core.conversation_history import ConversationHistoryStore
        from uri_core.core.file_store import FileStore
        from uri_core.core.graph_store import GraphStore
        from uri_core.core.evidence_fact_integrity import FileEvidenceStore
        from uri_core.external.operation_store import FileOperationStore
        from uri_core.external.store import ExternalCapabilityStore
        from uri_core.external.service_store import ConnectedServiceStore
        from uri_core.external.credentials import ExternalCredentialStore
        path = lambda name: str(self.private / name)
        user = self.m["principal_id"]
        # A client-owned key is restored by the worker before this constructor.
        import os
        from uri_core.core.runtime_identity import dpapi
        secret = dpapi((self.root / "secure/credential-store-key.dpapi").read_bytes(), True).hex()
        previous = os.environ.get("URI_EXTERNAL_CREDENTIAL_SECRET")
        os.environ["URI_EXTERNAL_CREDENTIAL_SECRET"] = secret
        try:
            credential_store = ExternalCredentialStore(root=path("users"))
        finally:
            if previous is None: os.environ.pop("URI_EXTERNAL_CREDENTIAL_SECRET", None)
            else: os.environ["URI_EXTERNAL_CREDENTIAL_SECRET"] = previous
        self.stores = {
            "profile": UserProfileStore(path("profile.json")), "memory": MemoryStore(path("memory.json")),
            "memory_settings": MemorySettingsStore(path("memory-settings.json")), "growth": GrowthLedgerStore(path("growth.json")),
            "approvals": ApprovalStore(path("approvals.json")), "sessions": SessionManager(path("sessions")),
            "experience": ExperienceStore(path("experience.json")), "skills": SkillMemory(path("skills.json")),
            "history": ConversationHistoryStore(path("history")), "files": FileStore(path("files")),
            "graph": GraphStore(path("graph.sqlite3")), "evidence": FileEvidenceStore(user_id=user, root=path("users")),
            "operations": FileOperationStore(user_id=user, root=path("users")),
            "external_capabilities": ExternalCapabilityStore(root=path("users")),
            "connections": ConnectedServiceStore(root=path("users"), credential_store=credential_store),
            "credentials": credential_store,
        }
        # Initialization is client-owned. Subsequent remote profile projections
        # read _load only and cannot trigger creation at the server's request.
        self.stores["profile"].load_or_create()

    def _check_private_tree(self):
        if self.private.resolve() != self.root / "private":
            raise PersistenceError("PRIVATE_CONTAINMENT")
        for path in self.private.rglob("*"):
            if not path.resolve().is_relative_to(self.private):
                raise PersistenceError("PRIVATE_CONTAINMENT")

    def _binding(self, session):
        return Binding(server_id=self.m["server_id"], client_id=self.m["client_id"],
                       principal_id=self.m["principal_id"], session_id=session)

    def _version(self, db, store):
        row = db.execute("SELECT version FROM versions WHERE store=?", (store,)).fetchone()
        return row[0] if row else 0

    def _read(self, query, scope):
        ClientStatePorts(ClientStateSnapshot(**scope.model_dump()), scope.model_dump()).check_query(query, "reads")
        if query.store == "files" and query.method in {"get", "references_for"}:
            ids = (query.args or [query.kwargs["file_id"]]) if query.method == "get" else (query.args[0] if query.args else query.kwargs.get("file_ids", []))
            for file_id in ids:
                item = self.stores["files"].get(file_id)
                if item is not None and item.session_id != scope.session_id:
                    raise PersistenceError("FILE_SESSION_SCOPE")
        method = getattr(self.stores[query.store], query.method)
        inspect.signature(method).bind(*query.args, **query.kwargs)
        if query.store == "profile" and query.method == "load_or_create":
            result = self.stores["profile"]._load()
            if result is None:
                raise PersistenceError("PROFILE_UNAVAILABLE")
        else:
            result = method(*query.args, **query.kwargs)
        if query.store == "approvals":
            if query.method == "list_pending":
                result = [item for item in result if item.session_id == scope.session_id]
            elif result is not None and result.session_id != scope.session_id:
                raise PersistenceError("APPROVAL_SESSION_SCOPE")
        if query.store == "sessions":
            result = self.stores["sessions"]._serialize_session(result)
        value = projection(result)
        public_projection(value)
        return value

    def snapshot(self, session_id, queries):
        scope = self._binding(session_id)
        with self.writer(), self._db() as db:
            # Drop store caches before reads so another owned writer's commits
            # and external file edits cannot be masked by stale objects.
            self._construct_stores()
            reads = [ReadProjection(query=q, result=(result := self._read(q, scope)),
                                    store_version=self._version(db, q.store), result_digest=digest(result)) for q in queries]
            snapshot = ClientStateSnapshot(**scope.model_dump(), reads=reads)
            for store in {q.store for q in queries}:
                subset = sorted([r.model_dump() for r in reads if r.query.store == store], key=lambda r: digest(r["query"]))
                db.execute("INSERT OR REPLACE INTO views VALUES(?,?,?,?,?)", (
                    session_id, store, self._version(db, store), digest(subset), json.dumps(subset)))
            return snapshot

    def consent(self, mutation_set):
        """Trusted local UI command only; never exposed by the server API."""
        self._validate_set(mutation_set)
        with self.writer(), self._db() as db:
            db.execute("INSERT OR IGNORE INTO consents VALUES(?)", (digest(mutation_set.model_dump()),))

    def _validate_set(self, value):
        expected = self._binding(value.session_id)
        for field in ("server_id", "client_id", "principal_id"):
            if getattr(value, field) != getattr(expected, field):
                raise PersistenceError("MUTATION_SCOPE")
        ports = ClientStatePorts(ClientStateSnapshot(**expected.model_dump()), expected.model_dump())
        for mutation in value.mutations:
            ports.check_query(mutation.query, "writes")

    def _backup(self, operation):
        self._check_private_tree()
        backup = self.journal / operation
        if backup.exists() or backup.resolve() != backup:
            raise PersistenceError("BACKUP_CONFLICT")
        # Single writer owns all SQLite connections and closes every method
        # before this copy. There is no external execution in a state commit.
        shutil.copytree(self.private, backup)
        for path in backup.rglob("*"):
            if path.is_file():
                with path.open("rb+") as handle:
                    import os
                    os.fsync(handle.fileno())
        from uri_core.core.runtime_identity import atomic_json, sha
        atomic_json(self.journal / (operation + "-hashes.json"), {
            p.relative_to(backup).as_posix(): sha(p) for p in backup.rglob("*") if p.is_file()})
        return backup

    def _restore(self, backup):
        backup = Path(backup).resolve()
        private = self.private.resolve()
        if not backup.is_relative_to(self.journal.resolve()) or private != self.root / "private":
            raise PersistenceError("RESTORE_CONTAINMENT")
        from uri_core.core.runtime_identity import sha
        hashes = json.loads((self.journal / (backup.name + "-hashes.json")).read_text())
        actual = {p.relative_to(backup).as_posix(): sha(p) for p in backup.rglob("*") if p.is_file()}
        if actual != hashes:
            raise PersistenceError("RESTORE_HASH_MISMATCH")
        for path in private.rglob("*"):
            if path.is_file():
                if not path.resolve().is_relative_to(private):
                    raise PersistenceError("RESTORE_CONTAINMENT")
                if not (backup / path.relative_to(private)).exists():
                    path.unlink()  # only newly-created synthetic client files
        for path in backup.rglob("*"):
            if path.is_file():
                if not path.resolve().is_relative_to(backup):
                    raise PersistenceError("RESTORE_CONTAINMENT")
                target = private / path.relative_to(backup)
                if not target.resolve().is_relative_to(private):
                    raise PersistenceError("RESTORE_CONTAINMENT")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)

    def _recover(self):
        with self._db() as db:
            for row in db.execute("SELECT operation,backup FROM transactions WHERE state='PREPARED'").fetchall():
                self._restore(row["backup"])
                db.execute("UPDATE transactions SET state='ROLLED_BACK' WHERE operation=?", (row["operation"],))

    def _invoke_mutation(self, query, scope, replacement=None):
        args, kwargs = list(query.args), dict(query.kwargs)
        # Reconstruct only existing validated DTOs for their exact methods.
        if query.store == "profile" and query.method == "save":
            from uri_core.core.user_profile import UserProfile
            if args: args[0] = UserProfile(**args[0])
            elif "profile" in kwargs: kwargs["profile"] = UserProfile(**kwargs["profile"])
        if query.store == "evidence" and query.method == "add":
            from uri_core.core.evidence_fact_integrity import EvidenceRecord
            if args: args[0] = EvidenceRecord(**args[0])
            elif "record" in kwargs: kwargs["record"] = EvidenceRecord(**kwargs["record"])
        if query.store == "operations" and query.method == "create":
            from uri_core.external.operation_store import OperationRecord
            if args: args[0] = OperationRecord(**args[0])
            elif "record" in kwargs: kwargs["record"] = OperationRecord(**kwargs["record"])
        if query.store == "sessions" and query.method == "save_session" and replacement is not None:
            from dataclasses import fields
            from uri_core.core.state import SessionState
            if replacement.get("session_id") != scope.session_id or set(replacement) - {f.name for f in fields(SessionState)}:
                raise PersistenceError("SESSION_REPLACEMENT_SCOPE")
            manager = self.stores["sessions"]
            # Reuse the original fact codecs; no arbitrary class deserialization.
            values = dict(replacement)
            for name in ("current_facts", "evidence_facts", "historical_facts"):
                values[name] = manager._deserialize_fact_collection(values.get(name, {}))
            values["fact_history"] = manager._deserialize_fact_history(values.get("fact_history", {}))
            manager.sessions[scope.session_id] = SessionState(**values)
        if query.store == "files":
            if query.method == "save":
                import base64, hashlib
                encoded = kwargs.get("content")
                if not isinstance(encoded, dict) or set(encoded) != {"encoding", "data", "sha256"} or encoded["encoding"] != "base64":
                    raise PersistenceError("FILE_BYTES_REQUIRED")
                content = base64.b64decode(encoded["data"], validate=True)
                if len(content) > 16 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != encoded["sha256"]:
                    raise PersistenceError("FILE_BYTES_INVALID")
                if kwargs.get("session_id") != scope.session_id:
                    raise PersistenceError("FILE_SESSION_SCOPE")
                kwargs["content"] = content
            elif query.method == "delete":
                file_id = args[0] if args else kwargs["file_id"]
                stored = self.stores["files"].get(file_id)
                if stored is not None and stored.session_id != scope.session_id:
                    raise PersistenceError("FILE_SESSION_SCOPE")
        if query.store == "approvals" and query.method in {"decide", "consume"}:
            action = self.stores["approvals"].get(args[0] if args else kwargs["action_id"])
            if action is not None and action.session_id != scope.session_id:
                raise PersistenceError("APPROVAL_SESSION_SCOPE")
        if query.store == "connections" and query.method == "register_service":
            from uri_core.external.service_contract import ConnectedServiceDescriptor
            if args: args[0] = ConnectedServiceDescriptor(**args[0])
            elif "descriptor" in kwargs: kwargs["descriptor"] = ConnectedServiceDescriptor(**kwargs["descriptor"])
        method = getattr(self.stores[query.store], query.method)
        inspect.signature(method).bind(*args, **kwargs)
        result = method(*args, **kwargs)
        if result is False:
            raise PersistenceError("STORE_MUTATION_REFUSED")
        return projection(result)

    def commit(self, value, fault=None):
        self._validate_set(value)
        operation, payload = value.operation_id, digest(value.model_dump())
        with self.writer():
            self._recover()
            self._construct_stores()
            with self._db() as db:
                prior = db.execute("SELECT * FROM transactions WHERE operation=?", (operation,)).fetchone()
                if prior:
                    if prior["digest"] != payload:
                        raise PersistenceError("IDEMPOTENCY_CONFLICT")
                    if prior["state"] == "COMMITTED":
                        return json.loads(prior["receipt"])
                    raise PersistenceError("OPERATION_ROLLED_BACK")
                if not db.execute("SELECT 1 FROM consents WHERE digest=?", (payload,)).fetchone():
                    raise PersistenceError("CONSENT_REQUIRED")
                for mutation in value.mutations:
                    store = mutation.query.store
                    if self._version(db, store) != mutation.base_version:
                        raise PersistenceError("VERSION_CONFLICT")
                    view = db.execute("SELECT reads FROM views WHERE session=? AND store=? AND version=? AND digest=?",
                        (value.session_id, store, mutation.base_version, mutation.previous_digest)).fetchone()
                    if view is None:
                        raise PersistenceError("PROJECTION_REQUIRED")
                    fresh = []
                    for raw in json.loads(view[0]):
                        query = ReadQuery.model_validate(raw["query"])
                        result = self._read(query, self._binding(value.session_id))
                        fresh.append(ReadProjection(query=query, result=result, store_version=mutation.base_version,
                                                    result_digest=digest(result)).model_dump())
                    if digest(sorted(fresh, key=lambda r: digest(r["query"]))) != mutation.previous_digest:
                        raise PersistenceError("SOURCE_CHANGED")
                backup = self._backup(operation)
                db.execute("INSERT INTO transactions VALUES(?,?,?,?,NULL)", (operation, payload, "PREPARED", str(backup)))
            try:
                results = []
                for index, mutation in enumerate(value.mutations):
                    results.append(self._invoke_mutation(mutation.query, self._binding(value.session_id), mutation.replacement))
                    if fault: fault(index)
                self._check_private_tree()
                for path in self.private.rglob("*"):
                    if path.is_file():
                        with path.open("rb+") as handle:
                            import os
                            handle.flush()
                            os.fsync(handle.fileno())
                with self._db() as db:
                    versions = {}
                    for store in {m.query.store for m in value.mutations}:
                        versions[store] = self._version(db, store) + 1
                        db.execute("INSERT OR REPLACE INTO versions VALUES(?,?)", (store, versions[store]))
                    receipt = {"schema_version": "uri.client.v1", "client_id": self.m["client_id"],
                        "server_id": self.m["server_id"], "operation_id": operation, "mutation_digest": payload,
                        "outcome": "COMMITTED", "versions": versions, "results": results}
                    db.execute("UPDATE transactions SET state='COMMITTED',receipt=? WHERE operation=?",
                               (json.dumps(receipt), operation))
                return receipt
            except Exception:
                self._restore(backup)
                with self._db() as db:
                    db.execute("UPDATE transactions SET state='ROLLED_BACK' WHERE operation=?", (operation,))
                self._construct_stores()
                raise PersistenceError("COMMIT_ROLLED_BACK") from None
