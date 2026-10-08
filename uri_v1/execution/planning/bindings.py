"""Explicit runtime bindings and opaque handle table (Stage 2, Slice 1).

Enforces runtime-owned opaque handles, strict source binding through SourceRegistry
with zero path fallback, zero fuzzy sheet matching, and zero empty-table defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from uri_v1.execution.officefile import WorkbookStructure
from uri_v1.execution.workspace import WorkspaceInput
from uri_v1.memory.sources import SourceRegistry
from .contracts import CompiledPlan, PortType, SourceRef


class BindingError(ValueError):
    """Typed failure during source binding or handle resolution."""
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Handle:
    """Opaque runtime-issued token scoped to user, task, run, node and port."""
    user_id: str
    task_id: str
    run_id: str
    node_id: str
    port: str
    value_sha256: str
    port_type: PortType


def _value_digest(value: Any) -> str:
    """Compute deterministic SHA-256 digest of an intermediate node value."""
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, WorkbookStructure):
        canonical_bytes = json.dumps(value.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()
    if isinstance(value, (dict, list, tuple)):
        canonical_bytes = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _validate_port_value(value: Any, port_type: PortType) -> None:
    """Validate that node output satisfies the declared PortType schema."""
    if port_type == PortType.WORKBOOK_STRUCTURE:
        if not isinstance(value, WorkbookStructure) and not (isinstance(value, dict) and "sheets" in value):
            raise BindingError("INVALID_NODE_OUTPUT", "Expected WorkbookStructure or dict with 'sheets'")
    elif port_type == PortType.STRUCTURE_SELECTION:
        if not isinstance(value, dict) or "sheets" not in value:
            raise BindingError("INVALID_NODE_OUTPUT", "Expected dict with 'sheets' list for STRUCTURE_SELECTION")
        for s in value["sheets"]:
            if not isinstance(s, dict) or "name" not in s or "headers" not in s:
                raise BindingError("INVALID_NODE_OUTPUT", "Each sheet in STRUCTURE_SELECTION must have 'name' and 'headers'")
    elif port_type == PortType.STRUCTURE_COMPARISON:
        if not isinstance(value, dict) or "match_on" not in value or "sheets" not in value:
            raise BindingError("INVALID_NODE_OUTPUT", "Expected dict with 'match_on' and 'sheets' for STRUCTURE_COMPARISON")
    elif port_type == PortType.REPORT_ARTIFACT:
        if not isinstance(value, dict) or value.get("schema_version") != "uri.plan.report.v1":
            raise BindingError("INVALID_NODE_OUTPUT", "Expected report dict with schema_version uri.plan.report.v1")
    elif port_type == PortType.SOURCE_XLSX:
        pass


class HandleTable:
    """Per-run isolated table of runtime-issued handles.

    Models and proposals never see or create handles. Handles are issued only
    after schema-valid execution. Unissued or failed-node handles raise UNBOUND_INPUT.
    """
    def __init__(self, user_id: str, task_id: str, run_id: str):
        self.user_id = user_id
        self.task_id = task_id
        self.run_id = run_id
        self._entries: dict[tuple[str, str], tuple[Handle, Any]] = {}

    def issue(self, node_id: str, port: str, value: Any, port_type: PortType) -> Handle:
        """Issue an opaque handle after validating value against port_type."""
        _validate_port_value(value, port_type)
        val_sha = _value_digest(value)
        handle = Handle(
            user_id=self.user_id,
            task_id=self.task_id,
            run_id=self.run_id,
            node_id=node_id,
            port=port,
            value_sha256=val_sha,
            port_type=port_type,
        )
        self._entries[(node_id, port)] = (handle, value)
        return handle

    def get(self, node_id: str, port: str) -> Any:
        """Retrieve value for an issued handle. Fails with UNBOUND_INPUT if not found."""
        key = (node_id, port)
        if key not in self._entries:
            raise BindingError("UNBOUND_INPUT", f"Port '{node_id}.{port}' has not been issued a handle")
        return self._entries[key][1]

    def get_handle(self, node_id: str, port: str) -> Handle:
        key = (node_id, port)
        if key not in self._entries:
            raise BindingError("UNBOUND_INPUT", f"Port '{node_id}.{port}' has not been issued a handle")
        return self._entries[key][0]

    def validate_handle(self, handle: Handle) -> bool:
        """Check that handle matches table scope and exists with matching digest."""
        if (
            handle.user_id != self.user_id
            or handle.task_id != self.task_id
            or handle.run_id != self.run_id
        ):
            return False
        key = (handle.node_id, handle.port)
        if key not in self._entries:
            return False
        stored_handle, _ = self._entries[key]
        return stored_handle.value_sha256 == handle.value_sha256 and stored_handle.port_type == handle.port_type


def bind_sources(
    plan: CompiledPlan,
    sources: SourceRegistry,
    candidates: Sequence[str] | Mapping[str, str] | None = None,
) -> tuple[WorkspaceInput, ...]:
    """Resolve and bind required sources from CompiledPlan to hash-verified WorkspaceInputs.

    Disallows filesystem paths, fuzzy matches, and latest-file fallbacks.
    """
    candidate_map: dict[str, str] = {}
    if candidates is not None:
        if isinstance(candidates, Mapping):
            candidate_map = dict(candidates)
        else:
            candidate_map = {str(c): "" for c in candidates}

    # Collect unique source IDs from plan
    needed_sources: set[str] = set()
    for node in plan.nodes:
        for binding in node.inputs.values():
            if isinstance(binding, SourceRef):
                needed_sources.add(binding.source_id)

    if not needed_sources:
        return ()

    scan = sources.scan()
    if not scan.complete and scan.reason:
        raise BindingError("SOURCE_SCAN_INCOMPLETE", scan.reason)

    inputs: list[WorkspaceInput] = []
    seen_roles: set[str] = set()

    for sid in sorted(needed_sources):
        if candidates is not None and sid not in candidate_map:
            raise BindingError("UNKNOWN_SOURCE", f"Source ID '{sid}' not in authorized candidates")

        locator = sources.locate(sid, scan)
        if locator is None:
            raise BindingError("UNKNOWN_SOURCE", f"Source ID '{sid}' could not be located in registry")

        ref = sources.fingerprint(locator)
        if ref is None or ref.content_sha256 is None:
            raise BindingError("INPUT_NOT_CURRENT", f"Source ID '{sid}' fingerprint unavailable or unverified")

        expected_sha = candidate_map.get(sid, "")
        if expected_sha and ref.content_sha256 != expected_sha:
            raise BindingError("INPUT_NOT_CURRENT", f"Source ID '{sid}' hash {ref.content_sha256} does not match expected {expected_sha}")

        role = f"src_{sid[:8]}"
        if role in seen_roles:
            role = f"src_{sid[:12]}"
        seen_roles.add(role)

        inputs.append(WorkspaceInput(
            role=role,
            source_id=sid,
            content_sha256=ref.content_sha256,
        ))

    return tuple(inputs)
