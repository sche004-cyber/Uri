"""Prove that the listener on a working-system server port is THIS installation's paired server (Codex WS round 1, F3).

    <runtime>\\.venv\\Scripts\\python.exe scripts\\ws_server_identity.py <server manifest> [--selftest-wrong-key]

Fetches `/runtime/identity?nonce=<fresh>` from 127.0.0.1:<manifest port> and verifies the frozen identity proof
(`runtime_identity.verify_proof`: every identity field equals the manifest's, the nonce matches, and the Ed25519
signature verifies with the manifest's public key). A health response alone proves nothing. Exit 0 and JSON
{"ok": true, ...} only when the proof verifies; exit 1 otherwise. Read-only; sends no credential.

--selftest-wrong-key (launcher self-test only): verifies the live proof against the same manifest identity but a
freshly generated, valid public key, and succeeds only if that fails with IDENTITY_PROOF_FAILED. This exercises the
signature check itself, not manifest-path validation (Codex WS round 2, LOW).
"""
import json
import secrets
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv):
    from uri_core.core.runtime_identity import RuntimeManifest, verify_proof
    try:
        manifest = RuntimeManifest(argv[1])
    except Exception as exc:
        print(json.dumps({"ok": False, "code": "MANIFEST_" + str(exc)}))
        return 1
    port = int(manifest.data["port"])
    if port == 8000:
        print(json.dumps({"ok": False, "code": "LEGACY_PORT_REFUSED"}))
        return 1
    nonce = secrets.token_hex(32)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/runtime/identity?nonce={nonce}", timeout=3) as r:
            body = r.read(8193)
        if len(body) > 8192:
            raise ValueError("IDENTITY_TOO_LARGE")
        result = json.loads(body)
        if "--selftest-wrong-key" in argv:
            from types import SimpleNamespace
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            other = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw,
                                                                            serialization.PublicFormat.Raw).hex()
            wrong = SimpleNamespace(identity_fields=manifest.identity_fields, data=dict(manifest.data, public_key=other))
            try:
                verify_proof(wrong, result, nonce)
            except Exception as exc:
                refused = str(exc) == "IDENTITY_PROOF_FAILED"
                print(json.dumps({"ok": refused, "wrong_key_refused_with": str(exc)}))
                return 0 if refused else 1
            print(json.dumps({"ok": False, "code": "WRONG_KEY_ACCEPTED"}))
            return 1
        identity = verify_proof(manifest, result, nonce)
    except Exception as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "args", ["IDENTITY_NOT_PROVEN"])[0] or "IDENTITY_NOT_PROVEN"}))
        return 1
    print(json.dumps({"ok": True, "server_id": identity["server_id"], "generation": identity["generation"], "port": port}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
