"""UI-CONTROLS-TYPO-20261018: a failed Brain profile switch restores the previous known-good profile (closes QC-F5).

Simulation level: the real Brain host class (scripts/ws_brain_host.py) with recorded GPU census samples, a real GPU
lease in a temp directory and a fake RuntimeManager whose start succeeds, fails or blocks per profile. The real worker
bridge for the health explanation. The live switch with the real Brain is covered by the milestone's live evidence."""
import json
import threading
import time

import pytest

from tests.oi.test_brain_quick_controls import ROOMY, LONG, FakeMgr, bridge, frozen, qc_host, request
from tests.ws.test_ws_worker_bridge import fake  # noqa: F401  (pytest fixture)
from uri_operational_intelligence import brain_health as BH
from uri_operational_intelligence import brain_quick_controls as QC
from uri_operational_intelligence import gpu_lease as G
from uri_operational_intelligence import runtime_profile_selection as PS
from uri_operational_intelligence import runtime_profiles as RP
from uri_operational_intelligence import runtime_v1 as R


class FakeRM:
    """Stands in for RuntimeManager: `plan` maps a profile id to READY, FAILED or BLOCK (load until stopped)."""
    plan = {}
    started = []

    def __init__(self, cfg, state_dir=None):
        self.cfg, self.owns_instance, self._contained, self.load_seconds = cfg, True, None, 1.0
        self._stop = threading.Event()

    def ensure_ready(self, on_state=None):
        pid = RP.describe(self.cfg)["id"]
        FakeRM.started.append(pid)
        what = FakeRM.plan.get(pid, "READY")
        if what == "BLOCK":
            self._stop.wait(20)
            return R.Readiness(state="STOPPED", url="x", detail="STOPPED")
        if what == "FAILED":
            return R.Readiness(state="FAILED", url="x", detail="READY_TIMEOUT")
        return R.Readiness(state=R.READY, url="x", pid=4242, model_id="qwen")

    def stop(self):
        self._stop.set()
        return True


@pytest.fixture()
def host(tmp_path, monkeypatch):
    H, h = qc_host(tmp_path, lambda: ROOMY)
    monkeypatch.setattr(H.R, "RuntimeManager", FakeRM)
    monkeypatch.setattr(h, "owners", lambda: set())
    monkeypatch.setattr(h, "calibrate", lambda pid, **k: h.set("READY", detail=None, explain="Brain ready."))
    FakeRM.plan, FakeRM.started = {}, []
    h.lease = G.acquire("runtime_v1_brain", label="test", expected_vram_mib=h.required_mib,
                        directory=tmp_path / "lease")
    h.mgr = FakeMgr()                     # Standard (frozen) runs before the switch
    h.deadline = time.monotonic() + 30
    yield H, h
    if h.lease is not None:
        h.lease.release("test")


def lease_mib(tmp_path):
    return json.loads((tmp_path / "lease" / "lease.json").read_text())["expected_vram_mib"]


def test_failed_switch_restores_the_previous_profile_and_says_so(host, tmp_path):
    H, h = host
    FakeRM.plan = {"c64k-visoff-mtpoff": "FAILED"}
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    h.reconfigure()
    sw = h.report["profile_switch"]
    assert FakeRM.started == ["c64k-visoff-mtpoff", "frozen"]
    assert sw["result"] == "FAILED", "the switch itself failed; that stays recorded"
    assert sw["restored"] is True
    fb = sw["fallback"]
    assert fb["to"] == "frozen" and fb["label"] == "Standard" and fb["result"] == "READY"
    assert fb["after"] == {"state": "FAILED", "detail": "READY_TIMEOUT"} and fb["seconds"] is not None
    # the host serves the frozen config again: object, selection (absent = frozen), lease budget, report
    assert R.config_digest(h.cfg) == R.config_digest(frozen()) and h.report["profile"]["id"] == "frozen"
    assert not (h.report_dirs[0] / PS.SELECTION_FILE).exists()
    assert h.required_mib == G.RUNTIME_V1_DEVICE_MIB and lease_mib(tmp_path) == G.RUNTIME_V1_DEVICE_MIB
    assert h.report["state"] == "READY" and h.mgr is not None
    assert "SWITCH_FALLBACK" in [x["detail"] for x in h.report["history"]]


