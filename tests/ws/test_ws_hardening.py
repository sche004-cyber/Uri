"""WS hardening: GPU lease and census (T1), Brain host (T2), health and bridge commands (T3).

Simulation level: real OS locks and real child processes for the lease; recorded counter samples for the census;
a fake llama endpoint for calibration. Live behaviour is covered separately (tests/ws/test_ws_worker_live.py and the
hardening evidence)."""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from uri_operational_intelligence import brain_health as BH
from uri_operational_intelligence import gpu_lease as G
from uri_operational_intelligence.worker_bridge import BridgeRefused
from tests.ws.test_ws_worker_bridge import CFG, SID, FakeCore, fake, make  # noqa: F401  (fixture re-export)

REPO = Path(__file__).resolve().parents[2]
MB = 2**20
LUID = "luid_0x00000000_0x0000c181"


def raw(procs, adapter_mib):
    """A counter sample shaped like the PowerShell census output (values in bytes)."""
    p = []
    for pid, ded, nonlocal_ in procs:
        p.append({"i": "pid_%d_%s_phys_0" % (pid, LUID), "c": "dedicated usage", "v": int(ded * MB)})
        p.append({"i": "pid_%d_%s_phys_0" % (pid, LUID), "c": "non local usage", "v": int(nonlocal_ * MB)})
        p.append({"i": "pid_%d_luid_0x00000000_0x0000ea62_phys_0" % pid, "c": "dedicated usage", "v": 5 * MB})
    return {"p": p, "a": [{"i": LUID + "_phys_0", "v": int(adapter_mib * MB)},
                          {"i": "luid_0x00000000_0x0000ea62_phys_0", "v": 0}]}


CARD = (16368, "AMD Radeon RX 7900 GRE")


# ---- T1 lease ----------------------------------------------------------------------------------------------------
HOLD = """
import sys, time
sys.path.insert(0, %r)
from uri_operational_intelligence import gpu_lease as G
l = G.acquire("benchmark", label="child bench", directory=sys.argv[1], max_hold_s=float(sys.argv[2]))
print("HELD", __import__("os").getpid(), flush=True)
time.sleep(60)
""" % str(REPO)


def child_holder(tmp_path, max_hold="600"):
    # A venv python.exe on Windows is a launcher; the holder's real pid is the one it prints.
    p = subprocess.Popen([sys.executable, "-c", HOLD, str(tmp_path), max_hold], stdout=subprocess.PIPE, text=True)
    word, pid = p.stdout.readline().split()
    assert word == "HELD"
    p.holder_pid = int(pid)
    return p


def kill_holder(p):
    """Hard kill of the real holder (no release), then its launcher."""
    import psutil
    try:
        psutil.Process(p.holder_pid).kill()
        psutil.Process(p.holder_pid).wait(10)
    except psutil.Error:
        pass
    p.kill()
    p.wait()


def test_lease_acquire_release_and_history(tmp_path):
    with G.acquire("runtime_v1_brain", label="t", directory=tmp_path) as lease:
        assert lease.held and G.status(tmp_path)["state"] == "HELD"
    assert G.status(tmp_path)["state"] == "FREE"
    events = [json.loads(x)["event"] for x in (tmp_path / "history.jsonl").read_text().splitlines()]
    assert events == ["ACQUIRED", "RELEASED"]


def test_second_workload_refused_with_holder_and_wait_times_out(tmp_path):
    p = child_holder(tmp_path)
    try:
        t0 = time.monotonic()
        with pytest.raises(G.GpuBusy) as e:
            G.acquire("runtime_v1_brain", directory=tmp_path, wait_s=1.0, poll_s=0.2)
        assert 0.9 <= time.monotonic() - t0 < 5
        assert e.value.holder["purpose"] == "benchmark" and e.value.holder["pid"] == p.holder_pid
        assert G.status(tmp_path)["state"] == "HELD"
        assert p.poll() is None            # the holder is never touched
    finally:
        kill_holder(p)


def test_dead_holder_is_recovered_without_touching_anyone(tmp_path):
    p = child_holder(tmp_path)
    kill_holder(p)                                   # crash: no release, the OS frees the lock
    assert G.status(tmp_path)["stale_record"] is True
    with G.acquire("runtime_v1_brain", directory=tmp_path) as lease:
        assert lease.record["recovered_from"]["pid"] == p.holder_pid
    assert "STALE_RECOVERED" in (tmp_path / "history.jsonl").read_text()


