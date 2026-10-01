"""Deterministic proposal compiler (Stage 2 §2.3, F3).

`compile_proposal` turns an untrusted proposal into an immutable `CompiledPlan`,
a typed `Rejection`, or a `ClarificationRequired`. Checks run in the order
Stage 2 §2.3 fixes, and each failure has its own reason code. The compiler
keeps every proposed node and edge: it never re-sorts by tier, chains nodes to
a predecessor, fills a default, or corrects a name to a "closest" match.
"""
from __future__ import annotations

from .contracts import (UNQUALIFIED, VERIFIER_COVERAGE, AmbiguousSources, ClarificationRequired, CompiledPlan,
                        FromBinding, Limits, Mechanism, PlanNode, PortType, ProposalInvalid, Rejection,
                        SemanticProposal, SourceBinding)

REJECTION_CODES = frozenset({
    "PROPOSAL_INVALID", "LIMIT_EXCEEDED", "NO_EXECUTABLE_PLAN", "PARTIAL_NOT_SUPPORTED", "DUPLICATE_NODE",
    "UNKNOWN_ACTION", "UNKNOWN_ACTION_VERSION", "UNKNOWN_PORT", "PORT_ARITY", "PORT_TYPE_MISMATCH", "UNKNOWN_SOURCE",
    "UNBOUND_REQUIRED_INPUT", "LITERAL_INVALID", "CYCLE", "UNREACHABLE_OUTPUT", "UNQUALIFIED_ACTION",
    "NO_VERIFIER_COVERAGE",
})


def _is_xlsx_candidate(candidate) -> bool:
    return candidate.media_type == "spreadsheet" and candidate.name.casefold().endswith(".xlsx")


def _topological(node_ids, edges):
    """Kahn's algorithm; ties broken by node id so the order is deterministic. None on a cycle."""
    incoming = {n: set() for n in node_ids}
    for src, _, dst, _ in edges: incoming[dst].add(src)
    order, done = [], set()
    while len(order) < len(node_ids):
        ready = sorted(n for n in node_ids if n not in done and incoming[n] <= done)
        if not ready: return None
        order.append(ready[0]); done.add(ready[0])
    return tuple(order)


