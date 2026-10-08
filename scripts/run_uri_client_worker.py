"""C3 bounded worker, owned by one client UI/stdio controller."""
import sys

# C1 isolated-mode gate FIRST: without -I the script directory is sys.path[0] and any module imported
# below (argparse, json, pathlib, ...) could be shadowed by a file planted there.
if not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
import argparse
import json
import os
from pathlib import Path
import uuid

# C1 import gate, loaded by exact path BEFORE anything from the source root: the root never goes on
# sys.path, and pinned packages compile only from plain source files (see scripts/c1_bootstrap.py).
_C1_BOOT = Path(__file__).resolve().parents[1] / "scripts" / "c1_bootstrap.py"
c1_bootstrap = type(sys)("c1_bootstrap")
c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_C1_BOOT), _C1_BOOT.read_bytes()
exec(compile(c1_bootstrap.SOURCE, str(_C1_BOOT), "exec"), c1_bootstrap.__dict__)
sys.modules["c1_bootstrap"] = c1_bootstrap
c1_bootstrap.install(_C1_BOOT.parents[1])

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from uri_core.client_contracts import ClientMutationSet, ReadQuery, canonical
from uri_core.client_runtime.frames import FrameError, read_frame, write_frame
from uri_core.client_runtime.manifest import ClientManifest
from uri_core.core.runtime_identity import FixtureGuard, RuntimeIdentityError, atomic_json, child_environment, dpapi, install_source_pin
from scripts.uri_server_launcher import NamedMutex


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        manifest = ClientManifest(args.manifest)
        m = manifest.data
        root = Path(m["client_root"])
        # Every later import from the pinned packages (Core and the client-only adapters) must
        # execute exactly the validated bytes.
        install_source_pin(Path(m["source_root"]).resolve(), manifest.source_files)
        if Path.cwd().resolve() != root:
            raise RuntimeIdentityError("CLIENT_CWD_MISMATCH")
        safe = child_environment(root, Path(m["interpreter"]))
        os.environ.clear()
        os.environ.update(safe)
        # Protect against accidental reads of another client's native account
        # or database, using the same C1 fixture mechanism before store imports.
        from types import SimpleNamespace
        guard = FixtureGuard(SimpleNamespace(data={"state_root": str(root), "source_root": m["source_root"]}))
        sys.addaudithook(guard)
        with NamedMutex("Local\\URI_Client_" + m["client_id"], 0):
            key = Ed25519PrivateKey.from_private_bytes(dpapi((root / "secure/client-key.dpapi").read_bytes(), True))
            from cryptography.hazmat.primitives import serialization
            public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
            if public != m["client_public_key"]:
                raise RuntimeIdentityError("CLIENT_KEY_MISMATCH")
            from uri_core.client_runtime.persistence import ClientPersistence, PersistenceError
            from uri_core.client_runtime.transport import TransportError
            from uri_core.core.client_state_ports import StatePortError
            persistence = ClientPersistence(manifest)
            import psutil
            process = psutil.Process()
            if Path(process.exe()).resolve() != Path(m["process_image"]).resolve():
                raise RuntimeIdentityError("CLIENT_PROCESS_IMAGE")
            generation = str(uuid.uuid4())
            atomic_json(root / "control/worker-instance.json", {"pid": process.pid,
                "create_time": process.create_time(), "generation": generation,
                "client_id": m["client_id"], "manifest_digest": manifest.digest})
            guard.starting = False
            from uri_core.client_runtime.turn_service import TurnService
            # Provider adapters are composed here, outside Core (M31 boundary); none is qualified by default.
            from uri_harness_adapters import default_registry
            harnesses = default_registry()
            turns = TurnService(manifest, persistence, harness=harnesses)
            while True:
                command = read_frame(sys.stdin.buffer)
                if command is None:
                    break
                try:
                    kind = command.get("command")
                    required = {"identity": {"command", "nonce"}, "snapshot": {"command", "session_id", "queries"},
                                "consent": {"command", "mutations"}, "commit": {"command", "mutations"},
                                "close": {"command"}, "session": {"command"}, "preflight": {"command"},
                                "server_request": {"command", "method", "path", "body"},
                                "harness_discover": {"command"},
                                "turn_start": {"command", "session_id", "text", "reasoning"},
                                "turn_intent": {"command", "session_id", "text", "reasoning", "intent_decision"},
                                "turn_decide": {"command", "turn_id", "approve"}}
                    if kind not in required or set(command) != required[kind]:
                        raise ValueError("COMMAND_SCHEMA")
                    if kind == "identity":
                        nonce = command["nonce"]
                        if not isinstance(nonce, str) or len(nonce) != 64 or any(c not in "0123456789abcdef" for c in nonce):
                            raise ValueError("NONCE_INVALID")
                        identity = {"client_id": m["client_id"], "server_id": m["server_id"],
                            "manifest_digest": manifest.digest, "generation": generation, "pid": process.pid,
                            "create_time": process.create_time(), "nonce": nonce}
                        result = {**identity, "signature": key.sign(canonical(identity)).hex()}
                    elif kind == "preflight":
                        from uri_core.client_runtime.readiness import client_preflight
                        result = client_preflight(manifest)
                    elif kind == "snapshot":
                        result = persistence.snapshot(command["session_id"], [ReadQuery.model_validate(q) for q in command["queries"]]).model_dump()
                    elif kind in {"consent", "commit"}:
                        mutation_set = ClientMutationSet.model_validate(command["mutations"])
                        if kind == "consent":
                            persistence.consent(mutation_set)
                            result = {"state": "CONSENT_RECORDED"}
                        else:
                            result = persistence.commit(mutation_set)
                    elif kind == "harness_discover":
                        result = {"harnesses": harnesses.discover(), "fallback": "none"}
                    elif kind in {"turn_start", "turn_intent", "turn_decide"}:
                        result = turns.handle(kind, command)
                    elif kind in {"session", "server_request"}:
                        from uri_core.client_runtime.transport import ClientTransport
                        transport = ClientTransport(manifest)
                        if kind == "session":
                            result = transport.session()
                        else:
                            if command["method"] not in {"GET", "POST"}:
                                raise ValueError("METHOD_INVALID")
                            result = transport.request(command["method"], command["path"], command["body"])
                    else:
                        write_frame(sys.stdout.buffer, {"result": "CLOSED"})
                        break
                    write_frame(sys.stdout.buffer, {"result": "OK", "value": result})
                except (PersistenceError, TransportError, StatePortError, RuntimeIdentityError) as error:
                    write_frame(sys.stdout.buffer, {"result": "REFUSED", "code": str(error)})
                except Exception:
                    # Raw validation exceptions include private args; keep them
                    # on neither stdout protocol nor diagnostic stderr.
                    write_frame(sys.stdout.buffer, {"result": "REFUSED", "code": "CLIENT_COMMAND_REFUSED"})
        return 0
    except Exception:
        print("CLIENT_WORKER_REFUSED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
