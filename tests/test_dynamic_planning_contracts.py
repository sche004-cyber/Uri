"""Dynamic planning slice 1: proposal schema, PortType closure, canonical hashing, snapshots."""
from dataclasses import replace
import json

import pytest

from uri_v1.planning import actions
from uri_v1.planning.contracts import (UNQUALIFIED, CapabilityContract, CapabilitySnapshot, InputSpec, LiteralSpec,
                                                 PortType, ProposalInvalid, SemanticProposal, sha256_of)
from uri_v1.planning.provider_port import FixtureProvider, parse_raw

A = "a" * 32


def proposal(**over):
    base = {"schema_version": "uri.plan.proposal.v1", "outputs": ["w.report"], "cannot": [], "nodes": [
        {"id": "ia", "action": actions.INSPECT, "action_version": "1", "inputs": {"source": {"source": A}}, "literals": {}},
        {"id": "sa", "action": actions.SELECT, "action_version": "1", "inputs": {"structure": {"from": "ia.structure"}},
         "literals": {"sheets": ["Orders"]}},
        {"id": "w", "action": actions.WRITE, "action_version": "1", "inputs": {"items": {"from": ["sa.selection"]}}, "literals": {}}]}
    base.update(over)
    return base


def code_of(raw):
    with pytest.raises(ProposalInvalid) as exc: SemanticProposal.parse(raw)
    return exc.value.code


def test_port_type_vocabulary_is_closed():
    assert {t.value for t in PortType} == {"SOURCE_XLSX", "WORKBOOK_STRUCTURE", "STRUCTURE_SELECTION", "STRUCTURE_COMPARISON",
                                           "REPORT_ARTIFACT"}
    with pytest.raises(ValueError): PortType("string")
    with pytest.raises(ValueError): InputSpec(("WORKBOOK_STRUCTURE",))   # a raw string is not a PortType


@pytest.mark.parametrize("raw", [None, [], "text", 3])
def test_parse_refuses_non_objects(raw):
    assert code_of(raw) == "PROPOSAL_INVALID"


def test_parse_refuses_extra_and_missing_keys():
    assert code_of(dict(proposal(), approval="GRANTED")) == "PROPOSAL_INVALID"
    missing = proposal(); del missing["cannot"]
    assert code_of(missing) == "PROPOSAL_INVALID"
    for extra in ({"approval": "GRANTED"}, {"effect": "WRITE_BACK"}, {"handle": "h1"}):
        p = proposal(); p["nodes"][0].update(extra)
        assert code_of(p) == "PROPOSAL_INVALID"
    p = proposal(); p["nodes"][0]["inputs"]["source"] = {"source": A, "path": "/tmp/x.xlsx"}
    assert code_of(p) == "PROPOSAL_INVALID"
    assert code_of(proposal(schema_version="uri.plan.proposal.v2")) == "PROPOSAL_INVALID"


@pytest.mark.parametrize("source", ["C:/Users/x/wb_a.xlsx", "/home/x/wb_a.xlsx", "wb_a.xlsx", "hdl:7f3a:ia.structure",
                                    "A" * 32, "a" * 31, "latest", ""])
def test_parse_refuses_paths_handles_and_non_ids(source):
    p = proposal(); p["nodes"][0]["inputs"]["source"] = {"source": source}
    assert code_of(p) == "PROPOSAL_INVALID"


def test_parse_refuses_oversize():
    assert code_of(proposal(cannot=[{"reason_code": "X", "text": "t"}] * 17)) == "LIMIT_EXCEEDED"
    p = proposal(); p["nodes"][1]["literals"]["sheets"] = ["s%d" % i for i in range(33)]
    assert code_of(p) == "LIMIT_EXCEEDED"
    p = proposal(); p["nodes"][1]["literals"]["sheets"] = ["x" * 5000] * 20
    assert code_of(p) == "LIMIT_EXCEEDED"
    p = proposal(); p["nodes"][2]["inputs"]["items"]["from"] = ["sa.selection"] * 9
    assert code_of(p) == "LIMIT_EXCEEDED"
    p = proposal(); p["nodes"][1]["literals"]["sheets"] = ["bad\x00name"]
    assert code_of(p) == "PROPOSAL_INVALID"


def test_raw_text_parsing_is_strict():
    assert parse_raw('{"a": 1, "a": 2}') is None       # duplicate keys
    assert parse_raw("[1, 2]") is None
    assert parse_raw("{") is None
    assert parse_raw(None) is None
    result = FixtureProvider('{"schema_version":').propose({}, {}, ())
    assert result.error == "PROPOSAL_INVALID" and result.parsed is None
    assert FixtureProvider(fail="timeout").propose({}, {}, ()).error == "PROVIDER_UNAVAILABLE"


