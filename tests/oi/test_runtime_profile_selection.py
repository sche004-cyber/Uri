"""RUNTIME-PROFILES-INTEG: the integrated worker verifies the Brain against the selected resource profile."""
import json
from pathlib import Path

import pytest

from uri_operational_intelligence import runtime_profile_selection as PS
from uri_operational_intelligence import runtime_profiles as RP
from uri_operational_intelligence import runtime_v1 as R

ROOT = Path(R.REPO_ROOT)


def frozen():
    return R.load_config()


def write_raw(tmp_path, obj):
    p = PS.selection_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return p


def test_absent_file_is_the_frozen_config_object(tmp_path):
    cfg = frozen()
    out, note = PS.select(cfg, PS.selection_path(tmp_path))
    assert out is cfg and note == {"source": "frozen", "file": None}
    assert R.expected_argv(out) == R.expected_argv(frozen())


def test_valid_selection_derives_the_measured_profile(tmp_path):
    p = PS.write(tmp_path, 65536, "gpu", False)
    cfg, note = PS.select(frozen(), p)
    assert note["source"] == "selection" and note["profile"]["id"] == "c64k-visgpu-mtpoff"
    argv = R.expected_argv(cfg)
    assert argv[argv.index("-c") + 1] == "65536" and "--mmproj" in argv and "-md" not in argv
    # identical to what the host derives from its --profile argument
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import ws_brain_host as H
    host_cfg = RP.derive_config(frozen(), *H.parse_profile("65536,gpu,0"))
    assert R.expected_argv(host_cfg) == argv and R.pinned_artifacts(host_cfg) == R.pinned_artifacts(cfg)


def test_frozen_combination_selection_returns_frozen_object(tmp_path):
    p = PS.write(tmp_path, 32768, "gpu", True)
    cfg = frozen()
    out, note = PS.select(cfg, p)
    assert out is cfg and note["source"] == "selection" and note["profile"]["frozen"] is True


@pytest.mark.parametrize("obj,code", [
    ("{not json", "PROFILE_SELECTION_UNREADABLE"),
    ({"schema": "other", "ctx": 65536, "vision": "off", "mtp": False}, "PROFILE_SELECTION_SCHEMA"),
    ([1, 2], "PROFILE_SELECTION_SCHEMA"),
    ({"schema": PS.SCHEMA, "ctx": "65536", "vision": "off", "mtp": False}, "PROFILE_SELECTION_INVALID"),
    ({"schema": PS.SCHEMA, "ctx": 65536, "vision": "off", "mtp": "no"}, "PROFILE_SELECTION_INVALID"),
    ({"schema": PS.SCHEMA, "ctx": True, "vision": "off", "mtp": False}, "PROFILE_SELECTION_INVALID"),
    ({"schema": PS.SCHEMA, "ctx": 50000, "vision": "off", "mtp": False}, "CONTEXT_UNSUPPORTED"),
    ({"schema": PS.SCHEMA, "ctx": 65536, "vision": "maybe", "mtp": False}, "VISION_MODE_UNKNOWN"),
    ({"schema": PS.SCHEMA, "ctx": 131072, "vision": "gpu", "mtp": True}, "PROFILE_NOT_MEASURED"),
])
def test_invalid_selection_keeps_frozen_and_reports(tmp_path, obj, code):
    p = write_raw(tmp_path, obj)
    cfg = frozen()
    out, note = PS.select(cfg, p)
    assert out is cfg and note["source"] == "frozen" and note["error"] == code


def test_selection_cannot_name_binary_model_port_or_flags(tmp_path):
    p = write_raw(tmp_path, {"schema": PS.SCHEMA, "ctx": 65536, "vision": "off", "mtp": False,
                             "binary": "C:/evil.exe", "port": 9999, "extra_args": ["--host", "0.0.0.0"]})
    cfg, note = PS.select(frozen(), p)
    f = frozen()
    assert note["source"] == "selection"
    assert cfg["runtime"]["binary"] == f["runtime"]["binary"] and cfg["runtime"]["port"] == f["runtime"]["port"]
    assert cfg["model"]["path"] == f["model"]["path"] and "0.0.0.0" not in " ".join(R.expected_argv(cfg))


