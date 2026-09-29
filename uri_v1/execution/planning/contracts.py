"""Closed data contracts for dynamic planning slice 1.

Everything here is data. A `SemanticProposal` is untrusted model output with a
closed schema (`uri.plan.proposal.v1`); a `CapabilityContract` is a read-only
projection of an approved handler's declaration; a `CompiledPlan` is the only
thing the runner executes and the verifier checks, bound by its SHA-256.

Stage 2 references: §2.1 (proposal, F1/F5/F9/F10), §2.2 (contracts, F2/F4),
§2.3 (compiled plan, F3), §2.4 (sources and handles, F10-F12).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re

PROPOSAL_SCHEMA_VERSION = "uri.plan.proposal.v1"
PLAN_SCHEMA_VERSION = "uri.plan.compiled.v1"
REPORT_SCHEMA_VERSION = "uri.plan.report.v1"
REPORT_NAME = "plan_report.json"
TASK_CLASS_PREFIX = "PLANNED_STRUCTURE_REPORT@"
CAPABILITY_ID = "uri.plan.compiled"

# Hard caps checked while parsing, before any compile-time limit applies.
MAX_PROPOSAL_BYTES = 64 * 1024
MAX_PARSE_NODES = 64
MAX_FROM_REFS = 8
MAX_AMBIGUOUS = 8
MAX_OUTPUTS = 8
MAX_CANNOT = 16
MAX_LITERAL_ITEMS = 32
MAX_LITERAL_LEN = 128
MAX_TEXT_LEN = 500

_NODE_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_PORT = _NODE_ID
_ACTION = re.compile(r"^[a-z][a-z0-9_.]{0,127}$")
_VERSION = re.compile(r"^[0-9]{1,6}$")
_SOURCE_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^([a-z][a-z0-9_]{0,31})\.([a-z][a-z0-9_]{0,31})$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class PortType(str, Enum):
    """Closed port vocabulary. Compatibility is equality; nothing is coerced."""
    SOURCE_XLSX = "SOURCE_XLSX"
    WORKBOOK_STRUCTURE = "WORKBOOK_STRUCTURE"
    STRUCTURE_SELECTION = "STRUCTURE_SELECTION"
    STRUCTURE_COMPARISON = "STRUCTURE_COMPARISON"
    REPORT_ARTIFACT = "REPORT_ARTIFACT"


class Mechanism(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC = "SEMANTIC"


class Effect(str, Enum):
    READ_ONLY = "READ_ONLY"
    SCRATCH_WRITE = "SCRATCH_WRITE"


class Approval(str, Enum):
    NONE = "NONE"


# The oracle operations the planning verifier can independently recompute.
# A contract names one of these as its `verifier_coverage`; renaming an action
# keeps its coverage, so the verifier never matches on action spelling.
VERIFIER_COVERAGE = frozenset({"oracle.inspect_structure.v1", "oracle.select.v1", "oracle.compare.v1",
                               "oracle.report_write.v1"})
UNQUALIFIED = "UNQUALIFIED"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_of(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class ProposalInvalid(ValueError):
    """Typed parse failure; `code` is PROPOSAL_INVALID or LIMIT_EXCEEDED."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code, self.detail = code, detail


# -- capability contracts ------------------------------------------------------

@dataclass(frozen=True)
class LiteralSpec:
    kind: str                 # "string_list" | "enum"
    required: bool
    values: tuple = ()        # allowed values for "enum"
    max_items: int = MAX_LITERAL_ITEMS
    max_len: int = MAX_LITERAL_LEN

    def __post_init__(self):
        if self.kind not in ("string_list", "enum") or type(self.required) is not bool: raise ValueError("LITERAL_SPEC")
        if self.kind == "enum" and not self.values: raise ValueError("LITERAL_SPEC")

    def accepts(self, value) -> bool:
        if self.kind == "enum":
            return isinstance(value, str) and value in self.values
        return (isinstance(value, list) and 1 <= len(value) <= self.max_items and len(set(value)) == len(value)
                and all(isinstance(v, str) and 1 <= len(v) <= self.max_len for v in value))

    def to_dict(self) -> dict:
        return {"kind": self.kind, "required": self.required, "values": list(self.values),
                "max_items": self.max_items, "max_len": self.max_len}


@dataclass(frozen=True)
class InputSpec:
    types: tuple              # accepted PortTypes; a producer must declare one of them exactly
    required: bool = True
    max_refs: int = 1

    def __post_init__(self):
        if not self.types or not all(isinstance(t, PortType) for t in self.types): raise ValueError("INPUT_SPEC")
        if type(self.required) is not bool or not 1 <= self.max_refs <= MAX_FROM_REFS: raise ValueError("INPUT_SPEC")

    def to_dict(self) -> dict:
        return {"types": sorted(t.value for t in self.types), "required": self.required, "max_refs": self.max_refs}