def test_overdue_holder_is_reported_not_broken(tmp_path):
    p = child_holder(tmp_path, max_hold="0.1")
    try:
        time.sleep(0.3)
        st = G.status(tmp_path)
        assert st["state"] == "HELD" and st["overdue"] is True
        with pytest.raises(G.GpuBusy):
            G.acquire("runtime_v1_brain", directory=tmp_path, override={"by": "owner"})   # override never steals
        assert p.poll() is None
    finally:
        kill_holder(p)


def test_override_is_recorded(tmp_path):
    with G.acquire("runtime_v1_brain", directory=tmp_path, override={"by": "--override-contention"}) as lease:
        assert json.loads((tmp_path / "lease.json").read_text())["override"] == {"by": "--override-contention"}
        assert lease.record["override"]


def test_cli_workload_dies_with_its_lease_holder(tmp_path):
    import psutil
    env = dict(os.environ, URI_GPU_LEASE_DIR=str(tmp_path), PYTHONPATH=str(REPO))
    marker = tmp_path / "child.pid"
    child = "import os,time; open(%r,'w').write(str(os.getpid())); time.sleep(120)" % str(marker)
    p = subprocess.Popen([sys.executable, "-m", "uri_operational_intelligence.gpu_lease", "run", "--purpose", "benchmark",
                          "--", sys.executable, "-c", child], env=env, cwd=REPO)
    t0 = time.monotonic()
    while not marker.exists() and time.monotonic() - t0 < 30:
        time.sleep(0.2)
    workload = int(marker.read_text())
    assert G.status(tmp_path)["state"] == "HELD"
    holder = json.loads((tmp_path / "lease.json").read_text())["pid"]
    psutil.Process(holder).kill()                            # the holder crashes
    p.wait(30)
    t0 = time.monotonic()
    while psutil.pid_exists(workload) and time.monotonic() - t0 < 10:
        time.sleep(0.2)
    assert not psutil.pid_exists(workload)                   # the workload went with it
    assert G.status(tmp_path)["state"] == "FREE"


def test_cli_run_refuses_while_held_and_runs_when_free(tmp_path):
    env = dict(os.environ, URI_GPU_LEASE_DIR=str(tmp_path), PYTHONPATH=str(REPO))
    cmd = [sys.executable, "-m", "uri_operational_intelligence.gpu_lease", "run", "--purpose", "benchmark", "--",
           sys.executable, "-c", "print('BENCH_RAN')"]
    ok = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=REPO)
    assert ok.returncode == 0 and "BENCH_RAN" in ok.stdout
    with G.acquire("runtime_v1_brain", directory=tmp_path):
        busy = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=REPO)
    assert busy.returncode == 75 and "BENCH_RAN" not in busy.stdout and "GPU_LEASE_HELD" in busy.stderr


# ---- T1 census and budget ----------------------------------------------------------------------------------------
def test_census_picks_the_main_adapter_and_sums_per_process():
    c = G.census(raw([(1580, 311.3, 9.1), (18372, 1601.9, 349.4)], 1950), card=CARD)
    assert c["ok"] and c["luid"] == LUID and c["card_mib"] == 16368
    assert [p["pid"] for p in c["processes"]] == [18372, 1580]
    assert c["processes"][0]["dedicated_mib"] == 1601.9 and c["unattributed_mib"] == 36.8


def test_fit_desktop_only_fits_and_a_1gb_consumer_contends():
    desktop = G.census(raw([(1580, 311.3, 9), (3144, 84.3, 23), (5384, 65.8, 1)], 470), card=CARD)
    f = G.assess_fit(desktop)
    assert f["verdict"] == G.AT_RISK and 0 < f["margin_mib"] < G.AT_RISK_MARGIN_MIB     # 281 MB margin, measured case
    ollama = G.census(raw([(1580, 311.3, 9), (18372, 1601.9, 349)], 1920), card=CARD)
    f2 = G.assess_fit(ollama)
    assert f2["verdict"] == G.CONTENDED and f2["margin_mib"] <= -G.CONTENDED_SHORTFALL_MIB
    # measured live 2026-10-09: desktop + an open URI window, 15.2 GB free: a small shortfall starts AT_RISK
    ui_open = G.census(raw([(1580, 318, 9), (3144, 84, 23), (5384, 66, 1), (9999, 210, 5), (7777, 440, 12), (9252, 33, 1)], 1160), card=CARD)
    f3 = G.assess_fit(ui_open)
    assert f3["verdict"] == G.AT_RISK and -G.CONTENDED_SHORTFALL_MIB < f3["margin_mib"] < 0
    assert "short" in G.explain(f3)
    text = G.explain(f2)
    assert "llama-server" in text or "pid 18372" in text
    assert "will not stop" in text


