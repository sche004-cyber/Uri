import copy
import hashlib
import os

import pytest

from uri_operational_intelligence import runtime_v1 as R
from tests.oi.fake_llama import FakeLlama, free_port

FROZEN_FLAGS = ("-c 32768 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 -np 1 --host 127.0.0.1 --port 18470 --jinja "
                "--reasoning-format deepseek --no-webui --load-mode none --cache-ram 2048").split()
FROZEN_EXTRA = ("-b 2048 -ub 1024 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16").split()
FROZEN_MTP = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2", "-otd", "token_embd.weight=CPU"]


def test_config_is_the_frozen_runtime_v1():
    cfg = R.load_config()
    assert cfg["frozen"]["verdict"] == "A - STOCK"
    assert cfg["model"]["sha256"] == "66a3ca888ce13482b40c333db2432c0ebde3a7b13754fc29f0c6f5e89703ec66"
    assert cfg["runtime"]["binary_sha256"] == "4fdc1a67a8c1333429ea82186087a77db202fb588c2442dcdfa442b2182d0306"


def test_expected_argv_is_exactly_the_frozen_flag_set():
    argv = R.expected_argv(R.load_config())
    joined = " ".join(argv)
    for flag in (FROZEN_FLAGS, FROZEN_EXTRA, FROZEN_MTP):
        assert " ".join(flag) in joined
    assert "--mmproj" in argv and "-md" in argv
    # no unfrozen extras, e.g. a second slot, an API listener on 0.0.0.0 or unbounded reasoning
    assert "0.0.0.0" not in joined and "--reasoning-budget" not in joined and argv.count("-np") == 1


def test_pinned_artifacts_cover_binary_dll_model_projector_and_mtp():
    roles = [a["role"] for a in R.pinned_artifacts(R.load_config())]
    assert roles == ["server_binary", "vulkan_backend", "model", "vision_projector", "mtp_draft"]


def _cfg_for(tmp_path, files, port=None):
    cfg = copy.deepcopy(R.load_config())
    names = ["llama-server.exe", "ggml-vulkan.dll", "model.gguf", "mmproj.gguf", "mtp.gguf"]
    paths = {}
    for n in names:
        p = tmp_path / n
        if n in files:
            p.write_bytes(files[n])
        paths[n] = str(p)
    sha = lambda n: hashlib.sha256(files.get(n, b"")).hexdigest()
    cfg["runtime"]["binary"], cfg["runtime"]["binary_sha256"] = paths["llama-server.exe"], sha("llama-server.exe")
    cfg["model"]["path"], cfg["model"]["sha256"] = paths["model.gguf"], sha("model.gguf")
    cfg["model"]["mmproj"], cfg["model"]["mmproj_sha256"] = paths["mmproj.gguf"], sha("mmproj.gguf")
    cfg["model"]["mtp_draft"] = {"path": paths["mtp.gguf"], "sha256": sha("mtp.gguf")}
    if port:
        cfg["runtime"]["port"] = port
    return cfg


def test_verify_artifacts_match_cached_mismatch_missing(tmp_path, monkeypatch):
    files = {n: n.encode() * 10 for n in ["llama-server.exe", "ggml-vulkan.dll", "model.gguf", "mmproj.gguf", "mtp.gguf"]}
    monkeypatch.setattr(R, "VULKAN_DLL_SHA256", hashlib.sha256(files["ggml-vulkan.dll"]).hexdigest())
    cfg = _cfg_for(tmp_path, files)
    state = tmp_path / "state"
    v1 = R.verify_artifacts(cfg, state)
    assert v1["overall"] == "MATCH" and v1["methods"] == ["full"]
    v2 = R.verify_artifacts(cfg, state)
    assert v2["overall"] == "MATCH" and v2["methods"] == ["cached"]
    # A changed file (size/mtime differ) is re-hashed in full, never served from the cache.
    (tmp_path / "model.gguf").write_bytes(b"tampered")
    v3 = R.verify_artifacts(cfg, state)
    row = [a for a in v3["artifacts"] if a["role"] == "model"][0]
    assert v3["overall"] == "MISMATCH" and row["status"] == "MISMATCH" and row["method"] == "full"
    os.remove(tmp_path / "mtp.gguf")
    assert R.verify_artifacts(cfg, state)["overall"] == "MISSING"
    # full=True ignores the cache
    assert R.verify_artifacts(cfg, state, full=True)["methods"] == ["full"]


def test_status_stopped_when_nothing_listens(tmp_path):
    cfg = _cfg_for(tmp_path, {}, port=free_port())
    r = R.RuntimeManager(cfg, tmp_path / "state").status()
    assert r.state == R.STOPPED and not r.owned


def test_foreign_instance_on_port_is_never_adopted_or_started_over(tmp_path):
    with FakeLlama() as fake:
        cfg = _cfg_for(tmp_path, {}, port=fake.server_address[1])
        mgr = R.RuntimeManager(cfg, tmp_path / "state")
        r = mgr.status()
        assert r.state == R.FOREIGN_INSTANCE and r.detail == "EXECUTABLE_MISMATCH"
        r2 = mgr.ensure_ready(start=True)
        assert r2.state == R.FOREIGN_INSTANCE and not mgr.owns_instance
        assert not (tmp_path / "state" / "runtime_v1.instance.json").exists()


def test_missing_artifacts_refuse_start(tmp_path):
    cfg = _cfg_for(tmp_path, {}, port=free_port())
    mgr = R.RuntimeManager(cfg, tmp_path / "state")
    r = mgr.ensure_ready(start=True, timeout=5)
    assert r.state == R.ARTIFACT_MISSING and not mgr.owns_instance


def test_live_identity_problems():
    cfg = R.load_config()
    good = {"model_path": cfg["model"]["path"], "n_ctx": 32768, "build_info": "b11425-e117148a4", "total_slots": 1}
    assert R.live_identity_problems(cfg, good) == []
    assert R.live_identity_problems(cfg, dict(good, model_path="D:/other.gguf")) == ["MODEL_PATH_MISMATCH"]
    assert R.live_identity_problems(cfg, dict(good, n_ctx=16384)) == ["CONTEXT_SIZE_MISMATCH"]
    assert R.live_identity_problems(cfg, dict(good, build_info="b9999")) == ["BUILD_MISMATCH"]
    assert R.live_identity_problems(cfg, dict(good, total_slots=3)) == ["SLOT_COUNT_MISMATCH"]


def test_start_lock_excludes_a_second_starter(tmp_path):
    cfg = _cfg_for(tmp_path, {}, port=free_port())
    a, b = R.RuntimeManager(cfg, tmp_path / "s"), R.RuntimeManager(cfg, tmp_path / "s")
    a._acquire_lock()
    try:
        with pytest.raises(R.RuntimeError_) as e:
            b._acquire_lock()
        assert e.value.code == "START_LOCK_HELD"
    finally:
        a._release_lock()
    b._acquire_lock()
    b._release_lock()


def test_stop_never_touches_an_instance_it_did_not_start(tmp_path):
    cfg = _cfg_for(tmp_path, {}, port=free_port())
    assert R.RuntimeManager(cfg, tmp_path / "s").stop() is False
