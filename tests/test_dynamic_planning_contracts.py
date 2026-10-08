"""Tests for dynamic planning contracts, schemas, PortType closure and snapshots (G1)."""
from __future__ import annotations

import pytest

from uri_v1.execution.planning.actions import canonical_contracts, snapshot
from uri_v1.execution.planning.contracts import (
    CapabilityContract,
    CapabilitySnapshot,
    InputPortSpec,
    LiteralSpec,
    PortType,
    ProposalInvalid,
    SemanticProposal,
)


def test_port_type_closure():
    """PortType is a strict closed enum."""
    expected_members = {
        "SOURCE_XLSX",
        "WORKBOOK_STRUCTURE",
        "STRUCTURE_SELECTION",
        "STRUCTURE_COMPARISON",
        "REPORT_ARTIFACT",
    }
    assert {p.value for p in PortType} == expected_members


def test_semantic_proposal_parse_valid():
    """Valid proposal parses and computes sha256."""
    raw = {
        "schema_version": "uri.plan.proposal.v1",
        "nodes": [
          {
            "id": "node1",
            "action": "uri.plan.workbook.inspect_structure",
            "action_version": "1",
            "inputs": {"source": {"source": "src_1"}},
            "literals": {}
          }
        ],
        "outputs": [{"node_id": "node1", "port": "structure"}],
        "cannot": []
    }
    proposal = SemanticProposal.parse(raw)
    assert proposal.schema_version == "uri.plan.proposal.v1"
    assert len(proposal.nodes) == 1
    assert proposal.nodes[0].id == "node1"
    assert proposal.raw_sha256 is not None
    assert len(proposal.raw_sha256) == 64


def test_semantic_proposal_rejects_extra_keys():
    """Proposal with undeclared top-level keys is rejected."""
    raw = {
        "schema_version": "uri.plan.proposal.v1",
        "nodes": [],
        "outputs": [],
        "cannot": [],
        "extra_unauthorized_key": "injected"
    }
    with pytest.raises(ProposalInvalid) as exc:
        SemanticProposal.parse(raw)
    assert exc.value.code == "PROPOSAL_EXTRA_KEYS"


def test_semantic_proposal_rejects_invalid_schema():
    """Proposal with invalid schema version is rejected."""
    raw = {
        "schema_version": "uri.plan.proposal.v999",
        "nodes": [],
        "outputs": [],
        "cannot": []
    }
    with pytest.raises(ProposalInvalid) as exc:
        SemanticProposal.parse(raw)
    assert exc.value.code == "PROPOSAL_SCHEMA_INVALID"


def test_capability_snapshot_content_hashing():
    """Snapshot sha256 is deterministic and invariant to insertion order."""
    contracts = list(canonical_contracts())
    snap1 = CapabilitySnapshot.create(contracts)
    snap2 = CapabilitySnapshot.create(list(reversed(contracts)))
    assert snap1.sha256 == snap2.sha256
    assert len(snap1.sha256) == 64


def test_action_rename_by_ports():
    """Renaming an action while preserving its input/output PortTypes preserves contract compatibility."""
    contract = CapabilityContract(
        action_id="custom.renamed.inspect",
        version="1",
        mechanism="DETERMINISTIC",
        inputs={"source": InputPortSpec("source", (PortType.SOURCE_XLSX,), required=True)},
        outputs={"structure": PortType.WORKBOOK_STRUCTURE},
        literals={},
        effect="READ_ONLY",
        approval="NONE",
        verifier_coverage="",
        qualification="QUAL-TEST-01",
    )
    snap = CapabilitySnapshot.create([contract])
    retrieved = snap.get("custom.renamed.inspect", "1")
    assert retrieved is not None
    assert retrieved.inputs["source"].allowed_types == (PortType.SOURCE_XLSX,)
    assert retrieved.outputs["structure"] == PortType.WORKBOOK_STRUCTURE
