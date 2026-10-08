"""Live C2/C3 synthetic validation; cleanup proves ownership before signaling."""
import json
from pathlib import Path
import secrets
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from uri_core.client_contracts import ClientStateSnapshot, ReadQuery, canonical, digest
from uri_core.client_runtime.frames import read_frame, write_frame
from uri_core.client_runtime.manifest import ClientManifest, provision_client
from uri_core.core.client_state_ports import ClientStatePorts
from uri_core.core.runtime_identity import RuntimeManifest, child_environment, provision
from scripts.uri_client_launcher import status as client_status
from scripts.uri_server_launcher import launch, listener, owned_instance


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / "work/c1" / ("c3_live_" + uuid.uuid4().hex)
    port = next(p for p in range(18036, 18056) if listener(p) is None)
    server = RuntimeManifest(provision(root, base / "server", Path(sys.executable), port, "c2-paired-core"))
    principal = str(uuid.uuid4())
    manifests = [ClientManifest(provision_client(server.path, base / name, principal, ["remember_fact"])) for name in ("a", "b")]
    processes = []
    started = None
    evidence = {}

    def command(proc, value):
        write_frame(proc.stdin, value)
        result = read_frame(proc.stdout)
        if result is None or result["result"] != "OK":
            raise RuntimeError("LIVE_WORKER_COMMAND_FAILED")
        return result["value"]

    try:
        started = launch(server, "start")
        second = launch(server, "start")
        assert started["pid"] == second["pid"] and second["result"] == "ALREADY_RUNNING"
        identities = []
        for manifest in manifests:
            m = manifest.data
            proc = subprocess.Popen([m["interpreter"], "-B", "-I", m["worker_entrypoint"], "--manifest", str(manifest.path)],
                cwd=m["client_root"], env=child_environment(Path(m["client_root"]), Path(m["interpreter"])),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(proc)
            nonce = secrets.token_hex(32)
            identity = command(proc, {"command": "identity", "nonce": nonce})
            signature = identity.pop("signature")
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(m["client_public_key"])).verify(bytes.fromhex(signature), canonical(identity))
            assert identity["nonce"] == nonce and identity["manifest_digest"] == manifest.digest
            assert client_status(manifest)["pid"] == identity["pid"]
            identities.append(identity)
            assert command(proc, {"command": "session"})["state"] == "SESSION_READY"
            preflight = command(proc, {"command": "preflight"})
            assert preflight["client_id"] == m["client_id"] and preflight["worker_manifest"] == "VALIDATED"
            assert preflight["ui_build"] == "CLIENT_UI_PENDING_C6" and preflight["production_cutover"] is False
        session = str(uuid.uuid4())
        query = ReadQuery(store="memory", method="list_all")
        snapshot = ClientStateSnapshot.model_validate(command(processes[0], {
            "command": "snapshot", "session_id": session, "queries": [query.model_dump()]}))
        binding = {k: getattr(snapshot, k) for k in ("server_id", "client_id", "principal_id", "session_id")}
        ports = ClientStatePorts(snapshot, binding)
        ports.propose("memory", "add", kwargs={"category": "preference", "content": "synthetic isolated live memory"},
                      base_version=0, previous_digest=digest([r.model_dump() for r in snapshot.reads]))
        mutations = ports.mutation_set(str(uuid.uuid4()), str(uuid.uuid4())).model_dump()
        assert command(processes[0], {"command": "consent", "mutations": mutations})["state"] == "CONSENT_RECORDED"
        receipt = command(processes[0], {"command": "commit", "mutations": mutations})
        assert receipt["outcome"] == "COMMITTED"
        assert command(processes[0], {"command": "commit", "mutations": mutations}) == receipt
        other = command(processes[1], {"command": "snapshot", "session_id": session, "queries": [query.model_dump()]})
        assert other["reads"][0]["result"] == []
        readiness = command(processes[0], {"command": "server_request", "method": "GET",
                             "path": "/client/v1/capabilities", "body": None})
        assert readiness["client_id"] == manifests[0].data["client_id"]
        state = Path(server.data["state_root"])
        assert not any(p.name in {"graph.sqlite3", "profile.json", "memory.json", "approvals.json"} for p in state.rglob("*"))
        evidence = {"schema_version": "uri.client.v1", "server": started, "repeat": second,
            "clients": identities, "two_clients_same_principal": True, "client_private_roots_distinct": True,
            "client_b_memory_empty_after_client_a_commit": True, "identical_commit_replay": True,
            "pinned_server_session_handshake": True, "server_private_stores": False,
            "models_loaded_or_required": False, "ui_started": False, "production_cutover": False,
            "worker_preflight_live": "VALIDATED_WITH_UI_PARITY_PENDING"}
    finally:
        # Child pipes were created here and identity was verified. EOF is the
        # worker's normal lifetime close; cleanup never uses foreign PID records.
        for proc in processes:
            if proc.stdin and not proc.stdin.closed:
                if proc.poll() is None:
                    write_frame(proc.stdin, {"command": "close"})
                    closed = read_frame(proc.stdout)
                    assert closed["result"] == "CLOSED"
                proc.stdin.close()
            assert proc.wait(15) == 0
        if started is not None:
            proc = listener(port)
            observed = owned_instance(server, proc)
            assert observed["pid"] == started["pid"] and observed["generation"] == started["generation"]
            proc.terminate()
            proc.wait(15)
            assert listener(port) is None
    evidence["test_owned_workers_and_server_cleaned"] = True
    (base / "server/control/c3-live-evidence.json").write_text(json.dumps(evidence, indent=2))
    (root / "work/c1/c3-live-locator.json").write_text(json.dumps({"evidence": str(base / "server/control/c3-live-evidence.json")}))
    print(json.dumps({k: v for k, v in evidence.items() if k not in {"server", "repeat", "clients"}}))


if __name__ == "__main__":
    main()
