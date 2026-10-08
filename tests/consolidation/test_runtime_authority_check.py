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


def test_test_runners_outside_roots_and_genuine_agent_shells_are_not_runtimes():
    rep = verdict(snap(processes=[proc(rf"{PY} -m pytest {DEV}\uri-agent\test_x.py"),
                                  {"pid": 101, "ppid": 1, "image": r"C:\Program Files\Git\bin\bash.exe",
                                   "cmdline": r'"C:\Program Files\Git\bin\bash.exe" -c "source /c/Users/cheta/.claude/shell-snapshots/s.sh && grep run_uri_server.py x"'}]))
    assert rep["findings"] == []


# --- regressions for the Codex adversarial review (2026-10-08, verdict REJECT) -------------------------------------
FAILS = {"DONOR_ONLY", "QUARANTINED", "UNACCOUNTED"}


def test_shared_dependency_name_in_an_argument_does_not_hide_a_uri_server():
    rep = verdict(snap(processes=[proc('python D:/copies/uri-agent/scripts/run_uri_server.py --label "LM Studio"')]), strict=True)
    assert classes(rep) == ["UNACCOUNTED"] and rep["verdict"] == "CONTAMINATED"


def test_authorized_path_in_an_argument_does_not_launder_the_executable():
    cmd = f"python D:/copies/uri-agent/scripts/run_uri_isolated_server.py --log {RUNTIME}/scripts/run_uri_isolated_server.py"
    rep = verdict(snap(processes=[proc(cmd)]), strict=True)
    assert classes(rep)[0] in FAILS and rep["verdict"] == "CONTAMINATED"


def test_legacy_path_in_an_argument_does_not_make_a_donor_transitional():
    cmd = (rf"{PY} C:/Users/cheta/Development/uri-m37-m39-integration/run_desktop_server.py "
           r"--note C:/Users/cheta/Development/uri-agent/scripts/run_uri_server.py")
    rep = verdict(snap(processes=[proc(cmd)]))
    assert classes(rep)[0] in FAILS and rep["verdict"] == "CONTAMINATED"


def test_generic_uvicorn_module_service_on_any_port_and_any_address_is_caught():
    cmd = r"C:\Python313\pythonw.exe -m uvicorn other_uri.app:app --port 9100"
    rep = verdict(snap(processes=[{"pid": 77, "ppid": 1, "image": "pythonw.exe", "cmdline": cmd}],
                       listeners=[{"address": "0.0.0.0", "port": 9100, "pid": 77, "image": "pythonw.exe", "cmdline": cmd}]), strict=True)
    assert rep["verdict"] == "CONTAMINATED" and "UNACCOUNTED" in classes(rep)


def test_encoded_powershell_autostart_is_decoded_and_caught():
    import base64
    enc = base64.b64encode("python D:/x/uri-agent/scripts/run_uri_server.py".encode("utf-16-le")).decode()
    t = {"name": r"\Updater", "enabled": True, "action": f"powershell.exe -NoProfile -EncodedCommand {enc}"}
    rep = verdict(snap(scheduled_tasks=[t]), strict=True)
    assert rep["verdict"] == "CONTAMINATED"


def test_generic_python_autostart_task_is_reported():
    t = {"name": r"\Helper", "enabled": True, "action": r"C:\Python313\python.exe D:\tools\server.py --port 9200"}
    assert verdict(snap(scheduled_tasks=[t]))["verdict"] == "CONTAMINATED"


def test_ui_binding_requires_the_listener_to_serve_that_address():
    cmd = rf"{RUNTIME}/.venv/Scripts/python.exe {RUNTIME}/scripts/run_uri_isolated_server.py"
    rep = verdict(snap(listeners=[listener(8031, cmd, address="192.168.1.7")],
                       ui_preferences={"serverBaseUrl": "http://127.0.0.1:8031"}), strict=True)
    ui = [f for f in rep["findings"] if f["kind"] == "ui_server_binding"][0]
    assert ui["classification"] == "UNACCOUNTED" and rep["verdict"] == "CONTAMINATED"


def test_secret_arguments_are_redacted_from_findings():
    t = {"name": r"\URIServer", "enabled": True,
         "action": r"python C:\Users\cheta\Development\uri-agent\scripts\run_uri_server.py --api-key example-secret token=abc123"}
    rep = verdict(snap(scheduled_tasks=[t]))
    blob = json.dumps(rep)
    assert "example-secret" not in blob and "abc123" not in blob


