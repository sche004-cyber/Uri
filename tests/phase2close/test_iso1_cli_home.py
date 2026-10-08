"""ISO-1 (Phase 2 closure, 2026-10-08): the worker's client profile must isolate EVERY native CLI's login.

Found while building the acceptance `qualify` step: with USERPROFILE/HOME/APPDATA/LOCALAPPDATA pointed at the client
profile, Codex 0.158.0 still reported the OWNER's global login, because it resolves the Windows profile itself. The
worker therefore pins CODEX_HOME to `<client_root>/home/.codex` (`qualification.client_cli_homes`)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from uri_supervisor_bridge.qualification import client_cli_homes, native_auth_probe  # noqa: E402


def test_client_cli_homes_name_the_client_profile_only(tmp_path):
    pins = client_cli_homes(tmp_path)
    assert pins == {"CODEX_HOME": str(tmp_path / "home" / ".codex")} and (tmp_path / "home" / ".codex").is_dir()
    assert client_cli_homes(tmp_path / "other", create=False) == {"CODEX_HOME": str(tmp_path / "other" / "home" / ".codex")}
    assert not (tmp_path / "other").exists()


def test_the_real_worker_process_pins_codex_home(tmp_path):
    """REAL Phase 2 server + REAL supervised worker process: the worker records the pin it applied."""
    from phase2d.test_worker_process import SERVER, WORKER  # noqa: F401
    from phase2d.conftest import HARNESS_ROWS, fixture_record
    import uuid
    from scripts.uri_server_launcher import listener
    from uri_core.client_runtime.manifest import ClientManifest, provision_client
    from uri_core.client_runtime.frames import read_frame, write_frame
    from uri_core.core.runtime_identity import RuntimeManifest, child_environment, provision
    from uri_supervisor_bridge.composition import policy_path, write_policy
    base = ROOT / "work/c1" / ("p2close_iso1_" + uuid.uuid4().hex)
    port = next(p for p in range(18340, 18380) if listener(p) is None)
    server = RuntimeManifest(provision(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core"))
    write_policy(policy_path(server.data["state_root"]), HARNESS_ROWS)
    client = ClientManifest(provision_client(server.path, base / "c", str(uuid.uuid4()), ["remember_fact"]))
    fixture_record(Path(client.data["client_root"]), "claude_code", (None,))
    m = client.data
    sp = subprocess.Popen([server.data["interpreter"], "-B", "-I", SERVER, "--manifest", str(server.path)], cwd=server.data["state_root"],
                          env=child_environment(Path(server.data["state_root"]), Path(server.data["interpreter"])),
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wp = None
    try:
        import time
        deadline = time.monotonic() + 40
        while listener(port) is None and time.monotonic() < deadline:
            time.sleep(0.2)
        wp = subprocess.Popen([m["interpreter"], "-B", "-I", WORKER, "--manifest", str(client.path), "--allow-fixture-qualification"],
                              cwd=m["client_root"], env=child_environment(Path(m["client_root"]), Path(m["interpreter"])),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        write_frame(wp.stdin, {"command": "preflight"})
        assert read_frame(wp.stdout)["result"] == "OK"
        inst = json.loads((Path(m["client_root"]) / "control/worker-instance.json").read_text())
        assert inst["cli_homes_pinned"] == ["CODEX_HOME"]
        assert (Path(m["client_root"]) / "home" / ".codex").is_dir()
        write_frame(wp.stdin, {"command": "close"})
        assert read_frame(wp.stdout)["result"] == "CLOSED"
        wp.stdin.close()
        assert wp.wait(15) == 0
    finally:
        if wp is not None and wp.poll() is None:
            wp.kill()
        sp.kill()
        sp.wait(15)


@pytest.mark.skipif(shutil.which("codex") is None, reason="LIVE: Codex CLI not installed on this machine")
def test_live_profile_variables_alone_do_not_isolate_codex_but_the_pin_does(tmp_path):
    """LIVE, read-only (`codex login status` only; no login, no credential read). Documents the leak and the repair on
    this machine. When the owner is not logged in globally the first half cannot be observed and is reported as a skip."""
    exe = shutil.which("codex")
    home = tmp_path / "home"
    profile_only = {"USERPROFILE": str(home), "HOME": str(home)}
    leaked = native_auth_probe("codex_cli", exe, environ={**profile_only, "PATH": __import__("os").environ["PATH"],
                                                           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
    pinned = native_auth_probe("codex_cli", exe, environ={**profile_only, **client_cli_homes(tmp_path),
                                                           "PATH": __import__("os").environ["PATH"],
                                                           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
    assert pinned is False                      # the client profile has no login: fail closed
    if leaked is not True:
        pytest.skip("the owner's global Codex login is absent here; the leak half is not observable")
    assert leaked is True                       # without the pin, the owner's global login would have been used
