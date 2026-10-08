"""C3 credential-bearing transport verifies pinned server proof first."""
import json
import os
from pathlib import Path
import secrets
import urllib.error
import urllib.request
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from uri_core.client_contracts import FRAME_LIMIT, canonical
from uri_core.core.runtime_identity import dpapi


class TransportError(ValueError):
    pass


class ClientTransport:
    def __init__(self, manifest):
        self.m = manifest.data
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.secure = Path(self.m["client_root"]) / "secure/uri-credentials.dpapi"

    def _credentials(self):
        return json.loads(dpapi(self.secure.read_bytes(), True))

    def verify_server(self):
        nonce = secrets.token_hex(32)
        try:
            with self.opener.open(self.m["server_url"] + "/runtime/identity?nonce=" + nonce, timeout=10) as response:
                value = json.loads(response.read(8193))
            signature = value.pop("signature")
            if set(value) != {"server_id", "composition_id", "contract_version", "source_checkpoint",
                             "build_manifest_digest", "generation", "nonce"}:
                raise ValueError()
            if (value["server_id"] != self.m["server_id"] or value["contract_version"] != self.m["contract_version"] or
                    value["nonce"] != nonce or value["build_manifest_digest"] != self.m["server_manifest_digest"] or
                    value["composition_id"] != "c2-paired-core" or value["source_checkpoint"] != self.m["source_checkpoint"]):
                raise ValueError()
            uuid.UUID(value["generation"])
            identity = {k: v for k, v in value.items() if k != "nonce"}
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.m["server_public_key"])).verify(
                bytes.fromhex(signature), canonical({"identity": identity, "nonce": nonce}))
            return identity
        except Exception:
            raise TransportError("SERVER_IDENTITY_REFUSED") from None

    def _request(self, method, path, body, headers):
        if not path.startswith("/client/v1/") or "?" in path or "#" in path or ".." in path:
            raise TransportError("CLIENT_ROUTE_REQUIRED")
        self.verify_server()  # never send any bearer to an unproven listener
        payload = canonical(body) if body is not None else None
        if payload is not None and len(payload) > FRAME_LIMIT:
            raise TransportError("REQUEST_LIMIT")
        try:
            request = urllib.request.Request(self.m["server_url"] + path, payload,
                headers={"Content-Type": "application/json", **headers}, method=method)
            with self.opener.open(request, timeout=30) as response:
                data = response.read(FRAME_LIMIT + 1)
            if len(data) > FRAME_LIMIT:
                raise TransportError("RESPONSE_LIMIT")
            return json.loads(data)
        except urllib.error.HTTPError as error:
            # Status only: a foreign/upgraded handler might echo private data.
            raise TransportError("HTTP_" + str(error.code)) from None
        except TransportError:
            raise
        except Exception:
            raise TransportError("TRANSPORT_UNAVAILABLE") from None

    def session(self):
        credentials = self._credentials()
        value = self._request("POST", "/client/v1/session",
            {"server_id": self.m["server_id"], "client_id": self.m["client_id"]},
            {"Authorization": "Bearer " + credentials["principal_token"], "X-URI-Pairing": credentials["pairing_token"]})
        if (value.get("server_id"), value.get("client_id")) != (self.m["server_id"], self.m["client_id"]):
            raise TransportError("SESSION_BINDING")
        credentials["session_token"] = value["token"]
        temp = self.secure.with_name(uuid.uuid4().hex + ".tmp")
        with temp.open("xb") as handle:
            handle.write(dpapi(json.dumps(credentials).encode()))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.secure)
        return {"schema_version": "uri.client.v1", "state": "SESSION_READY"}

    def request(self, method, path, body=None):
        credentials = self._credentials()
        if not credentials.get("session_token"):
            raise TransportError("CLIENT_SESSION_REQUIRED")
        return self._request(method, path, body, {"Authorization": "Bearer " + credentials["session_token"],
                                                  "X-URI-Client": self.m["client_id"]})