def test_restore_from_long_context_writes_the_long_selection_back(tmp_path, monkeypatch):
    long_cfg = RP.derive_config(frozen(), *LONG)
    H, h = qc_host(tmp_path, lambda: ROOMY, cfg=long_cfg)
    monkeypatch.setattr(H.R, "RuntimeManager", FakeRM)
    monkeypatch.setattr(h, "owners", lambda: set())
    monkeypatch.setattr(h, "calibrate", lambda pid, **k: h.set("READY", detail=None))
    FakeRM.plan, FakeRM.started = {"frozen": "FAILED"}, []
    h.lease = G.acquire("runtime_v1_brain", label="t", expected_vram_mib=h.required_mib, directory=tmp_path / "lease")
    try:
        h.mgr = FakeMgr()
        h.sync_selection()
        assert request(h, {"ctx": 32768, "vision": "gpu", "mtp": True}) == "reconfigure"
        h.reconfigure()
        sw = h.report["profile_switch"]
        assert sw["result"] == "FAILED" and sw["restored"] is True and sw["fallback"]["label"] == "Long context"
        assert h.cfg is long_cfg and lease_mib(tmp_path) == 13658
        cfg_w, note = PS.select(frozen(), h.report_dirs[0] / PS.SELECTION_FILE)
        assert note["profile"]["id"] == "c64k-visoff-mtpoff"      # what the worker verifies against again
    finally:
        h.lease.release("test")


def test_restore_that_also_fails_is_a_truthful_failed_and_is_tried_once(host):
    H, h = host
    FakeRM.plan = {"c64k-visoff-mtpoff": "FAILED", "frozen": "FAILED"}
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    h.reconfigure()
    sw = h.report["profile_switch"]
    assert FakeRM.started == ["c64k-visoff-mtpoff", "frozen"], "one restore attempt, no loop"
    assert sw["result"] == "FAILED" and sw["restored"] is False and sw["fallback"]["result"] == "FAILED"
    assert h.report["state"] == "FAILED" and h.mgr is None
    assert h.lease is not None, "the lease is kept; Restart Brain uses it"


def test_stop_during_the_switch_load_ends_as_stopped_without_a_restore(host):
    H, h = host
    FakeRM.plan = {"c64k-visoff-mtpoff": "BLOCK"}
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    threading.Timer(0.6, lambda: BH.write_host_request(h.report_dirs[0], "stop")).start()
    h.reconfigure()
    sw = h.report["profile_switch"]
    assert sw["result"] == "STOPPED" and "fallback" not in sw
    assert FakeRM.started == ["c64k-visoff-mtpoff"]
    assert h.stop_requested is True          # the main loop then releases the lease and reports STOPPED


def test_stop_during_the_restore_ends_the_restore_as_stopped(host):
    H, h = host
    FakeRM.plan = {"c64k-visoff-mtpoff": "FAILED", "frozen": "BLOCK"}
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    threading.Timer(0.6, lambda: BH.write_host_request(h.report_dirs[0], "stop")).start()
    h.reconfigure()
    sw = h.report["profile_switch"]
    assert sw["result"] == "FAILED" and sw["fallback"]["result"] == "STOPPED" and sw["restored"] is False


def test_restart_requested_during_the_switch_waits_for_it_and_is_handled_after(host):
    H, h = host
    FakeRM.plan = {"c64k-visoff-mtpoff": "FAILED"}
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    real = FakeRM.ensure_ready

    def slow(self, on_state=None):
        if not FakeRM.started:
            BH.write_host_request(h.report_dirs[0], "restart")      # the user presses Restart Brain mid-switch
        return real(self, on_state)
    FakeRM.ensure_ready = slow
    try:
        h.reconfigure()
    finally:
        FakeRM.ensure_ready = real
    sw = h.report["profile_switch"]
    assert sw["result"] == "FAILED" and sw["restored"] is True
    # the restart was not consumed by the switch; the main loop takes it next and restarts the restored profile
    assert h.take_request() == "restart"
    assert h.report["profile"]["id"] == "frozen"


def test_no_restore_when_the_brain_was_stopped_before_the_switch(tmp_path, monkeypatch):
    H, h = qc_host(tmp_path, lambda: ROOMY)
    monkeypatch.setattr(H.R, "RuntimeManager", FakeRM)
    monkeypatch.setattr(h, "owners", lambda: set())
    monkeypatch.setattr(h, "acquire_lease", lambda: True)
    h.lease = type("L", (), {"heartbeat": lambda self, **k: None})()
    FakeRM.plan, FakeRM.started = {"c64k-visoff-mtpoff": "FAILED"}, []
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    h.reconfigure()
    sw = h.report["profile_switch"]
    assert sw["result"] == "FAILED" and "fallback" not in sw and FakeRM.started == ["c64k-visoff-mtpoff"]


def test_no_restore_to_a_research_profile(tmp_path, monkeypatch):
    p1 = RP.derive_config(frozen(), 65536, "gpu", False)          # unqualified P1 started with --profile
    H, h = qc_host(tmp_path, lambda: ROOMY, cfg=p1)
    monkeypatch.setattr(H.R, "RuntimeManager", FakeRM)
    monkeypatch.setattr(h, "owners", lambda: set())
    monkeypatch.setattr(h, "calibrate", lambda pid, **k: h.set("READY", detail=None))
    h.lease = type("L", (), {"heartbeat": lambda self, **k: None})()
    h.mgr = FakeMgr()
    FakeRM.plan, FakeRM.started = {"frozen": "FAILED"}, []
    assert request(h, {"ctx": 32768, "vision": "gpu", "mtp": True}) == "reconfigure"
    h.reconfigure()
    sw = h.report["profile_switch"]
    assert sw["result"] == "FAILED" and "fallback" not in sw and FakeRM.started == ["frozen"]