def test_cmd_wrapped_legacy_task_is_still_recognised_as_transitional():
    t = {"name": r"\URIServer", "enabled": True, "action": r'cmd.exe /c ""C:\Users\cheta\Development\uri-agent\.venv\Scripts\python.exe" "C:\Users\cheta\Development\uri-agent\scripts\run_uri_server.py" --port 8000 >> "C:\Users\cheta\Development\uri-agent\uri_workspace\logs\uri_server.log" 2>&1"'}
    assert classes(verdict(snap(scheduled_tasks=[t]))) == ["TRANSITIONAL_LEGACY"]


# --- regressions for the Codex adversarial review round 2 (2026-10-08, verdict REJECT) -----------------------------
def test_chained_cmd_command_cannot_hide_a_second_server_behind_an_authorized_one():
    for first in (f"python {RUNTIME}/scripts/run_uri_isolated_server.py",
                  "python C:/Users/cheta/Development/uri-agent/scripts/run_uri_server.py"):
        for sep in (" & ", " && ", " || ", " | ", " ; "):
            action = f"cmd.exe /c {first}{sep}python D:/copies/uri-agent/scripts/run_uri_server.py --port 9191"
            rep = verdict(snap(scheduled_tasks=[{"name": r"\Chained", "enabled": True, "action": action}]))
            assert rep["verdict"] == "CONTAMINATED", (first, sep)


def test_redirection_is_not_mistaken_for_a_command_separator():
    action = r'cmd.exe /c ""C:\Users\cheta\Development\uri-agent\.venv\Scripts\python.exe" "C:\Users\cheta\Development\uri-agent\scripts\run_uri_server.py" >> "x.log" 2>&1"'
    assert classes(verdict(snap(scheduled_tasks=[{"name": r"\URIServer", "enabled": True, "action": action}]))) == ["TRANSITIONAL_LEGACY"]


def test_bearer_and_encoded_secrets_are_redacted():
    import base64
    assert "abc123xyz" not in rac.redact('curl -H "Authorization: Bearer abc123xyz" http://x')
    enc = base64.b64encode("python run.py --api-key secret123456".encode("utf-16-le")).decode()
    out = rac.redact(f"powershell -EncodedCommand {enc}")
    assert enc not in out and "secret123456" not in out


def test_shared_dependency_requires_its_exact_install_directory():
    rep = verdict(snap(listeners=[listener(1234, r"C:\Tools\LM Studio Evil\server.exe --port 1234")]))
    assert classes(rep) == ["UNACCOUNTED"] and rep["verdict"] == "CONTAMINATED"


def test_powershell_command_and_encoded_forms_of_the_authorized_launcher_are_authorized():
    import base64
    script = f"{RUNTIME}/scripts/uri_server.ps1"
    cmd = f"powershell.exe -NoProfile -Command \"& '{script}' -Manifest m.json\""
    assert rac.classify(cmd, M)[0] == "AUTHORIZED"
    enc = base64.b64encode(f"& '{script}' -Manifest m.json".encode("utf-16-le")).decode()
    assert rac.classify(f"powershell.exe -EncodedCommand {enc}", M)[0] == "AUTHORIZED"


def test_relative_entrypoint_is_resolved_against_the_working_directory():
    cmd = r"python scripts\run_uri_isolated_server.py [wd=C:\Users\cheta\Development\uri-canonical-runtime-candidate]"
    assert rac.classify(cmd, M)[0] == "AUTHORIZED"
    cmd2 = r"python scripts\run_uri_server.py [wd=C:\Users\cheta\Development\uri-canonical-runtime-candidate]"
    assert rac.classify(cmd2, M)[0] == "UNACCOUNTED"


# --- regressions for the Codex adversarial review round 3 (2026-10-08, verdict REJECT) -----------------------------
def test_digit_adjacent_ampersand_still_separates_commands():
    for sep in ("1&", "1& ", " &1 ", "2&&"):
        action = f"cmd.exe /c python {RUNTIME}/scripts/run_uri_isolated_server.py {sep}python D:/copies/uri-agent/scripts/run_uri_server.py"
        rep = verdict(snap(scheduled_tasks=[{"name": r"\Chained", "enabled": True, "action": action}]))
        assert rep["verdict"] == "CONTAMINATED", sep


