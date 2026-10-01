"""M37 qualification evidence: pinned, gate-passed, bound to the frozen battery, reproducible."""
import hashlib
import json
from pathlib import Path

from scripts import m37_edge_qualification as driver
from uri_v1.edge.registry import default_registry

ROOT = Path(__file__).resolve().parents[1]


def test_default_registry_loads_pinned_evidence():
    reg = default_registry()
    assert [c.capability_id for c in reg.eligible("SCRIPT_WORKBOOK_REPAIR")] == ["uri.edge.script_workbook_literal_remap"]
    assert not reg.qualification_run


def test_recorded_results_bind_to_current_battery_and_gate():
    results = json.loads((ROOT / "docs/plans/M37_QUALIFICATION_RESULTS.json").read_text())
    assert results["gate_passed"] is True
    assert results["battery_sha256"] == hashlib.sha256(driver.lf(driver.BATTERY)).hexdigest()
    assert results["gate_sha256"] == hashlib.sha256(driver.lf(driver.GATE)).hexdigest()


def test_battery_decisions_reproduce(tmp_path):
    battery = json.loads(driver.BATTERY.read_text())
    recorded = {r["id"]: r for r in json.loads((ROOT / "docs/plans/M37_QUALIFICATION_RESULTS.json").read_text())["runs"][0]}
    for n, case in enumerate(battery["cases"]):
        d = tmp_path / str(n); d.mkdir()
        r = driver.run_case(case, battery, d)
        assert (r["route"], r["reason"], r["local_verification"]) == (recorded[case["id"]]["route"], recorded[case["id"]]["reason"],
                                                                      recorded[case["id"]]["local_verification"]), case["id"]
        assert [r["route"], r["reason"]] == case["expected"]
