"""BRAIN-QC-20261018: Brain Quick Controls (Thinking / Vision / Context) - catalog, worker commands, Brain host switch.

Simulation level: the real frozen Runtime v1 config and derived profiles, the real worker bridge against a fake llama
endpoint, the real Brain host class with recorded GPU census samples and a stubbed server start. The live switch
with the real Brain and the real UI is covered by the milestone's live evidence, not here."""
import json
import time

import pytest

from uri_operational_intelligence import brain_health as BH
from uri_operational_intelligence import brain_quick_controls as QC
from uri_operational_intelligence import gpu_lease as G
from uri_operational_intelligence import runtime_profile_selection as PS
from uri_operational_intelligence import runtime_profiles as RP
from uri_operational_intelligence import runtime_v1 as R
from uri_operational_intelligence.worker_bridge import BridgeRefused
from tests.ws.test_ws_hardening import CARD, Seq, load_host, raw
from tests.ws.test_ws_worker_bridge import SID, FakeCore, fake, make  # noqa: F401  (fixture re-export)

LONG = (65536, "off", False)
LONG_VISION = (65536, "gpu", False)


def frozen():
    return R.load_config()


# ---- catalog ----------------------------------------------------------------------------------------------------
def test_catalog_entries_are_measured_and_only_the_documented_ones_are_qualified():
    ids = [e["id"] for e in QC.CATALOG]
    assert len(ids) == len(set(ids))
    for e in QC.CATALOG:
        assert tuple(e["key"]) in RP.MEASURED_MIB          # nothing in the catalog runs on an estimate
    assert QC.entry_by_id("standard")["key"] == RP.FROZEN_KEY
    assert QC.entry_by_id("long")["key"] == LONG and QC.entry_by_id("long")["qualified"]
    lv = QC.entry_by_id("long-vision")
    assert lv["key"] == LONG_VISION and lv["qualified"] is False and "CRASH-1" in lv["reason"]
    assert {e["id"] for e in QC.CATALOG if e["qualified"]} == {"standard", "long", "standard-nodraft"}
    assert {e["id"] for e in QC.CATALOG if e["qualified"] and e.get("switchable", True)} == {"standard", "long"}


@pytest.mark.parametrize("target,code", [
    ("long-vision", "PROFILE_NOT_QUALIFIED"),
    ("standard-nodraft", "PROFILE_NOT_OFFERED"),
    ({"ctx": 32768, "vision": "gpu", "mtp": False}, "PROFILE_NOT_OFFERED"),
    ({"ctx": 65536, "vision": "gpu", "mtp": False}, "PROFILE_NOT_QUALIFIED"),
    ("nope", "PROFILE_UNKNOWN"),
    ({"ctx": 131072, "vision": "off", "mtp": True}, "PROFILE_UNKNOWN"),     # measured, not in the catalog
    ({"ctx": 16384, "vision": "off", "mtp": False}, "PROFILE_UNKNOWN"),
    ({"ctx": True, "vision": "off", "mtp": False}, "PROFILE_INVALID"),
    ({"ctx": 65536, "vision": "off"}, "PROFILE_INVALID"),
    (["long"], "PROFILE_INVALID"),
])
def test_switch_target_refuses_everything_outside_the_qualified_catalog(target, code):
    with pytest.raises(QC.QuickControlError) as e:
        QC.switch_target(target)
    assert e.value.code == code


def test_switch_target_accepts_ids_and_exact_keys():
    assert QC.switch_target("long") == LONG
    assert QC.switch_target({"ctx": 32768, "vision": "gpu", "mtp": True}) == RP.FROZEN_KEY


def test_controls_never_show_a_profile_active_before_the_worker_verified_it():
    long_cfg = RP.derive_config(frozen(), *LONG)
    host_long = RP.describe(long_cfg)
    for state in ("RECOVERING", "UNAVAILABLE", None, "CHECKING"):
        c = QC.controls(long_cfg, state, host_profile=host_long)
        assert c["active"] is None and not any(o["active"] for o in c["options"])
        assert c["configured"]["id"] == "c64k-visoff-mtpoff"
    c = QC.controls(long_cfg, "READY", host_profile=host_long)
    assert c["active"]["id"] == "long" and [o["id"] for o in c["options"] if o["active"]] == ["long"]
    # a switch in flight, or a host that reports another profile: not confirmed
    assert QC.controls(long_cfg, "READY", host_profile=host_long, switch={"pending": True})["active"] is None
    assert QC.controls(long_cfg, "READY", host_profile=RP.describe(frozen()))["active"] is None
    st = QC.controls(frozen(), "BUSY")
    assert st["active"]["id"] == "standard" and st["thinking"] == {"off": "fast", "on": "normal", "auto": "auto",
                                                                      "reload": False}


