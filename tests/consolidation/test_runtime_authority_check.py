"""Adversarial tests for the runtime authority checker: try to make an obsolete URI component look acceptable."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rac", ROOT / "scripts" / "uri_runtime_authority_check.py")
rac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rac)
MANIFEST_PATH = ROOT / "docs" / "governance" / "URI_RUNTIME_AUTHORITY_MANIFEST.json"
M = rac.load_manifest(MANIFEST_PATH)

DEV = "C:/Users/cheta/Development"
RUNTIME = f"{DEV}/uri-canonical-runtime-candidate"
PY = r"C:\Users\cheta\AppData\Local\Programs\Python\Python313\python.exe"


def snap(**kw):
    s = {"scheduled_tasks": [], "run_keys": [], "shortcuts": [], "processes": [], "listeners": [], "ui_preferences": None}
    s.update(kw)
    return s


def proc(cmd, pid=100):
    return {"pid": pid, "ppid": 1, "image": PY, "cmdline": cmd}


def listener(port, cmd, address="127.0.0.1"):
    return {"address": address, "port": port, "pid": 100, "image": PY, "cmdline": cmd}


def verdict(s, strict=False):
    return rac.evaluate(s, M, strict=strict)


def classes(rep):
    return [f["classification"] for f in rep["findings"]]


# --- the manifest itself -------------------------------------------------------------------------------------
def test_repository_manifest_loads_and_has_no_conflicting_roots():
    assert M["schema"] == "uri-runtime-authority/1"
    assert len({rac.norm(r["path"]) for r in M["roots"]}) == len(M["roots"])


def test_conflicting_root_classification_is_rejected(tmp_path):
    bad = copy.deepcopy(M)
    bad["roots"].append({"id": "x", "path": M["roots"][0]["path"].upper(), "classification": "QUARANTINED_UNTRUSTED"})
    p = tmp_path / "m.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(rac.ManifestError):
        rac.load_manifest(p)
    assert rac.main(["--manifest", str(p), "--snapshot", str(p)]) == 2


def test_unknown_root_classification_is_rejected(tmp_path):
    bad = copy.deepcopy(M)
    bad["roots"][0]["classification"] = "ACTIVE"
    p = tmp_path / "m.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(rac.ManifestError):
        rac.load_manifest(p)


# --- today's live legacy runtime ---------------------------------------------------------------------------------
LEGACY_CMD = (r'"C:\Users\cheta\Development\uri-agent\.venv\Scripts\python.exe"  '
              r'"C:\Users\cheta\Development\uri-agent\scripts\run_uri_server.py" --port 8000')


def test_live_legacy_server_is_accounted_but_fails_strict_mode():
    s = snap(listeners=[listener(8000, LEGACY_CMD)], processes=[proc(LEGACY_CMD)],
             scheduled_tasks=[{"name": "\\URIServer", "enabled": True, "action": "cmd.exe /c " + LEGACY_CMD}],
             ui_preferences={"serverBaseUrl": "http://127.0.0.1:8000"})
    assert set(classes(verdict(s))) == {"TRANSITIONAL_LEGACY"}
    assert verdict(s)["verdict"] == "NO_UNAUTHORIZED_RUNTIME"
    assert verdict(s, strict=True)["verdict"] == "CONTAMINATED"


def test_case_and_slash_variants_of_the_legacy_path_are_still_recognised():
    weird = r"C:/USERS/CHETA//development\URI-AGENT\scripts\RUN_URI_SERVER.py --port 8000"
    assert classes(verdict(snap(processes=[proc(weird)]))) == ["TRANSITIONAL_LEGACY"]


# --- attempts to activate obsolete / donor components ----------------------------------------------------------
@pytest.mark.parametrize("cmd,expected", [
    (rf"{PY} C:\Users\cheta\Development\uri-m37-m39-integration\run_desktop_server.py --port 8000", "DONOR_ONLY"),
    (rf"powershell -File C:\Users\cheta\Development\Uri\_V1\scripts\launch_uri.ps1", "DONOR_ONLY"),
    (rf"{PY} C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\scripts\run_uri_phase2_server.py", "DONOR_ONLY"),
    (rf"{PY} C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\scripts\uri_server_launcher.py start", "DONOR_ONLY"),
    (rf"{PY} C:\Users\cheta\Development\uri-agent\.tmp_m33_1_batch4_baseline_5973f6d\scripts\run_uri_server.py", "QUARANTINED"),
    (rf"{PY} D:\copies\uri-agent\scripts\run_uri_server.py --port 8000", "UNACCOUNTED"),
    (rf"{PY} C:\Users\cheta\Development\Uri\_V1-evil\scripts\run_uri_server.py", "UNACCOUNTED"),
    (rf"{PY} C:\Users\cheta\Development\uri-canonical-runtime-candidate-copy\scripts\uri_server_launcher.py", "UNACCOUNTED"),
])
def test_obsolete_or_unknown_server_processes_fail(cmd, expected):
    rep = verdict(snap(processes=[proc(cmd)]))
    assert classes(rep) == [expected]
    assert rep["verdict"] == "CONTAMINATED"


def test_legacy_entrypoint_inside_the_authoritative_root_is_not_authorized():
    for entry in ("scripts/run_uri_server.py --port 8000", "scripts/launch_uri.ps1", "Launch URI.bat"):
        rep = verdict(snap(processes=[proc(f"{PY} {RUNTIME}/{entry}")]))
        assert classes(rep) == ["UNACCOUNTED"], entry


def test_scheduled_task_or_startup_shortcut_to_a_donor_fails_even_when_not_running():
    t = {"name": "\\URIDesktop", "enabled": True, "action": r"C:\Users\cheta\Development\uri-dictation\Launch URI.bat"}
    assert verdict(snap(scheduled_tasks=[t]))["verdict"] == "CONTAMINATED"
    sc = {"path": r"C:\Users\cheta\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\URI.lnk",
          "target": r"C:\Users\cheta\Development\Uri\_V1\Launch URI Voice.bat", "startup": True}
    assert verdict(snap(shortcuts=[sc]))["verdict"] == "CONTAMINATED"


def test_disabled_task_is_reported_but_not_counted_as_active():
    t = {"name": "\\URIDesktop", "enabled": False, "action": r"C:\Users\cheta\Development\uri-dictation\Launch URI.bat"}
    rep = verdict(snap(scheduled_tasks=[t]))
    assert classes(rep) == ["DONOR_ONLY"] and rep["verdict"] != "CONTAMINATED"


def test_unknown_listener_on_a_uri_port_fails():
    rep = verdict(snap(listeners=[listener(8021, "")]))
    assert classes(rep) == ["UNACCOUNTED"] and rep["verdict"] == "CONTAMINATED"


def test_ui_bound_to_a_port_without_an_accounted_listener_fails():
    rep = verdict(snap(ui_preferences={"serverBaseUrl": "http://127.0.0.1:8031"}))
    assert rep["verdict"] == "CONTAMINATED"


def test_ui_bound_to_a_donor_server_fails():
    donor = rf"{PY} C:\Users\cheta\Development\uri-m37-m39-integration\run_desktop_server.py --port 8000"
    rep = verdict(snap(listeners=[listener(8000, donor)], ui_preferences={"serverBaseUrl": "http://127.0.0.1:8000"}))
    assert [f["classification"] for f in rep["findings"] if f["kind"] == "ui_server_binding"] == ["DONOR_ONLY"]


# --- model runtime ---------------------------------------------------------------------------------------------
def test_runtime_v1_from_the_pinned_root_is_authorized_but_an_unpinned_copy_is_quarantined():
    ok = r"D:\uri-model-lab\runtime\llama-b11425-bin-win-vulkan-x64\llama-server.exe -m D:\uri-model-lab\models\x.gguf --port 18470"
    bad = r"D:\uri-model-lab\runtime\llama-b11425-bin-win-vulkan-x64\llama-server.exe -m C:\uri-model-lab-nvme\models\x.gguf --port 18470"
    assert classes(verdict(snap(listeners=[listener(18470, ok)]))) == ["AUTHORIZED"]
    # The longest matching root wins: the quarantined model path inside the command must not be hidden by the binary path.
    rep = verdict(snap(listeners=[listener(18470, bad)]))
    assert classes(rep) == ["QUARANTINED"] and rep["verdict"] == "CONTAMINATED"


def test_authorized_launcher_pointed_at_a_legacy_state_root_is_not_laundered():
    cmd = rf"{RUNTIME}/.venv/Scripts/python.exe {RUNTIME}/scripts/run_uri_isolated_server.py --state {DEV}/uri-agent/uri_workspace"
    rep = verdict(snap(processes=[proc(cmd)]))
    assert classes(rep) == ["QUARANTINED"] and rep["verdict"] == "CONTAMINATED"


def test_nothing_may_be_launched_from_the_canonical_development_checkout():
    cmd = rf"{PY} {DEV}/uri-canonical-candidate/scripts/uri_server_launcher.py start"
    assert classes(verdict(snap(processes=[proc(cmd)]))) == ["UNACCOUNTED"]


def test_shared_ollama_is_not_contamination():
    rep = verdict(snap(listeners=[listener(11434, r"C:\Users\cheta\AppData\Local\Programs\Ollama\ollama.exe serve")]))
    assert classes(rep) == ["SHARED_DEPENDENCY"] and rep["verdict"] != "CONTAMINATED"


# --- the authorized path ---------------------------------------------------------------------------------------
def test_authorized_c1_launcher_in_the_runtime_root_is_clean():
    cmd = rf"{RUNTIME}\.venv\Scripts\python.exe {RUNTIME}\scripts\run_uri_isolated_server.py --manifest x"
    rep = verdict(snap(listeners=[listener(8031, cmd)], processes=[proc(cmd)],
                       ui_preferences={"serverBaseUrl": "http://127.0.0.1:8031"}), strict=True)
    assert set(classes(rep)) == {"AUTHORIZED"} and rep["verdict"] == "CLEAN"


def test_test_runners_and_agent_shells_are_not_runtimes():
    rep = verdict(snap(processes=[proc(rf"{PY} -m pytest {DEV}\uri-agent\test_x.py"),
                                  proc(r'bash -c "source /c/Users/cheta/.claude/shell-snapshots/s.sh && grep run_uri_server.py x"')]))
    assert rep["findings"] == []
