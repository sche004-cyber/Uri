"""URI-RUNTIME-VRAM-R1: resource profiles derived from the frozen Runtime v1 configuration."""
import json
from pathlib import Path

import pytest

from uri_operational_intelligence import gpu_lease as G
from uri_operational_intelligence import runtime_profiles as RP
from uri_operational_intelligence import runtime_v1 as R

FROZEN_JSON = Path(R.CONFIG_PATH)
MEASURED = {(32768, "gpu", True): 15626, (65536, "off", True): 15043, (65536, "off", False): 13658,
            (65536, "cpu", True): 15043, (16384, "off", True): 14270}


def frozen():
    return R.load_config()


def test_frozen_combination_returns_the_frozen_object_unchanged():
    cfg = frozen()
    digest = R.config_digest(cfg)
    out = RP.derive_config(cfg, 32768, "gpu", True, measured=MEASURED)
    assert out is cfg and R.config_digest(out) == digest and "profile" not in out
    assert R.expected_argv(out) == R.expected_argv(frozen())


def test_derivation_never_mutates_the_frozen_config_or_file():
    before = FROZEN_JSON.read_bytes()
    cfg = frozen()
    digest = R.config_digest(cfg)
    RP.derive_config(cfg, 65536, "off", False, measured=MEASURED)
    assert R.config_digest(cfg) == digest and FROZEN_JSON.read_bytes() == before


def test_mtp_off_vision_off_64k_argv_and_artifacts():
    cfg = RP.derive_config(frozen(), 65536, "off", False, measured=MEASURED)
    argv = R.expected_argv(cfg)
    assert argv[argv.index("-c") + 1] == "65536"
    assert "--no-mmproj" in argv and "--mmproj" not in argv
    for flag in ("-md", "--spec-type", "--spec-draft-n-max", "-otd", "draft-mtp", "token_embd.weight=CPU"):
        assert flag not in argv
    # every other frozen flag survives
    for flag in ("-b", "2048", "-ub", "1024", "--ctx-checkpoints", "16", "--cache-ram", "--load-mode", "-ctk", "q8_0"):
        assert flag in argv
    roles = [a["role"] for a in R.pinned_artifacts(cfg)]
    assert roles == ["server_binary", "vulkan_backend", "model"]
    assert cfg["profile"]["required_mib"] == 13658 and cfg["profile"]["qualified"] is False
    assert cfg["profile"]["derived_from_digest"] == R.config_digest(frozen())


def test_vision_cpu_adds_no_offload_and_keeps_projector_artifact():
    cfg = RP.derive_config(frozen(), 65536, "cpu", True, measured=MEASURED)
    argv = R.expected_argv(cfg)
    i = argv.index("--mmproj")
    assert argv[i + 2] == "--no-mmproj-offload" and "-md" in argv
    assert "vision_projector" in [a["role"] for a in R.pinned_artifacts(cfg)]


def test_unmeasured_or_unsupported_combinations_are_refused():
    with pytest.raises(RP.ProfileError) as e:
        RP.derive_config(frozen(), 131072, "gpu", True, measured=MEASURED)
    assert e.value.code == "PROFILE_NOT_MEASURED"
    with pytest.raises(RP.ProfileError) as e:
        RP.derive_config(frozen(), 50000, "off", True, measured=MEASURED)
    assert e.value.code == "CONTEXT_UNSUPPORTED"
    with pytest.raises(RP.ProfileError):
        RP.key_for(65536, "maybe", True)


def test_required_mib_defaults_to_frozen_constant():
    assert RP.cfg_required_mib(frozen(), G.RUNTIME_V1_DEVICE_MIB) == 15626
    cfg = RP.derive_config(frozen(), 65536, "off", True, measured=MEASURED)
    assert RP.cfg_required_mib(cfg, G.RUNTIME_V1_DEVICE_MIB) == 15043


def test_plan_change_never_shrinks_below_live_conversation(monkeypatch):
    monkeypatch.setattr(RP, "MEASURED_MIB", MEASURED)
    cur = {"id": "x", "ctx": 65536, "vision": "off", "mtp": True}
    p = RP.plan_change(cur, context=16384, live_tokens=30000)
    assert p["refused"] == "CONTEXT_SMALLER_THAN_CONVERSATION" and p["reload"] is False
    p = RP.plan_change(cur, context=16384, live_tokens=30000, confirm_shrink=True)
    assert p["refused"] is None and p["reload"] is True
    assert RP.plan_change(cur, context=65536)["reload"] is False          # same profile: nothing to do
    assert RP.plan_change(cur, vision="gpu")["refused"] == "PROFILE_NOT_MEASURED"


def test_thinking_is_per_request_not_a_profile():
    assert RP.thinking_depth(True) == "normal" and RP.thinking_depth(False) == "fast"
    from uri_operational_intelligence import reasoning_policy as P
    assert RP.thinking_depth(True) in P.USER_DEPTHS and RP.thinking_depth(False) in P.USER_DEPTHS


def test_describe_frozen_and_profile():
    assert RP.describe(frozen()) == {"id": "frozen", "ctx": 32768, "vision": "gpu", "mtp": True, "frozen": True}
    d = RP.describe(RP.derive_config(frozen(), 65536, "off", True, measured=MEASURED))
    assert d["id"] == "c64k-visoff-mtpon" and d["frozen"] is False and d["required_mib"] == 15043


def test_host_budgets_the_profile_request(tmp_path):
    import sys
    sys.path.insert(0, str(Path(R.REPO_ROOT) / "scripts"))
    import ws_brain_host as H
    host = H.Host(tmp_path / "rep", minutes=0.01, override=False, cfg=frozen(), state_dir=tmp_path / "s",
                  census=lambda: {"ok": False}, lease_dir=tmp_path / "l")
    assert host.required_mib == 15626 and host.report["profile"]["id"] == "frozen"
    cfg = RP.derive_config(frozen(), 65536, "off", True, measured=MEASURED)
    host = H.Host(tmp_path / "rep2", minutes=0.01, override=False, cfg=cfg, state_dir=tmp_path / "s2",
                  census=lambda: {"ok": False}, lease_dir=tmp_path / "l2")
    assert host.required_mib == 15043 and host.report["profile"]["id"] == "c64k-visoff-mtpon"
    json.dumps(host.report)
