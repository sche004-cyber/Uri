"""Closed Edge-minimum contracts (M37, PROVISIONAL / NOT FROZEN)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

from uri_v1.execution.acceptance import AcceptanceCriteria

EDGE_SCHEMA_VERSION = "m37.edge.v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class TaskClass(str, Enum):
    WORKBOOK_INSPECT = "WORKBOOK_INSPECT"
    SCRIPT_WORKBOOK_DIAGNOSE = "SCRIPT_WORKBOOK_DIAGNOSE"
    SCRIPT_WORKBOOK_REPAIR = "SCRIPT_WORKBOOK_REPAIR"


class Mechanism(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    EDGE_MODEL = "EDGE_MODEL"


class Qualification(str, Enum):
    QUALIFIED = "QUALIFIED"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNQUALIFIED = "UNQUALIFIED"


class DecisionKind(str, Enum):
    LOCAL = "LOCAL"
    ESCALATE = "ESCALATE"
    CLARIFY = "CLARIFY"


class Reason(str, Enum):
    QUALIFIED_LOCAL = "QUALIFIED_LOCAL"
    ALREADY_COMPATIBLE = "ALREADY_COMPATIBLE"
    NO_QUALIFIED_CAPABILITY = "NO_QUALIFIED_CAPABILITY"
    OUTSIDE_LOCAL_ENVELOPE = "OUTSIDE_LOCAL_ENVELOPE"
    AMBIGUOUS_REMAP = "AMBIGUOUS_REMAP"
    NO_REMAP = "NO_REMAP"
    DYNAMIC_ACCESS = "DYNAMIC_ACCESS"
    WORKBOOK_PATH_MISMATCH = "WORKBOOK_PATH_MISMATCH"
    UNREADABLE_INPUT = "UNREADABLE_INPUT"
    STALE_INPUT = "STALE_INPUT"
    CORRECTED_REFERENCE = "CORRECTED_REFERENCE"
    MEMORY_CONFLICT = "MEMORY_CONFLICT"
    MEMORY_PENDING_CORRECTION = "MEMORY_PENDING_CORRECTION"
    MEMORY_QUARANTINED = "MEMORY_QUARANTINED"
    INVALID_CONTEXT = "INVALID_CONTEXT"


_ROLES = {TaskClass.WORKBOOK_INSPECT: {"workbook"},
          TaskClass.SCRIPT_WORKBOOK_DIAGNOSE: {"script", "workbook"},
          TaskClass.SCRIPT_WORKBOOK_REPAIR: {"script", "workbook"}}


@dataclass(frozen=True)
class TaskInput:
    role: str
    source_id: str
    content_sha256: str

    def __post_init__(self):
        if self.role not in ("script", "workbook"): raise ValueError("INVALID_ROLE")
        if not _ID.fullmatch(self.source_id or "") or not _SHA.fullmatch(self.content_sha256 or ""):
            raise ValueError("HASH_BOUND_INPUT_REQUIRED")


@dataclass(frozen=True)
class EdgeTask:
    task_id: str
    task_class: TaskClass
    inputs: tuple
    acceptance: AcceptanceCriteria
    trace_id: str
    session_id: str

    def __post_init__(self):
        object.__setattr__(self, "task_class", TaskClass(self.task_class))
        if not _ID.fullmatch(self.task_id or "") or not re.fullmatch(r"[0-9a-f]{32}", self.trace_id or ""):
            raise ValueError("INVALID_TASK_IDENTITY")
        if not isinstance(self.acceptance, AcceptanceCriteria): raise ValueError("ACCEPTANCE_REQUIRED")
        roles = [i.role for i in self.inputs]
        if any(not isinstance(i, TaskInput) for i in self.inputs) or sorted(roles) != sorted(_ROLES[self.task_class]):
            raise ValueError("INPUT_ROLES_MISMATCH")

    def input(self, role) -> TaskInput:
        return next(i for i in self.inputs if i.role == role)


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str
    task_class: TaskClass
    version: str
    mechanism: Mechanism

    def __post_init__(self):
        object.__setattr__(self, "task_class", TaskClass(self.task_class))
        object.__setattr__(self, "mechanism", Mechanism(self.mechanism))
        if not _ID.fullmatch(self.capability_id) or not _ID.fullmatch(self.version): raise ValueError("INVALID_CAPABILITY")


@dataclass(frozen=True)
class EscalationRequest:
    """Only the unresolved remainder plus locally established, hashed facts (VG-1 G2)."""
    task_id: str
    task_class: TaskClass
    inputs: tuple
    acceptance: dict
    acceptance_sha256: str
    local_findings: dict
    unresolved: tuple
    trace_id: str
    schema_version: str = EDGE_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "task_id": self.task_id, "task_class": self.task_class.value,
                "inputs": [i.__dict__ for i in self.inputs], "acceptance": self.acceptance,
                "acceptance_sha256": self.acceptance_sha256, "local_findings": self.local_findings,
                "unresolved": list(self.unresolved), "trace_id": self.trace_id}


@dataclass(frozen=True)
class EdgeDecision:
    kind: DecisionKind
    reason: Reason
    task_id: str
    capability_id: str | None = None
    findings: dict = field(default_factory=dict)
    escalation: EscalationRequest | None = None
