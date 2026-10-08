"""Tests for bounded deterministic execution and live capability revalidation (G4)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import shutil
import uuid

import uri_v1.memory.recorder as memory_recorder
from uri_v1.execution.acceptance import AcceptanceCriteria
from uri_v1.execution.officefile import read_workbook_structure
from uri_v1.execution.planning.actions import (
    ActionExecutionError,
    action_inspect_structure,
    action_report_write,
    action_structure_compare,
    action_structure_select,
    canonical_contracts,
    snapshot,
)
from uri_v1.execution.planning.compiler import compile
from uri_v1.execution.planning.contracts import (
    CapabilityContract,
    CapabilitySnapshot,
    CompiledPlan,
    InputPortSpec,
    LiteralSpec,
    PortType,
    SemanticProposal,
)
from uri_v1.execution.planning.oracle import verifier_entries
from uri_v1.execution.planning.runner import PlanOutcome, PlanRunner
from uri_v1.execution.run_record import RunStore
from uri_v1.memory.log import MemoryLog
from uri_v1.memory.recorder import Recorder, _bootstrap_verifiers
from uri_v1.memory.sources import SourceRegistry
from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.results.version_ledger import ResultVersionLedger


USER = str(uuid.UUID(int=42))


def setup_test_env(tmp_path: Path):
    root = tmp_path / "authorized"
    root.mkdir()
    # Copy fixture workbooks into authorized root
    shutil.copy("fixtures/dynamic_planning/workbooks/finance_2025.xlsx", root / "fin_2025.xlsx")
    shutil.copy("fixtures/dynamic_planning/workbooks/finance_2026.xlsx", root / "fin_2026.xlsx")

    log = MemoryLog(USER, tmp_path / "private")
    sources = SourceRegistry(log)
    sources.register(root)

    recorder = Recorder(log, sources)
    ledger = ResultVersionLedger(USER, root=str(tmp_path / "results"))
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_store = RunStore(USER, runs_dir)
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    return root, log, sources, recorder, ledger, run_store, scratch, runs_dir


def test_actions_pure_functions():
    """Gate 4: Actions are pure functions with typed failures on invalid inputs."""
    wb_path = Path("fixtures/dynamic_planning/workbooks/finance_2025.xlsx")
    res = action_inspect_structure(wb_path)
    assert "structure" in res

    # Valid select
    sel = action_structure_select(res["structure"], sheets=["Summary"], headers=["Department", "Budget"])
    assert len(sel["selection"]["sheets"]) == 1
    assert sel["selection"]["sheets"][0]["name"] == "Summary"
    assert sel["selection"]["sheets"][0]["headers"] == ["Department", "Budget"]

    # Select missing sheet raises LITERAL_NOT_IN_SOURCE
    with pytest.raises(ActionExecutionError) as exc:
        action_structure_select(res["structure"], sheets=["NonexistentSheet"])
    assert exc.value.code == "LITERAL_NOT_IN_SOURCE"

    # Select missing header raises LITERAL_NOT_IN_SOURCE
    with pytest.raises(ActionExecutionError) as exc:
        action_structure_select(res["structure"], sheets=["Summary"], headers=["FakeColumn"])
    assert exc.value.code == "LITERAL_NOT_IN_SOURCE"


def test_runner_live_capability_changed_halts_descendants(tmp_path, monkeypatch):
    """Gate 4: Mutation of capability snapshot between compile and node execution halts descendants (F4)."""
    root, log, sources, recorder, ledger, run_store, scratch, runs_dir = setup_test_env(tmp_path)
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    _bootstrap_verifiers(verifier_entries(runs_dir))

    # Scan and locate source IDs
    scan = sources.scan()
    loc_2025 = next(l for l in scan.locators if l.relpath == "fin_2025.xlsx")
    loc_2026 = next(l for l in scan.locators if l.relpath == "fin_2026.xlsx")
    f_2025 = sources.fingerprint(loc_2025)
    f_2026 = sources.fingerprint(loc_2026)

    fixture_cases = json.loads(Path("fixtures/dynamic_planning/qualification_cases.json").read_bytes())["cases"]
    raw_prop = dict(fixture_cases["valid_two_workbook_compare"]["proposal"])
    # Map sources
    raw_prop["nodes"][0]["inputs"]["source"]["source"] = f_2025.source_id
    raw_prop["nodes"][1]["inputs"]["source"]["source"] = f_2026.source_id

    proposal = SemanticProposal.parse(raw_prop)
    initial_snap = snapshot()
    candidates = {f_2025.source_id: f_2025.content_sha256, f_2026.source_id: f_2026.content_sha256}

    plan = compile(proposal, initial_snap, candidates)
    assert isinstance(plan, CompiledPlan)

    # Provider will mutate snapshot to simulate live capability change before select_1 executes
    call_count = 0
    def dynamic_snapshot_provider():
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            # Invalidate qualification of uri.plan.structure.select
            mutated = [
                c if c.action_id != "uri.plan.structure.select" else
                CapabilityContract(
                    action_id=c.action_id,
                    version=c.version,
                    mechanism=c.mechanism,
                    inputs=c.inputs,
                    outputs=c.outputs,
                    literals=c.literals,
                    effect=c.effect,
                    approval=c.approval,
                    verifier_coverage=c.verifier_coverage,
                    qualification="QUAL-MUTATED-00",
                )
                for c in canonical_contracts()
            ]
            return CapabilitySnapshot.create(mutated)
        return initial_snap

    runner = PlanRunner(
        user_id=USER,
        scratch_root=scratch,
        run_store=run_store,
        recorder=recorder,
        ledger=ledger,
        sources=sources,
        snapshot_provider=dynamic_snapshot_provider,
    )

    label = "compare workbooks"
    trace_id = uuid.uuid4().hex
    turn_id = uuid.uuid4().hex
    task_id, _ = recorder.open_task(
        URIIntake().capture(USER, "session_1", turn_id, trace_id, label, spans={"file": (0, len(label))}),
        label,
    )

    outcome = runner.run(plan, task_id=task_id, trace_id=trace_id, session_id="session_1")
    assert outcome.status == "FAILED"
    assert outcome.verification_status != "VERIFIED"
    assert outcome.rejection is not None
    assert outcome.rejection.code == "CAPABILITY_CHANGED"
    # Ensure later nodes did not run
    node_ids_run = [r["node_id"] for r in outcome.node_receipts]
    assert "compare_1" not in node_ids_run
    assert "write_1" not in node_ids_run
