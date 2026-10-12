"""Phase 2D fixtures: Phase 2B synthetic authority + REAL paired server stack, plus helpers for persisted
qualification records (FIXTURE_ONLY, the fake NDJSON harness) and a Phase 2 server composition with an explicit
policy file. Everything at the executor level is SYNTHETIC unless a test says REAL."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from phase2b.conftest import (CLAUDE, CODEX, FAKE, SyntheticAuthority, authority, bridge, bridge_stack,  # noqa: E402,F401
                              fake_binding, fake_registry, uid)
from uri_supervisor_bridge.composition import DETERMINISTIC_ROW, phase2_server_composition, write_policy  # noqa: E402
from uri_supervisor_bridge.qualification import build_record, write_record  # noqa: E402

HARNESS_ROWS = {("client_external_harness", "claude_code", None), ("client_external_harness", "codex_cli", None),
                ("client_external_harness", "codex_cli", "gpt-6-sol")}


_IDENTITIES = {}


def client_identity(client_root):
    """(client_id, Ed25519 private key) of a client root. A real provisioned client (manifest + DPAPI key) uses its own
    identity; a bare tmp client root gets a test identity, stable for the life of the test process."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    root = Path(client_root).resolve()
    if root in _IDENTITIES:
        return _IDENTITIES[root]
    manifest = root / "client-manifest.json"
    if manifest.is_file() and (root / "secure/client-key.dpapi").is_file():
        from uri_core.core.runtime_identity import dpapi
        data = json.loads(manifest.read_text(encoding="utf-8"))
        key = Ed25519PrivateKey.from_private_bytes(dpapi((root / "secure/client-key.dpapi").read_bytes(), True))
        ident = (data["client_id"], key)
    else:
        ident = (str(uuid.uuid4()), Ed25519PrivateKey.generate())
    _IDENTITIES[root] = ident
    return ident


def trust_for(client_root):
    from uri_supervisor_bridge.qualification import RecordTrust
    cid, key = client_identity(client_root)
    return RecordTrust.from_private_key(cid, key)


def signed_record(client_root, **kw):
    """build_record signed by the client's own identity (what a trusted qualification run of that client does)."""
    cid, key = client_identity(client_root)
    return build_record(client_root=client_root, client_id=cid, signer=key, **kw)


def fixture_record(client_root, provider="claude_code", models=(None,), evidence=None, executable=None, version="0.0.1"):
    """Persist a signed FIXTURE_ONLY qualification record for the fake harness under `client_root`."""
    ev = Path(evidence) if evidence else Path(client_root) / "control" / f"fixture-evidence-{provider}.json"
    ev.parent.mkdir(parents=True, exist_ok=True)
    if not ev.exists():   # fixture evidence must name exactly the models it covers (R2-2, R3-2)
        ev.write_text(json.dumps({"fixture": True, "provider": provider, "models": list(models)}), encoding="utf-8")
    rec = signed_record(client_root, provider=provider, level="FIXTURE_ONLY", spec_id="generic_ndjson",
                        executable=executable or sys.executable, executable_args=[FAKE], version=version, models=list(models),
                        evidence_path=ev, qualified_by="tests/phase2d/conftest.py")
    return write_record(client_root, rec), rec