def test_own_server_is_not_counted_against_itself_and_unattributed_memory_blocks():
    c = G.census(raw([(1580, 311, 9), (4242, 13907, 1819)], 14300), card=CARD)
    assert G.assess_fit(c, owners={4242})["verdict"] in (G.FITS, G.AT_RISK)
    assert G.assess_fit(c)["verdict"] == G.CONTENDED
    releasing = G.census(raw([(1580, 311, 9)], 9000), card=CARD)          # a server just exited, memory still held
    f = G.assess_fit(releasing)
    assert f["unattributed_mib"] > 8000 and f["verdict"] == G.CONTENDED


def test_census_failure_is_unknown_not_fits():
    assert G.assess_fit({"ok": False, "error": "TimeoutExpired"})["verdict"] == G.UNKNOWN
    assert G.assess_fit(G.census({"p": [], "a": []}, card=CARD))["verdict"] == G.UNKNOWN


# ---- T3 health ---------------------------------------------------------------------------------------------------
SEL = {"kind": "server_local_model", "provider": "llamacpp-runtime-v1", "model": "qwen-test"}
FULLCFG = {"model": {"id": "qwen-test", "mtp_draft": {}}, "runtime": {"engine": "llama.cpp b11425 (Vulkan, win x64)",
           "ctx": 32768, "vision_enabled": True}, "tiers": {"fast": {}, "normal": {}, "deep": {}}}


SERVER = {"pid": 4242, "create_time": 500.0}


def health(r="READY", host=None, alive=True, perf=None, busy=False, sel=SEL, server=SERVER):
    return BH.assess(readiness={"state": r}, host=host, host_alive=alive, perf=perf or {}, busy=busy, selected=sel,
                     cfg=FULLCFG, now=1000.0, server=server)


def host(state, **kw):
    if "calibration" in kw:
        kw["calibration"] = dict({"server_pid": 4242, "server_create_time": 500.0}, **kw["calibration"])
    return {"schema": BH.REPORT_SCHEMA, "state": state, "updated_at": 990.0, **kw}


def test_health_states():
    assert health(host=host("READY", calibration={"decode_tps": 121.0, "t": 900}))["state"] == BH.READY
    assert health(host=host("READY", calibration={"decode_tps": 121.0, "t": 900}), busy=True)["state"] == BH.BUSY
    d = health(host=host("DEGRADED", calibration={"decode_tps": 27.0, "t": 900}, explain="slow"))
    assert d["state"] == BH.DEGRADED and "restart_brain" in d["recovery_options"]
    assert d["performance"]["calibration_tps"] == 27.0 and d["performance"]["evidence"] == "calibration"
    assert health(r="LOADING", host=host("LOADING"))["state"] == BH.RECOVERING
    assert health(r="STOPPED", host=host("RELEASE_WAIT"))["state"] == BH.RECOVERING
    w = health(r="STOPPED", host=host("WAITING_FOR_GPU", detail="GPU_CONTENDED", explain="In use by: ollama"))
    assert w["state"] == BH.UNAVAILABLE and w["reasons"] == ["GPU_CONTENDED"] and "close_gpu_apps" in w["recovery_options"]
    s = health(r="STOPPED", host=None, alive=False)
    assert s["state"] == BH.UNAVAILABLE and s["recovery_options"] == ["start_from_launcher"]
    assert health(r="STOPPED", host=host("STOPPED"))["recovery_options"] == ["start_brain"]
    n = health(sel={"provider": "deterministic"})
    assert n["state"] == BH.UNAVAILABLE and n["reasons"] == ["NOT_SELECTED"]


def test_turn_evidence_supersedes_calibration_and_dead_host_is_ignored():
    slow = {"decode_tps_median": 31.0, "decode_samples": 3}
    h = host("READY", calibration={"decode_tps": 120.0, "t": 900})
    assert health(host=h, perf=slow)["state"] == BH.DEGRADED
    fast = {"decode_tps_median": 118.0, "decode_samples": 4}
    assert health(host=host("DEGRADED", calibration={"decode_tps": 27.0, "t": 900}), perf=fast)["state"] == BH.READY
    stale = health(host=host("DEGRADED", calibration={"decode_tps": 27.0, "t": 900}), alive=False)
    assert stale["state"] == BH.READY and "SPEED_NOT_MEASURED" in stale["reasons"] and not stale["host"]["running"]


