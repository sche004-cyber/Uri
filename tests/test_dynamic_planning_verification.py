"""Tests for independent verification, oracle recomputation, and adversarial tamper detection (G5)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import shutil
import uuid

import uri_v1.memory.recorder as memory_recorder
from uri_v1.execution.acceptance import AcceptanceCriteria
from uri_v1.execution.planning.actions import canonical_contracts, snapshot
from uri_v1.execution.planning.compiler import compile
from uri_v1.execution.planning.contracts import CompiledPlan, SemanticProposal
from uri_v1.execution.planning.oracle import recompute, verifier_entries
from uri_v1.execution.planning.runner import PlanOutcome, PlanRunner
from uri_v1.execution.run_record import RunStore
from uri_v1.execution.verify import make_memory_verifier, verify_candidate
from uri_v1.execution.workspace import Workspace
from uri_v1.memory.log import MemoryLog
from uri_v1.memory.recorder import Recorder, _bootstrap_verifiers
from uri_v1.memory.sources import SourceRegistry
from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.results.version_ledger import ResultVersionLedger


USER = str(uuid.UUID(int=101))


def setup_verification_env(tmp_path: Path):
    root = tmp_path / "authorized"
    root.mkdir()
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


def test_positive_canonical_execution_and_independent_verification(tmp_path, monkeypatch):
    """Gate 5: Full canonical execution of two-workbook comparison passes independent verification with VERIFIED."""
    root, log, sources, recorder, ledger, run_store, scratch, runs_dir = setup_verification_env(tmp_path)
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    _bootstrap_verifiers(verifier_entries(runs_dir))

    scan = sources.scan()
    loc_2025 = next(l for l in scan.locators if l.relpath == "fin_2025.xlsx")
    loc_2026 = next(l for l in scan.locators if l.relpath == "fin_2026.xlsx")
    f_2025 = sources.fingerprint(loc_2025)
    f_2026 = sources.fingerprint(loc_2026)

    cases = json.loads(Path("fixtures/dynamic_planning/qualification_cases.json").read_bytes())["cases"]
    raw_prop = dict(cases["valid_two_workbook_compare"]["proposal"])
    raw_prop["nodes"][0]["inputs"]["source"]["source"] = f_2025.source_id
    raw_prop["nodes"][1]["inputs"]["source"]["source"] = f_2026.source_id

    proposal = SemanticProposal.parse(raw_prop)
    snap = snapshot()
    candidates = {f_2025.source_id: f_2025.content_sha256, f_2026.source_id: f_2026.content_sha256}

    plan = compile(proposal, snap, candidates)
    assert isinstance(plan, CompiledPlan)

    runner = PlanRunner(
        user_id=USER,
        scratch_root=scratch,
        run_store=run_store,
        recorder=recorder,
        ledger=ledger,
        sources=sources,
        snapshot_provider=snap,
    )

    label = "compare workbooks"
    trace_id = uuid.uuid4().hex
    turn_id = uuid.uuid4().hex
    task_id, _ = recorder.open_task(
        URIIntake().capture(USER, "session_1", turn_id, trace_id, label, spans={"file": (0, len(label))}),
        label,
    )

    outcome = runner.run(plan, task_id=task_id, trace_id=trace_id, session_id="session_1")
    assert outcome.status == "COMPLETED"
    assert outcome.verification_status == "VERIFIED"
    assert outcome.verifier_record_id is not None


def test_adversarial_forged_report_bytes_rejected(tmp_path, monkeypatch):
    """Gate 5: Forged or modified plan_report.json fails independent verification (never VERIFIED)."""
    root, log, sources, recorder, ledger, run_store, scratch, runs_dir = setup_verification_env(tmp_path)
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    _bootstrap_verifiers(verifier_entries(runs_dir))

    scan = sources.scan()
    loc_2025 = next(l for l in scan.locators if l.relpath == "fin_2025.xlsx")
    loc_2026 = next(l for l in scan.locators if l.relpath == "fin_2026.xlsx")
    f_2025 = sources.fingerprint(loc_2025)
    f_2026 = sources.fingerprint(loc_2026)

    cases = json.loads(Path("fixtures/dynamic_planning/qualification_cases.json").read_bytes())["cases"]
    raw_prop = dict(cases["valid_two_workbook_compare"]["proposal"])
    raw_prop["nodes"][0]["inputs"]["source"]["source"] = f_2025.source_id
    raw_prop["nodes"][1]["inputs"]["source"]["source"] = f_2026.source_id

    proposal = SemanticProposal.parse(raw_prop)
    snap = snapshot()
    candidates = {f_2025.source_id: f_2025.content_sha256, f_2026.source_id: f_2026.content_sha256}
    plan = compile(proposal, snap, candidates)

    # We test oracle recomputation directly:
    ws_run_id = uuid.uuid4().hex
    inputs = sources.scan()
    from uri_v1.execution.planning.bindings import bind_sources
    ws_inputs = bind_sources(plan, sources, candidates)
    ws = Workspace.create(user_id=USER, scratch_root=scratch, sources=sources, inputs=ws_inputs, run_id=ws_run_id)
    (ws.bundle / "plan.json").write_bytes(plan.canonical())

    # Write a forged report
    forged_report = {"schema_version": "uri.plan.report.v1", "plan_sha256": plan.sha256, "items": [{"kind": "forged", "data": "injected"}]}
    (ws.files / "plan_report.json").write_text(json.dumps(forged_report))

    ok = recompute(f"PLANNED_STRUCTURE_REPORT@{plan.sha256}", ws, ws.files / "plan_report.json")
    assert not ok  # Forged bytes rejected!


def test_adversarial_tampered_plan_json_rejected(tmp_path):
    """Gate 5: Tampered bundle/plan.json fails sha256 check against task_class suffix."""
    root, log, sources, recorder, ledger, run_store, scratch, runs_dir = setup_verification_env(tmp_path)
    scan = sources.scan()
    loc_2025 = next(l for l in scan.locators if l.relpath == "fin_2025.xlsx")
    loc_2026 = next(l for l in scan.locators if l.relpath == "fin_2026.xlsx")
    f_2025 = sources.fingerprint(loc_2025)
    f_2026 = sources.fingerprint(loc_2026)

    cases = json.loads(Path("fixtures/dynamic_planning/qualification_cases.json").read_bytes())["cases"]
    raw_prop = dict(cases["valid_two_workbook_compare"]["proposal"])
    raw_prop["nodes"][0]["inputs"]["source"]["source"] = f_2025.source_id
    raw_prop["nodes"][1]["inputs"]["source"]["source"] = f_2026.source_id

    proposal = SemanticProposal.parse(raw_prop)
    snap = snapshot()
    candidates = {f_2025.source_id: f_2025.content_sha256, f_2026.source_id: f_2026.content_sha256}
    plan = compile(proposal, snap, candidates)

    from uri_v1.execution.planning.bindings import bind_sources
    ws_inputs = bind_sources(plan, sources, candidates)
    ws = Workspace.create(user_id=USER, scratch_root=scratch, sources=sources, inputs=ws_inputs, run_id=uuid.uuid4().hex)

    # Tampered plan bytes
    (ws.bundle / "plan.json").write_bytes(b'{"tampered": true}')
    (ws.files / "plan_report.json").write_bytes(b'{}')

    ok = recompute(f"PLANNED_STRUCTURE_REPORT@{plan.sha256}", ws, ws.files / "plan_report.json")
    assert not ok


def test_extra_artifact_causes_only_changed_failure(tmp_path, monkeypatch):
    """Gate 5: Extra artifact in files/ causes only_changed acceptance check to fail."""
    root, log, sources, recorder, ledger, run_store, scratch, runs_dir = setup_verification_env(tmp_path)
    scan = sources.scan()
    loc_2025 = next(l for l in scan.locators if l.relpath == "fin_2025.xlsx")
    loc_2026 = next(l for l in scan.locators if l.relpath == "fin_2026.xlsx")
    f_2025 = sources.fingerprint(loc_2025)
    f_2026 = sources.fingerprint(loc_2026)

    cases = json.loads(Path("fixtures/dynamic_planning/qualification_cases.json").read_bytes())["cases"]
    raw_prop = dict(cases["valid_two_workbook_compare"]["proposal"])
    raw_prop["nodes"][0]["inputs"]["source"]["source"] = f_2025.source_id
    raw_prop["nodes"][1]["inputs"]["source"]["source"] = f_2026.source_id

    proposal = SemanticProposal.parse(raw_prop)
    snap = snapshot()
    candidates = {f_2025.source_id: f_2025.content_sha256, f_2026.source_id: f_2026.content_sha256}
    plan = compile(proposal, snap, candidates)

    from uri_v1.execution.planning.bindings import bind_sources
    ws_inputs = bind_sources(plan, sources, candidates)
    ws = Workspace.create(user_id=USER, scratch_root=scratch, sources=sources, inputs=ws_inputs, run_id=uuid.uuid4().hex)
    (ws.bundle / "plan.json").write_bytes(plan.canonical())

    # Legitimate report
    from uri_v1.execution.planning.actions import action_report_write
    action_report_write([], ws.files, plan.sha256)

    # Extra unauthorized artifact
    (ws.files / "unauthorized_leak.txt").write_text("leak")

    criteria = AcceptanceCriteria(
        revision=1,
        items=(
            {"kind": "only_changed", "paths": ["plan_report.json"]},
            {"kind": "report_recomputes", "path": "plan_report.json", "task_class": f"PLANNED_STRUCTURE_REPORT@{plan.sha256}"},
        ),
    )

    verdict = verify_candidate(ws, criteria, recompute=recompute)
    assert verdict["status"] == "FAILED"
