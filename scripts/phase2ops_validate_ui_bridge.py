"""Phase 2 UI/operations live validation: REAL Phase 2 server profile + REAL provisioned client + the REAL Dart
`SupervisedWorkerRuntime` driving the REAL Phase 2 worker profile (`uri_ui/test/supervised_runtime_live_test.dart`).

Executor: the SYNTHETIC fake harness through a persisted FIXTURE_ONLY record (no login, no credential, no native CLI).
Writes only under <repo>/work/c1 (git-ignored) and the optional --log file. Nothing frozen is touched: the Phase 2
profiles are started by this script, the UI opt-in file is written into the fresh client root only.

Usage:  python scripts/phase2ops_validate_ui_bridge.py [--log <file>]
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from phase2d.conftest import HARNESS_ROWS, fixture_record  # noqa: E402
from scripts.uri_server_launcher import listener  # noqa: E402
from uri_core.client_runtime.manifest import ClientManifest, provision_client  # noqa: E402
from uri_core.core.client_pairing import ClientPairingStore  # noqa: E402
from uri_core.core.runtime_identity import RuntimeManifest, atomic_json, child_environment, provision  # noqa: E402
from uri_supervisor_bridge.composition import policy_path, write_policy  # noqa: E402

SERVER = str(ROOT / "scripts/run_uri_phase2_server.py")
OPT_IN = {"schema": "uri.phase2ops.ui_profile.v1", "worker_profile": "phase2d-supervised"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    base = ROOT / "work/c1" / ("p2ops_ui_" + uuid.uuid4().hex)
    port = next(p for p in range(18260, 18290) if listener(p) is None)
    server = RuntimeManifest(provision(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core"))
    write_policy(policy_path(server.data["state_root"]), HARNESS_ROWS)
    client = ClientManifest(provision_client(server.path, base / "c", str(uuid.uuid4()), ["remember_fact"]))
    store = ClientPairingStore(server.data["control_root"], server.data["server_id"])
    with store.lock:
        data = store._load()
        data["clients"][client.data["client_id"]]["grants"].append("external_harness_task")
        atomic_json(store.path, data)
    client_root = Path(client.data["client_root"])
    fixture_record(client_root, "claude_code", (None,))
    atomic_json(client_root / "control" / "ui-supervised-profile.json", OPT_IN)       # the explicit per-installation opt-in
    sm = server.data
    log = Path(sm["state_root"]) / "logs" / "phase2-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    sp = subprocess.Popen([sm["interpreter"], "-B", "-I", SERVER, "--manifest", str(server.path)], cwd=sm["state_root"],
                          env=child_environment(Path(sm["state_root"]), Path(sm["interpreter"])), stdin=subprocess.DEVNULL,
                          stdout=open(log, "ab"), stderr=subprocess.STDOUT)
    out = {"base": str(base), "port": port, "client_manifest": str(client.path), "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        deadline = time.monotonic() + 40
        while listener(port) is None and time.monotonic() < deadline:
            time.sleep(0.2)
        if listener(port) is None:
            raise SystemExit("PHASE2_SERVER_DID_NOT_LISTEN")
        flutter = Path.home() / "flutter/bin/flutter.bat"
        t0 = time.time()
        r = subprocess.run([str(flutter), "test", "test/supervised_runtime_live_test.dart"], cwd=ROOT / "uri_ui",
                           env={**os.environ, "URI_CLIENT_MANIFEST": str(client.path)}, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out.update(exit=r.returncode, duration_s=round(time.time() - t0, 1), stdout_tail=r.stdout[-3000:], stderr_tail=r.stderr[-1500:])
        records = sorted((client_root / "control/supervisor/executions").glob("*.json"))
        out["execution_records"] = [json.loads(p.read_text(encoding="utf-8")) for p in records]
        print(r.stdout[-1500:])
        print("EXIT", r.returncode)
        if a.log:
            Path(a.log).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        return r.returncode
    finally:
        if sp.poll() is None:
            sp.kill()
        sp.wait(15)


if __name__ == "__main__":
    raise SystemExit(main())
