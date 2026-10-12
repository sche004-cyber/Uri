"""Phase 2B fixtures.

Two levels:
  * `synthetic` helpers: a test-only Ed25519 key signs ExecutionTickets exactly as the server would, so the bridge's
    authority verification can be attacked field by field without a server. SYNTHETIC authority, labelled.
  * `bridge_stack`: the REAL paired server app (TestClient), real client manifest, real DPAPI credentials, the real
    deterministic no-Brain coordinator, and a SupervisedTurnRunner whose harness execution goes through the real
    uri_supervisor with the SYNTHETIC fake harness executor. The only fake is the executor.
"""
from __future__ import annotations

import json
import secrets
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uri_core.client_contracts import canonical, digest  # noqa: E402
from uri_core.execution_contracts import ExecutionTicket  # noqa: E402
from uri_supervisor.executors import GENERIC_NDJSON  # noqa: E402
from uri_supervisor_bridge.authority import VERIFIER_ID, approval_digest_for, verify_authority  # noqa: E402
from uri_supervisor_bridge.bridge import ExecutorBinding, SupervisorBridge  # noqa: E402

FAKE = str(Path(__file__).parent / "helpers" / "fake_harness.py")
CLAUDE = {"kind": "client_external_harness", "provider": "claude_code", "model": None}
CODEX = {"kind": "client_external_harness", "provider": "codex_cli", "model": None}


def uid():
    return str(uuid.uuid4())


def fake_binding(provider):
    spec = replace(GENERIC_NDJSON, executor_id=provider, stdin="instructions")
    return ExecutorBinding(spec=spec, resolved_executable=sys.executable, extra_argv=(FAKE,), version="fake-0.0.1")


def fake_registry(*providers, usable=True):
    """Phase 1 HarnessRegistry with the fake executable, authenticated and FIXTURE_ONLY-qualified."""
    from uri_harness_adapters import default_registry
    reg = default_registry({p: [sys.executable, FAKE] for p in providers}, auth_probe=lambda hid: True)
    if usable:
        for p in providers:
            reg.qualify(p, "FIXTURE_ONLY", secrets.token_hex(32))
    return reg


# ---- synthetic authority -------------------------------------------------------------------

class SyntheticAuthority:
    """Signs tickets like the server does. Test-only key, never persisted outside the test."""

    def __init__(self, key=None, generation=None):
        self.key = key or Ed25519PrivateKey.generate()
        self.generation = generation or uid()
        self.binding = {"server_id": uid(), "client_id": uid(), "principal_id": uid(), "session_id": uid()}

    @property
    def public_key_hex(self):
        return self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def private_hex(self):
        return self.key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                      serialization.NoEncryption()).hex()

    @staticmethod
    def from_private_hex(hex_key, generation, binding):
        s = SyntheticAuthority(Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hex_key)), generation)
        s.binding = dict(binding)
        return s

    def issue(self, *, instruction="write a greeting", expected_file="out.txt", now=None, intent_digest=None,
              capability="external_harness_task", verifier_id=VERIFIER_ID, deadline_s=600, **overrides):
        now = int(now if now is not None else time.time())
        args = {"action": "run", "inputs": {"instruction": instruction, "expected_file": expected_file}}
        args_digest = digest(args)
        intent_digest = intent_digest or digest({"synthetic_intent": uid()})
        turn_id, op_id = uid(), uid()
        fields = dict(**self.binding, turn_id=turn_id, operation_id=op_id, ticket_id=uid(), generation=self.generation,
                      capability_id=capability, argument_digest=args_digest, workspace_handle=uid(), workspace_version=0,
                      approval_digest=None, approval_status="approved", verifier_id=verifier_id,
                      implementation_digest=digest(verifier_id), issued_at=now, expires_at=now + 60, deadline=now + deadline_s,
                      cancellation_nonce=secrets.token_hex(32))
        fields.update(overrides)
        if fields["approval_digest"] is None:
            probe = ExecutionTicket(**{**fields, "approval_digest": "0" * 64})
            fields["approval_digest"] = approval_digest_for(probe, intent_digest)
        ticket = ExecutionTicket(**fields)
        signed = {"schema_version": "uri.client.v1", "ticket": ticket.model_dump(),
                  "signature": self.key.sign(canonical(ticket.model_dump())).hex()}
        request = {"capability_id": capability, "argument_digest": args_digest, "approval_digest": ticket.approval_digest,
                   "arguments": args, "effect": "local_write", "reversible": True, "intent_digest": intent_digest}
        return signed, request, now

    def verify(self, signed, request, reasoning=CLAUDE, now=None):
        return verify_authority(signed, request=request, reasoning=reasoning, binding=self.binding,
                                server_public_key=self.public_key_hex, generation=self.generation,
                                now=now if now is not None else signed["ticket"]["issued_at"])


