"""Contracts and closed schemas for dynamic planning (Stage 2, Slice 1).

Typed capability contracts, capability snapshots, semantic proposal parsing,
compiled plan definitions and typed rejections.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping

PROPOSAL_SCHEMA_VERSION = "uri.plan.proposal.v1"
COMPILED_PLAN_SCHEMA_VERSION = "uri.plan.compiled.v1"
CONTRACT_SCHEMA_VERSION = "uri.plan.contract.v1"

_IDENTIFIER = re.compile(r"^[a-zA-Z0-9_.\-]+$")
_PORT_REF = re.compile(r"^([a-zA-Z0-9_.\-]+)\.([a-zA-Z0-9_.\-]+)$")


class PortType(str, Enum):
    """Closed vocabulary of port types for dataflow composition. No coercion."""
    SOURCE_XLSX = "SOURCE_XLSX"
    WORKBOOK_STRUCTURE = "WORKBOOK_STRUCTURE"
    STRUCTURE_SELECTION = "STRUCTURE_SELECTION"
    STRUCTURE_COMPARISON = "STRUCTURE_COMPARISON"
    REPORT_ARTIFACT = "REPORT_ARTIFACT"


class ProposalInvalid(ValueError):
    """Typed failure when a raw proposal violates closed schema or structure."""
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LiteralSpec:
    """Specification for literal parameters declared in capability contracts."""
    name: str
    expected_type: str  # "str", "list", "int", "bool", "dict"
    required: bool = True
    allowed_values: tuple[str, ...] = ()
    max_length: int = 256
    element_type: str | None = None  # for list items, e.g. "str"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expected_type": self.expected_type,
            "required": self.required,
            "allowed_values": list(self.allowed_values),
            "max_length": self.max_length,
            "element_type": self.element_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiteralSpec:
        return cls(
            name=data["name"],
            expected_type=data["expected_type"],
            required=data.get("required", True),
            allowed_values=tuple(data.get("allowed_values", ())),
            max_length=data.get("max_length", 256),
            element_type=data.get("element_type"),
        )


@dataclass(frozen=True)
class InputPortSpec:
    """Specification for an input port declared in capability contracts."""
    port: str
    allowed_types: tuple[PortType, ...]
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "allowed_types": [t.value for t in self.allowed_types],
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InputPortSpec:
        return cls(
            port=data["port"],
            allowed_types=tuple(PortType(t) for t in data["allowed_types"]),
            required=data.get("required", True),
        )


@dataclass(frozen=True)
class CapabilityContract:
    """Read-only projection of an approved handler's composition declaration."""
    action_id: str
    version: str
    mechanism: str  # "DETERMINISTIC" | "SEMANTIC"
    inputs: dict[str, InputPortSpec]
    outputs: dict[str, PortType]
    literals: dict[str, LiteralSpec]
    effect: str  # "READ_ONLY" | "SCRATCH_WRITE"
    approval: str  # "NONE"
    verifier_coverage: str  # e.g. "report_recomputes"
    qualification: str  # qualification id + sha, or "UNQUALIFIED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "version": self.version,
            "mechanism": self.mechanism,
            "inputs": {k: v.to_dict() for k, v in sorted(self.inputs.items())},
            "outputs": {k: v.value for k, v in sorted(self.outputs.items())},
            "literals": {k: v.to_dict() for k, v in sorted(self.literals.items())},
            "effect": self.effect,
            "approval": self.approval,
            "verifier_coverage": self.verifier_coverage,
            "qualification": self.qualification,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityContract:
        inputs = {}
        for k, v in data.get("inputs", {}).items():
            if isinstance(v, dict):
                inputs[k] = InputPortSpec.from_dict(v)
            elif isinstance(v, PortType):
                inputs[k] = InputPortSpec(k, (v,), required=True)
            elif isinstance(v, str):
                inputs[k] = InputPortSpec(k, (PortType(v),), required=True)
            else:
                inputs[k] = v

        outputs = {k: PortType(v) for k, v in data.get("outputs", {}).items()}
        literals = {k: LiteralSpec.from_dict(v) if isinstance(v, dict) else v for k, v in data.get("literals", {}).items()}
        return cls(
            action_id=data["action_id"],
            version=data["version"],
            mechanism=data["mechanism"],
            inputs=inputs,
            outputs=outputs,
            literals=literals,
            effect=data.get("effect", "READ_ONLY"),
            approval=data.get("approval", "NONE"),
            verifier_coverage=data.get("verifier_coverage", ""),
            qualification=data.get("qualification", "UNQUALIFIED"),
        )