# ---- host request file --------------------------------------------------------------------------------------------
def test_reconfigure_request_needs_a_profile_and_only_reconfigure_carries_one(tmp_path):
    with pytest.raises(ValueError):
        BH.write_host_request(tmp_path, "reconfigure")
    with pytest.raises(ValueError):
        BH.write_host_request(tmp_path, "restart", profile={"ctx": 65536, "vision": "off", "mtp": False})
    req = BH.write_host_request(tmp_path, "reconfigure", {"ctx": 65536, "vision": "off", "mtp": False, "x": 1})
    on_disk = json.loads((tmp_path / BH.REQUEST_FILE).read_text())
    assert on_disk["profile"] == {"ctx": 65536, "vision": "off", "mtp": False} == req["profile"]
    assert "reconfigure" not in BH.RESTART_ACTIONS and "reconfigure" in BH.ACTIONS


# ---- worker commands ----------------------------------------------------------------------------------------------
def bridge(fake, tmp_path, cfg=None, rep=None, alive=True):  # noqa: F811
    b, frames, o = make(fake, tmp_path, FakeCore())
    b.cfg = cfg or frozen()
    b.selected = dict(b.selected, provider="llamacpp-runtime-v1")
    rep = rep if rep is not None else {"schema": BH.REPORT_SCHEMA, "state": "READY", "updated_at": time.time(),
                                       "profile": RP.describe(b.cfg)}
    requests = []
    b._host_report = lambda: (rep, alive)

    def host_request(action, profile=None):
        requests.append((action, profile))
        return {"id": "req-%d" % len(requests)}
    b._host_request = host_request
    return b, rep, requests


def test_brain_restart_can_never_write_a_reconfigure(fake, tmp_path):  # noqa: F811
    b, _, requests = bridge(fake, tmp_path)
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_restart", {"command": "brain_restart", "action": "reconfigure"})
    assert e.value.code == "ACTION_INVALID" and requests == []


def test_reconfigure_refuses_unqualified_and_unknown_profiles_without_any_request(fake, tmp_path):  # noqa: F811
    b, _, requests = bridge(fake, tmp_path)
    for pid, code in (("long-vision", "PROFILE_NOT_QUALIFIED"), ("c64k-visgpu-mtpoff", "PROFILE_UNKNOWN"),
                      ("", "PROFILE_UNKNOWN")):
        with pytest.raises(BridgeRefused) as e:
            b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": pid})
        assert e.value.code == code
    for bad in ({"command": "brain_reconfigure"}, {"command": "brain_reconfigure", "profile_id": "long", "x": 1},
                {"command": "brain_reconfigure", "profile_id": "long", "confirm_shrink": True}):
        with pytest.raises(BridgeRefused) as e:
            b.handle("brain_reconfigure", bad)
        assert e.value.code == "COMMAND_SCHEMA"
    assert requests == []


def test_reconfigure_writes_one_request_gates_turns_and_reports_the_switch(fake, tmp_path):  # noqa: F811
    b, rep, requests = bridge(fake, tmp_path)
    b.history[SID] = [{"role": "user", "content": "the secret number is 4817"}]
    before = json.dumps(b.history)
    r = b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "long"})
    assert r["requested"] == "reconfigure" and r["target"]["id"] == "long"
    assert requests == [("reconfigure", {"ctx": 65536, "vision": "off", "mtp": False})]
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "hi", "depth": "fast"})
    assert e.value.code == "BRAIN_RESTARTING"
    with pytest.raises(BridgeRefused) as e:                  # one Brain request at a time
        b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "standard"})
    assert e.value.code == "BRAIN_RESTARTING"
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["state"] == "RECOVERING" and h["reasons"][0] == "PROFILE_SWITCH" and "Long context" in h["explain"]
    assert h["controls"]["switch"]["pending"] is True and h["controls"]["active"] is None
    # the host refused it (did not fit): the gate opens, the working Brain is still the one reported
    rep["requests"] = {"req-1": "REFUSED_DOES_NOT_FIT"}
    rep["profile_switch"] = {"id": "req-1", "result": "REFUSED_DOES_NOT_FIT", "explain": "The Brain was not switched."}
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["controls"]["switch"]["pending"] is False and h["controls"]["switch"]["last"]["result"].startswith("REF")
    assert json.dumps(b.history) == before                   # the conversation is never touched by a switch