@dataclass(frozen=True)
class CapabilityContract:
    """Read-only composition metadata. It grants no execution or install authority."""
    action_id: str
    version: str
    mechanism: Mechanism
    inputs: tuple             # ((port, InputSpec), ...)
    outputs: tuple            # ((port, PortType), ...)
    literals: tuple           # ((name, LiteralSpec), ...)
    effect: Effect
    approval: Approval
    verifier_coverage: str
    qualification: str        # sha256 of the pinned qualification record, or UNQUALIFIED

    def __post_init__(self):
        if not _ACTION.fullmatch(self.action_id or "") or not _VERSION.fullmatch(self.version or ""): raise ValueError("CONTRACT_ID")
        if not isinstance(self.mechanism, Mechanism) or not isinstance(self.effect, Effect) or not isinstance(self.approval, Approval):
            raise ValueError("CONTRACT_METADATA")
        for group, kind in ((self.inputs, InputSpec), (self.outputs, PortType), (self.literals, LiteralSpec)):
            names = [n for n, _ in group]
            if len(set(names)) != len(names) or not all(_PORT.fullmatch(n) and isinstance(v, kind) for n, v in group):
                raise ValueError("CONTRACT_PORTS")
        if not self.outputs: raise ValueError("CONTRACT_PORTS")
        if self.verifier_coverage not in VERIFIER_COVERAGE: raise ValueError("CONTRACT_COVERAGE")
        if self.qualification != UNQUALIFIED and not _SHA.fullmatch(self.qualification or ""): raise ValueError("CONTRACT_QUALIFICATION")

    def input(self, port): return dict(self.inputs).get(port)
    def output(self, port): return dict(self.outputs).get(port)
    def literal(self, name): return dict(self.literals).get(name)

    def to_dict(self) -> dict:
        return {"action_id": self.action_id, "version": self.version, "mechanism": self.mechanism.value,
                "inputs": {n: s.to_dict() for n, s in self.inputs}, "outputs": {n: t.value for n, t in self.outputs},
                "literals": {n: s.to_dict() for n, s in self.literals}, "effect": self.effect.value,
                "approval": self.approval.value, "verifier_coverage": self.verifier_coverage,
                "qualification": self.qualification}


@dataclass(frozen=True)
class CapabilitySnapshot:
    """Immutable, hashed set of contracts pinned per plan."""
    contracts: tuple

    def __post_init__(self):
        keys = [(c.action_id, c.version) for c in self.contracts]
        if not all(isinstance(c, CapabilityContract) for c in self.contracts) or len(set(keys)) != len(keys):
            raise ValueError("SNAPSHOT_CONTRACTS")
        object.__setattr__(self, "contracts", tuple(sorted(self.contracts, key=lambda c: (c.action_id, c.version))))

    def to_dict(self) -> dict:
        return {"contracts": [c.to_dict() for c in self.contracts]}

    @property
    def sha256(self) -> str:
        return sha256_of(self.to_dict())

    def get(self, action_id, version):
        return next((c for c in self.contracts if c.action_id == action_id and c.version == version), None)

    def knows(self, action_id) -> bool:
        return any(c.action_id == action_id for c in self.contracts)


# -- untrusted proposal ------------------------------------------------------------

@dataclass(frozen=True)
class FromBinding:
    refs: tuple               # ((node_id, port), ...) in proposed order
    listed: bool              # proposed as a list (only valid for multi-ref ports)


@dataclass(frozen=True)
class SourceBinding:
    source_id: str


@dataclass(frozen=True)
class AmbiguousSources:
    source_ids: tuple


@dataclass(frozen=True)
class ProposalNode:
    node_id: str
    action: str
    action_version: str
    inputs: tuple             # ((port, binding), ...)
    literals: tuple           # ((name, value), ...)


def _text(value, limit) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= limit and not any(ord(c) < 32 for c in value)


def _ref(value):
    match = _REF.fullmatch(value) if isinstance(value, str) else None
    if not match: raise ProposalInvalid("PROPOSAL_INVALID", "PORT_REF")
    return match.group(1), match.group(2)


