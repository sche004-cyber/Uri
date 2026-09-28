"""M38 qualification evidence is gate-passed, bound to the frozen gate, and the fake-harness scenarios reproduce."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import m38_harness_qualification as driver
from scripts.m37_edge_qualification import lf

ROOT = Path(__file__).resolve().parents[1]


def test_recorded_results_pass_and_bind_to_gate():
    results = json.loads((ROOT / "docs/plans/M38_QUALIFICATION_RESULTS.json").read_text())
    assert results["gate_passed"] is True
    assert results["gate_sha256"] == hashlib.sha256(lf(driver.GATE)).hexdigest()


@pytest.mark.parametrize("name", ["honest", "false_claim", "write_original", "hang_with_child"])
def test_scenarios_reproduce(name, tmp_path):
    expected = json.loads(lf(driver.GATE))["scenarios"][name]
    r = driver.run_scenario(name, tmp_path)
    assert (r["verified"], r["verification_status"], r["claimed_outcome"], sorted(r["flags"])) == (
        expected["verified"], expected["verification_status"], expected["claimed_outcome"], sorted(expected["flags"]))
    assert not r["bypass_flags"] and not r["secrets_in_records"] and not r["session_id_in_memory"] and not r["unkilled"]


def test_live_pilot_is_recorded_as_pilot_only():
    pilot = json.loads((ROOT / "docs/plans/M38_LIVE_PILOT_RESULTS.json").read_text())
    assert pilot["status"] == "PILOT_NOT_QUALIFICATION" and pilot["codex"].startswith("UNAVAILABLE")
    for row in pilot["rows"]:
        assert "error" in row or row["verification_status"] in ("VERIFIED", "FAILED", "PARTIALLY_VERIFIED", "UNVERIFIABLE", "CLAIMED_ONLY")
