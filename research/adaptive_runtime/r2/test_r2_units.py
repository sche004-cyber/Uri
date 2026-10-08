"""Unit tests for the R2 prototypes (planner decision rules, watchdog state machine, guard parsing).
Run: python -m pytest research/adaptive_runtime/r2/test_r2_units.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gpu_guard  # noqa: E402
import residency_watchdog as rw  # noqa: E402
import vram_planner as vp  # noqa: E402


# ------------------------------------------------------------------ planner

def test_full_never_fits_on_16gb_with_default_headroom():
    p = vp.plan(16368, 871)   # idle desktop as measured at session start
    assert p.budget_mib == 16368 - 871 - 768
    assert p.chosen != "full"
    assert p.candidates[0]["profile"] == "full" and not p.candidates[0]["fits"]


def test_full_fits_only_without_headroom_and_idle_desktop():
    p = vp.plan(16368, 600, headroom_mib=0)
    assert p.budget_mib == 15768 and p.chosen == "full" and p.fits and p.risk == "low"


def test_vision_cpu_is_next_in_default_order_and_fits_idle():
    p = vp.plan(16368, 871)
    assert p.chosen == "vision_cpu"
    assert p.arg_delta == ["--no-mmproj-offload"] and p.drop_args == []
    assert p.fits and p.margin_mib == (16368 - 871 - 768) - (15626 - 1106)


def test_pressure_1gb_consumer_drops_to_no_mtp_or_smaller():
    p = vp.plan(16368, 871 + 1090)           # desktop + Ollama 0.8B consumer
    assert p.chosen in ("no_mtp", "vision_cpu_no_mtp")
    assert p.fits


def test_nothing_fits_reports_demotion_honestly():
    p = vp.plan(16368, 4000)
    assert not p.fits and p.chosen == "vision_cpu_no_mtp"
    assert p.expected_demotion_mib == (15626 - 1106 - 1135) - (16368 - 4000)
    assert p.risk == "oversubscribed"


def test_owner_order_prefers_gpu_vision_over_mtp():
    p = vp.plan(16368, 871, order=("full", "no_mtp", "vision_cpu", "vision_cpu_no_mtp"))
    assert p.chosen == "no_mtp" and "-md" in p.drop_args


def test_blocks_policy():
    assert vp.plan(16368, 871, blocks_policy="always").env == vp.BLOCKS_128_MIB_ENV
    assert vp.plan(16368, 871, blocks_policy="never").env == {}
    assert vp.plan(16368, 871, blocks_policy="when_oversubscribed").env == {}
    assert vp.plan(16368, 4000, blocks_policy="when_oversubscribed").env == vp.BLOCKS_128_MIB_ENV


def test_within_headroom_risk_class():
    # full request 15,626 fits the raw free memory but not the budget with headroom
    p = vp.plan(16368, 600, headroom_mib=768, order=("full",))
    assert not p.fits and p.expected_demotion_mib == 0 and p.risk == "oversubscribed_within_headroom"


# ------------------------------------------------------------------ watchdog state machine

class FakeWatchdog(rw.Watchdog):
    """Drive step() with injected residency/metrics instead of counters and HTTP."""

    def __init__(self, cfg, tmp_path, feed):
        self.feed = iter(feed)
        super().__init__(cfg, tmp_path / "w", log=lambda m: None)

    def step(self, probe_fn=None):
        res, met = next(self.feed)
        rw.residency_for_pid = lambda pid: res
        rw.read_metrics = lambda url, timeout=5.0: met
        return super().step(probe_fn)


def _metrics(tokens, secs, rp=0):
    return {"tokens_predicted_total": tokens, "tokens_predicted_seconds_total": secs, "requests_processing": rp}


def test_healthy_load_no_alarm(tmp_path, monkeypatch):
    cfg = rw.WatchConfig(pid=1, url="u", expected_decode_tps=110)
    feed = [({"local": 15600, "nonlocal": 1121, "adapter": 16200}, _metrics(0, 0)),
            ({"local": 15600, "nonlocal": 1121, "adapter": 16200}, _metrics(256, 2.2)),
            ({"local": 15600, "nonlocal": 1121, "adapter": 16200}, _metrics(512, 4.5)),
            ({"local": 15600, "nonlocal": 1121, "adapter": 16200}, _metrics(600, 5.3))]
    wd = FakeWatchdog(cfg, tmp_path, feed)
    for _ in feed:
        wd.step()
    s = wd.summary()
    assert s["final_state"] == "OK" and not s["ever_degraded"] and not s["ever_at_risk"]
    assert s["window_tps"]["min"] > 100
    wd.close()


def test_demoted_slow_load_alarms_after_two_windows(tmp_path):
    cfg = rw.WatchConfig(pid=1, url="u", expected_decode_tps=110, consecutive=2)
    res = {"local": 14024, "nonlocal": 2649, "adapter": 16300}
    feed = [(res, _metrics(0, 0)), (res, _metrics(100, 4.0)), (res, _metrics(200, 8.0)), (res, _metrics(300, 12.0))]
    wd = FakeWatchdog(cfg, tmp_path, feed)
    states = [wd.step().state for _ in feed]
    assert states[1] == "AT_RISK" or states[0] == "AT_RISK"
    assert states[-1] == "DEGRADED" and wd.summary()["first_degraded_at_s"] is not None
    assert wd.summary()["demoted_mib"]["max"] == 2649 - 872
    wd.close()


def test_demoted_but_fast_is_at_risk_not_degraded(tmp_path):
    # the 128 MiB-block case: 2.7 GB non-local yet 101 tok/s
    cfg = rw.WatchConfig(pid=1, url="u", expected_decode_tps=110)
    res = {"local": 14181, "nonlocal": 2704, "adapter": 16300}
    feed = [(res, _metrics(0, 0)), (res, _metrics(300, 3.0)), (res, _metrics(600, 6.0))]
    wd = FakeWatchdog(cfg, tmp_path, feed)
    states = [wd.step().state for _ in feed]
    assert states[-1] == "AT_RISK" and not wd.summary()["ever_degraded"]
    wd.close()


def test_small_windows_are_ignored(tmp_path):
    cfg = rw.WatchConfig(pid=1, url="u", min_window_tokens=32)
    res = {"local": 15600, "nonlocal": 1121, "adapter": 16200}
    feed = [(res, _metrics(0, 0)), (res, _metrics(4, 1.0)), (res, _metrics(8, 2.0))]   # 4 tokens per window: noise
    wd = FakeWatchdog(cfg, tmp_path, feed)
    for _ in feed:
        wd.step()
    assert wd.summary()["window_tps"]["n"] == 0 and wd.state == "OK"
    wd.close()


def test_recovery_after_restart(tmp_path):
    cfg = rw.WatchConfig(pid=1, url="u", consecutive=1)
    slow = {"local": 14024, "nonlocal": 2649, "adapter": 16300}
    fast = {"local": 15600, "nonlocal": 1121, "adapter": 16200}
    feed = [(slow, _metrics(0, 0)), (slow, _metrics(100, 4.0)), (fast, _metrics(0, 0)), (fast, _metrics(300, 2.6))]
    wd = FakeWatchdog(cfg, tmp_path, feed)
    states = [wd.step().state for _ in feed]
    assert states[1] == "DEGRADED" and states[-1] == "RECOVERED"
    wd.close()


def test_metrics_parser_sums_labelled_series():
    txt = ("# HELP llamacpp:tokens_predicted_total x\nllamacpp:tokens_predicted_total 123\n"
           "llamacpp:tokens_predicted_seconds_total 1.5\nllamacpp:requests_processing 0\n"
           "llamacpp:spec_decode_num_accepted_tokens_per_pos_total{position=\"0\"} 5\n")
    out = {}
    for m in rw._METRIC.finditer(txt):
        out[m.group(1)] = out.get(m.group(1), 0.0) + float(m.group(2))
    assert out["tokens_predicted_total"] == 123 and out["tokens_predicted_seconds_total"] == 1.5
    assert out["spec_decode_num_accepted_tokens_per_pos_total"] == 5


# ------------------------------------------------------------------ guard

def test_guard_parses_counter_paths(monkeypatch):
    sample = ("\\\\PC\\gpu process memory(pid_16100_luid_0x0_0xc181_phys_0)\\local usage=12807\n"
              "\\\\PC\\gpu process memory(pid_16100_luid_0x0_0xc181_phys_0)\\non local usage=3910\n"
              "\\\\PC\\gpu process memory(pid_1580_luid_0x0_0xc181_phys_0)\\local usage=293\n")

    class R:
        stdout = sample

    monkeypatch.setattr(gpu_guard.subprocess, "run", lambda *a, **k: R())
    monkeypatch.setattr(gpu_guard.psutil, "Process", lambda pid=None: (_ for _ in ()).throw(Exception("no")))
    procs = gpu_guard.gpu_processes()
    assert procs[16100]["local_mib"] == 12807 and procs[16100]["nonlocal_mib"] == 3910
    assert procs[1580]["local_mib"] == 293 and procs[1580]["nonlocal_mib"] == 0


def test_guard_allow_list(monkeypatch):
    monkeypatch.setattr(gpu_guard, "gpu_processes", lambda: {
        16100: {"local_mib": 12807, "nonlocal_mib": 3910, "name": "llama-server.exe", "cmd": ""},
        15272: {"local_mib": 1090, "nonlocal_mib": 0, "name": "ollama.exe", "cmd": ""},
        1580: {"local_mib": 293, "nonlocal_mib": 0, "name": "dwm.exe", "cmd": ""}})
    owners = gpu_guard.foreign_owners(1500, ("ollama",))
    assert [o["pid"] for o in owners] == [16100]
    assert gpu_guard.foreign_owners(1500, ("ollama", "llama-server")) == []