def test_calibration_of_another_instance_is_ignored():
    h = host("DEGRADED", calibration={"decode_tps": 27.0, "t": 900})
    assert health(host=h)["state"] == BH.DEGRADED
    other = health(host=h, server={"pid": 5151, "create_time": 800.0})       # a different server now answers
    assert other["state"] == BH.READY and other["performance"]["calibration_tps"] is None
    assert "SPEED_NOT_MEASURED" in other["reasons"]
    assert health(host=h, server=None)["performance"]["calibration_tps"] is None


def test_desktop_compositor_alone_does_not_suggest_closing_apps():
    h = host("DEGRADED", calibration={"decode_tps": 27.0, "t": 900},
             residency={"consumers": [{"pid": 1, "name": "dwm.exe", "role": "desktop compositor", "dedicated_mib": 311}]})
    assert "close_gpu_apps" not in health(host=h)["recovery_options"]


def test_host_request_and_report_link(tmp_path):
    req = BH.write_host_request(tmp_path, "restart")
    assert json.loads((tmp_path / BH.REQUEST_FILE).read_text())["id"] == req["id"]
    with pytest.raises(ValueError):
        BH.write_host_request(tmp_path, "kill_everything")
    assert BH.read_host_report(tmp_path) == (None, False)
    import psutil
    me = psutil.Process()
    (tmp_path / BH.REPORT_FILE).write_text(json.dumps({"schema": BH.REPORT_SCHEMA, "state": "READY",
                                                       "host_pid": me.pid, "host_started": me.create_time()}))
    assert BH.read_host_report(tmp_path)[1] is True
    (tmp_path / BH.REPORT_FILE).write_text(json.dumps({"schema": BH.REPORT_SCHEMA, "host_pid": me.pid,
                                                       "host_started": me.create_time() - 100}))
    assert BH.read_host_report(tmp_path)[1] is False        # pid reused by another process: not our host


# ---- T3 bridge commands ------------------------------------------------------------------------------------------
def test_bridge_health_restart_and_turn_status(fake, tmp_path):  # noqa: F811
    requests = []
    srv_ct = time.time() - 3600
    rep = {"schema": BH.REPORT_SCHEMA, "state": "READY", "calibration": {"decode_tps": 119.0, "t": time.time() - 5,
           "server_pid": 77, "server_create_time": srv_ct}, "updated_at": time.time()}
    b, frames, _ = make(fake, tmp_path, FakeCore())
    b._host_report = lambda: (rep, True)
    b._host_request = lambda a: requests.append(a) or {"id": "r1"}
    from uri_operational_intelligence.runtime_v1 import Readiness
    b._status = lambda: Readiness("READY", fake.url, model_id="qwen-test",
                                  live_identity={"process": {"pid": 77, "create_time": srv_ct}})
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["state"] == "READY" and h["performance"]["calibration_tps"] == 119.0
    # samples of a previous instance (before this calibration) never count
    old = time.time() - 60
    for _ in range(3):
        b._perf.append((old, {"predicted_n": 200, "predicted_per_second": 25.0}))
    assert b.handle("brain_health", {"command": "brain_health"})["state"] == "READY"
    for _ in range(3):
        b._perf.append((time.time(), {"predicted_n": 200, "predicted_per_second": 26.0}))
    d = b.handle("brain_health", {"command": "brain_health"})
    assert d["state"] == "DEGRADED" and d["performance"]["decode_samples"] == 3
    assert b.handle("brain_restart", {"command": "brain_restart", "action": "restart"})["requested"] == "restart"
    assert requests == ["restart"]
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_restart", {"command": "brain_restart", "action": "format_disk"})
    assert e.value.code == "ACTION_INVALID"
    b._host_report = lambda: (rep, False)
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_restart", {"command": "brain_restart", "action": "restart"})
    assert e.value.code == "BRAIN_HOST_NOT_RUNNING"
    st = b.handle("oi_turn_status", {"command": "oi_turn_status"})
    assert st["busy"] is False and st["turn_id"] is None


