"""Phase 2D opt-in client worker: the frozen C3 worker protocol with harness execution through the supervisor.

This is a COMPOSITION PROFILE, not a cutover: the frozen `scripts/run_uri_client_worker.py` stays the entrypoint named
by every client manifest and the one the frozen UI spawns. This script accepts the same manifest, applies the same
C1 gates (isolated mode, bootstrap import gate, source pin, cwd, sanitized environment, fixture guard, single
instance, key/image identity), and differs only in what it composes:

  * `uri_supervisor_bridge.qualification.compose_client`: persisted, re-validated qualification records instead of
    "nothing qualified"; `harness_discover` additionally returns the qualification report;
  * `uri_supervisor_bridge.worker_service.SupervisedWorkerService`: the frozen turn protocol served by the
    `SupervisedTurnRunner` (verify_authority -> SupervisorBridge -> uri_supervisor), plus `turn_cancel` and the
    optional digest-bound `turn_decide`.

`--allow-fixture-qualification` honours `FIXTURE_ONLY` records (test fixture executors); it is never set by a launcher.
Nothing here logs in, reads or copies credentials, or changes any configuration.
"""
import sys

if not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import uuid

_C1_BOOT = Path(__file__).resolve().parents[1] / "scripts" / "c1_bootstrap.py"
c1_bootstrap = type(sys)("c1_bootstrap")
c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_C1_BOOT), _C1_BOOT.read_bytes()
exec(compile(c1_bootstrap.SOURCE, str(_C1_BOOT), "exec"), c1_bootstrap.__dict__)
sys.modules["c1_bootstrap"] = c1_bootstrap
c1_bootstrap.install(_C1_BOOT.parents[1])

PHASE2_PACKAGES = ("uri_supervisor", "uri_supervisor_bridge")