def test_path_traversal_cannot_launder_through_a_shared_or_authorized_prefix():
    cases = [r"D:/New folder (2)/LM Studio/../../URI-preservation/server.exe --port 1234",
             r"C:/Users/cheta/AppData/Local/Programs/Ollama/../../../../../../uri-model-lab-nvme/llama-server.exe --port 1234",
             rf"{RUNTIME}/scripts/../../uri-agent/scripts/run_uri_isolated_server.py"]
    for c in cases:
        rep = verdict(snap(listeners=[listener(1234, c)], processes=[proc(c)]))
        assert rep["verdict"] == "CONTAMINATED", c
        assert "SHARED_DEPENDENCY" not in classes(rep) and "AUTHORIZED" not in classes(rep), c


def test_redact_never_raises_on_odd_input():
    for v in (42, b"token=abc12345", None, 3.5, ["x"]):
        assert isinstance(rac.redact(v), str)
    assert "abc12345" not in rac.redact(b"token=abc12345")


# --- regression for the Codex adversarial review round 4 (2026-10-08, verdict REJECT) ------------------------------
def test_any_executable_inside_a_manifest_root_is_evaluated_without_a_uri_hint():
    cmd = "D:/URI-preservation/server.exe --port 9100"
    for s in (snap(scheduled_tasks=[{"name": r"\Plain", "enabled": True, "action": cmd}]),
              snap(run_keys=[{"name": "HKCU:Run/Plain", "value": cmd}]),
              snap(shortcuts=[{"path": r"C:\Startup\plain.lnk", "target": cmd, "startup": True}]),
              snap(listeners=[{"address": "0.0.0.0", "port": 9100, "pid": 9, "image": "D:/URI-preservation/server.exe", "cmdline": ""}]),
              snap(processes=[{"pid": 9, "ppid": 1, "image": "D:/URI-preservation/server.exe", "cmdline": cmd}],
                   listeners=[{"address": "0.0.0.0", "port": 9100, "pid": 9, "image": "D:/URI-preservation/server.exe", "cmdline": cmd}])):
        rep = verdict(s)
        assert rep["verdict"] == "CONTAMINATED" and "DONOR_ONLY" in classes(rep), s


def test_extended_length_prefix_does_not_change_classification():
    cmd = r"python \\?\C:\Users\cheta\Development\uri-agent\scripts\run_uri_server.py --port 8000"
    assert rac.classify(cmd, M)[0] == "TRANSITIONAL_LEGACY"


# --- regression for the Codex adversarial review round 5 (2026-10-08, verdict REJECT) ------------------------------
def test_running_donor_or_quarantined_worker_without_a_listener_fails():
    for cmd in ("D:/URI-preservation/worker.exe --work", "C:/uri-model-lab-nvme/worker.exe --work"):
        rep = verdict(snap(processes=[{"pid": 5, "ppid": 1, "image": cmd.split()[0], "cmdline": cmd}]))
        assert rep["verdict"] == "CONTAMINATED", cmd


def test_donor_test_runs_count_because_no_name_based_exemption_exists():
    cmd = "C:/Users/cheta/.codex/worktrees/uri-phase2a/uri-agent/.venv/Scripts/python.exe -I -m pytest tests/phase2a"
    rep = verdict(snap(processes=[{"pid": 6, "ppid": 1, "image": "python.exe", "cmdline": cmd}]))
    assert classes(rep) == ["DONOR_ONLY"] and rep["verdict"] == "CONTAMINATED"


# --- regressions for the Codex adversarial review round 6 (2026-10-08, verdict REJECT) -----------------------------
def test_test_runner_exemption_cannot_hide_a_donor_worker():
    for cmd in ("D:/URI-preservation/tests/worker.exe --work",
                "C:/Users/cheta/Development/Uri/_V1/.venv/Scripts/python.exe C:/Users/cheta/Development/Uri/_V1/test_worker.py",
                "C:/Users/cheta/Development/Uri/_V1/.venv/Scripts/python.exe C:/Users/cheta/Development/Uri/_V1/worker_chain.py",
                "D:/URI-preservation/worker.exe -m pytest"):
        rep = verdict(snap(processes=[{"pid": 5, "ppid": 1, "image": "x.exe", "cmdline": cmd}]))
        assert rep["verdict"] == "CONTAMINATED", cmd


def test_agent_shell_marker_in_an_argument_does_not_hide_a_donor_worker():
    cmd = "D:/URI-preservation/worker.exe --env CLAUDE_CODE_SHELL=1 --note .claude/shell-snapshots/x"
    assert verdict(snap(processes=[{"pid": 5, "ppid": 1, "image": "worker.exe", "cmdline": cmd}]))["verdict"] == "CONTAMINATED"