def test_no_turn_starts_until_the_host_has_acted_on_a_restart(fake, tmp_path):  # noqa: F811
    rep = {"schema": BH.REPORT_SCHEMA, "state": "READY", "updated_at": time.time() - 10}
    b, frames, _ = make(fake, tmp_path, FakeCore())
    b._host_report = lambda: (rep, True)
    b._host_request = lambda a: {"id": "req-1"}
    b.handle("brain_restart", {"command": "brain_restart", "action": "restart"})
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "hi", "depth": "fast"})
    assert e.value.code == "BRAIN_RESTARTING"
    assert b.handle("brain_health", {"command": "brain_health"})["state"] == "RECOVERING"
    rep.update(state="READY", last_request={"id": "req-1", "result": "ACCEPTED"}, updated_at=time.time() + 1)
    with pytest.raises(BridgeRefused):            # accepted but not acted on yet: still gated
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "hi", "depth": "fast"})
    b._host_report = lambda: (None, False)          # an unreadable report is not evidence of a dead host
    with pytest.raises(BridgeRefused):
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "hi", "depth": "fast"})
    b._host_report = lambda: (rep, True)
    rep.update(last_request={"id": "req-1", "result": "DONE", "done_state": "READY"}, requests={"req-1": "DONE"})
    fake.scripts.append({"chunks": [("answer", "ok")], "finish": "stop"})
    assert b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "hi", "depth": "fast"})["accepted"]
    b.wait(10)


def test_restart_gate_opens_when_the_host_is_gone(fake, tmp_path):  # noqa: F811
    state = {"alive": True}
    b, _, _ = make(fake, tmp_path, FakeCore())
    b._host_report = lambda: ({"schema": BH.REPORT_SCHEMA, "state": "READY"}, state["alive"])
    b._host_request = lambda a: {"id": "req-2"}
    b.handle("brain_restart", {"command": "brain_restart", "action": "stop"})
    assert b._restart_pending()
    state["alive"] = False
    assert not b._restart_pending()


def test_the_gate_follows_the_latest_request_and_ignored_requests_open_it(fake, tmp_path):  # noqa: F811
    rep = {"schema": BH.REPORT_SCHEMA, "state": "READY", "requests": {}}
    ids = iter(["a", "b", "c"])
    b, _, _ = make(fake, tmp_path, FakeCore())
    b._host_report = lambda: (rep, True)
    b._host_request = lambda a: {"id": next(ids)}
    b.handle("brain_restart", {"command": "brain_restart", "action": "stop"})       # "a" overwritten before read
    b.handle("brain_restart", {"command": "brain_restart", "action": "start"})      # "b"
    assert b._restart_pending()
    rep["requests"] = {"b": "DONE"}
    assert not b._restart_pending()
    b.handle("brain_restart", {"command": "brain_restart", "action": "restart"})    # "c"
    rep["requests"] = {"b": "DONE", "c": "IGNORED_INVALID_OR_STALE"}
    assert not b._restart_pending()


def test_host_liveness_needs_positive_evidence(monkeypatch):
    import psutil
    now = time.time()

    def denied(pid):
        raise psutil.AccessDenied(pid)
    monkeypatch.setattr(psutil, "Process", denied)
    assert BH.host_alive({"host_pid": 1, "updated_at": now - 5}, now=now) is True       # fresh heartbeat
    assert BH.host_alive({"host_pid": 1, "updated_at": now - 500}, now=now) is False    # stale heartbeat

    def gone(pid):
        raise psutil.NoSuchProcess(pid)
    monkeypatch.setattr(psutil, "Process", gone)
    assert BH.host_alive({"host_pid": 1, "updated_at": now}, now=now) is False


def test_timings_belong_to_the_verified_server_instance(fake, tmp_path):  # noqa: F811
    from uri_operational_intelligence.runtime_v1 import Readiness
    ident = {"pid": 4242, "create_time": time.time() - 100}
    b, _, _ = make(fake, tmp_path, FakeCore())
    b._status = lambda: Readiness("READY", fake.url, model_id="qwen-test",
                                  live_identity={"process": dict(ident)})
    b._host_report = lambda: (None, False)                    # no host: identity alone decides
    for _ in range(3):
        b._perf.append((time.time(), {"predicted_n": 200, "predicted_per_second": 25.0}))
    assert b.handle("brain_health", {"command": "brain_health"})["state"] == "DEGRADED"
    ident.update(pid=5151, create_time=time.time())           # a new instance: old samples are dropped
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["state"] == "READY" and h["performance"]["decode_samples"] == 0
    b._status = lambda: Readiness("READY", fake.url, model_id="qwen-test")      # identity not established
    for _ in range(3):
        b._perf.append((time.time(), {"predicted_n": 200, "predicted_per_second": 25.0}))
    assert b.handle("brain_health", {"command": "brain_health"})["performance"]["decode_samples"] == 0


