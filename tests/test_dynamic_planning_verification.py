"""Dynamic planning slice 1, gate G5 and C-1: independent verification and edge compatibility."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

import uri_v1.memory.recorder as memory_recorder
from tests.m37_edge_support import SALES, Env, make_workbook, report_acceptance
from uri_v1.edge import report as edge_report
from uri_v1.edge.contracts import TaskClass
from uri_v1.execution.planning import actions, oracle
from uri_v1.execution.planning.contracts import REPORT_NAME, canonical
from uri_v1.execution.verify import verify_candidate
from uri_v1.execution.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


def qual():
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


@pytest.mark.parametrize("case_id", ["C26", "C27", "C28", "C29", "C30", "C31"])
def test_tampering_is_never_verified(battery, case_id):
    obs = battery(case_id)
    assert obs["status"] == "NOT_VERIFIED", obs
    assert obs.get("memory_verification") != "VERIFIED" and obs.get("runstore_verification") != "VERIFIED"


def test_extra_artifact_fails_only_changed(battery):
    obs = battery("C28")
    assert obs["memory_verification"] == "FAILED" and obs["runstore_verification"] == "FAILED"


def test_modified_original_is_caught_before_the_verdict(battery):
    obs = battery("C30")
    assert obs["status"] == "NOT_VERIFIED" and obs["reason"] == "VERIFIER_SOURCE_NOT_CURRENT"
    assert obs["declared_original_mutation"] and obs["originals_changed_during_run"]


def test_monkeypatched_write_adapter_forging_bytes_is_refused(battery, monkeypatch):
    real = actions.write_report
    def forged(ctx, inputs, literals):
        out = real(ctx, inputs, literals)
        path = ctx.files / REPORT_NAME
        report = json.loads(path.read_bytes()); report["items"][0]["value"]["only_right_sheets"] = ["Invented"]
        data = canonical(report); path.write_bytes(data)
        import hashlib
        return {"report": {"relpath": REPORT_NAME, "sha256": hashlib.sha256(data).hexdigest()}}
    monkeypatch.setattr(actions, "write_report", forged)
    obs = battery("C01")
    # Audit F2: an adapter that is not the qualified implementation is refused before it runs, so it
    # can neither forge the report nor reach the verifier. (C26 still checks the verifier catches forgery.)
    assert obs["status"] == "NOT_ATTEMPTED" and obs["reason"] == "ADAPTER_NOT_QUALIFIED"
    assert obs["executed"] == ["ia", "ib", "sa", "sb", "cmp"] and obs.get("runstore_verification") is None


@pytest.mark.parametrize("case_id,code", [("C32a", "PROPOSAL_INVALID"), ("C32b", "PROVIDER_UNAVAILABLE")])
def test_provider_failure_gives_no_run(battery, case_id, code):
    obs = battery(case_id)
    assert (obs["status"], obs["reason"], obs["run_id"], obs["adapter_calls"]) == ("NOT_ATTEMPTED", code, None, [])


def test_wrong_literal_verifies_as_executed_but_is_a_semantic_miss(battery):
    obs = battery("C33")
    assert obs["status"] == "VERIFIED"
    comparison = json.loads(obs["report_bytes"])["items"][0]["value"]
    assert comparison["shared_sheets"] == [] and comparison["only_left_sheets"] == ["Vendors"]


def test_oracle_refuses_foreign_or_malformed_task_classes(battery):
    obs = battery("C01")
    ws = Workspace.open(obs["workspace_dir"])
    report = ws.files / REPORT_NAME
    good = "PLANNED_STRUCTURE_REPORT@" + obs["plan_sha256"]
    assert oracle.recompute(good, ws, report)
    for bad in ("PLANNED_STRUCTURE_REPORT@" + "0" * 64, "PLANNED_STRUCTURE_REPORT@xyz", "WORKBOOK_INSPECT", None, good + " "):
        assert not oracle.recompute(bad, ws, report)
    (ws.files / "wb_a.xlsx").write_bytes(b"changed copy")                 # a manifest copy no longer matches
    assert not oracle.recompute(good, ws, report)


def test_oracle_refuses_non_canonical_plan_bytes(battery):
    obs = battery("C01")
    ws = Workspace.open(obs["workspace_dir"])
    plan_path = ws.bundle / "plan.json"
    plan_path.write_bytes(json.dumps(json.loads(plan_path.read_bytes()), indent=1).encode())
    assert not oracle.recompute("PLANNED_STRUCTURE_REPORT@" + obs["plan_sha256"], ws, ws.files / REPORT_NAME)


def test_composed_dispatch_matches_edge_on_the_m37_inspect_fixture(tmp_path, monkeypatch):
    env = Env(tmp_path, monkeypatch)
    make_workbook(env.root / "sales.xlsx", SALES)
    result = env.edge.handle(env.task(TaskClass.WORKBOOK_INSPECT))
    assert result.route == "LOCAL_VERIFIED"
    ws = Workspace.open(env.store.get(result.local.run_id)["started"]["workspace_dir"])
    criteria = report_acceptance("WORKBOOK_INSPECT")
    strip = lambda r: (r["status"], [(i["kind"], i["status"]) for i in r["items"]])
    assert strip(verify_candidate(ws, criteria, recompute=oracle.dispatch)) == strip(verify_candidate(ws, criteria, recompute=edge_report.recompute))
    assert strip(verify_candidate(ws, criteria, recompute=oracle.dispatch))[0] == "VERIFIED"
    report = ws.files / edge_report.REPORT_NAME
    report.write_bytes(report.read_bytes().replace(b'"Amount"', b'"Amt"'))
    forged = strip(verify_candidate(ws, criteria, recompute=oracle.dispatch))
    assert forged == strip(verify_candidate(ws, criteria, recompute=edge_report.recompute)) and forged[0] == "FAILED"


def test_qualification_script_end_to_end(tmp_path):
    out = tmp_path / "results.json"
    proc = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "dynamic_planning_qualification.py"), "--out", str(out)],
                          capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    result = json.loads(out.read_text())
    assert result["gate_passed"] and all(v["numerator"] == 0 for v in result["counters"].values())
    assert all(v["denominator"] > 0 for v in result["counters"].values())
    assert result["expected_outcome"]["rate"] == 1.0


def test_qualification_driver_refuses_a_changed_battery(tmp_path):
    raw = json.loads((ROOT / "fixtures/dynamic_planning/qualification_cases.json").read_bytes())
    raw["cases"][0]["description"] += " (changed)"
    changed = tmp_path / "cases.json"; changed.write_text(json.dumps(raw))
    out = tmp_path / "results.json"
    script = str(ROOT / "scripts" / "dynamic_planning_qualification.py")
    proc = subprocess.run([sys.executable, "-B", script, "--cases", str(changed), "--out", str(out)],
                          capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    assert proc.returncode == 2 and "REFUSED" in proc.stderr and not out.exists()
    proc = subprocess.run([sys.executable, "-B", script, "--cases", str(changed), "--out", str(out), "--non-qualifying"],
                          capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    result = json.loads(out.read_text())
    assert proc.returncode == 1 and result["qualifying"] is False and result["gate_passed"] is False
    assert result["status"].startswith("NON_QUALIFYING")
