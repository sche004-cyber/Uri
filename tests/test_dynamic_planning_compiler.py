"""Dynamic planning slice 1, gate G1: the deterministic compiler (pure; no filesystem)."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from uri_v1.execution.planning import actions
from uri_v1.execution.planning.compiler import compile_proposal
from uri_v1.execution.planning.contracts import (UNQUALIFIED, CompiledPlan, Limits, Mechanism, Rejection, SourceCandidate)

BATTERY = json.loads((Path(__file__).resolve().parents[1] / "fixtures/dynamic_planning/qualification_cases.json").read_bytes())
CASES = {c["id"]: c for c in BATTERY["cases"]}
LABELS = ("$src:root1/wb_a.xlsx", "$src:root1/wb_b.xlsx", "$src:root1/wb_malformed.xlsx", "$src:root1/wb_big_header.xlsx",
          "$src:root2/wb_a.xlsx")
IDS = {label: hashlib.sha256(label.encode()).hexdigest()[:32] for label in LABELS}
CANDIDATES = tuple(SourceCandidate(IDS[l], l.split("/", 1)[1], "spreadsheet", hashlib.sha256(l.encode()).hexdigest())
                   for l in LABELS)
RENAMED = actions.snapshot(actions.renamed(actions.default_catalog(), actions.INSPECT, "uri.plan.workbook.load_workbook_structure"))


def sub(value):
    if isinstance(value, str): return IDS.get(value, value)
    if isinstance(value, list): return [sub(v) for v in value]
    if isinstance(value, dict): return {k: sub(v) for k, v in value.items()}
    return value


def compiled(case_id, snapshot=None, **kw):
    case = CASES[case_id]
    snap = snapshot or (RENAMED if case.get("snapshot") == "renamed_inspect" else actions.snapshot())
    return compile_proposal(sub(case["proposal"]), snap, CANDIDATES, **kw)


@pytest.mark.parametrize("case_id,code", [("C05", "UNKNOWN_ACTION"), ("C06", "DUPLICATE_NODE"), ("C07", "UNKNOWN_PORT"),
                                          ("C08", "PORT_TYPE_MISMATCH"), ("C09", "CYCLE"), ("C10", "UNBOUND_REQUIRED_INPUT"),
                                          ("C11", "UNKNOWN_ACTION_VERSION"), ("C12", "NO_EXECUTABLE_PLAN"),
                                          ("C13", "LIMIT_EXCEEDED"), ("C14", "UNREACHABLE_OUTPUT"), ("C25", "PROPOSAL_INVALID")])
def test_battery_rejections(case_id, code):
    result = compiled(case_id)
    assert isinstance(result, Rejection) and result.code == code, result


@pytest.mark.parametrize("case_id", ["C01", "C02", "C03", "C04", "C33"])
def test_battery_compiles(case_id):
    assert isinstance(compiled(case_id), CompiledPlan)


def test_reversed_node_order_gives_the_same_plan():
    assert compiled("C01").sha256 == compiled("C02").sha256


def test_repeated_instances_branch_and_join_are_kept():
    plan = compiled("C01")
    assert [n.action_id for n in plan.nodes].count(actions.INSPECT) == 2
    assert [n.action_id for n in plan.nodes].count(actions.SELECT) == 2
    assert ("sa", "selection", "cmp", "left") in plan.edges and ("sb", "selection", "cmp", "right") in plan.edges
    assert plan.order.index("cmp") > max(plan.order.index("sa"), plan.order.index("sb"))
    two_consumers = compiled("C03")
    assert {("ia", "structure", "s1", "structure"), ("ia", "structure", "s2", "structure")} <= set(two_consumers.edges)


def test_non_commuting_item_order_is_preserved():
    forward = compiled("C27")
    p = sub(CASES["C27"]["proposal"])
    p["nodes"][5]["inputs"]["items"]["from"] = list(reversed(p["nodes"][5]["inputs"]["items"]["from"]))
    backward = compile_proposal(p, actions.snapshot(), CANDIDATES)
    items = lambda plan: dict(plan.node("w").inputs)["items"][1]
    assert items(forward) == (("cmp", "comparison"), ("sa", "selection"))
    assert items(backward) == (("sa", "selection"), ("cmp", "comparison"))
    assert forward.sha256 != backward.sha256


def test_rename_with_same_ports_still_composes_and_keeps_coverage():
    plan = compiled("C04")
    assert plan.node("ia").action_id == "uri.plan.workbook.load_workbook_structure"
    assert plan.node("ia").verifier_coverage == "oracle.inspect_structure.v1"


def test_plan_binds_sources_by_id_and_hash():
    plan = compiled("C01")
    by = {c.source_id: c.content_sha256 for c in CANDIDATES}
    assert set(plan.sources) == {(IDS[LABELS[0]], by[IDS[LABELS[0]]]), (IDS[LABELS[1]], by[IDS[LABELS[1]]])}
    assert plan.task_class == "PLANNED_STRUCTURE_REPORT@" + plan.sha256 and len(plan.task_class) == 89


def test_edge_and_output_limits():
    p = sub(CASES["C01"]["proposal"])
    assert compile_proposal(p, actions.snapshot(), CANDIDATES, limits=Limits(max_edges=4)).code == "LIMIT_EXCEEDED"
    assert compile_proposal(p, actions.snapshot(), CANDIDATES, limits=Limits(max_nodes=5)).code == "LIMIT_EXCEEDED"
    p["outputs"] = ["w.report", "cmp.comparison"]
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "LIMIT_EXCEEDED"


def test_literals_are_checked_against_their_specs():
    for literals in ({"sheets": []}, {"sheets": ["Orders", "Orders"]}, {"sheets": "Orders"}, {}, {"sheets": ["Orders"], "sheet": ["x"]}):
        p = sub(CASES["C01"]["proposal"]); p["nodes"][2]["literals"] = literals
        assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "LITERAL_INVALID", literals
    p = sub(CASES["C01"]["proposal"]); p["nodes"][4]["literals"] = {"match_on": "position"}
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "LITERAL_INVALID"


def test_unused_node_and_missing_outputs_are_unreachable():
    p = sub(CASES["C01"]["proposal"]); p["outputs"] = []
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "UNREACHABLE_OUTPUT"
    p = sub(CASES["C01"]["proposal"])
    p["nodes"].append({"id": "extra", "action": actions.INSPECT, "action_version": "1",
                       "inputs": {"source": {"source": IDS[LABELS[1]]}}, "literals": {}})
    r = compile_proposal(p, actions.snapshot(), CANDIDATES)
    assert r.code == "UNREACHABLE_OUTPUT" and r.detail == "UNUSED_NODE:extra"


def test_cannot_with_nodes_is_not_executable_in_slice_1():
    p = sub(CASES["C01"]["proposal"]); p["cannot"] = [{"reason_code": "OUT_OF_SCOPE", "text": "email the vendor"}]
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "PARTIAL_NOT_SUPPORTED"


def test_single_port_refuses_a_list_and_multi_port_arity():
    p = sub(CASES["C01"]["proposal"]); p["nodes"][2]["inputs"]["structure"]["from"] = ["ia.structure"]
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "PORT_ARITY"
    p = sub(CASES["C01"]["proposal"]); p["nodes"][5]["inputs"]["items"]["from"] = ["cmp.comparison"] * 5
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "PORT_ARITY"


def test_unknown_input_port_and_source_on_a_non_source_port():
    p = sub(CASES["C01"]["proposal"]); p["nodes"][2]["inputs"]["structures"] = {"from": "ia.structure"}
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "UNKNOWN_PORT"
    p = sub(CASES["C01"]["proposal"]); p["nodes"][2]["inputs"]["structure"] = {"source": IDS[LABELS[0]]}
    assert compile_proposal(p, actions.snapshot(), CANDIDATES).code == "PORT_TYPE_MISMATCH"


def test_non_spreadsheet_candidate_is_a_type_mismatch():
    cands = CANDIDATES + (SourceCandidate("c" * 32, "notes.txt", "document", "d" * 64),)
    p = sub(CASES["C01"]["proposal"]); p["nodes"][0]["inputs"]["source"] = {"source": "c" * 32}
    assert compile_proposal(p, actions.snapshot(), cands).code == "PORT_TYPE_MISMATCH"


def test_unqualified_or_semantic_actions_never_compile():
    catalog = actions.default_catalog()
    for change in ({"qualification": UNQUALIFIED}, {"mechanism": Mechanism.SEMANTIC}):
        snap = actions.snapshot(tuple((replace(c, **change) if c.action_id == actions.COMPARE else c, fn) for c, fn in catalog))
        r = compile_proposal(sub(CASES["C01"]["proposal"]), snap, CANDIDATES)
        assert r.code == "UNQUALIFIED_ACTION" and r.detail == "cmp"


def test_compile_is_deterministic_and_does_not_mutate_input():
    p = sub(CASES["C01"]["proposal"]); before = json.dumps(p, sort_keys=True)
    assert compile_proposal(p, actions.snapshot(), CANDIDATES) == compile_proposal(p, actions.snapshot(), CANDIDATES)
    assert json.dumps(p, sort_keys=True) == before