def test_restart_refused_while_a_turn_runs_and_status_stays_open(fake, tmp_path):  # noqa: F811
    fake.scripts.append({"chunks": [("answer", "x")] * 3, "finish": "stop", "first_delay": 1.5})
    b, frames, _ = make(fake, tmp_path, FakeCore())
    b._host_report = lambda: ({"schema": BH.REPORT_SCHEMA, "state": "READY"}, True)
    b._host_request = lambda a: {"id": "r"}
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "What is VRAM?", "depth": "fast"})
    time.sleep(0.3)
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_restart", {"command": "brain_restart", "action": "restart"})
    assert e.value.code == "TURN_IN_PROGRESS"
    st = b.handle("oi_turn_status", {"command": "oi_turn_status"})
    assert st["busy"] and st["turn_id"] == r["turn_id"] and st["idle_s"] >= 0.2 and st["age_s"] >= st["idle_s"]
    assert b.handle("brain_health", {"command": "brain_health"})["state"] == "BUSY"
    b.wait(10)
    assert b.handle("oi_turn_status", {"command": "oi_turn_status"})["busy"] is False


def test_new_command_schemas_are_exact(fake, tmp_path):  # noqa: F811
    b, _, _ = make(fake, tmp_path, FakeCore())
    for bad in ({"command": "brain_health", "x": 1}, {"command": "brain_restart"},
                {"command": "oi_turn_status", "turn_id": "t"}):
        with pytest.raises(BridgeRefused) as e:
            b.handle(bad["command"], bad)
        assert e.value.code == "COMMAND_SCHEMA"


# ---- T2 host (pieces that need no GPU) ---------------------------------------------------------------------------
def load_host():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ws_brain_host", REPO / "scripts" / "ws_brain_host.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Seq:
    def __init__(self, samples):
        self.samples, self.n = samples, 0

    def __call__(self):
        s = self.samples[min(self.n, len(self.samples) - 1)]
        self.n += 1
        return s


def new_host(tmp_path, census, override=False, port=18470, quiet=0.05):
    H = load_host()
    H.GPU_POLL_S = 0.05
    H.QUIET_S = quiet
    cfg = {"model": {"id": "qwen-test"}, "runtime": {"port": port, "ctx": 32768}}
    h = H.Host(tmp_path / "client", minutes=1, override=override, cfg=cfg, state_dir=tmp_path / "state",
               census=census, lease_dir=tmp_path / "lease")
    return H, h


def test_host_waits_while_contended_and_explains_then_starts_when_free(tmp_path):
    busy = G.census(raw([(1580, 311, 9), (18372, 1602, 349)], 1950), card=CARD)
    free = G.census(raw([(1580, 311, 9)], 330), card=CARD)
    H, h = new_host(tmp_path, Seq([busy, busy, free]))
    assert h.wait_for_gpu() is True
    states = [x["state"] for x in h.report["history"]]
    assert "WAITING_FOR_GPU" in states
    rep = json.loads((tmp_path / "client" / BH.REPORT_FILE).read_text())
    assert rep["schema"] == BH.REPORT_SCHEMA
    assert "will not stop" in rep["explain"]          # the last waiting explanation stays until the next state


def test_host_waits_for_a_quiet_window_after_contention(tmp_path):
    busy = G.census(raw([(1580, 311, 9), (20036, 13907, 1819)], 14300), card=CARD)    # another session's load
    gap = G.census(raw([(1580, 311, 9)], 330), card=CARD)                              # between its loads
    H, h = new_host(tmp_path, Seq([busy, gap, gap, gap]))
    H.QUIET_S = 1.0
    t0 = time.monotonic()
    assert h.wait_for_gpu() is True
    assert time.monotonic() - t0 >= 1.0
    details = [x["detail"] for x in h.report["history"]]
    assert "GPU_CONTENDED" in details and "GPU_QUIET_WINDOW" in details


def test_quiet_window_survives_a_host_restart(tmp_path):
    busy = G.census(raw([(1580, 311, 9), (20036, 13907, 1819)], 14300), card=CARD)
    gap = G.census(raw([(1580, 311, 9)], 330), card=CARD)
    H, h = new_host(tmp_path, Seq([busy]), quiet=600)
    h.deadline = time.monotonic() + 0.2
    assert h.wait_for_gpu() is False                       # saw contention, then the host exited
    H2, h2 = new_host(tmp_path, Seq([gap]), quiet=600)     # a fresh host process on a momentarily free GPU
    h2.deadline = time.monotonic() + 0.3
    assert h2.wait_for_gpu() is False
    assert h2.report["detail"] == "GPU_QUIET_WINDOW"


