"""Tests for deterministic proposal compiler and DAG validator (G1)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from uri_v1.execution.planning.actions import canonical_contracts, snapshot
from uri_v1.execution.planning.compiler import compile
from uri_v1.execution.planning.contracts import (
    CapabilityContract,
    CapabilitySnapshot,
    CompiledPlan,
    InputPortSpec,
    LiteralSpec,
    PortType,
    Rejection,
    SemanticProposal,
)


def load_fixture_cases():
    fixture_path = Path("fixtures/dynamic_planning/qualification_cases.json")
    return json.loads(fixture_path.read_bytes())["cases"]


def test_compiler_valid_two_workbook_compare():
    """Gate 1: Canonical valid two-workbook plan compiles to a verified DAG."""
    cases = load_fixture_cases()
    raw = cases["valid_two_workbook_compare"]["proposal"]
    proposal = SemanticProposal.parse(raw)
    snap = snapshot()
    candidates = {"src_fin_2025": "dummy_sha_1", "src_fin_2026": "dummy_sha_2"}

    result = compile(proposal, snap, candidates)
    assert isinstance(result, CompiledPlan)
    assert len(result.nodes) == 6
    assert len(result.edges) == 5
    assert len(result.sources) == 2
    assert result.sha256 is not None


def test_compiler_arbitrary_rename_with_same_ports():
    """Gate 1: Renaming an action while keeping declared ports still compiles."""
    contracts = list(canonical_contracts())
    # Replace uri.plan.structure.compare with renamed action
    renamed = CapabilityContract(
        action_id="uri.plan.custom_comparator",
        version="1",
        mechanism="DETERMINISTIC",
        inputs={
            "left": InputPortSpec("left", (PortType.STRUCTURE_SELECTION,), required=True),
            "right": InputPortSpec("right", (PortType.STRUCTURE_SELECTION,), required=True),
        },
        outputs={"comparison": PortType.STRUCTURE_COMPARISON},
        literals={
            "match_on": LiteralSpec("match_on", expected_type="str", required=True, allowed_values=("sheet_name",)),
        },
        effect="READ_ONLY",
        approval="NONE",
        verifier_coverage="",
        qualification="QUAL-CUSTOM-01",
    )
    # Replace in contracts
    new_contracts = [c for c in contracts if c.action_id != "uri.plan.structure.compare"] + [renamed]
    custom_snap = CapabilitySnapshot.create(new_contracts)

    cases = load_fixture_cases()
    raw = cases["valid_two_workbook_compare"]["proposal"]
    # Change compare_1 action to the renamed action
    for n in raw["nodes"]:
        if n["id"] == "compare_1":
            n["action"] = "uri.plan.custom_comparator"

    proposal = SemanticProposal.parse(raw)
    candidates = {"src_fin_2025": "dummy_sha_1", "src_fin_2026": "dummy_sha_2"}
    result = compile(proposal, custom_snap, candidates)
    assert isinstance(result, CompiledPlan)
    assert any(n.action_id == "uri.plan.custom_comparator" for n in result.nodes)


def test_compiler_unsupported_cannot_only():
    """Gate 1: Unsupported goal (cannot[] only) gives typed Rejection, no executable success."""
    cases = load_fixture_cases()
    raw = cases["unsupported_cannot_only"]["proposal"]
    proposal = SemanticProposal.parse(raw)
    snap = snapshot()

    result = compile(proposal, snap, {})
    assert isinstance(result, Rejection)
    assert result.code == "UNSUPPORTED_GOAL"


def test_compiler_cycle_detection():
    """Gate 1: Cyclic dependency graph is rejected."""
    cases = load_fixture_cases()
    raw = cases["cycle_detection"]["proposal"]
    proposal = SemanticProposal.parse(raw)
    
    transform_contract = CapabilityContract(
        action_id="test.action.transform",
        version="1",
        mechanism="DETERMINISTIC",
        inputs={"item": InputPortSpec("item", (PortType.STRUCTURE_SELECTION,), required=True)},
        outputs={"item": PortType.STRUCTURE_SELECTION},
        literals={},
        effect="READ_ONLY",
        approval="NONE",
        verifier_coverage="report_recomputes",
        qualification="QUAL-TEST-01",
    )
    snap = CapabilitySnapshot.create([transform_contract])

    result = compile(proposal, snap, {})
    assert isinstance(result, Rejection)
    assert result.code == "CYCLE_DETECTED"


def test_compiler_unknown_source_candidate():
    """Gate 1: Reference to un-candidated source is rejected."""
    cases = load_fixture_cases()
    raw = cases["unknown_source_candidate"]["proposal"]
    proposal = SemanticProposal.parse(raw)
    snap = snapshot()
    candidates = {"authorized_source_1": "sha"}

    result = compile(proposal, snap, candidates)
    assert isinstance(result, Rejection)
    assert result.code == "UNKNOWN_SOURCE_CANDIDATE"


def test_compiler_port_type_mismatch():
    """Gate 1: Type mismatch between producer output and consumer input is rejected."""
    cases = load_fixture_cases()
    raw = cases["port_type_mismatch"]["proposal"]
    proposal = SemanticProposal.parse(raw)
    snap = snapshot()
    candidates = {"src_fin_2025": "sha"}

    result = compile(proposal, snap, candidates)
    assert isinstance(result, Rejection)
    assert result.code == "TYPE_MISMATCH"


def test_compiler_preserves_proposed_order_for_non_dependent_nodes():
    """Gate 1: Non-dependent operations preserve proposed order (stable topological tie-break)."""
    cases = load_fixture_cases()
    raw = cases["valid_two_workbook_compare"]["proposal"]

    # In raw, inspect_1 is before inspect_2.
    # Now let's reverse them in proposal: inspect_2 before inspect_1
    reversed_raw = dict(raw)
    nodes = list(raw["nodes"])
    # Swap nodes 0 and 1
    nodes[0], nodes[1] = nodes[1], nodes[0]
    reversed_raw["nodes"] = nodes

    proposal = SemanticProposal.parse(reversed_raw)
    snap = snapshot()
    candidates = {"src_fin_2025": "dummy_sha_1", "src_fin_2026": "dummy_sha_2"}
    result = compile(proposal, snap, candidates)
    assert isinstance(result, CompiledPlan)
    assert result.nodes[0].node_id == "inspect_2"
    assert result.nodes[1].node_id == "inspect_1"