def test_write_refuses_unmeasured(tmp_path):
    with pytest.raises(RP.ProfileError):
        PS.write(tmp_path, 131072, "gpu", True)
    assert not PS.selection_path(tmp_path).exists()


def test_worker_reads_selection_before_guard_and_records_it():
    src = (ROOT / "scripts" / "run_uri_integrated_worker.py").read_text(encoding="utf-8")
    i_cfg = src.index("frozen_cfg = cfg = R.load_config()")
    i_sel = src.index("profile = PS.ProfileFollower(frozen_cfg, PS.selection_path(root),")
    i_guard = src.index("sys.addaudithook(guard)")
    assert i_cfg < i_sel < i_guard
    assert '"brain_profile": brain_profile' in src
    # the guard pins the frozen (superset) artifacts, readiness follows the profile, health follows the profile
    assert "for art in R.pinned_artifacts(frozen_cfg):" in src
    assert "manager = profile" in src and "readiness=manager.status" in src
    assert "profile_sinks.append(oi)" in src


class FakeManager:
    made = []

    def __init__(self, cfg):
        self.cfg = cfg
        FakeManager.made.append(cfg)

    def status(self):
        return ("status", RP.describe(self.cfg)["id"])


def test_frozen_artifacts_are_a_superset_of_every_profile():
    f = frozen()
    allowed = {a["path"] for a in R.pinned_artifacts(f)}
    for (ctx, vision, mtp) in RP.MEASURED_MIB:
        cfg = RP.derive_config(f, ctx, vision, mtp)
        assert {a["path"] for a in R.pinned_artifacts(cfg)} <= allowed


def test_follower_switches_profile_without_a_new_worker(tmp_path):
    FakeManager.made = []
    seen = []
    path = PS.selection_path(tmp_path)
    fol = PS.ProfileFollower(frozen(), path, FakeManager, on_change=lambda c, n: seen.append(RP.describe(c)["id"]))
    assert fol.status() == ("status", "frozen") and fol.note["source"] == "frozen"
    PS.write(tmp_path, 65536, "off", False)
    assert fol.status() == ("status", "c64k-visoff-mtpoff") and seen == ["c64k-visoff-mtpoff"]
    import os
    import time
    PS.write(tmp_path, 32768, "gpu", False)
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))   # stat signature changes even on coarse clocks
    assert fol.status() == ("status", "c32k-visgpu-mtpoff") and seen[-1] == "c32k-visgpu-mtpoff"
    assert fol.changes[-1]["from"] == "c64k-visoff-mtpoff" and fol.changes[-1]["to"] == "c32k-visgpu-mtpoff"
    n = len(FakeManager.made)
    fol.status()
    assert len(FakeManager.made) == n          # unchanged file: no new manager
    path.write_text("{broken", encoding="utf-8")
    assert fol.status() == ("status", "frozen") and fol.note["error"] == "PROFILE_SELECTION_UNREADABLE"
    path.unlink()
    assert fol.status() == ("status", "frozen")


def test_follower_same_profile_rewrite_keeps_manager(tmp_path):
    FakeManager.made = []
    PS.write(tmp_path, 65536, "off", False)
    fol = PS.ProfileFollower(frozen(), PS.selection_path(tmp_path), FakeManager)
    first = fol.manager
    p = PS.selection_path(tmp_path)
    PS.write(tmp_path, 65536, "off", False)
    st = p.stat()
    import os
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert fol.refresh() is False and fol.manager is first


def test_health_backend_names_the_profile():
    from uri_operational_intelligence import brain_health as BH
    assert BH.backend(frozen())["profile"] == {"id": "frozen", "frozen": True}
    b = BH.backend(RP.derive_config(frozen(), 32768, "gpu", False))
    assert b["profile"]["id"] == "c32k-visgpu-mtpoff" and b["profile"]["qualified"] is False
    assert b["provider"] == "Runtime v1 (local)" and b["context"] == 32768 and b["speculative"] is None