# --- regressions for the Codex adversarial review round 7 (2026-10-08, verdict REJECT) -----------------------------
def test_allow_listed_names_and_python_prefixed_executables_cannot_hide_donor_workers():
    for cmd in ("python.exe D:/URI-preservation/phase2d_regression.py",
                "D:/URI-preservation/python-worker.exe -m pytest"):
        assert verdict(snap(processes=[{"pid": 5, "ppid": 1, "image": "x.exe", "cmdline": cmd}]))["verdict"] == "CONTAMINATED", cmd


def test_shell_running_a_donor_script_or_a_fake_shell_is_not_skipped():
    for cmd in (r'"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" -File D:/URI-preservation/worker.ps1 CLAUDE_CODE_SHELL',
                r"D:/URI-preservation/cmd.exe /c CLAUDE_CODE_SHELL"):
        assert verdict(snap(processes=[{"pid": 5, "ppid": 1, "image": "x.exe", "cmdline": cmd}]))["verdict"] == "CONTAMINATED", cmd


def test_a_chain_ending_in_the_checker_is_still_evaluated():
    # The probe now excludes only its own PIDs; a command that merely names the checker is classified like any other.
    cmd = r"powershell.exe -Command D:/URI-preservation/worker.ps1; python C:/x/scripts/uri_runtime_authority_check.py"
    assert verdict(snap(processes=[{"pid": 5, "ppid": 1, "image": "powershell.exe", "cmdline": cmd}]))["verdict"] == "CONTAMINATED"
    assert not hasattr(rac, "_is_self_probe") and not hasattr(rac, "_is_test_runner")


# --- regressions for the Codex adversarial review round 8 (2026-10-08, verdict REJECT) -----------------------------
def test_uri_named_program_outside_every_root_is_counted_with_or_without_a_listener():
    cmd = "D:/rogue/uri_server.exe --port 9100"
    rep = verdict(snap(processes=[{"pid": 3, "ppid": 1, "image": "D:/rogue/uri_server.exe", "cmdline": cmd}],
                       listeners=[{"address": "0.0.0.0", "port": 9100, "pid": 3, "image": "D:/rogue/uri_server.exe", "cmdline": cmd}]))
    assert rep["verdict"] == "CONTAMINATED" and set(classes(rep)) == {"UNACCOUNTED"}
    rep2 = verdict(snap(processes=[{"pid": 4, "ppid": 1, "image": "D:/rogue/uri_worker.exe", "cmdline": "D:/rogue/uri_worker.exe --serve"}]))
    assert rep2["verdict"] == "CONTAMINATED"


def test_bash_c_and_powershell_dot_sourcing_are_parsed():
    assert rac.launch_targets("bash -c 'D:/URI-preservation/worker.exe --x'")[0][1] == "D:/URI-preservation/worker.exe"
    assert rac.launch_targets("powershell -Command . D:/URI-preservation/w.ps1")[0][1] == "D:/URI-preservation/w.ps1"
    shell = r'"C:\Program Files\Git\bin\bash.exe" -c "D:/URI-preservation/worker.exe CLAUDE_CODE_SHELL"'
    assert verdict(snap(processes=[{"pid": 5, "ppid": 1, "image": "bash.exe", "cmdline": shell}]))["verdict"] == "CONTAMINATED"


# --- regressions for the Codex adversarial review round 9 (2026-10-08, verdict REJECT) -----------------------------
def test_unlisted_program_inside_the_authoritative_root_fails_without_a_listener():
    cmd = f"{RUNTIME}/tools/plain_worker.exe --work"
    rep = verdict(snap(processes=[{"pid": 2, "ppid": 1, "image": f"{RUNTIME}/tools/plain_worker.exe", "cmdline": cmd}]))
    assert classes(rep) == ["UNACCOUNTED"] and rep["verdict"] == "CONTAMINATED"


def test_trusted_shell_launching_a_uri_named_program_is_not_skipped():
    cmd = r'"C:\Program Files\Git\bin\bash.exe" -c "/d/rogue/uri_worker.exe --serve CLAUDE_CODE_SHELL"'
    assert verdict(snap(processes=[{"pid": 2, "ppid": 1, "image": "bash.exe", "cmdline": cmd}]))["verdict"] == "CONTAMINATED"


def test_uri_named_image_with_a_neutral_command_line_is_evaluated():
    rep = verdict(snap(processes=[{"pid": 2, "ppid": 1, "image": r"D:\rogue\uri_worker.exe", "cmdline": "worker --serve"}]))
    assert rep["verdict"] == "CONTAMINATED"