def test_host_starts_at_once_on_a_free_gpu(tmp_path):
    free = G.census(raw([(1580, 311, 9)], 330), card=CARD)
    H, h = new_host(tmp_path, Seq([free]))
    t0 = time.monotonic()
    assert h.wait_for_gpu() is True and time.monotonic() - t0 < 1.0
    assert "WAITING_FOR_GPU" not in [x["state"] for x in h.report["history"]]


def test_host_override_starts_next_to_contention_and_records_it(tmp_path):
    busy = G.census(raw([(1580, 311, 9), (18372, 1602, 349)], 1950), card=CARD)
    H, h = new_host(tmp_path, Seq([busy]), override=True)
    assert h.wait_for_gpu() is True and h.report["override"]["by"] == "--override-contention"
    assert h.report["gpu"]["fit"]["verdict"] == G.CONTENDED


def test_host_release_wait_is_measured_not_a_fixed_delay(tmp_path):
    releasing = G.census(raw([(1580, 311, 9)], 9000), card=CARD)
    done = G.census(raw([(1580, 311, 9)], 330), card=CARD)
    H, h = new_host(tmp_path, Seq([releasing, releasing, done]))
    h.stopped_at = time.time()
    assert h.wait_for_gpu() is True
    assert "RELEASE_WAIT" in [x["state"] for x in h.report["history"]]
    assert h.report["release_measurement"]["unattributed_mib"] < H.RELEASE_UNATTRIBUTED_MIB


def test_stop_during_load_kills_the_owned_job_without_waiting(tmp_path, monkeypatch):
    H, h = new_host(tmp_path, Seq([G.census(raw([(1580, 311, 9)], 330), card=CARD)]))
    events = {"stopped": False}

    class SlowManager:
        owns_instance = True

        def __init__(self, *a, **k):
            pass

        def ensure_ready(self, on_state=None):
            on_state and on_state("LOADING")
            while not events["stopped"]:
                time.sleep(0.05)
            time.sleep(5)              # the accepted manager keeps polling after a kill; the host must not wait
            return None

        def stop(self):
            events["stopped"] = True
            return True
    monkeypatch.setattr(H.R, "RuntimeManager", SlowManager)
    (tmp_path / "client").mkdir(parents=True, exist_ok=True)
    threading.Timer(0.5, lambda: BH.write_host_request(tmp_path / "client", "stop")).start()
    t0 = time.monotonic()
    assert h.start_brain() is False
    assert time.monotonic() - t0 < 3 and events["stopped"] is True
    assert h.report["detail"] == "STOPPED_DURING_LOAD"


def test_a_restart_request_during_load_is_kept_for_later(tmp_path):
    H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]))
    (tmp_path / "client").mkdir(parents=True, exist_ok=True)
    BH.write_host_request(tmp_path / "client", "restart")
    assert h.take_request(only="stop") is None
    assert h.take_request() == "restart"


def test_unmeasurable_gpu_and_unfinished_release_wait_instead_of_starting(tmp_path):
    H, h = new_host(tmp_path, Seq([{"ok": False, "error": "TimeoutExpired"}]))
    h.deadline = time.monotonic() + 0.3
    assert h.wait_for_gpu() is False and h.report["detail"] == "GPU_UNMEASURED"
    releasing = G.census(raw([(1580, 311, 9)], 9000), card=CARD)
    H, h = new_host(tmp_path, Seq([releasing]))
    H.RELEASE_TIMEOUT_S = 0.0
    h.deadline = time.monotonic() + 0.3
    assert h.wait_for_gpu() is False and h.report["detail"] == "VRAM_RELEASE_TIMEOUT"