@dataclass(frozen=True)
class CapabilitySnapshot:
    """Immutable, content-addressed collection of capability contracts pinned per plan."""
    contracts: tuple[CapabilityContract, ...]
    sha256: str

    @classmethod
    def create(cls, contracts: tuple[CapabilityContract, ...] | list[CapabilityContract]) -> CapabilitySnapshot:
        sorted_contracts = tuple(sorted(contracts, key=lambda c: (c.action_id, c.version)))
        payload = [c.to_dict() for c in sorted_contracts]
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        return cls(contracts=sorted_contracts, sha256=digest)

    def get(self, action_id: str, version: str) -> CapabilityContract | None:
        return next((c for c in self.contracts if c.action_id == action_id and c.version == version), None)

    def view(self) -> list[dict[str, Any]]:
        """Projected read-only view of contracts for prompt assembly."""
        return [c.to_dict() for c in self.contracts]


@dataclass(frozen=True)
class SourceRef:
    """Symbolic reference to an authorized input source candidate."""
    source_id: str


@dataclass(frozen=True)
class PortRef:
    """Symbolic reference to producer node's output port."""
    from_node: str
    from_port: str


@dataclass(frozen=True)
class ProposalNode:
    id: str
    action: str
    action_version: str
    inputs: dict[str, SourceRef | PortRef]
    literals: dict[str, Any]


@dataclass(frozen=True)
class ProposalOutput:
    node_id: str
    port: str


@dataclass(frozen=True)
class ProposalCannot:
    reason_code: str
    text: str


@dataclass(frozen=True)
class SemanticProposal:
    """Parsed model proposal with closed schema."""
    schema_version: str
    nodes: tuple[ProposalNode, ...]
    outputs: tuple[ProposalOutput, ...]
    cannot: tuple[ProposalCannot, ...]
    raw_sha256: str

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> SemanticProposal:
        if not isinstance(raw, dict):
            raise ProposalInvalid("PROPOSAL_NOT_DICT", "Proposal must be a JSON dictionary")
        if raw.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
            raise ProposalInvalid("PROPOSAL_SCHEMA_INVALID", f"Expected schema_version {PROPOSAL_SCHEMA_VERSION}")

        allowed_keys = {"schema_version", "nodes", "outputs", "cannot"}
        extra_keys = set(raw.keys()) - allowed_keys
        if extra_keys:
            raise ProposalInvalid("PROPOSAL_EXTRA_KEYS", f"Unknown top-level keys: {sorted(extra_keys)}")

        raw_bytes = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()

        # Parse cannot
        cannot_items = []
        for c in raw.get("cannot", []):
            if not isinstance(c, dict) or "reason_code" not in c or "text" not in c:
                raise ProposalInvalid("CANNOT_ITEM_SHAPE", "Each cannot item must have reason_code and text")
            cannot_items.append(ProposalCannot(reason_code=str(c["reason_code"]), text=str(c["text"])))

        # Parse nodes
        raw_nodes = raw.get("nodes", [])
        if not isinstance(raw_nodes, list):
            raise ProposalInvalid("NODES_NOT_LIST", "Proposal nodes must be a list")

        nodes = []
        for n in raw_nodes:
            if not isinstance(n, dict):
                raise ProposalInvalid("NODE_NOT_DICT", "Each node must be a dict")
            required_node_keys = {"id", "action", "action_version", "inputs", "literals"}
            missing = required_node_keys - set(n.keys())
            if missing:
                raise ProposalInvalid("NODE_MISSING_KEYS", f"Node missing keys: {sorted(missing)}")
            node_id = str(n["id"])
            if not _IDENTIFIER.fullmatch(node_id):
                raise ProposalInvalid("INVALID_NODE_ID", f"Invalid node id: {node_id}")

            raw_inputs = n["inputs"]
            if not isinstance(raw_inputs, dict):
                raise ProposalInvalid("INPUTS_NOT_DICT", f"Node {node_id} inputs must be a dict")

            parsed_inputs: dict[str, SourceRef | PortRef] = {}
            for port_name, binding in raw_inputs.items():
                if not isinstance(binding, dict):
                    raise ProposalInvalid("BINDING_NOT_DICT", f"Binding for {node_id}.{port_name} must be a dict")
                if "from" in binding and "source" in binding:
                    raise ProposalInvalid("AMBIGUOUS_BINDING", f"Binding cannot have both 'from' and 'source'")
                if "source" in binding:
                    parsed_inputs[port_name] = SourceRef(source_id=str(binding["source"]))
                elif "from" in binding:
                    from_str = str(binding["from"])
                    match = _PORT_REF.fullmatch(from_str)
                    if not match:
                        raise ProposalInvalid("INVALID_PORT_REF", f"Port ref must be <node>.<port>, got {from_str}")
                    parsed_inputs[port_name] = PortRef(from_node=match.group(1), from_port=match.group(2))
                else:
                    raise ProposalInvalid("INVALID_BINDING", f"Binding must specify 'from' or 'source'")

            raw_literals = n["literals"]
            if not isinstance(raw_literals, dict):
                raise ProposalInvalid("LITERALS_NOT_DICT", f"Node {node_id} literals must be a dict")

            nodes.append(ProposalNode(
                id=node_id,
                action=str(n["action"]),
                action_version=str(n["action_version"]),
                inputs=parsed_inputs,
                literals=dict(raw_literals),
            ))

        # Parse outputs
        raw_outputs = raw.get("outputs", [])
        if not isinstance(raw_outputs, list):
            raise ProposalInvalid("OUTPUTS_NOT_LIST", "Proposal outputs must be a list")

        outputs = []
        for out in raw_outputs:
            if isinstance(out, dict):
                if "node_id" in out and "port" in out:
                    outputs.append(ProposalOutput(node_id=str(out["node_id"]), port=str(out["port"])))
                elif "from" in out:
                    match = _PORT_REF.fullmatch(str(out["from"]))
                    if not match:
                        raise ProposalInvalid("INVALID_OUTPUT_REF", f"Output ref must be <node>.<port>")
                    outputs.append(ProposalOutput(node_id=match.group(1), port=match.group(2)))
                else:
                    raise ProposalInvalid("OUTPUT_SHAPE_INVALID", f"Output dict must have node_id/port or from")
            elif isinstance(out, str):
                match = _PORT_REF.fullmatch(out)
                if not match:
                    raise ProposalInvalid("INVALID_OUTPUT_REF", f"Output ref must be <node>.<port>")
                outputs.append(ProposalOutput(node_id=match.group(1), port=match.group(2)))
            else:
                raise ProposalInvalid("OUTPUT_TYPE_INVALID", "Output item must be dict or str")

        return cls(
            schema_version=PROPOSAL_SCHEMA_VERSION,
            nodes=tuple(nodes),
            outputs=tuple(outputs),
            cannot=tuple(cannot_items),
            raw_sha256=raw_sha,
        )