@pytest.fixture
def authority():
    return SyntheticAuthority()


@pytest.fixture
def bridge(tmp_path):
    b = SupervisorBridge(tmp_path / "client", registry=fake_registry("claude_code", "codex_cli"),
                         executors={"claude_code": fake_binding("claude_code"), "codex_cli": fake_binding("codex_cli")},
                         timeout_s=15, inactivity_s=4)
    yield b
    b.close()


# ---- real paired stack --------------------------------------------------------------------

@pytest.fixture
def bridge_stack(monkeypatch):
    from fastapi.testclient import TestClient
    from uri_core.app.paired_server import create_app
    from uri_core.client_runtime.manifest import ClientManifest, provision_client
    from uri_core.client_runtime.persistence import ClientPersistence
    from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
    from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, atomic_json, dpapi, provision
    from uri_supervisor_bridge.runner import SupervisedTurnRunner

    base = ROOT / "work/c1" / ("p2b_" + uuid.uuid4().hex)
    server_manifest = provision(ROOT, base / "server", Path(sys.executable), 18234, "c2-paired-core")
    runtime = RuntimeIdentity(RuntimeManifest(server_manifest))
    rows = {("client_external_harness", "claude_code", None), ("client_external_harness", "codex_cli", None),
            ("server_local_model", "uri-deterministic", None)}
    app = create_app(runtime, composition={"policy": ReasoningSelectionPolicy(rows),
                                           "qualified": ("remember_fact", "external_harness_task")})
    principal = uid()
    cm = ClientManifest(provision_client(server_manifest, base / "client", principal, ["remember_fact"]))
    pairings = app.state.client_service.pairings
    with pairings.lock:
        data = pairings._load()
        data["clients"][cm.data["client_id"]]["grants"].append("external_harness_task")
        atomic_json(pairings.path, data)
    cred = json.loads(dpapi((Path(cm.data["client_root"]) / "secure/uri-credentials.dpapi").read_bytes(), True))
    registry = fake_registry("claude_code", "codex_cli")
    bridge = SupervisorBridge(cm.data["client_root"], registry=registry,
                              executors={"claude_code": fake_binding("claude_code"), "codex_cli": fake_binding("codex_cli")},
                              timeout_s=15, inactivity_s=4)
    with TestClient(app) as http:
        s = http.post("/client/v1/session", json={"server_id": cred["server_id"], "client_id": cred["client_id"]},
                      headers={"Authorization": "Bearer " + cred["principal_token"], "X-URI-Pairing": cred["pairing_token"]}).json()
        headers = {"Authorization": "Bearer " + s["token"], "X-URI-Client": cred["client_id"]}
        calls = []

        def call(method, path, body):
            calls.append((method, path))
            r = http.request(method, path, json=body, headers=headers)
            return r.status_code, r.json()
        persistence = ClientPersistence(cm)
        runner = SupervisedTurnRunner(cm, persistence, call, cm.data["server_public_key"], runtime.generation, bridge,
                                      harness=registry)
        yield Stack(runner, persistence, app, call, calls, cm, bridge)
    bridge.close()


class Stack:
    def __init__(self, runner, persistence, app, call, calls, cm, bridge):
        self.runner, self.persistence, self.app, self.call, self.calls, self.cm, self.bridge = runner, persistence, app, call, calls, cm, bridge
        self.client_root = Path(cm.data["client_root"])

    @property
    def L(self):
        return self.bridge.L

    def results(self):
        return list((self.client_root / "workspace" / "results").rglob("*"))

    def result_files(self):
        return [p for p in self.results() if p.is_file()]

    def turn_record(self, turn_id):
        return self.app.state.client_service._load()["turns"][turn_id]

    def run(self, text="use the harness to write a greeting into out.txt", session=None, reasoning=CLAUDE, approve=lambda req: True):
        return self.runner.run(text, session or uid(), reasoning, approve)