def test_reconfigure_is_refused_while_a_turn_runs(fake, tmp_path):  # noqa: F811
    import threading
    b, _, requests = bridge(fake, tmp_path)
    gate = threading.Event()
    b._start("t-1", gate.wait)
    try:
        with pytest.raises(BridgeRefused) as e:
            b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "long"})
        assert e.value.code == "TURN_IN_PROGRESS" and requests == []
        assert b.handle("brain_health", {"command": "brain_health"})["controls"]["schema"] == QC.SCHEMA
    finally:
        gate.set()
        b.wait(5)


def test_reconfigure_needs_the_host_and_a_selected_runtime(fake, tmp_path):  # noqa: F811
    b, _, requests = bridge(fake, tmp_path, alive=False)
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "long"})
    assert e.value.code == "BRAIN_HOST_NOT_RUNNING"
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["controls"]["can_switch"] is False and h["controls"]["cannot_switch_reason"] == "BRAIN_HOST_NOT_RUNNING"
    b._host_request = None
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "long"})
    assert e.value.code == "BRAIN_CONTROL_UNAVAILABLE" and requests == []


def test_already_active_profile_is_not_reloaded(fake, tmp_path):  # noqa: F811
    b, _, requests = bridge(fake, tmp_path, cfg=RP.derive_config(frozen(), *LONG))
    r = b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "long"})
    assert r["already_active"] is True and requests == []


def test_a_conversation_that_would_not_fit_the_smaller_context_is_refused_not_confirmed(fake, tmp_path):  # noqa: F811
    """Review R1-02: nothing trims the history sent to the Brain, so a shrink below the live conversation (plus one
    answer) is refused outright; there is no confirm path that would make the next turns fail."""
    b, _, requests = bridge(fake, tmp_path, cfg=RP.derive_config(frozen(), *LONG))
    b._context_tokens = {SID: 30000, "other": 1000}     # the largest session decides (30,000 + 4,096 > 32,768)
    r = b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "standard"})
    assert r["refused"] == "CONTEXT_SMALLER_THAN_CONVERSATION" and r["requested"] is None
    assert r["detail"] == {"live_tokens": 30000, "answer_reserve": 4096, "ctx": 32768}
    assert requests == []
    with pytest.raises(BridgeRefused) as e:               # the old confirm path no longer exists
        b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "standard", "confirm_shrink": True})
    assert e.value.code == "COMMAND_SCHEMA" and requests == []
    b._context_tokens = {SID: 20000}                       # fits with room for an answer: switched
    r = b.handle("brain_reconfigure", {"command": "brain_reconfigure", "profile_id": "standard"})
    assert r["requested"] == "reconfigure" and requests == [("reconfigure", {"ctx": 32768, "vision": "gpu", "mtp": True})]


def test_answer_context_size_is_recorded_per_session(fake, tmp_path):  # noqa: F811
    b, _, _ = bridge(fake, tmp_path)
    fake.scripts.append({"chunks": [("answer", "ok")], "finish": "stop"})
    tid = b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "hi", "depth": "fast"})["turn_id"]
    b.wait(10)
    sink = b._sink(tid)
    sink.emit(tid, "answer.done", metrics={"prompt_n": 120, "cache_n": 30000, "predicted_n": 80})
    assert b._context_tokens[SID] == 30200 and b._largest_context() == 30200
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["controls"]["switch"]["context_tokens"] == 30200


# ---- Brain host ---------------------------------------------------------------------------------------------------
class FakeMgr:
    def __init__(self, owns=True):
        self.owns_instance, self._contained, self.stopped = owns, None, 0

    def stop(self):
        self.stopped += 1
        return True


