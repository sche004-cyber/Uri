"""C3 manifest validation and local developer provisioning of fresh clients."""
from pathlib import Path
import hashlib
import json
import os
import secrets
import subprocess
import sys
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uri_core.client_contracts import digest
from uri_core.core.runtime_identity import (BASELINE, RuntimeIdentityError, RuntimeManifest, absolute,
                                          atomic_json, dpapi, sha, source_files, dependency_digest)


class ClientManifest:
    def __init__(self, path, validate=True):
        self.path = absolute(str(path))
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise RuntimeIdentityError("CLIENT_MANIFEST_UNREADABLE") from None
        if validate:
            self.validate()
        self.digest = digest(self.data)

    def validate(self):
        m = self.data
        required = {"schema_version", "client_id", "principal_id", "source_root", "source_checkpoint",
                    "source_digest", "interpreter", "interpreter_sha256", "process_image", "process_image_sha256",
                    "worker_entrypoint", "client_root", "server_id", "server_url", "server_public_key",
                    "contract_version", "client_public_key", "ui_binary", "ui_sha256", "server_manifest_digest", "dependency_digest"}
        if not isinstance(m, dict) or set(m) != required or m["schema_version"] != "uri.client.v1":
            raise RuntimeIdentityError("CLIENT_MANIFEST_SCHEMA")
        for key in ("client_id", "principal_id", "server_id"):
            if str(uuid.UUID(m[key])) != m[key]:
                raise RuntimeIdentityError("CLIENT_MANIFEST_BINDING")
        root = Path(__file__).resolve().parents[2]
        client = absolute(m["client_root"])
        if absolute(m["source_root"]) != root or m["source_checkpoint"] != BASELINE:
            raise RuntimeIdentityError("CLIENT_SOURCE_MISMATCH")
        if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != BASELINE:
            raise RuntimeIdentityError("CLIENT_SOURCE_CHECKPOINT")
        if not client.is_relative_to(root / "work/c1") or client == root / "work/c1" or self.path != client / "client-manifest.json":
            raise RuntimeIdentityError("CLIENT_SYNTHETIC_ROOT_REQUIRED")
        if absolute(m["interpreter"]) != root / ".venv/Scripts/python.exe" or sha(m["interpreter"]) != m["interpreter_sha256"]:
            raise RuntimeIdentityError("CLIENT_INTERPRETER_MISMATCH")
        if absolute(m["worker_entrypoint"]) != root / "scripts/run_uri_client_worker.py":
            raise RuntimeIdentityError("CLIENT_WORKER_MISMATCH")
        observed = source_files(root)
        if digest(observed) != m["source_digest"]:
            raise RuntimeIdentityError("CLIENT_SOURCE_DIGEST")
        self.source_files = observed
        if dependency_digest() != m["dependency_digest"]:
            raise RuntimeIdentityError("CLIENT_DEPENDENCIES")
        if sha(m["process_image"]) != m["process_image_sha256"]:
            raise RuntimeIdentityError("CLIENT_PROCESS_IMAGE")
        from urllib.parse import urlparse
        address = urlparse(m["server_url"])
        if (address.scheme != "http" or address.hostname != "127.0.0.1" or address.username or
                address.path or address.query or address.fragment or address.port is None or
                address.port in (8000, 8018, 8021, 11434, 1234)):
            raise RuntimeIdentityError("CLIENT_SERVER_ADDRESS")
        if m["contract_version"] != "uri-runtime/1":
            raise RuntimeIdentityError("CLIENT_CONTRACT")
        for key in ("client_public_key", "server_public_key"):
            if not isinstance(m[key], str) or len(bytes.fromhex(m[key])) != 32:
                raise RuntimeIdentityError("CLIENT_KEY_INVALID")
        for name in ("private", "workspace", "config", "secure", "control", "home", "temp"):
            if (client / name).resolve() != client / name:
                raise RuntimeIdentityError("CLIENT_ROOT_REDIRECTED")
        if (m["ui_binary"] is None) != (m["ui_sha256"] is None):
            raise RuntimeIdentityError("CLIENT_UI_MANIFEST")
        if m["ui_binary"] is not None:
            binary = absolute(m["ui_binary"])
            if not binary.is_relative_to(root) or sha(binary) != m["ui_sha256"]:
                raise RuntimeIdentityError("CLIENT_UI_MISMATCH")


def provision_client(server_manifest, client_root, principal_id, grants, mode="office"):
    """Fresh synthetic client only. No existing accounts or preferences copied."""
    server = RuntimeManifest(server_manifest)
    root = absolute(server.data["source_root"])
    client = absolute(str(client_root))
    if not client.is_relative_to(root / "work/c1") or client == root / "work/c1" or client.exists():
        raise RuntimeIdentityError("FRESH_CLIENT_ROOT_REQUIRED")
    if client.is_relative_to(absolute(server.data["state_root"])):
        raise RuntimeIdentityError("CLIENT_CANNOT_BE_SERVER_STATE")
    from uri_core.core.capability_registry import CapabilityRegistry
    from uri_core.config.modes import VALID_MODES
    registry = CapabilityRegistry(str(root / "uri_workspace/capabilities_registry.json"))
    if mode not in VALID_MODES or set(grants) - {d.id for d in registry.list_capabilities()}:
        raise RuntimeIdentityError("CLIENT_GRANTS_INVALID")
    client.mkdir(parents=True)
    sid = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True).strip().split(",")[-1].strip('"')
    result = subprocess.run(["icacls", str(client), "/inheritance:r", "/grant:r", "*"+sid+":(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], capture_output=True)
    if result.returncode:
        raise RuntimeIdentityError("CLIENT_ACL_FAILED")
    for name in ("private", "workspace", "config", "secure", "control", "home/roaming", "home/local", "temp"):
        (client / name).mkdir(parents=True, exist_ok=True)
    from uri_core.core.client_pairing import ClientPairingStore
    pair = ClientPairingStore(server.data["control_root"], server.data["server_id"]).provision(
        principal_id, grants=grants, mode=mode)
    (client / "secure/uri-credentials.dpapi").write_bytes(dpapi(json.dumps(pair).encode()))
    (client / "secure/credential-store-key.dpapi").write_bytes(dpapi(secrets.token_bytes(32)))
    key = Ed25519PrivateKey.generate()
    (client / "secure/client-key.dpapi").write_bytes(dpapi(key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())))
    manifest = {"schema_version": "uri.client.v1", "client_id": pair["client_id"], "principal_id": principal_id,
                "source_root": str(root), "source_checkpoint": BASELINE, "source_digest": digest(source_files(root)),
                "interpreter": server.data["interpreter"], "interpreter_sha256": server.data["interpreter_sha256"],
                "process_image": server.data["process_image"], "process_image_sha256": server.data["process_image_sha256"],
                "worker_entrypoint": str(root / "scripts/run_uri_client_worker.py"), "client_root": str(client),
                "server_id": server.data["server_id"], "server_url": "http://127.0.0.1:"+str(server.data["port"]),
                "server_public_key": server.data["public_key"], "contract_version": server.data["contract_version"],
                "server_manifest_digest": server.digest,
                "dependency_digest": server.data["dependency_manifest_digest"],
                "client_public_key": key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex(),
                "ui_binary": None, "ui_sha256": None}
    atomic_json(client / "client-manifest.json", manifest)
    return client / "client-manifest.json"