def test_canonical_hash_ignores_node_order_and_key_order_but_keeps_item_order():
    a = SemanticProposal.parse(proposal())
    reordered = proposal(); reordered["nodes"] = list(reversed(reordered["nodes"]))
    reordered = json.loads(json.dumps(reordered, sort_keys=True))
    assert SemanticProposal.parse(reordered).sha256 == a.sha256
    swapped = proposal(); swapped["nodes"][2]["inputs"]["items"]["from"] = ["sa.selection", "sa.selection"]
    swapped2 = proposal(); swapped2["nodes"][2]["inputs"]["items"]["from"] = ["sa.selection"]
    assert SemanticProposal.parse(swapped).sha256 != SemanticProposal.parse(swapped2).sha256


def test_canonical_hash_is_unicode_exact():
    p1 = proposal(); p1["nodes"][1]["literals"]["sheets"] = ["Café"]
    p2 = proposal(); p2["nodes"][1]["literals"]["sheets"] = ["Cafe\u0301"]
    assert SemanticProposal.parse(p1).sha256 != SemanticProposal.parse(p2).sha256   # no normalization, no folding
    assert sha256_of({"b": 1, "a": "é"}) == sha256_of({"a": "é", "b": 1})


def test_snapshot_hash_tracks_contract_changes():
    snap = actions.snapshot()
    assert snap.sha256 == actions.snapshot().sha256
    catalog = actions.default_catalog()
    bumped = tuple((replace(c, version="2") if c.action_id == actions.SELECT else c, fn) for c, fn in catalog)
    renamed = actions.renamed(catalog, actions.INSPECT, "uri.plan.workbook.load_workbook_structure")
    assert len({snap.sha256, actions.snapshot(bumped).sha256, actions.snapshot(renamed).sha256}) == 3
    with pytest.raises(ValueError): CapabilitySnapshot((catalog[0][0], catalog[0][0]))


def test_contracts_are_qualified_by_the_pinned_record():
    assert all(c.qualification == actions.QUALIFICATION_SHA256 for c in actions.snapshot().contracts)


def test_tampered_qualification_record_fails_closed(tmp_path, monkeypatch):
    fake = tmp_path / "q.json"; fake.write_bytes(actions.QUALIFICATION_PATH.read_bytes().replace(b"QUALIFIED", b"QUALIFIEd", 1))
    monkeypatch.setattr(actions, "QUALIFICATION_PATH", fake)
    assert all(c.qualification == UNQUALIFIED for c in actions.snapshot().contracts)


def test_contract_metadata_is_required_never_defaulted():
    good = actions.snapshot().contracts[0]
    for bad in ({"mechanism": "DETERMINISTIC"}, {"verifier_coverage": "oracle.anything"}, {"outputs": ()},
                {"qualification": "maybe"}, {"action_id": "Bad Name"}, {"version": "v1"}):
        with pytest.raises(ValueError): replace(good, **bad)
    with pytest.raises(ValueError): LiteralSpec("enum", True)
    with pytest.raises(ValueError): CapabilityContract(**{**good.__dict__, "inputs": (("x", "SOURCE_XLSX"),)})


# -- repair round after the independent audit of c5d47a0 (N2, N8) -------------------------------------

def test_deeply_nested_provider_text_is_a_typed_invalid_proposal():
    for depth in (100_000, 20):
        raw = '{"schema_version":"uri.plan.proposal.v1","nodes":[],"outputs":[],"cannot":' + "[" * depth + "]" * depth + "}"
        result = FixtureProvider(raw).propose({}, {}, ())
        assert result.parsed is None and result.error == "PROPOSAL_INVALID"


def test_oversized_provider_text_is_refused_before_parsing():
    from uri_v1.planning.provider_port import MAX_RAW_BYTES
    raw = '{"schema_version":"uri.plan.proposal.v1","nodes":[],"outputs":[],"cannot":[],"pad":"' + "x" * MAX_RAW_BYTES + '"}'
    assert parse_raw(raw) is None


def test_deeply_nested_proposal_dict_is_rejected_not_crashed():
    from uri_v1.planning.compiler import compile_proposal
    nested = cur = []
    for _ in range(5000):
        nxt = []; cur.append(nxt); cur = nxt
    result = compile_proposal({"schema_version": "uri.plan.proposal.v1", "nodes": [], "outputs": [], "cannot": nested},
                              actions.snapshot(), ())
    assert (result.code, result.detail) == ("PROPOSAL_INVALID", "NESTING_DEPTH")
    with pytest.raises(ProposalInvalid, match="PROPOSAL_INVALID"):
        SemanticProposal.parse(proposal(cannot=[[[[[[[[[[[[[[[[["x"]]]]]]]]]]]]]]]]]))
    assert SemanticProposal.parse(proposal())                                       # a normal proposal still parses


def test_run_proposal_turns_a_raising_provider_into_a_typed_outcome():
    from uri_v1.planning.runner import run_proposal
    class Broken:
        provider_id, model_id, config_sha256 = "broken", "none", ""
        def propose(self, *a): raise TimeoutError("socket")
    outcome, plan, result = run_proposal(Broken(), actions.snapshot(), (), runner=None, goal_context={}, task_id="t",
                                         trace_id="t", session_id="s")
    assert outcome.status == "NOT_ATTEMPTED" and outcome.reason == "PROVIDER_UNAVAILABLE" and plan is None