def qc_host(tmp_path, census, cfg=None):
    H = load_host()
    H.GPU_POLL_S = 0.05
    H.QUIET_S = 0.0
    h = H.Host(tmp_path / "client" / "control" / "oi", minutes=1, override=False, cfg=cfg or frozen(),
               state_dir=tmp_path / "state", census=census, lease_dir=tmp_path / "lease", frozen_cfg=frozen())
    return H, h


def request(h, profile):
    h.report_dirs[0].mkdir(parents=True, exist_ok=True)
    BH.write_host_request(h.report_dirs[0], "reconfigure", profile)
    return h.take_request()


# Free memory 14,500 MiB: the frozen request (15,626) is CONTENDED, Long context (13,658) FITS.
TIGHT = G.census(raw([(1580, 1800, 9)], 1868), card=CARD)
ROOMY = G.census(raw([(1580, 311, 9)], 330), card=CARD)


def test_host_refuses_an_unqualified_target_even_from_a_hand_written_request(tmp_path):
    H, h = qc_host(tmp_path, Seq([ROOMY]))
    assert request(h, {"ctx": 65536, "vision": "gpu", "mtp": False}) is None
    assert h.pending_profile is None
    assert h.report["last_request"]["result"] == "REFUSED_PROFILE_NOT_QUALIFIED"
    rid = h.report["last_request"]["id"]
    assert h.report["requests"][rid] == "REFUSED_PROFILE_NOT_QUALIFIED"
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure" and h.pending_profile == LONG


def test_host_refuses_a_switch_that_would_not_fit_before_stopping_anything(tmp_path, monkeypatch):
    long_cfg = RP.derive_config(frozen(), *LONG)
    H, h = qc_host(tmp_path, Seq([TIGHT]), cfg=long_cfg)
    h.mgr = FakeMgr()
    monkeypatch.setattr(h, "owners", lambda: set())
    monkeypatch.setattr(h, "start_brain", lambda: pytest.fail("must not start"))
    assert request(h, {"ctx": 32768, "vision": "gpu", "mtp": True}) == "reconfigure"
    h.reconfigure()
    assert h.mgr is not None and h.mgr.stopped == 0 and h.cfg is long_cfg
    sw = h.report["profile_switch"]
    assert sw["result"] == "REFUSED_DOES_NOT_FIT" and "not switched" in sw["explain"]
    assert sw["fit"]["required_mib"] == G.RUNTIME_V1_DEVICE_MIB      # R1-03: the request the start would budget
    assert h.report["requests"][sw["id"]] == "REFUSED_DOES_NOT_FIT"
    assert h.report["last_request"]["result"] == "REFUSED_DOES_NOT_FIT"


def test_host_switch_derives_the_profile_writes_the_selection_and_updates_the_lease(tmp_path, monkeypatch):
    H, h = qc_host(tmp_path, Seq([ROOMY]))
    h.lease = G.acquire("runtime_v1_brain", label="test", expected_vram_mib=h.required_mib, directory=tmp_path / "lease")
    try:
        mgr = FakeMgr()
        h.mgr = mgr
        monkeypatch.setattr(h, "owners", lambda: set())
        started = []

        def fake_start():
            started.append((RP.describe(h.cfg)["id"], h.required_mib))
            h.mgr = FakeMgr()
            h.set("READY", detail=None)
            return True
        monkeypatch.setattr(h, "_start_brain", fake_start)
        assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
        h.reconfigure()
        assert mgr.stopped == 1 and started == [("c64k-visoff-mtpoff", 13658)]
        assert R.config_digest(h.cfg) == R.config_digest(RP.derive_config(frozen(), *LONG))
        sel = h.report_dirs[0] / PS.SELECTION_FILE
        cfg_w, note = PS.select(frozen(), sel)                    # what the worker will verify against
        assert note["source"] == "selection" and R.expected_argv(cfg_w) == R.expected_argv(h.cfg)
        lease = json.loads((tmp_path / "lease" / "lease.json").read_text())
        assert lease["expected_vram_mib"] == 13658
        sw = h.report["profile_switch"]
        assert sw["from"] == "frozen" and sw["to"] == "c64k-visoff-mtpoff" and sw["result"] == "READY"
        assert sw["seconds"] is not None and h.report["profile"]["id"] == "c64k-visoff-mtpoff"
        assert sw["fit_before"]["required_mib"] == 13658 and sw["started_stopped_brain"] is False
        # and back to Standard: the frozen config object itself, no selection file (absent = frozen)
        assert request(h, {"ctx": 32768, "vision": "gpu", "mtp": True}) == "reconfigure"
        h.reconfigure()
        assert h.cfg is h._frozen_cfg and not sel.exists() and h.required_mib == G.RUNTIME_V1_DEVICE_MIB
        assert json.loads((tmp_path / "lease" / "lease.json").read_text())["expected_vram_mib"] == G.RUNTIME_V1_DEVICE_MIB
    finally:
        h.lease.release("test")


