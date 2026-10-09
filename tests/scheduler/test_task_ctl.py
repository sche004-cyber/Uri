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


def test_live_validation_must_be_one_complete_live_run(tmp_path, inv):
    """Codex rounds 9-10 (C3-01, R10-02): result, journal, attempts and both GIFs must describe one live run."""
    import hashlib
    ev = tmp_path / "ev"
    g1, g2 = b"GIF89a-one", b"GIF89a-two"
    h1, h2 = hashlib.sha256(g1).hexdigest(), hashlib.sha256(g2).hexdigest()
    result = {"mode": "live", "simulated": False, "verdict": "PASS", "chain": {"ok": True},
              "harness": {"mode": "LIVE", "available": True}, "v1": {"sha256": h1}, "v2": {"sha256": h2}}
    journal = [{"step": "1.service_started", "mode": "live"}, {"step": "6.gif_v1_verified", "sha256": h1},
               {"step": "9.gif_v2_verified", "sha256": h2}, {"step": "10.approved_v2"}]
    attempts = [{"mode": "LIVE", "harness": "claude_code"}, {"mode": "LIVE", "harness": "claude_code"}]

    def plan(result=result, journal=journal, attempts=attempts, gifs=(g1, g2), name="result.json"):
        if ev.exists():
            for f in ev.iterdir():
                f.unlink()
        ev.mkdir(exist_ok=True)
        (ev / name).write_text(json.dumps(result), encoding="utf-8")
        for fname, body in (("journal.json", journal), ("attempts.json", attempts)):
            if body is not None:
                (ev / fname).write_text(json.dumps(body), encoding="utf-8")
        for fname, data in zip(("v1.gif", "v2.gif"), gifs or ()):
            (ev / fname).write_bytes(data)
        code, out = ps("-Action", "plan", "-State", str(tmp_path / "s"), "-PythonExe", sys.executable,
                       "-LiveValidation", str(ev / name))
        assert code == 0, out
        return "live_claude_validation_passed : True" in out

    assert plan()
    assert not plan(result={"simulated": False, "verdict": "PASS"})              # the two-field file of round 9
    assert not plan(result=dict(result, simulated=True))
    assert not plan(result=dict(result, mode="fixture"))
    assert not plan(result=dict(result, harness={"mode": "LIVE", "available": False}))
    assert not plan(result=dict(result, chain={"ok": False}))
    assert not plan(journal=[])                                                    # the empty journal of round 10
    assert not plan(journal=[j for j in journal if j["step"] != "10.approved_v2"])
    assert not plan(journal=[dict(j, sha256="0" * 64) if "sha256" in j else j for j in journal])   # another run
    assert not plan(attempts=attempts[:1])
    assert not plan(attempts=attempts + [{"mode": "FIXTURE", "harness": "claude_fixture"}])
    assert not plan(gifs=(g1, b"GIF89a-other"))
    assert not plan(gifs=None)
    assert not plan(name="other.json")


def test_apply_with_another_task_name_or_uriserver_is_refused(tmp_path, inv):
    code, out = ps("-Action", "install", "-State", str(tmp_path / "s"), "-TaskName", "URISchedulerProbe", "-Apply")
    assert code != 0 and "dry runs" in out
    code, out = ps("-Action", "uninstall", "-TaskName", "URIServer", "-Apply")
    assert code != 0 and "never touched" in out


def test_rollback_dry_run_only_targets_this_scheduler_service(tmp_path, inv):
    """Codex rounds 9-10 (C3-02, R10-03): real argv positions, the exact state dir, and the recorded start time."""
    import os
    import socket
    state = tmp_path / "scheduler"
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        port = so.getsockname()[1]
    fake = ROOT / "tests" / "scheduler" / "helpers" / "fake_claude.py"
    svc = subprocess.Popen([sys.executable, "-m", "uri_scheduler.service", "run", "--state", str(state), "--mode", "fixture",
                            "--fixture-script", str(fake), "--port", str(port), "--tick-s", "30"], cwd=str(ROOT),
                           env=dict(os.environ, PYTHONPATH=str(ROOT)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sleep = "import time; time.sleep(60)"
    other = subprocess.Popen([sys.executable, "-c", sleep])
    lookalike = subprocess.Popen([sys.executable, "-c", sleep, "-m", "uri_scheduler.service", "run", "--state", str(state)])
    quoted = subprocess.Popen([sys.executable, "-c", sleep, f" -m uri_scheduler.service run --state {state} "])
    try:
        assert json.loads(svc.stdout.readline())["ready"]
        real = json.loads((state / "service.json").read_text(encoding="utf-8"))
        code, out = ps("-Action", "uninstall", "-State", str(state))
        assert code == 0 and f"would stop scheduler service pid {svc.pid}" in out and svc.poll() is None
        for p in (other, lookalike, quoted):
            (state / "service.json").write_text(json.dumps(dict(real, pid=p.pid)), encoding="utf-8")
            code, out = ps("-Action", "uninstall", "-State", str(state))
            assert code == 0 and "left alone" in out and p.poll() is None, out
        (state / "service.json").write_text(json.dumps(dict(real, started=real["started"] - 3600)), encoding="utf-8")
        code, out = ps("-Action", "uninstall", "-State", str(state))                 # a reused pid: wrong start time
        assert code == 0 and "left alone" in out
        (state / "service.json").write_text(json.dumps(real), encoding="utf-8")
        code, out = ps("-Action", "uninstall", "-State", str(state) + "-other")
        assert "would stop scheduler service" not in out
        code, out = ps("-Action", "uninstall", "-Apply")                              # rollback without -State
        assert code != 0 and "needs -State" in out
    finally:
        for p in (svc, other, lookalike, quoted):
            p.kill()