def compile_proposal(proposal, snapshot, candidates, *, limits: Limits = Limits()):
    # 1. schema and size limits
    if not isinstance(proposal, SemanticProposal):
        try: proposal = SemanticProposal.parse(proposal)
        except ProposalInvalid as exc: return Rejection(exc.code, exc.detail)
    if not proposal.nodes:
        return Rejection("NO_EXECUTABLE_PLAN", "CANNOT_ONLY" if proposal.cannot else "NO_NODES")
    if proposal.cannot:
        # A remainder the proposal itself declares unsupported: partial plans are slice 2 (Stage 2 §2.7).
        return Rejection("PARTIAL_NOT_SUPPORTED", "CANNOT_WITH_NODES")
    edge_count = sum(len(b.refs) for n in proposal.nodes for _, b in n.inputs if isinstance(b, FromBinding))
    if len(proposal.nodes) > limits.max_nodes: return Rejection("LIMIT_EXCEEDED", "NODES")
    if edge_count > limits.max_edges: return Rejection("LIMIT_EXCEEDED", "EDGES")
    if len(proposal.outputs) > limits.max_outputs: return Rejection("LIMIT_EXCEEDED", "OUTPUTS")

    # 2. unique ids; action and version present in the snapshot
    ids = [n.node_id for n in proposal.nodes]
    if len(set(ids)) != len(ids): return Rejection("DUPLICATE_NODE", sorted({i for i in ids if ids.count(i) > 1})[0])
    contracts = {}
    for node in proposal.nodes:
        contract = snapshot.get(node.action, node.action_version)
        if contract is None:
            return Rejection("UNKNOWN_ACTION_VERSION" if snapshot.knows(node.action) else "UNKNOWN_ACTION", node.node_id)
        contracts[node.node_id] = contract

    # 3. ports, types and sources
    by_id = {c.source_id: c for c in candidates}
    edges, typed, sources, clarifications = [], [], set(), []
    for node in proposal.nodes:
        contract = contracts[node.node_id]
        for port, binding in node.inputs:
            spec = contract.input(port)
            if spec is None: return Rejection("UNKNOWN_PORT", f"{node.node_id}.{port}")
            if isinstance(binding, FromBinding):
                if len(binding.refs) > spec.max_refs or (binding.listed and spec.max_refs == 1):
                    return Rejection("PORT_ARITY", f"{node.node_id}.{port}")
                for src, src_port in binding.refs:
                    producer = contracts.get(src)
                    out_type = producer.output(src_port) if producer else None
                    if out_type is None: return Rejection("UNKNOWN_PORT", f"{src}.{src_port}")
                    typed.append((out_type, spec.types, f"{src}.{src_port}->{node.node_id}.{port}"))
                    edges.append((src, src_port, node.node_id, port))
            else:
                if PortType.SOURCE_XLSX not in spec.types: return Rejection("PORT_TYPE_MISMATCH", f"source->{node.node_id}.{port}")
                ids_named = (binding.source_id,) if isinstance(binding, SourceBinding) else binding.source_ids
                for sid in ids_named:
                    candidate = by_id.get(sid)
                    if candidate is None: return Rejection("UNKNOWN_SOURCE", f"{node.node_id}.{port}")
                    if not _is_xlsx_candidate(candidate): return Rejection("PORT_TYPE_MISMATCH", f"{sid}->{node.node_id}.{port}")
                if isinstance(binding, AmbiguousSources):
                    clarifications.append(ClarificationRequired(node.node_id, port, tuple(binding.source_ids)))
                else:
                    sources.add((binding.source_id, by_id[binding.source_id].content_sha256))
        bound = {p for p, _ in node.inputs}
        for port, spec in contract.inputs:
            if spec.required and port not in bound: return Rejection("UNBOUND_REQUIRED_INPUT", f"{node.node_id}.{port}")

    # 4. literals against their specs (data-dependent names are checked against real data at run time)
        given = dict(node.literals)
        for name, value in given.items():
            spec = contract.literal(name)
            if spec is None or not spec.accepts(list(value) if isinstance(value, tuple) else value):
                return Rejection("LITERAL_INVALID", f"{node.node_id}.{name}")
        for name, spec in contract.literals:
            if spec.required and name not in given: return Rejection("LITERAL_INVALID", f"{node.node_id}.{name}")

    # 5a. acyclic. Checked on the resolved references before their types (disclosed deviation from the
    # Stage 2 §2.3 order): with the closed slice-1 port vocabulary every cycle also mismatches a type,
    # so checking types first would make CYCLE unreachable.
    order = _topological(ids, edges)
    if order is None: return Rejection("CYCLE", "")
    for out_type, accepted, detail in typed:
        if out_type not in accepted: return Rejection("PORT_TYPE_MISMATCH", detail)

    # 5b. every declared output is a report and every node feeds it
    if not proposal.outputs: return Rejection("UNREACHABLE_OUTPUT", "NO_DECLARED_OUTPUT")
    for node_id, port in proposal.outputs:
        producer = contracts.get(node_id)
        if producer is None or producer.output(port) is not PortType.REPORT_ARTIFACT:
            return Rejection("UNREACHABLE_OUTPUT", f"{node_id}.{port}")
    reached, frontier = set(), [n for n, _ in proposal.outputs]
    while frontier:
        current = frontier.pop()
        if current in reached: continue
        reached.add(current)
        frontier.extend(src for src, _, dst, _ in edges if dst == current)
    unused = sorted(set(ids) - reached)
    if unused: return Rejection("UNREACHABLE_OUTPUT", f"UNUSED_NODE:{unused[0]}")

    # 6. deterministic and qualified only (a SEMANTIC node is never compiled for execution in slice 1)
    for node_id in order:
        contract = contracts[node_id]
        if contract.mechanism is not Mechanism.DETERMINISTIC or contract.qualification == UNQUALIFIED:
            return Rejection("UNQUALIFIED_ACTION", node_id)

    # 7. a verifier covers every node, so every terminal output is recomputable
        if contract.verifier_coverage not in VERIFIER_COVERAGE: return Rejection("NO_VERIFIER_COVERAGE", node_id)

    if clarifications:
        return sorted(clarifications, key=lambda c: (c.node_id, c.port))[0]

    plan_nodes = []
    for node in sorted(proposal.nodes, key=lambda n: n.node_id):
        contract = contracts[node.node_id]
        inputs = tuple((port, ("from", binding.refs) if isinstance(binding, FromBinding) else ("source", binding.source_id))
                       for port, binding in node.inputs)
        plan_nodes.append(PlanNode(node.node_id, contract.action_id, contract.version, contract.qualification,
                                   contract.verifier_coverage, inputs, node.literals))
    return CompiledPlan(tuple(plan_nodes), tuple(sorted(edges)), tuple(sorted(sources)), tuple(proposal.outputs), order,
                        proposal.sha256, snapshot.sha256)
