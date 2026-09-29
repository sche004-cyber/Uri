"""Dynamic planning slice 1, gate G3: source binding, handles and isolation."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys

import pytest

import uri_v1.memory.recorder as memory_recorder
from uri_v1.execution.planning.bindings import BindingError, Handle, HandleTable, bind_sources, valid_value
from uri_v1.execution.planning.contracts import CompiledPlan, PortType

ROOT = Path(__file__).resolve().parents[1]


def qual():
    """The qualification driver, loaded once per process (tests reuse its real-store case harness)."""
    name = "dynamic_planning_qualification"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return sys.modules[name]


@pytest.fixture
def battery(tmp_path, monkeypatch):
    q = qual()
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    q.bootstrap(tmp_path / "runs")
    cases, _ = q.load_battery()
    by_id = {c["id"]: c for c in cases}
    return lambda case_id, **over: q.run_case(dict(by_id[case_id], **over), by_id, tmp_path / "cases", tmp_path / "runs")


def test_unknown_source_is_rejected_never_corrected(battery):
    obs = battery("C15")
    assert obs["status"] == "REJECTED" and obs["rejection_code"] == "UNKNOWN_SOURCE" and obs["run_id"] is None


def test_same_name_in_two_roots_needs_clarification_with_both_ids(battery):
    obs = battery("C16")
    assert obs["status"] == "NEEDS_CLARIFICATION" and obs["run_id"] is None and obs["adapter_calls"] == []
    assert obs["clarification"] == ["$src:root1/wb_a.xlsx", "$src:root2/wb_a.xlsx"]


def test_stale_candidate_is_not_attempted(battery):
    obs = battery("C17")
    assert (obs["status"], obs["reason"], obs["run_id"], obs["adapter_calls"]) == ("NOT_ATTEMPTED", "INPUT_NOT_CURRENT", None, [])


def test_wrong_case_literal_is_not_fuzzy_matched(battery):
    obs = battery("C18")
    assert obs["status"] == "NOT_ATTEMPTED" and obs["reason"] == "LITERAL_NOT_IN_SOURCE"
    assert obs["run_events"] == ["RUN_STARTED", "RUN_ABORTED"] and "cmp" not in obs["adapter_calls"]


@pytest.mark.parametrize("case_id", ["C19", "C20"])
def test_paths_and_handle_tokens_are_not_sources(battery, case_id):
    obs = battery(case_id)
    assert obs["status"] == "REJECTED" and obs["rejection_code"] == "PROPOSAL_INVALID" and obs["run_id"] is None


def test_malformed_workbook_halts_before_descendants(battery):
    obs = battery("C21")
    assert obs["status"] == "NOT_ATTEMPTED" and obs["reason"] == "XLSX_NOT_ZIP" and obs["adapter_calls"] == ["ia"]


def test_run_binds_exactly_the_plan_sources(battery):
    obs = battery("C01")
    assert obs["status"] == "VERIFIED"
    manifest = sorted((m["source_id"], m["content_sha256"]) for m in obs["manifest"])
    assert manifest == sorted(tuple(s) for s in obs["plan"]["sources"])
    assert {m["original_relpath"] for m in obs["manifest"]} == {"wb_a.xlsx", "wb_b.xlsx"}


def _plan(sources):
    return CompiledPlan((), (), tuple(sources), (), (), "0" * 64, "0" * 64)


class _Sources:
    def __init__(self, current): self.current = current
    def verify_source(self, sid, sha): return self.current


def test_bind_sources_refuses_unknown_mismatched_and_stale():
    from uri_v1.execution.planning.contracts import SourceCandidate
    cand = (SourceCandidate("a" * 32, "a.xlsx", "spreadsheet", "1" * 64),)
    assert bind_sources(_plan([("a" * 32, "1" * 64)]), _Sources(True), cand)[0].source_id == "a" * 32
    for plan, current, code in ((_plan([("b" * 32, "1" * 64)]), True, "UNKNOWN_SOURCE"),
                                (_plan([("a" * 32, "2" * 64)]), True, "SOURCE_HASH_MISMATCH"),
                                (_plan([("a" * 32, "1" * 64)]), False, "INPUT_NOT_CURRENT")):
        with pytest.raises(BindingError, match=code): bind_sources(plan, _Sources(current), cand)
    with pytest.raises(BindingError, match="PLAN_REQUIRED"): bind_sources({"sources": []}, _Sources(True), cand)


SEL = {"source_id": "a" * 32, "sheets": [{"name": "Orders", "header": ["Id"]}]}


def test_handles_are_issued_only_for_valid_values():
    table = HandleTable(user_id="u", task_id="t", run_id="r")
    with pytest.raises(BindingError, match="OUTPUT_TYPE_INVALID"): table.issue("sa", "selection", {"sheets": []}, PortType.STRUCTURE_SELECTION)
    with pytest.raises(BindingError, match="UNBOUND_INPUT"): table.get("sa", "selection")   # a failed node issued nothing
    handle = table.issue("sa", "selection", SEL, PortType.STRUCTURE_SELECTION)
    assert table.get("sa", "selection") == SEL and table.resolve(handle) == SEL
    with pytest.raises(BindingError, match="HANDLE_ALREADY_ISSUED"): table.issue("sa", "selection", SEL, PortType.STRUCTURE_SELECTION)
    got = table.get("sa", "selection"); got["sheets"].clear()
    assert table.get("sa", "selection") == SEL        # callers get copies; the issued value cannot be mutated


def test_fabricated_foreign_and_unissued_handles_fail():
    table = HandleTable(user_id="u", task_id="t", run_id="r")
    handle = table.issue("sa", "selection", SEL, PortType.STRUCTURE_SELECTION)
    with pytest.raises(BindingError, match="HANDLE_FABRICATED"): table.resolve(Handle("u", "t", "r", "sa", "selection", handle.value_sha256))
    with pytest.raises(BindingError, match="HANDLE_FABRICATED"): table.resolve(replace(handle))
    with pytest.raises(BindingError, match="HANDLE_FABRICATED"): table.resolve("sa.selection")
    for other in (HandleTable(user_id="u2", task_id="t", run_id="r"), HandleTable(user_id="u", task_id="t2", run_id="r"),
                  HandleTable(user_id="u", task_id="t", run_id="r2")):
        with pytest.raises(BindingError, match="HANDLE_FOREIGN"): other.resolve(handle)
    twin = HandleTable(user_id="u", task_id="t", run_id="r")
    with pytest.raises(BindingError, match="UNBOUND_INPUT"): twin.resolve(handle)
    with pytest.raises(TypeError): __import__("pickle").dumps(handle)


def test_value_shapes_are_closed():
    assert valid_value(SEL, PortType.STRUCTURE_SELECTION)
    assert not valid_value(dict(SEL, extra=1), PortType.STRUCTURE_SELECTION)
    assert not valid_value(SEL, PortType.STRUCTURE_COMPARISON)
    assert not valid_value({"relpath": "other.json", "sha256": "0" * 64}, PortType.REPORT_ARTIFACT)
    assert not valid_value({"source_id": "a" * 32, "sheets": []}, PortType.STRUCTURE_SELECTION)