@dataclass(frozen=True)
class PlanNode:
    """Compiled node ready for validated execution."""
    node_id: str
    action_id: str
    version: str
    qualification_sha: str
    inputs: dict[str, SourceRef | PortRef]
    literals: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        serialized_inputs = {}
        for k, v in sorted(self.inputs.items()):
            if isinstance(v, SourceRef):
                serialized_inputs[k] = {"source": v.source_id}
            else:
                serialized_inputs[k] = {"from": f"{v.from_node}.{v.from_port}"}
        return {
            "node_id": self.node_id,
            "action_id": self.action_id,
            "version": self.version,
            "qualification_sha": self.qualification_sha,
            "inputs": serialized_inputs,
            "literals": self.literals,
        }


@dataclass(frozen=True)
class PlanEdge:
    from_node: str
    from_port: str
    to_node: str
    to_port: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "from_port": self.from_port,
            "to_node": self.to_node,
            "to_port": self.to_port,
        }


@dataclass(frozen=True)
class BoundSource:
    source_id: str
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class CompiledPlan:
    """Immutable compiled execution DAG with cryptographic fingerprint."""
    nodes: tuple[PlanNode, ...]
    edges: tuple[PlanEdge, ...]
    sources: tuple[BoundSource, ...]
    outputs: tuple[ProposalOutput, ...]
    proposal_sha256: str
    snapshot_sha256: str
    sha256: str

    @classmethod
    def create(cls, *, nodes: tuple[PlanNode, ...], edges: tuple[PlanEdge, ...],
               sources: tuple[BoundSource, ...], outputs: tuple[ProposalOutput, ...],
               proposal_sha256: str, snapshot_sha256: str) -> CompiledPlan:
        # Build canonical representation and hash
        payload = {
            "schema_version": COMPILED_PLAN_SCHEMA_VERSION,
            "proposal_sha256": proposal_sha256,
            "snapshot_sha256": snapshot_sha256,
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "sources": [s.to_dict() for s in sorted(sources, key=lambda s: s.source_id)],
            "outputs": [{"node_id": o.node_id, "port": o.port} for o in outputs],
        }
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        return cls(
            nodes=nodes,
            edges=edges,
            sources=sources,
            outputs=outputs,
            proposal_sha256=proposal_sha256,
            snapshot_sha256=snapshot_sha256,
            sha256=digest,
        )

    def canonical(self) -> bytes:
        payload = {
            "schema_version": COMPILED_PLAN_SCHEMA_VERSION,
            "proposal_sha256": self.proposal_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "sources": [s.to_dict() for s in sorted(self.sources, key=lambda s: s.source_id)],
            "outputs": [{"node_id": o.node_id, "port": o.port} for o in self.outputs],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": COMPILED_PLAN_SCHEMA_VERSION,
            "plan_sha256": self.sha256,
            "proposal_sha256": self.proposal_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "sources": [s.to_dict() for s in self.sources],
            "outputs": [{"node_id": o.node_id, "port": o.port} for o in self.outputs],
        }


@dataclass(frozen=True)
class Rejection:
    """Typed deterministic rejection of an invalid or unexecutable proposal."""
    code: str
    detail: str


@dataclass(frozen=True)
class PartialPlan:
    """Partitioned plan when proposal has unresolved remainder (Slice 2 interface)."""
    supported: tuple[PlanNode, ...]
    unresolved: tuple[ProposalNode, ...]
    reasons: dict[str, str]