def test_a_load_stopped_before_its_spawn_is_reaped_before_the_lease_goes(tmp_path, monkeypatch):
    H, h = new_host(tmp_path, Seq([G.census(raw([(1580, 311, 9)], 330), card=CARD)]))
    killed = []

    class Contained:
        pass

    class LateSpawner:
        owns_instance = True

        def __init__(self, *a, **k):
            self._contained = None

        def ensure_ready(self, on_state=None):
            time.sleep(1.0)                    # the stop arrives before the spawn
            self._contained = Contained()      # ... and the spawn still happens
            time.sleep(0.5)
            return None

        def stop(self):
            if self._contained is not None:
                killed.append(True)
            self._contained = None
            return True
    monkeypatch.setattr(H.R, "RuntimeManager", LateSpawner)
    assert h.acquire_lease()
    (tmp_path / "client").mkdir(parents=True, exist_ok=True)
    threading.Timer(0.3, lambda: BH.write_host_request(tmp_path / "client", "stop")).start()
    assert h.start_brain() is False
    assert h.loaders and G.status(tmp_path / "lease")["state"] == "HELD"     # still held while the loader lives
    h.release_lease("test")                                                   # waits for the loader, however long
    assert killed == [True] and h.loaders == [] and G.status(tmp_path / "lease")["state"] == "FREE"


def test_a_long_living_loader_keeps_the_lease_and_exit_leaves_release_to_the_os(tmp_path):
    H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]))
    assert h.acquire_lease()
    stop = threading.Event()
    t = threading.Thread(target=stop.wait, daemon=True)
    t.start()

    class M:
        _contained = None

        def stop(self):
            return True
    h.loaders.append((t, M()))
    h.deadline = time.monotonic() - 1            # host exiting
    h.release_lease("host exit", at_exit=True)
    assert G.status(tmp_path / "lease")["state"] == "HELD" and h.report["lease"]["released_by"].startswith("process exit")
    stop.set()
    t.join(2)
    h.release_lease("later")
    assert G.status(tmp_path / "lease")["state"] == "FREE"


def test_requests_are_marked_done_with_the_state_they_left(tmp_path):
    H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]))
    (tmp_path / "client").mkdir(parents=True, exist_ok=True)
    BH.write_host_request(tmp_path / "client", "stop")
    assert h.take_request() == "stop" and h.report["last_request"]["result"] == "ACCEPTED"
    h.set("STOPPED", detail="STOP_REQUESTED")
    h.finish_request()
    lr = json.loads((tmp_path / "client" / BH.REPORT_FILE).read_text())["last_request"]
    assert lr["result"] == "DONE" and lr["done_state"] == "STOPPED"


def test_host_requests_are_explicit_fresh_and_used_once(tmp_path):
    H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]))
    (tmp_path / "client").mkdir(parents=True, exist_ok=True)
    req = BH.write_host_request(tmp_path / "client", "restart")
    assert h.take_request() == "restart" and h.take_request() is None
    stale = dict(req, id="old", requested_at=time.time() - 3600)
    (tmp_path / "client" / BH.REQUEST_FILE).write_text(json.dumps(stale))
    assert h.take_request() is None and h.report["last_request"]["result"] == "IGNORED_INVALID_OR_STALE"
    (tmp_path / "client" / BH.REQUEST_FILE).write_text(json.dumps(dict(req, id="x", action="rm -rf")))
    assert h.take_request() is None


class Timings(BaseHTTPRequestHandler):
    tps = 120.0

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(n))
        assert body["n_predict"] == 160 and body["ignore_eos"] is True
        out = json.dumps({"content": "x", "timings": {"predicted_n": 160, "predicted_per_second": self.tps,
                                                      "prompt_ms": 20}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


@pytest.mark.parametrize("tps,state", [(121.0, "READY"), (27.0, "DEGRADED")])
def test_calibration_classifies_the_instance(tmp_path, tps, state):
    handler = type("T", (Timings,), {"tps": tps})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        H, h = new_host(tmp_path, Seq([G.census(raw([(1580, 311, 9)], 330), card=CARD)]), port=srv.server_address[1])
        h.calibrate(pid=999999)
        assert h.report["state"] == state and h.report["calibration"]["decode_tps"] == tps
    finally:
        srv.shutdown()


def test_calibration_failure_is_reported_as_degraded(tmp_path):
    H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]), port=1)    # nothing listens
    h.calibrate(pid=1)
    assert h.report["state"] == "DEGRADED" and h.report["detail"] == "CALIBRATION_FAILED"


def test_host_waits_for_another_uri_lease_holder(tmp_path):
    p = child_holder(tmp_path / "lease")
    try:
        H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]))
        h.deadline = time.monotonic() + 1.5
        assert h.acquire_lease() is False
        assert h.report["state"] == "WAITING_FOR_LEASE" and h.report["lease"]["holder"]["purpose"] == "benchmark"
        assert p.poll() is None
    finally:
        kill_holder(p)
