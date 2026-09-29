"""Explicit source bindings and runtime-issued handles (Stage 2 §2.4, F10-F12).

Sources are bound only by trusted candidate id and content hash; there is no
path, fuzzy, first-match or "latest file" binding. Handles are opaque runtime
tokens issued only after a node's value validates against its declared output
type. Proposals never see or create them; a consumer of an unissued handle
fails with UNBOUND_INPUT, never an empty default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re

from uri_v1.execution.workspace import WorkspaceInput
from uri_v1.memory.contracts import IdentityStatus
from .contracts import REPORT_NAME, CompiledPlan, PortType, SourceCandidate, canonical

_SOURCE_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class BindingError(ValueError):
    """Typed failure; the reason code is the message."""


def candidates_from_registry(sources) -> tuple:
    """Trusted candidates: every source the registry can locate and hash right now."""
    scan = sources.scan()
    out = []
    for locator in scan.locators:
        ref = sources.fingerprint(locator)
        if ref is None or ref.identity_status != IdentityStatus.HASH_VERIFIED or ref.content_sha256 is None: continue
        out.append(SourceCandidate(ref.source_id, ref.relpath, ref.media_type, ref.content_sha256))
    return tuple(out)


def bind_sources(plan: CompiledPlan, sources, candidates) -> tuple:
    """One WorkspaceInput per distinct plan source, only for trusted, still-current candidates."""
    if not isinstance(plan, CompiledPlan): raise BindingError("PLAN_REQUIRED")
    by_id = {c.source_id: c for c in candidates}
    inputs = []
    for source_id, sha in plan.sources:
        candidate = by_id.get(source_id)
        if candidate is None: raise BindingError("UNKNOWN_SOURCE")
        if candidate.content_sha256 != sha: raise BindingError("SOURCE_HASH_MISMATCH")
        if not sources.verify_source(source_id, sha): raise BindingError("INPUT_NOT_CURRENT")
        inputs.append(WorkspaceInput("source", source_id, sha))
    return tuple(inputs)


# -- value validation per port type ------------------------------------------------

def _names(value, allow_none=False) -> bool:
    return isinstance(value, list) and all((allow_none and v is None) or (isinstance(v, str) and v) for v in value)


def _sheet_list(value, keys) -> bool:
    return isinstance(value, list) and all(isinstance(s, dict) and set(s) == keys and isinstance(s["name"], str) for s in value)


def valid_value(value, port_type: PortType) -> bool:
    if not isinstance(value, dict): return False
    if port_type is PortType.WORKBOOK_STRUCTURE:
        return (set(value) == {"source_id", "sheets"} and _SOURCE_ID.fullmatch(str(value["source_id"])) is not None
                and _sheet_list(value["sheets"], {"name", "header", "error_cells"})
                and all(_names(s["header"], True) and type(s["error_cells"]) is int for s in value["sheets"]))
    if port_type is PortType.STRUCTURE_SELECTION:
        return (set(value) == {"source_id", "sheets"} and _SOURCE_ID.fullmatch(str(value["source_id"])) is not None
                and bool(value["sheets"]) and _sheet_list(value["sheets"], {"name", "header"})
                and all(_names(s["header"], True) for s in value["sheets"]))
    if port_type is PortType.STRUCTURE_COMPARISON:
        keys = {"match_on", "left_source_id", "right_source_id", "shared_sheets", "only_left_sheets", "only_right_sheets"}
        return (set(value) == keys and value["match_on"] == "sheet_name"
                and _sheet_list(value["shared_sheets"], {"name", "shared", "only_left", "only_right"})
                and all(_names(s[k]) for s in value["shared_sheets"] for k in ("shared", "only_left", "only_right"))
                and _names(value["only_left_sheets"]) and _names(value["only_right_sheets"]))
    if port_type is PortType.REPORT_ARTIFACT:
        return set(value) == {"relpath", "sha256"} and value["relpath"] == REPORT_NAME and _SHA.fullmatch(str(value["sha256"])) is not None
    return False


# -- handles ---------------------------------------------------------------------------

_ISSUED = object()


@dataclass(frozen=True)
class Handle:
    user_id: str
    task_id: str
    run_id: str
    node_id: str
    port: str
    value_sha256: str
    _issued: object = field(default=None, init=False, compare=False, repr=False)

    def __reduce__(self): raise TypeError("handles cannot be serialized")


class HandleTable:
    """Per-run handle table owned by the runner. No default, no latest, no fallback."""

    def __init__(self, *, user_id, task_id, run_id):
        self.user_id, self.task_id, self.run_id = user_id, task_id, run_id
        self._values = {}

    def issue(self, node_id, port, value, port_type: PortType) -> Handle:
        if (node_id, port) in self._values: raise BindingError("HANDLE_ALREADY_ISSUED")
        if not valid_value(value, port_type): raise BindingError("OUTPUT_TYPE_INVALID")
        data = canonical(value)
        handle = Handle(self.user_id, self.task_id, self.run_id, node_id, port, hashlib.sha256(data).hexdigest())
        object.__setattr__(handle, "_issued", _ISSUED)
        self._values[(node_id, port)] = (handle, data)
        return handle

    def get(self, node_id, port):
        entry = self._values.get((node_id, port))
        if entry is None: raise BindingError("UNBOUND_INPUT")
        return json.loads(entry[1])

    def resolve(self, handle):
        if not isinstance(handle, Handle) or handle._issued is not _ISSUED: raise BindingError("HANDLE_FABRICATED")
        if (handle.user_id, handle.task_id, handle.run_id) != (self.user_id, self.task_id, self.run_id):
            raise BindingError("HANDLE_FOREIGN")
        entry = self._values.get((handle.node_id, handle.port))
        if entry is None or entry[0] is not handle: raise BindingError("UNBOUND_INPUT")
        return json.loads(entry[1])