class Phase2SourceFinder:
    """Same discipline as the C1 bootstrap finder for the two Phase 2 packages: plain source files under the source
    root only, never cached bytecode, digest of the executed bytes recorded. The source root stays off sys.path."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.executed = {}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] not in PHASE2_PACKAGES:
            return None
        base = os.path.join(self.root, *fullname.split("."))
        package, module = os.path.join(base, "__init__.py"), base + ".py"
        is_package, is_module = os.path.isfile(package), os.path.isfile(module)
        if is_package and is_module:
            raise ImportError("PHASE2_SOURCE_AMBIGUOUS", name=fullname)
        if not (is_package or is_module):
            raise ImportError("PHASE2_SOURCE_NOT_FOUND", name=fullname)
        origin = package if is_package else module
        loader = c1_bootstrap.SourceOnlyLoader(fullname, origin)
        spec = importlib.util.spec_from_file_location(fullname, origin, loader=loader,
                                                      submodule_search_locations=[base] if is_package else None)
        self.executed[os.path.relpath(origin, self.root).replace("\\", "/")] = loader
        return spec


_ROOT = _C1_BOOT.parents[1]
_P2 = Phase2SourceFinder(_ROOT)
sys.meta_path.insert(1, _P2)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from uri_core.client_contracts import ClientMutationSet, ReadQuery, canonical  # noqa: E402
from uri_core.client_runtime.frames import FrameError, read_frame, write_frame  # noqa: E402
from uri_core.client_runtime.manifest import ClientManifest  # noqa: E402
from uri_core.core.runtime_identity import FixtureGuard, RuntimeIdentityError, atomic_json, child_environment, dpapi, install_source_pin  # noqa: E402
from scripts.uri_server_launcher import NamedMutex  # noqa: E402
import uri_supervisor  # noqa: E402,F401
import uri_supervisor_bridge  # noqa: E402,F401
from uri_supervisor_bridge.composition import compose_and_build  # noqa: E402
from uri_supervisor_bridge.worker_service import SupervisedWorkerService  # noqa: E402


def phase2_source_digests():
    """SHA-256 of every Phase 2 source file as it was COMPILED by this process (loader-recorded), for the instance record."""
    out = {}
    for rel, loader in sorted(_P2.executed.items()):
        out[rel] = loader.executed_digest
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--allow-fixture-qualification", action="store_true")
    args = parser.parse_args()
    try:
        manifest = ClientManifest(args.manifest)
        m = manifest.data
        root = Path(m["client_root"])
        install_source_pin(Path(m["source_root"]).resolve(), manifest.source_files)
        if Path.cwd().resolve() != root:
            raise RuntimeIdentityError("CLIENT_CWD_MISMATCH")
        safe = child_environment(root, Path(m["interpreter"]))
        os.environ.clear()
        os.environ.update(safe)
        # ISO-1 (Phase 2 closure): Codex ignores USERPROFILE and would read the owner's global login; pin its home to
        # the client profile so probes and executors of this client only ever see the client profile's own login.
        from uri_supervisor_bridge.qualification import client_cli_homes
        os.environ.update(client_cli_homes(root))
        # Persisted qualification is re-validated under the client-profile environment BEFORE the fixture guard, so
        # the executable hashes and version/auth probes run once here; the guard then admits exactly those files.
        from uri_supervisor_bridge.qualification import RecordTrust
        # EXE-1 (operational qualification): a Codex record composes only while the executor environment names THIS
        # profile's Codex home and that home selects a Windows sandbox backend; re-checked before every execution.
        composition, bridge = compose_and_build(root, trust=RecordTrust.from_manifest(m), allow_fixture=args.allow_fixture_qualification,
                                                codex_home=client_cli_homes(root, create=False)["CODEX_HOME"])
        from types import SimpleNamespace

        class Phase2FixtureGuard(FixtureGuard):
            """The frozen guard plus exactly one exception: the null device. `subprocess` opens it O_RDWR for
            stdin=DEVNULL, which the frozen guard counts as an external write; every live `--version` and auth-status
            probe would then fail closed inside this profile (found while repairing review round 2, R2-1)."""
            _NULL = Path(os.devnull).resolve()

            def check_path(self, value, write=False):
                if not isinstance(value, int) and value is not None and Path(os.fsdecode(value)).resolve() == self._NULL:
                    return
                return super().check_path(value, write)
        guard = Phase2FixtureGuard(SimpleNamespace(data={"state_root": str(root), "source_root": m["source_root"]}))
        for pkg in PHASE2_PACKAGES:
            guard.read_roots.append((Path(m["source_root"]) / pkg).resolve())
        for b in composition.executors.values():
            for p in (b.resolved_executable, *b.extra_argv, *(f for f, _ in b.pinned_files)):
                if p and Path(str(p)).is_file():
                    guard.read_files.add(Path(str(p)).resolve())
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
            from uri_core.client_runtime.turn_runner import TurnError
            persistence = ClientPersistence(manifest)
            import psutil
            process = psutil.Process()
            if Path(process.exe()).resolve() != Path(m["process_image"]).resolve():
                raise RuntimeIdentityError("CLIENT_PROCESS_IMAGE")
            generation = str(uuid.uuid4())
            atomic_json(root / "control/worker-instance.json", {"pid": process.pid,
                "create_time": process.create_time(), "generation": generation, "profile": "phase2d-supervised",
                "client_id": m["client_id"], "manifest_digest": manifest.digest,
                "phase2_source_digest": hashlib.sha256(canonical(phase2_source_digests())).hexdigest(),
                "qualified": composition.qualified(), "fixture_allowed": bool(args.allow_fixture_qualification),
                "cli_homes_pinned": sorted(client_cli_homes(root, create=False)),
                "execution_lifecycle": True})
            guard.starting = False
            harnesses = composition.registry
            turns = SupervisedWorkerService(manifest, persistence, bridge, harness=harnesses, composition=composition)
            EXECUTION = {"execution_begin": {"command", "turn_id", "approval_digest", "proposal_digest"},
                         "execution_status": {"command", "execution_id"}, "execution_cancel": {"command", "execution_id"},
                         "execution_list": {"command"}}
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
                                "turn_decide": {"command", "turn_id", "approve"},
                                "turn_cancel": {"command", "turn_id"}, **EXECUTION}
                    if kind not in required or not (set(command) == required[kind]
                                                    or (kind == "turn_decide" and set(command) == required[kind] | {"approval_digest"})):
                        raise ValueError("COMMAND_SCHEMA")
                    # While an execution is in flight the private stores are the execution thread's (frozen loop:
                    # settle -> persist history); UI reads/writes wait for the terminal state. Status/cancel stay open.
                    if kind in {"snapshot", "consent", "commit"} and turns.execution_active is not None:
                        raise TurnError("EXECUTION_IN_PROGRESS")
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
                        result = {**client_preflight(manifest), "worker_profile": "phase2d-supervised",
                                  "production_cutover": False, "execution_lifecycle": sorted(EXECUTION),
                                  "mid_run_cancel": True, "execution_active": turns.execution_active}
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
                        live = {p: b.revalidate() if b.revalidate is not None else None for p, b in composition.executors.items()}
                        result = {"harnesses": harnesses.discover(), "fallback": "none",
                                  "qualification": composition.report, "qualification_live": live,
                                  "supervisor": "uri_supervisor_bridge"}
                    elif kind in {"turn_start", "turn_intent", "turn_decide", "turn_cancel"} or kind in EXECUTION:
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
                        # An execution still in flight is withdrawn (job kill) and its record made terminal before
                        # the worker goes away; the UI's reconnect then finds `uncertain`, never a forgotten run.
                        closed = turns.executions.close(30.0)
                        released = turns.release_pending("WORKER_CLOSED")      # CAP-1: abandoned cards free the server
                        write_frame(sys.stdout.buffer, {"result": "CLOSED", "execution": closed, "released": released})
                        break
                    write_frame(sys.stdout.buffer, {"result": "OK", "value": result})
                except (PersistenceError, TransportError, StatePortError, RuntimeIdentityError, TurnError) as error:
                    write_frame(sys.stdout.buffer, {"result": "REFUSED", "code": str(getattr(error, "code", error))})
                except Exception:
                    write_frame(sys.stdout.buffer, {"result": "REFUSED", "code": "CLIENT_COMMAND_REFUSED"})
            turns.executions.close(30.0)       # stdin EOF (the UI is gone): same withdrawal before the ledger closes
            turns.release_pending("WORKER_STDIN_EOF")
            bridge.close()
        return 0
    except Exception:
        print("CLIENT_WORKER_REFUSED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