def test_same_profile_request_is_a_no_op(tmp_path, monkeypatch):
    H, h = qc_host(tmp_path, Seq([ROOMY]))
    h.mgr = FakeMgr()
    monkeypatch.setattr(h, "_start_brain", lambda: pytest.fail("must not restart"))
    assert request(h, {"ctx": 32768, "vision": "gpu", "mtp": True}) == "reconfigure"
    h.reconfigure()
    assert h.mgr.stopped == 0 and h.report["profile_switch"]["result"] == "ALREADY_ACTIVE"


def test_an_attached_brain_is_never_switched(tmp_path, monkeypatch):
    H, h = qc_host(tmp_path, Seq([ROOMY]))
    h.mgr = FakeMgr(owns=False)
    monkeypatch.setattr(h, "_start_brain", lambda: pytest.fail("must not start"))
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    h.reconfigure()
    assert h.mgr.stopped == 0 and h.report["profile_switch"]["result"] == "REFUSED_ATTACHED_INSTANCE"


def test_a_waiting_start_takes_a_smaller_profile_that_fits(tmp_path):
    H, h = qc_host(tmp_path, Seq([TIGHT]))
    h.deadline = time.monotonic() + 30
    h.report_dirs[0].mkdir(parents=True, exist_ok=True)
    import threading

    def later():
        time.sleep(0.3)
        BH.write_host_request(h.report_dirs[0], "reconfigure", {"ctx": 65536, "vision": "off", "mtp": False})
    threading.Thread(target=later, daemon=True).start()
    assert h.wait_for_gpu() is True                               # frozen waited CONTENDED, Long context fits
    assert "GPU_CONTENDED" in [x["detail"] for x in h.report["history"]]
    assert h.required_mib == 13658 and h.report["gpu"]["fit"]["verdict"] == G.FITS
    assert (h.report_dirs[0] / PS.SELECTION_FILE).exists()


def test_host_start_removes_a_stale_selection_for_the_frozen_config(tmp_path):
    H, h = qc_host(tmp_path, Seq([ROOMY]))
    sel = PS.write(tmp_path / "client", 65536, "off", False)
    assert sel == h.report_dirs[0] / PS.SELECTION_FILE
    h.sync_selection()
    assert not sel.exists()
    H2, h2 = qc_host(tmp_path, Seq([ROOMY]), cfg=RP.derive_config(frozen(), *LONG))
    h2.sync_selection()
    assert PS.select(frozen(), sel)[1]["profile"]["id"] == "c64k-visoff-mtpoff"


def test_frozen_runtime_v1_argv_is_unchanged():
    cfg = frozen()
    assert RP.derive_config(cfg, *RP.FROZEN_KEY) is cfg
    argv = R.expected_argv(cfg)
    assert argv[argv.index("-c") + 1] == "32768" and "-md" in argv and "--mmproj" in argv


def test_a_switch_on_a_stopped_brain_starts_it_and_says_so(tmp_path, monkeypatch):
    """Review R1-08.3: documented behaviour - a Vision / Context choice while the user's Brain is stopped starts it."""
    H, h = qc_host(tmp_path, Seq([ROOMY]))
    monkeypatch.setattr(h, "acquire_lease", lambda: True)
    started = []
    monkeypatch.setattr(h, "_start_brain", lambda: started.append(RP.describe(h.cfg)["id"]) or True)
    assert request(h, {"ctx": 65536, "vision": "off", "mtp": False}) == "reconfigure"
    h.reconfigure()
    assert started == ["c64k-visoff-mtpoff"] and h.report["profile_switch"]["started_stopped_brain"] is True
