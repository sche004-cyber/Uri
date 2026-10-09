"""Owner-gated logon-task script: install/rollback procedures exercised WITHOUT changing the live startup configuration.

Every call here is a dry run (no -Apply). The Windows task inventory (names) is compared before and after.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CTL = ROOT / "scripts" / "scheduler_task_ctl.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Task Scheduler only")


def ps(*args):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(CTL), *args],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def inventory():
    r = subprocess.run(["schtasks", "/query", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=60)
    return sorted({line.split(",")[0] for line in r.stdout.splitlines() if line.strip()})


@pytest.fixture
def inv():
    before = inventory()
    yield before
    assert inventory() == before, "the live task inventory changed"


def test_plan_and_verify_change_nothing(tmp_path, inv):
    state = tmp_path / "scheduler"
    code, out = ps("-Action", "plan", "-State", str(state), "-ClientHome", str(tmp_path), "-PythonExe", sys.executable)
    assert code == 0 and "Nothing changed (plan only)." in out
    assert "python_exists" in out and "live_claude_validation_passed : False" in out
    code, out = ps("-Action", "verify", "-State", str(state), "-PythonExe", sys.executable)
    assert code == 0 and "nothing registered" in out
    assert "TriggerUser" in out and "IgnoreNew" in out


def test_install_without_apply_lists_failing_preconditions(tmp_path, inv):
    code, out = ps("-Action", "install", "-State", str(tmp_path / "s"), "-ClientHome", str(tmp_path / "missing"),
                   "-PythonExe", str(tmp_path / "no_python.exe"))
    assert code == 0 and "DRY RUN" in out
    for name in ("python_exists", "client_home_exists", "live_claude_validation_passed"):
        assert name in out.split("Failing preconditions:")[1]


def test_live_validation_must_be_a_real_pass(tmp_path, inv):
    fake = tmp_path / "result.json"
    for body, ok in (({"simulated": True, "verdict": "PASS"}, False), ({"simulated": False, "verdict": "BLOCKED_AS_EXPECTED"}, False),
                     ({"simulated": False, "verdict": "PASS"}, True)):
        fake.write_text(json.dumps(body), encoding="utf-8")
        code, out = ps("-Action", "plan", "-State", str(tmp_path / "s"), "-PythonExe", sys.executable, "-LiveValidation", str(fake))
        assert code == 0 and f"live_claude_validation_passed : {ok}" in out


def test_apply_with_another_task_name_or_uriserver_is_refused(tmp_path, inv):
    code, out = ps("-Action", "install", "-State", str(tmp_path / "s"), "-TaskName", "URISchedulerProbe", "-Apply")
    assert code != 0 and "dry runs" in out
    code, out = ps("-Action", "uninstall", "-TaskName", "URIServer", "-Apply")
    assert code != 0 and "never touched" in out


def test_rollback_dry_run_only_targets_this_scheduler_service(tmp_path, inv):
    state = tmp_path / "scheduler"
    state.mkdir()
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    mine = subprocess.Popen([sys.executable, "-c", "import time, sys; time.sleep(60)", "uri_scheduler.service", str(state)])
    try:
        time.sleep(0.5)
        (state / "service.json").write_text(json.dumps({"pid": other.pid}), encoding="utf-8")
        code, out = ps("-Action", "uninstall", "-State", str(state))
        assert code == 0 and "left alone" in out and other.poll() is None
        (state / "service.json").write_text(json.dumps({"pid": mine.pid}), encoding="utf-8")
        code, out = ps("-Action", "uninstall", "-State", str(state))
        assert code == 0 and f"would stop scheduler service pid {mine.pid}" in out and mine.poll() is None
    finally:
        other.kill()
        mine.kill()
