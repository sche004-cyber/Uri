"""Provision a fresh working-system installation inside a MATERIALIZED runtime tree (development only).

    <runtime>\\.venv\\Scripts\\python.exe scripts\\ws_provision.py [--name NAME] [--port PORT] [--grant-harness]

Run from the materialized runtime (HEAD == e8e3b65 + overlay + integration paths; frozen `runtime_identity`
refuses anything else). Creates new roots under `<runtime>/work/ws/<name>/`; nothing existing is modified, and
no legacy data, task, shortcut or service is touched. Writes:
  * server state root with the accepted Phase 2 policy rows (the same rows the accepted acceptance campaign uses);
  * client root, paired to that server, granted `remember_fact` (and `external_harness_task` with --grant-harness);
  * `control/ui-integrated-profile.json`: the explicit opt-in the UI needs before it spawns the integrated worker;
  * `<runtime>/work/ws/current.json`: the paths the launcher uses.
The port is chosen in 18300-18339 and is never 8000 (the legacy instance).
"""
import argparse
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPT_IN = {"schema": "uri.ws.ui_profile.v1", "worker_profile": "ws-integrated"}
LEGACY_PORTS = {8000}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=time.strftime("ws-%Y%m%d-%H%M%S"))
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--grant-harness", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from phase2d.conftest import HARNESS_ROWS  # the accepted policy rows (same as the acceptance campaign)
    from scripts.uri_server_launcher import listener
    from uri_core.client_runtime.manifest import ClientManifest, provision_client
    from uri_core.core.client_pairing import ClientPairingStore
    from uri_core.core.runtime_identity import RuntimeManifest, atomic_json, provision as provision_server
    from uri_supervisor_bridge.composition import policy_path, write_policy
    if Path(sys.executable).resolve() != (ROOT / ".venv/Scripts/python.exe").resolve():
        raise SystemExit("RUN_WITH_THE_RUNTIME_VENV: " + str(ROOT / ".venv/Scripts/python.exe"))
    base = ROOT / "work/ws" / a.name
    if base.exists():
        raise SystemExit("WS_NAME_EXISTS")
    port = a.port or next(p for p in range(18300, 18340) if listener(p) is None)
    if port in LEGACY_PORTS or not (1024 < port < 65536):
        raise SystemExit("WS_PORT_REFUSED")
    server = RuntimeManifest(provision_server(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core"))
    write_policy(policy_path(server.data["state_root"]), HARNESS_ROWS)
    client = ClientManifest(provision_client(server.path, base / "client", str(uuid.uuid4()), ["remember_fact"]))
    if a.grant_harness:
        store = ClientPairingStore(server.data["control_root"], server.data["server_id"])
        with store.lock:
            data = store._load()
            data["clients"][client.data["client_id"]]["grants"].append("external_harness_task")
            atomic_json(store.path, data)
    client_root = Path(client.data["client_root"])
    atomic_json(client_root / "control" / "ui-integrated-profile.json", OPT_IN)
    # Seed the worker's Runtime v1 artifact cache from the host's verified cache (metadata-keyed; any changed file is
    # fully re-hashed by the worker). Absent cache: the worker hashes on first readiness check.
    host_cache = ROOT / "work/oi/state/artifact_hash_cache.json"
    if host_cache.is_file():
        (client_root / "control/oi").mkdir(parents=True, exist_ok=True)
        shutil.copy2(host_cache, client_root / "control/oi/artifact_hash_cache.json")
    current = {"schema": "uri.ws.installation.v1", "name": a.name, "runtime_root": str(ROOT), "port": port,
               "server_manifest": str(server.path), "client_manifest": str(client.path),
               "client_root": str(client_root), "harness_grant": bool(a.grant_harness),
               "provisioned": time.strftime("%Y-%m-%dT%H:%M:%S")}
    atomic_json(ROOT / "work/ws/current.json", current)
    print(json.dumps(current, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
