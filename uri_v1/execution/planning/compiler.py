"""Deterministic proposal compiler and DAG validator (Stage 2, Slice 1).

Validates semantic proposals against capability contracts, typed ports,
declared sources, acyclicity and verifier coverage. Preserves proposal ordering
and rejects experimental fallback logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contracts import (
    BoundSource,
    CapabilityContract,
    CapabilitySnapshot,
    CompiledPlan,
    LiteralSpec,
    PartialPlan,
    PlanEdge,
    PlanNode,
    PortRef,
    PortType,
    ProposalCannot,
    ProposalNode,
    ProposalOutput,
    Rejection,
    SemanticProposal,
    SourceRef,
)


@dataclass(frozen=True)
class CompilerLimits:
    """Strict limits to prevent unbounded DAG or resource explosion."""
    max_nodes: int = 16
    max_edges: int = 32
    max_literals_per_node: int = 16
    max_literal_string_len: int = 256


_DEFAULT_LIMITS = CompilerLimits()


def compile(
    proposal: SemanticProposal,
    snapshot: CapabilitySnapshot,
    candidates: Sequence[str] | Mapping[str, str] | None = None,
    *,
    limits: CompilerLimits | None = None,
) -> CompiledPlan | Rejection | PartialPlan:
    """Deterministically compile and validate a SemanticProposal against a CapabilitySnapshot.

    Checks run in strict sequence with typed reasons:
    1. Schema and size limits;
    2. Unique node IDs; action + version present in snapshot;
    3. Every required input port bound; typed port compatibility; valid source candidates;
    4. Literal validation against contract LiteralSpec;
    5. Acyclic DAG (Kahn's algorithm) and output reachability;
    6. Mechanism DETERMINISTIC and qualified;
    7. Verifier coverage for terminal outputs.
    """
    lim = limits or _DEFAULT_LIMITS

    # Step 1: Empty or unsupported goal checks & size limits
    if not proposal.nodes:
        if proposal.cannot:
            reasons = "; ".join(f"{c.reason_code}: {c.text}" for c in proposal.cannot)
            return Rejection("UNSUPPORTED_GOAL", f"Proposal declared cannot: {reasons}")
        return Rejection("EMPTY_PROPOSAL", "Proposal contains zero executable nodes")

    if len(proposal.nodes) > lim.max_nodes:
        return Rejection("NODE_LIMIT_EXCEEDED", f"Node count {len(proposal.nodes)} exceeds limit {lim.max_nodes}")

    if not proposal.outputs:
        return Rejection("NO_OUTPUTS_DECLARED", "Proposal must declare at least one desired output")

    if len(proposal.outputs) > lim.max_nodes:
        return Rejection("OUTPUT_LIMIT_EXCEEDED", f"Output count {len(proposal.outputs)} exceeds limit {lim.max_nodes}")

    # Build candidate lookup
    candidate_map: dict[str, str] = {}
    if candidates is not None:
        if isinstance(candidates, Mapping):
            candidate_map = dict(candidates)
        else:
            candidate_map = {str(c): "" for c in candidates}

    # Step 2: Unique node IDs and action presence in snapshot
    node_ids: set[str] = set()
    node_by_id: dict[str, ProposalNode] = {}
    contract_by_node_id: dict[str, CapabilityContract] = {}

    for node in proposal.nodes:
        if node.id in node_ids:
            return Rejection("DUPLICATE_NODE_ID", f"Duplicate node ID: {node.id}")
        node_ids.add(node.id)
        node_by_id[node.id] = node

        contract = snapshot.get(node.action, node.action_version)
        if contract is None:
            return Rejection("UNKNOWN_ACTION", f"Action '{node.action}' version '{node.action_version}' not in snapshot")
        contract_by_node_id[node.id] = contract

    # Step 3: Input ports and typed bindings
    edges: list[PlanEdge] = []
    referenced_sources: dict[str, str] = {}

    for node in proposal.nodes:
        contract = contract_by_node_id[node.id]

        # Check required input ports are present
        for port_name, port_spec in contract.inputs.items():
            if port_spec.required and port_name not in node.inputs:
                return Rejection("MISSING_INPUT_PORT", f"Node '{node.id}' missing required input port '{port_name}'")

        # Check all provided inputs are declared in contract
        for port_name, binding in node.inputs.items():
            if port_name not in contract.inputs:
                return Rejection("UNKNOWN_INPUT_PORT", f"Node '{node.id}' input '{port_name}' not in contract")

            port_spec = contract.inputs[port_name]

            if isinstance(binding, SourceRef):
                # Must accept SOURCE_XLSX
                if PortType.SOURCE_XLSX not in port_spec.allowed_types:
                    return Rejection(
                        "TYPE_MISMATCH",
                        f"Node '{node.id}' port '{port_name}' cannot bind SourceRef (expects {[t.value for t in port_spec.allowed_types]})"
                    )
                # Source must be in trusted candidates
                if candidates is not None and binding.source_id not in candidate_map:
                    return Rejection("UNKNOWN_SOURCE_CANDIDATE", f"Source ID '{binding.source_id}' not in trusted candidates")
                referenced_sources[binding.source_id] = candidate_map.get(binding.source_id, "")

            elif isinstance(binding, PortRef):
                # Producer node must exist
                if binding.from_node not in node_by_id:
                    return Rejection("PRODUCER_NOT_FOUND", f"Node '{node.id}' input '{port_name}' references nonexistent producer '{binding.from_node}'")
                producer_contract = contract_by_node_id[binding.from_node]

                # Output port must exist on producer
                if binding.from_port not in producer_contract.outputs:
                    return Rejection(
                        "OUTPUT_PORT_NOT_FOUND",
                        f"Producer '{binding.from_node}' has no output port '{binding.from_port}'"
                    )

                producer_port_type = producer_contract.outputs[binding.from_port]
                # Type compatibility: exact equal type, no coercion
                if producer_port_type not in port_spec.allowed_types:
                    return Rejection(
                        "TYPE_MISMATCH",
                        f"Node '{node.id}' port '{port_name}' expects {[t.value for t in port_spec.allowed_types]}, got {producer_port_type.value} from '{binding.from_node}.{binding.from_port}'"
                    )

                edges.append(PlanEdge(
                    from_node=binding.from_node,
                    from_port=binding.from_port,
                    to_node=node.id,
                    to_port=port_name,
                ))

    if len(edges) > lim.max_edges:
        return Rejection("EDGE_LIMIT_EXCEEDED", f"Edge count {len(edges)} exceeds limit {lim.max_edges}")

    # Step 4: Literal validation against LiteralSpec
    for node in proposal.nodes:
        contract = contract_by_node_id[node.id]

        if len(node.literals) > lim.max_literals_per_node:
            return Rejection("LITERAL_LIMIT_EXCEEDED", f"Node '{node.id}' exceeds max literals limit")

        for lit_name, lit_spec in contract.literals.items():
            if lit_spec.required and lit_name not in node.literals:
                return Rejection("MISSING_LITERAL", f"Node '{node.id}' missing required literal '{lit_name}'")

        for lit_name, lit_val in node.literals.items():
            if lit_name not in contract.literals:
                return Rejection("UNKNOWN_LITERAL", f"Node '{node.id}' has undeclared literal '{lit_name}'")

            lit_spec = contract.literals[lit_name]

            # Type check
            if lit_spec.expected_type == "str":
                if not isinstance(lit_val, str):
                    return Rejection("INVALID_LITERAL_TYPE", f"Literal '{lit_name}' in '{node.id}' must be str")
                if len(lit_val) > lit_spec.max_length:
                    return Rejection("INVALID_LITERAL_LENGTH", f"Literal '{lit_name}' in '{node.id}' exceeds max length {lit_spec.max_length}")
                if lit_spec.allowed_values and lit_val not in lit_spec.allowed_values:
                    return Rejection("INVALID_LITERAL_VALUE", f"Literal '{lit_name}' in '{node.id}' must be one of {lit_spec.allowed_values}")

            elif lit_spec.expected_type == "list":
                if not isinstance(lit_val, (list, tuple)):
                    return Rejection("INVALID_LITERAL_TYPE", f"Literal '{lit_name}' in '{node.id}' must be list")
                if len(lit_val) > lit_spec.max_length:
                    return Rejection("INVALID_LITERAL_LENGTH", f"Literal '{lit_name}' list in '{node.id}' exceeds length limit")
                if lit_spec.element_type == "str":
                    for item in lit_val:
                        if not isinstance(item, str) or len(item) > lim.max_literal_string_len:
                            return Rejection("INVALID_LITERAL_ELEMENT", f"Element in '{lit_name}' must be str within length limit")

            elif lit_spec.expected_type == "int":
                if type(lit_val) is not int:
                    return Rejection("INVALID_LITERAL_TYPE", f"Literal '{lit_name}' in '{node.id}' must be int")

            elif lit_spec.expected_type == "bool":
                if not isinstance(lit_val, bool):
                    return Rejection("INVALID_LITERAL_TYPE", f"Literal '{lit_name}' in '{node.id}' must be bool")

    # Step 5: Acyclicity (Kahn's algorithm) & stable topological sort
    in_degree: dict[str, int] = {n.id: 0 for n in proposal.nodes}
    adjacency: dict[str, list[str]] = {n.id: [] for n in proposal.nodes}

    for edge in edges:
        in_degree[edge.to_node] += 1
        adjacency[edge.from_node].append(edge.to_node)

    # Initial zero-indegree nodes, preserving exact proposal appearance order
    zero_in = [n.id for n in proposal.nodes if in_degree[n.id] == 0]
    topo_order: list[str] = []

    # Map node id to original proposal index for stable tie-breaking
    orig_index = {n.id: idx for idx, n in enumerate(proposal.nodes)}

    while zero_in:
        # Stable: pick node that appeared earliest in proposal
        zero_in.sort(key=lambda nid: orig_index[nid])
        curr = zero_in.pop(0)
        topo_order.append(curr)

        for neighbor in adjacency[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                zero_in.append(neighbor)

    if len(topo_order) < len(proposal.nodes):
        return Rejection("CYCLE_DETECTED", "Cycle detected in proposal dependency graph")

    # Check output reachability
    for out in proposal.outputs:
        if out.node_id not in node_by_id:
            return Rejection("UNREACHABLE_OUTPUT", f"Output node '{out.node_id}' does not exist")
        contract = contract_by_node_id[out.node_id]
        if out.port not in contract.outputs:
            return Rejection("OUTPUT_PORT_NOT_FOUND", f"Output node '{out.node_id}' has no output port '{out.port}'")

    # Step 6: Mechanism DETERMINISTIC and qualified
    for node_id in topo_order:
        contract = contract_by_node_id[node_id]
        if contract.mechanism != "DETERMINISTIC":
            return Rejection("SEMANTIC_NODE_NOT_EXECUTABLE", f"Node '{node_id}' has SEMANTIC mechanism, unexecutable in Slice 1")
        if contract.qualification == "UNQUALIFIED" or not contract.qualification:
            return Rejection("UNQUALIFIED_ACTION", f"Action for node '{node_id}' is UNQUALIFIED")

    # Step 7: Verifier coverage for terminal outputs
    for out in proposal.outputs:
        contract = contract_by_node_id[out.node_id]
        if not contract.verifier_coverage:
            return Rejection("UNVERIFIABLE_OUTPUT", f"Terminal output node '{out.node_id}' has no verifier coverage")

    # Construct compiled nodes in strict topological order
    compiled_nodes: list[PlanNode] = []
    for node_id in topo_order:
        prop_node = node_by_id[node_id]
        contract = contract_by_node_id[node_id]
        compiled_nodes.append(PlanNode(
            node_id=prop_node.id,
            action_id=contract.action_id,
            version=contract.version,
            qualification_sha=contract.qualification,
            inputs=prop_node.inputs,
            literals=prop_node.literals,
        ))

    bound_sources = tuple(
        BoundSource(source_id=sid, content_sha256=sha)
        for sid, sha in sorted(referenced_sources.items())
    )

    return CompiledPlan.create(
        nodes=tuple(compiled_nodes),
        edges=tuple(edges),
        sources=bound_sources,
        outputs=proposal.outputs,
        proposal_sha256=proposal.raw_sha256,
        snapshot_sha256=snapshot.sha256,
    )
