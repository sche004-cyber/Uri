"""Local capability registry and qualification gate.

Qualification sets eligibility; nothing else does. A capability is eligible to
complete work locally only when a qualification record names its exact id and
version as QUALIFIED with `passed: true`, and the record file's SHA-256 matches
the digest the caller pins. Experimental and model-backed capabilities are
listed but can never complete a task without such a record.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contracts import CapabilityDescriptor, Mechanism, Qualification, TaskClass

QUALIFICATION_SCHEMA_VERSION = "m37.edge.qualification.v1"

CAPABILITIES = (
    CapabilityDescriptor("uri.edge.workbook_inspect", TaskClass.WORKBOOK_INSPECT, "1", Mechanism.DETERMINISTIC),
    CapabilityDescriptor("uri.edge.script_workbook_diagnose", TaskClass.SCRIPT_WORKBOOK_DIAGNOSE, "1", Mechanism.DETERMINISTIC),
    CapabilityDescriptor("uri.edge.script_workbook_literal_remap", TaskClass.SCRIPT_WORKBOOK_REPAIR, "1", Mechanism.DETERMINISTIC),
)


class QualificationRecord:
    """Parsed, digest-checked qualification evidence."""

    def __init__(self, raw: dict, sha256: str):
        if raw.get("schema_version") != QUALIFICATION_SCHEMA_VERSION or not isinstance(raw.get("capabilities"), list):
            raise ValueError("QUALIFICATION_SCHEMA")
        self.sha256 = sha256
        self.entries = {}
        for e in raw["capabilities"]:
            if set(e) != {"capability_id", "version", "mechanism", "status", "passed", "evidence"}: raise ValueError("QUALIFICATION_ENTRY")
            self.entries[(e["capability_id"], e["version"])] = e

    @classmethod
    def load(cls, path, expected_sha256: str) -> "QualificationRecord":
        # CRLF-normalized, like the frozen M33.3 anchors, so a Windows autocrlf checkout pins the same digest.
        data = Path(path).read_bytes().replace(b"\r\n", b"\n")
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256: raise ValueError("QUALIFICATION_DIGEST_MISMATCH")
        return cls(json.loads(data), actual)

    def status(self, cap: CapabilityDescriptor) -> Qualification:
        e = self.entries.get((cap.capability_id, cap.version))
        if not e or e["mechanism"] != cap.mechanism.value: return Qualification.UNQUALIFIED
        if e["status"] == Qualification.QUALIFIED.value and e["passed"] is True: return Qualification.QUALIFIED
        return Qualification.EXPERIMENTAL if e["status"] == Qualification.EXPERIMENTAL.value else Qualification.UNQUALIFIED


class CapabilityRegistry:
    def __init__(self, record: QualificationRecord | None, capabilities=CAPABILITIES, *, qualification_run=False):
        self.record, self.capabilities = record, tuple(capabilities)
        # A qualification run evaluates candidates before a record exists. It is
        # an explicit mode, recorded in every decision's findings, and never the default.
        self.qualification_run = qualification_run

    def status(self, cap) -> Qualification:
        if self.qualification_run and cap.mechanism is Mechanism.DETERMINISTIC: return Qualification.QUALIFIED
        return self.record.status(cap) if self.record else Qualification.UNQUALIFIED

    def eligible(self, task_class) -> list:
        return [c for c in self.capabilities if c.task_class == TaskClass(task_class) and self.status(c) is Qualification.QUALIFIED]


# Pinned M37 self-qualification evidence (driver: scripts/m37_edge_qualification.py).
# Self-qualification by the implementer; PROVISIONAL until independently audited.
DEFAULT_EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "docs" / "plans" / "M37_EDGE_QUALIFICATION_EVIDENCE.json"
DEFAULT_EVIDENCE_SHA256 = "99aca93634913094733fdcb1859b976a95a96877b1e69a6fa89143a307995bcb"


def default_registry() -> CapabilityRegistry:
    return CapabilityRegistry(QualificationRecord.load(DEFAULT_EVIDENCE_PATH, DEFAULT_EVIDENCE_SHA256))
