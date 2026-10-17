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
    i_cfg = src.index("cfg = R.load_config()")
    i_sel = src.index("cfg, brain_profile = PS.select(cfg, PS.selection_path(root))")
    i_guard = src.index("sys.addaudithook(guard)")
    assert i_cfg < i_sel < i_guard
    assert '"brain_profile": brain_profile' in src