def _binding(raw):
    if not isinstance(raw, dict) or len(raw) != 1: raise ProposalInvalid("PROPOSAL_INVALID", "BINDING_SHAPE")
    (key, value), = raw.items()
    if key == "from":
        if isinstance(value, list):
            if not 1 <= len(value) <= MAX_FROM_REFS: raise ProposalInvalid("LIMIT_EXCEEDED", "FROM_REFS")
            return FromBinding(tuple(_ref(v) for v in value), True)
        return FromBinding((_ref(value),), False)
    if key == "source":
        # Only a trusted candidate id is a source. A path, a handle or anything else is refused (F10/F11).
        if not isinstance(value, str) or not _SOURCE_ID.fullmatch(value): raise ProposalInvalid("PROPOSAL_INVALID", "SOURCE_ID")
        return SourceBinding(value)
    if key == "sources_ambiguous":
        if (not isinstance(value, list) or not 2 <= len(value) <= MAX_AMBIGUOUS or len(set(value)) != len(value)
                or not all(isinstance(v, str) and _SOURCE_ID.fullmatch(v) for v in value)):
            raise ProposalInvalid("PROPOSAL_INVALID", "SOURCE_ID")
        return AmbiguousSources(tuple(value))
    raise ProposalInvalid("PROPOSAL_INVALID", "BINDING_KIND")


def _literal(value):
    if isinstance(value, str):
        if not _text(value, MAX_LITERAL_LEN): raise ProposalInvalid("PROPOSAL_INVALID", "LITERAL")
        return value
    if isinstance(value, list):
        if len(value) > MAX_LITERAL_ITEMS: raise ProposalInvalid("LIMIT_EXCEEDED", "LITERAL_ITEMS")
        if not all(_text(v, MAX_LITERAL_LEN) for v in value): raise ProposalInvalid("PROPOSAL_INVALID", "LITERAL")
        return tuple(value)
    raise ProposalInvalid("PROPOSAL_INVALID", "LITERAL")


def _node(raw) -> ProposalNode:
    if not isinstance(raw, dict) or set(raw) != {"id", "action", "action_version", "inputs", "literals"}:
        raise ProposalInvalid("PROPOSAL_INVALID", "NODE_SHAPE")
    if not isinstance(raw["id"], str) or not _NODE_ID.fullmatch(raw["id"]): raise ProposalInvalid("PROPOSAL_INVALID", "NODE_ID")
    if not isinstance(raw["action"], str) or not _ACTION.fullmatch(raw["action"]): raise ProposalInvalid("PROPOSAL_INVALID", "ACTION")
    if not isinstance(raw["action_version"], str) or not _VERSION.fullmatch(raw["action_version"]):
        raise ProposalInvalid("PROPOSAL_INVALID", "ACTION_VERSION")
    if not isinstance(raw["inputs"], dict) or not isinstance(raw["literals"], dict): raise ProposalInvalid("PROPOSAL_INVALID", "NODE_SHAPE")
    if len(raw["inputs"]) > 16 or len(raw["literals"]) > 16: raise ProposalInvalid("LIMIT_EXCEEDED", "NODE_FIELDS")
    for name in list(raw["inputs"]) + list(raw["literals"]):
        if not isinstance(name, str) or not _PORT.fullmatch(name): raise ProposalInvalid("PROPOSAL_INVALID", "PORT_NAME")
    return ProposalNode(raw["id"], raw["action"], raw["action_version"],
                        tuple(sorted((p, _binding(b)) for p, b in raw["inputs"].items())),
                        tuple(sorted((n, _literal(v)) for n, v in raw["literals"].items())))


def _binding_dict(binding):
    if isinstance(binding, FromBinding):
        refs = [f"{n}.{p}" for n, p in binding.refs]
        return {"from": refs if binding.listed else refs[0]}
    if isinstance(binding, SourceBinding): return {"source": binding.source_id}
    return {"sources_ambiguous": list(binding.source_ids)}