def test_consolidation_tools_may_run_from_the_development_checkout_but_nothing_else():
    dev = f"{DEV}/uri-canonical-candidate"
    ok = [rf"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -File {dev}/scripts/uri_authorized_start.ps1 -Action validate",
          f"{dev}/.venv/Scripts/python.exe {dev}/scripts/uri_runtime_authority_check.py --strict"]
    for c in ok:
        assert rac.classify(c, M)[0] == "AUTHORIZED", c
    assert rac.classify(f"{dev}/.venv/Scripts/python.exe {dev}/scripts/run_uri_phase2_server.py", M)[0] == "UNACCOUNTED"


# --- regressions for the Codex adversarial review round 10 (2026-10-08, verdict REJECT) ----------------------------
def test_consolidation_tool_names_outside_the_dev_checkout_are_selected_and_fail():
    rep = verdict(snap(processes=[proc("python D:/rogue/uri_runtime_authority_check.py")],
                       scheduled_tasks=[{"name": r"\Rogue", "enabled": True, "action": "powershell -File D:/rogue/uri_authorized_start.ps1"}]))
    assert rep["verdict"] == "CONTAMINATED" and set(classes(rep)) == {"UNACCOUNTED"}


def test_authorized_command_line_cannot_mask_a_rogue_process_image():
    cmd = f"{RUNTIME}/.venv/Scripts/python.exe {RUNTIME}/scripts/run_uri_phase2_server.py"
    rep = verdict(snap(processes=[{"pid": 7, "ppid": 1, "image": "D:/rogue/uri_worker.exe", "cmdline": cmd}]))
    assert rep["verdict"] == "CONTAMINATED"
    ok = verdict(snap(processes=[{"pid": 8, "ppid": 1, "image": r"C:\Users\cheta\AppData\Local\Programs\Python\Python313\python.exe", "cmdline": cmd}]))
    assert classes(ok) == ["AUTHORIZED"]


# --- regressions for the Codex adversarial review round 11 (2026-10-08, verdict REJECT) ----------------------------
def test_agent_shell_skip_requires_the_real_image_to_be_the_trusted_shell():
    cmd = r'"C:\Program Files\Git\bin\bash.exe" -c "echo CLAUDE_CODE_SHELL"'
    rep = verdict(snap(processes=[{"pid": 2, "ppid": 1, "image": "D:/rogue/uri_worker.exe", "cmdline": cmd}]))
    assert rep["verdict"] == "CONTAMINATED"
    ok = verdict(snap(processes=[{"pid": 3, "ppid": 1, "image": r"C:\Program Files\Git\bin\bash.exe", "cmdline": cmd}]))
    assert ok["findings"] == []


def test_interpreter_image_listener_with_a_neutral_command_line_is_evaluated():
    rep = verdict(snap(listeners=[{"address": "0.0.0.0", "port": 9100, "pid": 9, "image": "C:/Python313/python.exe",
                                   "cmdline": "neutral-service"}]))
    assert rep["verdict"] == "CONTAMINATED"


def test_gate_self_exclusion_requires_the_exact_gate_script_path():
    src = open(rac.__file__, encoding="utf-8").read()
    assert 'gate_path = norm(os.path.join(os.path.dirname(os.path.abspath(__file__)), "uri_authorized_start.ps1"))' in src
    assert '_basename(tg) == "uri_authorized_start.ps1"' not in src


# --- regression for the Codex adversarial review round 12 (2026-10-08, verdict REJECT) -----------------------------
def test_live_privacy_filter_uses_the_real_image_for_the_agent_shell_skip():
    fake_shell = {"pid": 2, "ppid": 1, "image": r"D:\rogue\uri_worker.exe",
                  "cmdline": r'"C:\Program Files\Git\bin\bash.exe" -c "echo CLAUDE_CODE_SHELL"'}
    real_shell = dict(fake_shell, pid=3, image=r"C:\Program Files\Git\bin\bash.exe")
    assert rac.keep_process(fake_shell, M["roots"], set(), set()) is True
    assert rac.keep_process(real_shell, M["roots"], set(), set()) is False


def test_live_privacy_filter_keeps_everything_evaluate_would_select():
    cases = [proc(f"{RUNTIME}/tools/plain_worker.exe"), proc("D:/URI-preservation/worker.exe --work"),
             {"pid": 4, "ppid": 1, "image": r"D:\rogue\uri_worker.exe", "cmdline": "worker --serve"},
             proc("python D:/rogue/uri_runtime_authority_check.py")]
    for c in cases:
        assert rac.keep_process(c, M["roots"], set(), set()), c