class Stack:
    """REAL paired server (TestClient), real client manifest/persistence/DPAPI, SupervisedWorkerService over the real
    SupervisedTurnRunner and SupervisorBridge; executor = fake harness through a persisted FIXTURE_ONLY record."""

    def __init__(self, base, *, policy_rows=None, records=(("claude_code", (None,)), ("codex_cli", (None, "gpt-6-sol"))),
                 bridge_kwargs=None, allow_fixture=True):
        from fastapi.testclient import TestClient
        from uri_core.app.paired_server import create_app
        from uri_core.client_runtime.manifest import ClientManifest, provision_client
        from uri_core.client_runtime.persistence import ClientPersistence
        from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, atomic_json, dpapi, provision
        from uri_supervisor_bridge.composition import compose_and_build, policy_path
        from uri_supervisor_bridge.runner import SupervisedTurnRunner
        from uri_supervisor_bridge.worker_service import SupervisedWorkerService

        server_manifest = provision(ROOT, base / "server", Path(sys.executable), 18234, "c2-paired-core")
        runtime = RuntimeIdentity(RuntimeManifest(server_manifest))
        self.policy_file = policy_path(RuntimeManifest(server_manifest).data["state_root"])
        rows = set(policy_rows if policy_rows is not None else HARNESS_ROWS)
        write_policy(self.policy_file, rows)
        self.composition = phase2_server_composition(self.policy_file)
        self.app = create_app(runtime, composition=self.composition)
        principal = uid()
        cm = ClientManifest(provision_client(server_manifest, base / "client", principal, ["remember_fact"]))
        pairings = self.app.state.client_service.pairings
        with pairings.lock:
            data = pairings._load()
            data["clients"][cm.data["client_id"]]["grants"].append("external_harness_task")
            atomic_json(pairings.path, data)
        self.cm, self.client_root = cm, Path(cm.data["client_root"])
        self.records = {}
        for provider, models in records:
            self.records[provider] = fixture_record(self.client_root, provider, models)[1]
        self.client_composition, self.bridge = compose_and_build(self.client_root, trust=trust_for(self.client_root), allow_fixture=allow_fixture,
                                                                **(bridge_kwargs or {"timeout_s": 15, "inactivity_s": 4}))
        cred = json.loads(dpapi((self.client_root / "secure/uri-credentials.dpapi").read_bytes(), True))
        self.http = TestClient(self.app)
        self.http.__enter__()
        s = self.http.post("/client/v1/session", json={"server_id": cred["server_id"], "client_id": cred["client_id"]},
                           headers={"Authorization": "Bearer " + cred["principal_token"], "X-URI-Pairing": cred["pairing_token"]}).json()
        headers = {"Authorization": "Bearer " + s["token"], "X-URI-Client": cred["client_id"]}
        self.headers = headers
        self.calls = []

        def call(method, path, body):
            self.calls.append((method, path))
            r = self.http.request(method, path, json=body, headers=headers)
            return r.status_code, r.json()
        self.persistence = ClientPersistence(cm)
        self.runner = SupervisedTurnRunner(cm, self.persistence, call, cm.data["server_public_key"], runtime.generation,
                                           self.bridge, harness=self.client_composition.registry)
        self.service = self.new_service()

    def server_status(self, turn_id):
        """The server's own view of a turn (frozen GET status route), as the worker's execution status reports it."""
        return self.http.get(f"/client/v1/turns/{turn_id}/status", headers=self.headers).json()

    def new_service(self):
        """A worker-side service on this client; a second one simulates a worker restart/reconnect. In-process: the
        real runner, no HTTP transport hop."""
        from uri_supervisor_bridge.worker_service import SupervisedWorkerService
        svc = SupervisedWorkerService(self.cm, self.persistence, self.bridge, harness=self.client_composition.registry,
                                      composition=self.client_composition, server_status=self.server_status)
        svc.runner = self.runner
        return svc

    def close(self):
        self.http.__exit__(None, None, None)
        self.bridge.close()

    @property
    def L(self):
        return self.bridge.L

    def tasks(self):
        return self.L.q1("SELECT COUNT(*) FROM task")[0]

    def result_files(self):
        d = self.client_root / "workspace" / "results"
        return [p for p in d.rglob("*") if p.is_file()] if d.exists() else []

    def turn_record(self, turn_id):
        return self.app.state.client_service._load()["turns"][turn_id]

    def start(self, text, session=None, reasoning=CLAUDE):
        return self.service.handle("turn_start", {"command": "turn_start", "session_id": session or uid(), "text": text, "reasoning": reasoning})

    def decide(self, turn, approve=True, digest=None, service=None):
        cmd = {"command": "turn_decide", "turn_id": turn["turn_id"], "approve": approve}
        if digest is not None:
            cmd["approval_digest"] = digest
        return (service or self.service).handle("turn_decide", cmd)


@pytest.fixture
def stack(tmp_path):
    s = Stack(ROOT / "work/c1" / ("p2d_" + uuid.uuid4().hex))
    yield s
    s.close()