@dataclass(frozen=True)
class SemanticProposal:
    nodes: tuple
    outputs: tuple            # ((node_id, port), ...)
    cannot: tuple             # ((reason_code, text), ...)

    @classmethod
    def parse(cls, raw) -> "SemanticProposal":
        if not isinstance(raw, dict): raise ProposalInvalid("PROPOSAL_INVALID", "NOT_AN_OBJECT")
        try: size = len(canonical(raw))
        except (TypeError, ValueError): raise ProposalInvalid("PROPOSAL_INVALID", "NOT_JSON")
        if size > MAX_PROPOSAL_BYTES: raise ProposalInvalid("LIMIT_EXCEEDED", "PROPOSAL_BYTES")
        if set(raw) != {"schema_version", "nodes", "outputs", "cannot"}: raise ProposalInvalid("PROPOSAL_INVALID", "TOP_LEVEL_KEYS")
        if raw["schema_version"] != PROPOSAL_SCHEMA_VERSION: raise ProposalInvalid("PROPOSAL_INVALID", "SCHEMA_VERSION")
        nodes, outputs, cannot = raw["nodes"], raw["outputs"], raw["cannot"]
        if not isinstance(nodes, list) or not isinstance(outputs, list) or not isinstance(cannot, list):
            raise ProposalInvalid("PROPOSAL_INVALID", "TOP_LEVEL_TYPES")
        if len(nodes) > MAX_PARSE_NODES or len(outputs) > MAX_OUTPUTS or len(cannot) > MAX_CANNOT:
            raise ProposalInvalid("LIMIT_EXCEEDED", "TOP_LEVEL_COUNTS")
        parsed_cannot = []
        for item in cannot:
            if (not isinstance(item, dict) or set(item) != {"reason_code", "text"} or not isinstance(item["reason_code"], str)
                    or not _REASON.fullmatch(item["reason_code"]) or not _text(item["text"], MAX_TEXT_LEN)):
                raise ProposalInvalid("PROPOSAL_INVALID", "CANNOT_ITEM")
            parsed_cannot.append((item["reason_code"], item["text"]))
        return cls(tuple(_node(n) for n in nodes), tuple(_ref(o) for o in outputs), tuple(parsed_cannot))

    def to_dict(self) -> dict:
        """Canonical form: node order and key order carry no meaning, so both are normalized.
        The order of refs inside a listed `from` is kept (it is the proposed item order)."""
        nodes = [{"id": n.node_id, "action": n.action, "action_version": n.action_version,
                  "inputs": {p: _binding_dict(b) for p, b in n.inputs},
                  "literals": {k: list(v) if isinstance(v, tuple) else v for k, v in n.literals}} for n in self.nodes]
        nodes.sort(key=canonical)
        return {"schema_version": PROPOSAL_SCHEMA_VERSION, "nodes": nodes,
                "outputs": sorted(f"{n}.{p}" for n, p in self.outputs),
                "cannot": sorted(({"reason_code": c, "text": t} for c, t in self.cannot), key=canonical)}

    @property
    def sha256(self) -> str:
        return sha256_of(self.to_dict())


# -- trusted inputs and compile results --------------------------------------------

@dataclass(frozen=True)
class SourceCandidate:
    """A source the runtime itself found and hashed. Proposals may only name these ids."""
    source_id: str
    name: str
    media_type: str
    content_sha256: str


@dataclass(frozen=True)
class Limits:
    max_nodes: int = 16
    max_edges: int = 32
    max_outputs: int = 1           # slice 1 writes exactly one report
    node_seconds: float = 10.0
    run_seconds: float = 60.0
    max_output_bytes: int = 1024 * 1024


@dataclass(frozen=True)
class PlanNode:
    node_id: str
    action_id: str
    version: str
    qualification_sha: str
    verifier_coverage: str
    inputs: tuple             # ((port, ("from", ((node, port), ...)) | ("source", source_id)), ...)
    literals: tuple           # ((name, value), ...)

    def to_dict(self) -> dict:
        inputs = {}
        for port, (kind, value) in self.inputs:
            inputs[port] = {"from": [f"{n}.{p}" for n, p in value]} if kind == "from" else {"source": value}
        return {"id": self.node_id, "action_id": self.action_id, "version": self.version,
                "qualification_sha": self.qualification_sha, "verifier_coverage": self.verifier_coverage,
                "inputs": inputs, "literals": {k: list(v) if isinstance(v, tuple) else v for k, v in self.literals}}


@dataclass(frozen=True)
class CompiledPlan:
    nodes: tuple              # PlanNode, sorted by id
    edges: tuple              # ((from_node, from_port, to_node, to_port), ...) sorted
    sources: tuple            # ((source_id, content_sha256), ...) sorted
    outputs: tuple            # ((node_id, port), ...)
    order: tuple              # deterministic topological order of node ids
    proposal_sha256: str
    snapshot_sha256: str

    def to_dict(self) -> dict:
        return {"schema_version": PLAN_SCHEMA_VERSION, "nodes": [n.to_dict() for n in self.nodes],
                "edges": [list(e) for e in self.edges], "sources": [list(s) for s in self.sources],
                "outputs": [f"{n}.{p}" for n, p in self.outputs], "order": list(self.order),
                "proposal_sha256": self.proposal_sha256, "snapshot_sha256": self.snapshot_sha256}

    def canonical(self) -> bytes:
        return canonical(self.to_dict())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()

    @property
    def task_class(self) -> str:
        return TASK_CLASS_PREFIX + self.sha256

    def node(self, node_id):
        return next((n for n in self.nodes if n.node_id == node_id), None)


@dataclass(frozen=True)
class Rejection:
    code: str
    detail: str = ""


@dataclass(frozen=True)
class ClarificationRequired:
    """Ambiguous candidate sources: the user chooses; slice 1 never auto-binds."""
    node_id: str
    port: str
    candidate_ids: tuple


@dataclass(frozen=True)
class PartialPlan:
    """Slice 2 (Stage 2 §2.7). Defined for the interface only; slice 1 never produces one."""
    supported: tuple
    unresolved: tuple
    reasons: tuple
