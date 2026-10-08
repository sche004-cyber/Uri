"""C2 exact request-scoped read ports and deferred client mutations."""
from copy import deepcopy
import ast
import json
from pathlib import Path

from uri_core.client_contracts import Binding, ClientMutationSet, Mutation, ReadQuery, digest


class StatePortError(ValueError):
    pass


class NeedsContext(StatePortError):
    def __init__(self, query):
        super().__init__("NEEDS_CONTEXT")
        self.query = query


def method_contract():
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "docs/architecture/C2_STORE_METHOD_CONTRACT.json").read_text(encoding="utf-8"))


class ClientStatePorts:
    def __init__(self, snapshot, binding):
        self.contract = method_contract()
        self.binding = Binding.model_validate(binding)
        self._check_binding(snapshot)
        self.reads = {}
        self.mutations = []
        for read in snapshot.reads:
            self.check_query(read.query, "reads")
            self.reads[read.query.key()] = deepcopy(read)

    def _check_binding(self, snapshot):
        for name in ("server_id", "client_id", "principal_id", "session_id"):
            if getattr(snapshot, name) != getattr(self.binding, name):
                raise StatePortError("CONTEXT_SCOPE")

    def check_query(self, query, disposition):
        entry = self.contract.get(query.store)
        if entry is None or query.method not in entry[disposition]:
            raise StatePortError("METHOD_NOT_ALLOWED")
        # Legacy methods with session/user arguments remain scoped; no IDs
        # inside a model/private snapshot can choose another owner.
        signature = ast.parse("def method(" + entry["methods"][query.method] + "):\n pass").body[0].args
        positional = [a.arg for a in signature.posonlyargs + signature.args]
        if positional and positional[0] in {"self", "cls"}: positional = positional[1:]
        values = dict(zip(positional, query.args))
        if set(values) & set(query.kwargs):
            raise StatePortError("DUPLICATE_ARGUMENT")
        values.update(query.kwargs)
        if "user_id" in values and values["user_id"] != self.binding.principal_id:
            raise StatePortError("PRINCIPAL_SCOPE")
        if "session_id" in values and values["session_id"] != self.binding.session_id:
            raise StatePortError("SESSION_SCOPE")
        if query.store in {"sessions", "history", "files"}:
            if query.method in {"get_session", "save_session", "reset_session", "append_turn",
                                "annotate_latest_turn", "delete_session", "list_for_session"}:
                scope = values.get("session_id")
                if scope != self.binding.session_id:
                    raise StatePortError("SESSION_SCOPE")
            if query.method == "list_sessions":
                # Cross-session history is an explicit later facade, not a
                # task-scoped context projection.
                raise StatePortError("SESSION_SCOPE")

    def read(self, store, method, *args, **kwargs):
        query = ReadQuery(store=store, method=method, args=list(args), kwargs=kwargs)
        self.check_query(query, "reads")
        projection = self.reads.get(query.key())
        if projection is None:
            raise NeedsContext(query)
        return deepcopy(projection.result)

    def propose(self, store, method, *, args=(), kwargs=None, base_version, previous_digest, replacement=None):
        query = ReadQuery(store=store, method=method, args=list(args), kwargs=kwargs or {})
        self.check_query(query, "writes")
        known = [r for r in self.reads.values() if r.query.store == store]
        if not known or any(r.store_version != base_version for r in known):
            raise StatePortError("BASE_VERSION_REQUIRED")
        if previous_digest != digest(sorted([r.model_dump() for r in known], key=lambda r: digest(r["query"]))):
            raise StatePortError("PREVIOUS_PROJECTION_DIGEST")
        if replacement is not None:
            from dataclasses import fields
            from uri_core.core.state import SessionState
            if replacement.get("session_id") != self.binding.session_id or set(replacement) - {f.name for f in fields(SessionState)}:
                raise StatePortError("SESSION_REPLACEMENT_SCOPE")
        payload = query.model_dump() if replacement is None else {"query": query.model_dump(), "replacement": replacement}
        mutation = Mutation(query=query, base_version=base_version, previous_digest=previous_digest,
                            payload_digest=digest(payload), replacement=replacement)
        self.mutations.append(mutation)
        return mutation

    def mutation_set(self, operation_id, idempotency_key):
        return ClientMutationSet(**self.binding.model_dump(), operation_id=operation_id,
                                 idempotency_key=idempotency_key, mutations=list(self.mutations))
