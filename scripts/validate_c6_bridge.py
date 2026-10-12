"""Live C6 bridge validation: real isolated server + provisioned client + Flutter test of the Dart bridge."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uri_core.client_runtime.manifest import provision_client
from uri_core.core.runtime_identity import RuntimeManifest, provision
from scripts.uri_server_launcher import launch, listener


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / "work/c1" / ("c6_bridge_" + uuid.uuid4().hex)
    port = next(p for p in range(18260, 18280) if listener(p) is None)
    server = RuntimeManifest(provision(root, base / "server", Path(sys.executable), port, "c2-paired-core"))
    client = provision_client(server.path, base / "client", str(uuid.uuid4()), ["remember_fact"])
    started = launch(server, "start")
    try:
        flutter = Path.home() / "flutter/bin/flutter.bat"
        result = subprocess.run([str(flutter), "test", "test/paired_runtime_live_test.dart"], cwd=root / "uri_ui",
                                env={**os.environ, "URI_CLIENT_MANIFEST": str(client)}, capture_output=True, text=True)
        print(result.stdout[-1500:])
        return result.returncode
    finally:
        proc = listener(port)
        if proc is not None and proc.pid == started["pid"]:
            proc.terminate()
            proc.wait(15)


if __name__ == "__main__":
    raise SystemExit(main())