def test_a_successful_switch_is_unchanged_and_has_no_fallback_record(host):
    H, h = host
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    h.reconfigure()
    sw = h.report["profile_switch"]
    assert sw["result"] == "READY" and "fallback" not in sw and "restored" not in sw
    assert FakeRM.started == ["c64k-visoff-mtpoff"]


def test_worker_explains_the_restore_while_it_runs(fake, tmp_path):  # noqa: F811
    b, rep, _requests = bridge(fake, tmp_path)
    r = b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "long"})
    rid = r["request_id"]
    rep["profile_switch"] = {"id": rid, "from": "frozen", "to": "c64k-visoff-mtpoff", "result": "FAILED",
                             "restored": False, "fallback": {"to": "frozen", "label": "Standard",
                                                             "result": "IN_PROGRESS"}}
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["state"] == BH.RECOVERING and h["controls"]["switch"]["pending"] is True
    assert "did not start with Long context" in h["explain"] and "going back to Standard" in h["explain"]
    assert h["controls"]["switch"]["last"]["fallback"]["result"] == "IN_PROGRESS"


def test_profile_id_maps_back_to_the_catalog():
    assert QC.entry_by_profile_id("frozen")["id"] == "standard"
    assert QC.entry_by_profile_id("c64k-visoff-mtpoff")["id"] == "long"
    assert QC.entry_by_profile_id("nope") is None


def test_restore_to_standard_draft_off_after_the_closure(tmp_path, monkeypatch):
    """Closure ec2fab54 made P3 (Standard, draft off) a Quick Controls target; a failed switch away from it restores it."""
    p3 = RP.derive_config(frozen(), 32768, "gpu", False)
    H, h = qc_host(tmp_path, lambda: ROOMY, cfg=p3)
    monkeypatch.setattr(H.R, "RuntimeManager", FakeRM)
    monkeypatch.setattr(h, "owners", lambda: set())
    monkeypatch.setattr(h, "calibrate", lambda pid, **k: h.set("READY", detail=None))
    FakeRM.plan, FakeRM.started = {"c64k-visoff-mtpoff": "FAILED"}, []
    h.lease = G.acquire("runtime_v1_brain", label="t", expected_vram_mib=h.required_mib, directory=tmp_path / "lease")
    try:
        h.mgr = FakeMgr()
        assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
        h.reconfigure()
        sw = h.report["profile_switch"]
        assert sw["restored"] is True and sw["fallback"]["to"] == "c32k-visgpu-mtpoff"
        assert sw["fallback"]["label"] == QC.entry_by_id("standard-nodraft")["label"]
        assert FakeRM.started == ["c64k-visoff-mtpoff", "c32k-visgpu-mtpoff"] and lease_mib(tmp_path) == 14360
    finally:
        h.lease.release("test")


def test_a_request_that_supersedes_a_waiting_restore_keeps_its_record(host):
    """Review R1-04: the superseded restore is persisted with the new switch, and `from` is marked as not running."""
    H, h = host
    h.mgr = None                          # the failed switch stopped the Brain; the restore waits for GPU memory
    h.report["profile_switch"] = {"id": "req-1", "from": "frozen", "to": "c64k-visoff-mtpoff", "result": "FAILED",
                                  "fallback": {"to": "frozen", "label": "Standard", "result": "IN_PROGRESS"}}
    h.report["last_request"] = {"id": "req-2"}
    h.pending_profile = tuple(LONG)
    assert h.apply_pending_profile() is True
    sw = h.report["profile_switch"]
    assert sw["id"] == "req-2" and sw["result"] == "IN_PROGRESS" and sw["from_ran"] is False
    assert sw["superseded"] == {"id": "req-1", "to": "c64k-visoff-mtpoff", "result": "FAILED",
                                "fallback": {"to": "frozen", "label": "Standard", "result": "SUPERSEDED"}}
    written = json.loads((h.report_dirs[0] / H.REPORT_FILE).read_text())
    assert written["profile_switch"]["superseded"]["fallback"]["result"] == "SUPERSEDED"


def test_an_ordinary_new_switch_has_no_superseded_record(host):
    H, h = host
    h.mgr = None
    h.report["profile_switch"] = {"id": "req-1", "result": "READY"}
    h.report["last_request"] = {"id": "req-2"}
    h.pending_profile = tuple(LONG)
    h.apply_pending_profile()
    assert "superseded" not in h.report["profile_switch"] and "from_ran" not in h.report["profile_switch"]
