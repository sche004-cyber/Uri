"""R5-1 (O2 real-application run 2026-10-15): the app starts the Office service on demand through
scripts/run_uri_office_service.py, and the service stops by itself when that app exits (--parent-pid)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[2]
ENTRY = REPO / "scripts" / "run_uri_office_service.py"

PARENT = r'''
import os, subprocess, sys, time
state, entry, port = sys.argv[1], sys.argv[2], sys.argv[3]
p = subprocess.Popen([sys.executable, "-B", "-I", entry, "run", "--state", state, "--port", port,
                      "--parent-pid", str(os.getpid())], env=dict(os.environ, URI_OFFICE_O2="0"),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 if os.name == "nt" else 0)
for _ in range(120):
    if os.path.exists(os.path.join(state, "service.json")):
        break
    time.sleep(0.25)
print(p.pid, flush=True)
'''


def test_entry_script_runs_isolated_and_service_stops_with_its_parent(tmp_path):
    state = tmp_path / "state"
    script = tmp_path / "parent.py"
    script.write_text(PARENT, encoding="utf-8")
    out = subprocess.run([sys.executable, "-B", str(script), str(state), str(ENTRY), "18598"], capture_output=True,
                         text=True, timeout=90)
    child = int(out.stdout.strip())
    try:
        svc = json.loads((state / "service.json").read_text(encoding="utf-8"))
        assert svc["pid"] == child and svc["port"] == 18598
        deadline = time.monotonic() + 20
        while psutil.pid_exists(child) and time.monotonic() < deadline:
            time.sleep(0.25)
        assert not psutil.pid_exists(child), "service kept running after the app that started it exited"
        assert not (state / "service.json").exists(), "service.json left behind"
    finally:
        if psutil.pid_exists(child):
            psutil.Process(child).kill()


def test_entry_script_does_not_depend_on_the_current_directory(tmp_path):
    r = subprocess.run([sys.executable, "-B", "-I", str(ENTRY), "--help"], cwd=tmp_path, capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0 and "run" in r.stdout


def test_a_second_launch_that_cannot_bind_keeps_the_running_services_token(tmp_path):
    """Codex O2-R5-01: the token file is written only after the port is bound."""
    import socket
    from uri_office import service as SVC

    class FakeOffice:
        state = tmp_path / "state"
    FakeOffice.state.mkdir()
    (FakeOffice.state / "api-token").write_text("LIVE-TOKEN", encoding="utf-8")
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen(1)
    try:
        import pytest
        with pytest.raises(OSError):
            SVC.serve(FakeOffice(), "127.0.0.1", busy.getsockname()[1])
    finally:
        busy.close()
    assert (FakeOffice.state / "api-token").read_text(encoding="utf-8") == "LIVE-TOKEN"


def test_the_office_port_cannot_be_shared(tmp_path):
    """Windows SO_REUSEADDR would let a second server listen on the same loopback port; the Office server refuses."""
    import pytest
    from uri_office import service as SVC

    class FakeOffice:
        state = tmp_path / "s1"
    FakeOffice.state.mkdir()
    srv, _ = SVC.serve(FakeOffice(), "127.0.0.1", 0)
    try:
        port = srv.server_address[1]

        class Other:
            state = tmp_path / "s2"
        Other.state.mkdir()
        with pytest.raises(OSError):
            SVC.serve(Other(), "127.0.0.1", port)
        from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
        with pytest.raises(OSError):
            ThreadingHTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)   # a plain reuse-address server too
    finally:
        srv.server_close()


def test_a_quick_restart_on_the_same_port_binds_after_traffic(tmp_path):
    """Codex O2-R5-05: the exclusive bind must not stop the service from starting again at once on its fixed port
    after it served requests (server-side TIME_WAIT) or while a client still held an accepted connection."""
    import socket
    import threading
    import urllib.request
    from uri_office import service as SVC

    class FakeOffice:
        state = tmp_path / "s"
    FakeOffice.state.mkdir()
    srv, token = SVC.serve(FakeOffice(), "127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(5):
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/contract",
                                                          headers={"Authorization": f"Bearer {token}"}), timeout=5)
        except Exception:  # noqa: BLE001 - the fake office has no routes; any HTTP answer makes a connection
            pass
    held = socket.create_connection(("127.0.0.1", port))
    srv.shutdown()
    srv.server_close()
    srv2, _ = SVC.serve(FakeOffice(), "127.0.0.1", port)      # immediately, same port
    srv2.server_close()
    held.close()
