"""Brain Quick Controls - controlled canonical integration review IC-1 (IC1-01, IC1-02, IC1-04) regressions."""
import threading
import time

from tests.oi.test_brain_quick_controls import bridge, qc_host, request, FakeMgr, TIGHT
from tests.ws.test_ws_worker_bridge import fake  # noqa: F401  (pytest fixture)
from tests.ws.test_ws_hardening import Seq, raw, CARD
from uri_operational_intelligence import brain_health as BH
from uri_operational_intelligence import gpu_lease as G


def test_restart_during_a_switch_leaves_no_stale_switch(fake, tmp_path):  # noqa: F811
    b, rep, _requests = bridge(fake, tmp_path)
    assert b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "long"})["requested"] == \
        "reconfigure"
    # Restart Brain while the switch is pending: the restart replaces the switch.
    b.handle("brain_restart", {"command": "brain_restart", "action": "restart"})
    assert b._switch is None
    rep["requests"] = {"req-2": "DONE"}
    assert b.handle("brain_health", {"command": "brain_health"})["controls"]["switch"]["pending"] is False
    # A later ordinary restart is reported as a restart, never as a profile switch.
    b.handle("brain_restart", {"command": "brain_restart", "action": "restart"})
    h = b.handle("brain_health", {"command": "brain_health"})
    assert b._switch is None
    assert "PROFILE_SWITCH" not in h["reasons"]
    assert h["controls"]["switch"]["pending"] is False


def test_stop_while_a_switch_waits_for_the_gpu_ends_the_switch_as_stopped(tmp_path, monkeypatch):
    _H, h = qc_host(tmp_path, Seq([TIGHT]))
    h.mgr = FakeMgr()
    monkeypatch.setattr(h, "owners", lambda: set())
    monkeypatch.setattr(h, "acquire_lease", lambda: True)
    h.lease = object.__new__(type("L", (), {"heartbeat": lambda self, **k: None}))
    busy = G.census(raw([(1580, 4000, 9)], 4068), card=CARD)
    seq = iter([TIGHT] + [busy] * 1000)
    h.census = lambda: next(seq)
    h.deadline = time.monotonic() + 20
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    threading.Timer(0.6, lambda: BH.write_host_request(h.report_dirs[0], "stop")).start()
    h.reconfigure()
    assert h.report["profile_switch"]["result"] == "STOPPED"


def test_selection_write_is_retried_before_an_error_is_recorded(tmp_path, monkeypatch):
    _H, h = qc_host(tmp_path, Seq([TIGHT]))
    calls = []
    real = h._sync_selection_once

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            h.report["selection_error"] = "PermissionError"
            return
        real()
    monkeypatch.setattr(h, "_sync_selection_once", flaky)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    h.sync_selection()
    assert len(calls) == 3
    assert "selection_error" not in h.report
