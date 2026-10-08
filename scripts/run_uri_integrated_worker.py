"""Working-system client worker: the accepted Phase 2 supervised worker plus Operational Intelligence turns with
streamed events (WS blueprint W2, owner decision WS-D1).

COMPOSITION PROFILE, not a cutover. The frozen `scripts/run_uri_client_worker.py` and the accepted
`scripts/run_uri_supervised_worker.py` are unchanged. This script accepts the same client manifest and applies the
same C1 gates: isolated mode, bootstrap import gate, source pin, cwd, sanitized environment, fixture guard, single
instance, and key/image identity. Its composition is the accepted one (`compose_and_build`,
`SupervisedWorkerService`). It adds:

  * `uri_operational_intelligence` loaded like the Phase 2 packages: plain source under the source root, with the
    executed digests recorded in the instance file;
  * the OI orchestrator, whose Core gateway is THIS client's runner (`PairedCoreGateway`). Every action still goes
    through Intent Discovery, confirmation, approval, the signed ticket and client execution;
  * streamed event frames `{"event": uri.oi.event.v1}` for OI turns (`worker_bridge.IntegratedTurns`);
  * read-only Runtime v1 readiness. The worker never starts or stops Runtime v1; only
    `uri_operational_intelligence.host` does.

Framing: every frame, reply or event, is written under one lock. Replies stay in request order. An OI job and a
supervised execution exclude each other, and while either runs, commands that use the same runner or stores are
refused.
"""
import sys

if not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import threading
import uuid

_C1_BOOT = Path(__file__).resolve().parents[1] / "scripts" / "c1_bootstrap.py"
c1_bootstrap = type(sys)("c1_bootstrap")
c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_C1_BOOT), _C1_BOOT.read_bytes()
exec(compile(c1_bootstrap.SOURCE, str(_C1_BOOT), "exec"), c1_bootstrap.__dict__)
sys.modules["c1_bootstrap"] = c1_bootstrap
c1_bootstrap.install(_C1_BOOT.parents[1])

PHASE2_PACKAGES = ("uri_supervisor", "uri_supervisor_bridge")
WS_PACKAGES = ("uri_operational_intelligence",)
WORKER_PROFILE = "ws-integrated"


class SourceFinder:
    """Same discipline as the accepted Phase 2 finder, for the Phase 2 packages and the OI package."""

    def __init__(self, root, packages):
        self.root, self.packages = os.path.abspath(root), packages
        self.executed = {}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] not in self.packages:
            return None
        base = os.path.join(self.root, *fullname.split("."))
        package, module = os.path.join(base, "__init__.py"), base + ".py"
        is_package, is_module = os.path.isfile(package), os.path.isfile(module)
        if is_package and is_module:
            raise ImportError("WS_SOURCE_AMBIGUOUS", name=fullname)
        if not (is_package or is_module):
            raise ImportError("WS_SOURCE_NOT_FOUND", name=fullname)
        origin = package if is_package else module
        loader = c1_bootstrap.SourceOnlyLoader(fullname, origin)
        spec = importlib.util.spec_from_file_location(fullname, origin, loader=loader,
                                                      submodule_search_locations=[base] if is_package else None)
        self.executed[os.path.relpath(origin, self.root).replace("\\", "/")] = loader
        return spec


_ROOT = _C1_BOOT.parents[1]
_FINDER = SourceFinder(_ROOT, PHASE2_PACKAGES + WS_PACKAGES)
sys.meta_path.insert(1, _FINDER)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from uri_core.client_contracts import ClientMutationSet, ReadQuery, canonical  # noqa: E402
from uri_core.client_runtime.frames import read_frame, write_frame  # noqa: E402
from uri_core.client_runtime.manifest import ClientManifest  # noqa: E402
from uri_core.core.runtime_identity import FixtureGuard, RuntimeIdentityError, atomic_json, child_environment, dpapi, install_source_pin  # noqa: E402
from scripts.uri_server_launcher import NamedMutex  # noqa: E402
import uri_supervisor  # noqa: E402,F401
import uri_supervisor_bridge  # noqa: E402,F401
from uri_supervisor_bridge.composition import compose_and_build  # noqa: E402
from uri_supervisor_bridge.worker_service import SupervisedWorkerService  # noqa: E402
from uri_operational_intelligence import brain_client as BC, runtime_v1 as R  # noqa: E402
from uri_operational_intelligence import worker_bridge as WB  # noqa: E402
from uri_operational_intelligence.orchestrator import Orchestrator, PairedCoreGateway  # noqa: E402
from uri_operational_intelligence.task_ledger import TaskLedger  # noqa: E402

STORE_COMMANDS = {"snapshot", "consent", "commit", "turn_start", "turn_intent", "turn_decide", "turn_cancel",
                  "execution_begin"}


def source_digests():
    return {rel: loader.executed_digest for rel, loader in sorted(_FINDER.executed.items())}


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
        # The frozen Runtime v1 configuration is read once, before the guard (it lives under the source root's
        # model_lab/, outside the guard's read roots). The worker only ever READS Runtime v1 state.
        cfg = R.load_config()
        oi_state = root / "control" / "oi"
        safe = child_environment(root, Path(m["interpreter"]))
        os.environ.clear()
        os.environ.update(safe)
        from uri_supervisor_bridge.qualification import client_cli_homes, RecordTrust
        os.environ.update(client_cli_homes(root))
        composition, bridge = compose_and_build(root, trust=RecordTrust.from_manifest(m), allow_fixture=args.allow_fixture_qualification,
                                                codex_home=client_cli_homes(root, create=False)["CODEX_HOME"])
        from types import SimpleNamespace

        class WorkerGuard(FixtureGuard):
            """The frozen guard plus the accepted null-device exception (Phase 2 R2-1)."""
            _NULL = Path(os.devnull).resolve()

            def check_path(self, value, write=False):
                if not isinstance(value, int) and value is not None and Path(os.fsdecode(value)).resolve() == self._NULL:
                    return
                return super().check_path(value, write)
        guard = WorkerGuard(SimpleNamespace(data={"state_root": str(root), "source_root": m["source_root"]}))
        for pkg in PHASE2_PACKAGES + WS_PACKAGES:
            guard.read_roots.append((Path(m["source_root"]) / pkg).resolve())
        for b in composition.executors.values():
            for p in (b.resolved_executable, *b.extra_argv, *(f for f, _ in b.pinned_files)):
                if p and Path(str(p)).is_file():
                    guard.read_files.add(Path(str(p)).resolve())
        # Runtime v1 readiness re-checks the five pinned artifacts (metadata cache under the client root; a full hash
        # only when a file changed). Exactly those files are readable, nothing else outside the roots.
        for art in R.pinned_artifacts(cfg):
            guard.read_files.add(Path(art["path"]).resolve())
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
                "create_time": process.create_time(), "generation": generation, "profile": WORKER_PROFILE,
                "client_id": m["client_id"], "manifest_digest": manifest.digest,
                "phase2_source_digest": hashlib.sha256(canonical(source_digests())).hexdigest(),
                "qualified": composition.qualified(), "fixture_allowed": bool(args.allow_fixture_qualification),
                "cli_homes_pinned": sorted(client_cli_homes(root, create=False)),
                "execution_lifecycle": True, "oi": True})
            guard.starting = False
            harnesses = composition.registry
            turns = SupervisedWorkerService(manifest, persistence, bridge, harness=harnesses, composition=composition)

            class LazyRunner:
                """The service builds its runner (server identity + session) on first use, as the accepted worker does."""
                def __getattr__(self, name):
                    return getattr(turns._runner(), name)

            write_lock = threading.Lock()

            def write(frame):
                with write_lock:
                    write_frame(sys.stdout.buffer, frame)

            manager = R.RuntimeManager(cfg, state_dir=oi_state)
            client = BC.BrainClient(R.base_url(cfg))
            ledger = TaskLedger(oi_state / "tasks")
            ledger.acquire_owner()
            ledger.recover()
            orch = Orchestrator(client=client, core=PairedCoreGateway(LazyRunner()), brain_selection={}, ledger=ledger,
                                capability_ids={"remember_fact", "external_harness_task"}, readiness=manager.status)

            # Client-scoped memory is read under a fixed per-client session id (Core requires a UUID session).
            memory_session = str(uuid.uuid5(uuid.NAMESPACE_URL, "uri-ws-memory:" + m["client_id"]))

            def memory():
                q = ReadQuery(store="memory", method="list_all")
                rows = persistence.snapshot(memory_session, [q]).reads[0].result or []
                return [r.get("fact", {}).get("value") for r in rows if isinstance(r, dict)]

            oi = WB.IntegratedTurns(orchestrator=orch, cfg=cfg, status=manager.status,
                                    write_event=lambda ev: write({"event": ev}), memory=memory, defer_start=True)
            EXECUTION = {"execution_begin": {"command", "turn_id", "approval_digest", "proposal_digest"},
                         "execution_status": {"command", "execution_id"}, "execution_cancel": {"command", "execution_id"},
                         "execution_list": {"command"}}
            while True:
                command = read_frame(sys.stdin.buffer)
                if command is None:
                    break
                try:
                    kind = command.get("command")
                    if kind in WB.COMMANDS:
                        if kind not in WB.OPEN_WHILE_BUSY and turns.execution_active is not None:
                            raise TurnError("EXECUTION_IN_PROGRESS")
                        try:
                            result = oi.handle(kind, command)
                        except WB.BridgeRefused as exc:
                            raise TurnError(exc.code) from None
                        write({"result": "OK", "value": result})
                        oi.release()          # the reply (with the turn id) is out before any event of that turn
                        continue
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
                    if kind in {"snapshot", "consent", "commit"} and turns.execution_active is not None:
                        raise TurnError("EXECUTION_IN_PROGRESS")
                    if kind in STORE_COMMANDS and oi.busy:
                        raise TurnError("OI_TURN_IN_PROGRESS")
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
                        result = {**client_preflight(manifest), "worker_profile": WORKER_PROFILE,
                                  "production_cutover": False, "execution_lifecycle": sorted(EXECUTION),
                                  "mid_run_cancel": True, "execution_active": turns.execution_active,
                                  "oi_commands": sorted(WB.COMMANDS), "event_schema": "uri.oi.event.v1",
                                  "oi_busy": oi.busy}
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
                        closed = shutdown(oi, turns)
                        write({"result": "CLOSED", **closed})
                        break
                    write({"result": "OK", "value": result})
                except (PersistenceError, TransportError, StatePortError, RuntimeIdentityError, TurnError) as error:
                    write({"result": "REFUSED", "code": str(getattr(error, "code", error))})
                except Exception:
                    write({"result": "REFUSED", "code": "CLIENT_COMMAND_REFUSED"})
            shutdown(oi, turns)       # stdin EOF (the UI is gone) or after close: same withdrawal, idempotent
            bridge.close()
            ledger.release_owner()
        return 0
    except Exception:
        print("CLIENT_WORKER_REFUSED", file=sys.stderr)
        return 1


def shutdown(oi, turns):
    """Same withdrawal rules as the accepted worker, plus: cancel a running OI turn and release pending OI approvals
    as denials, so abandoned cards never hold server capacity (CAP-1). `closing` is set first, so a job that is still
    finishing releases its own card when it registers it (Codex WS round 1, F2). A job that outlives the join (a Core
    call that does not return) cannot be released from here; the server's idle expiry stays the backstop."""
    oi.begin_close()
    job = oi._job
    unfinished = False
    if job is not None and job[1].is_alive():
        oi.release()          # a deferred job that never got its go signal must still be able to end
        oi.o.cancel(job[0], "worker_closed")
        job[1].join(30.0)
        unfinished = job[1].is_alive()
    released_oi = 0
    for tid in list(oi.pending):
        try:
            oi.handle("oi_abandon", {"command": "oi_abandon", "turn_id": tid})
            released_oi += 1
        except Exception:
            pass
    closed = turns.executions.close(30.0)
    released = turns.release_pending("WORKER_CLOSED")
    return {"execution": closed, "released": released, "released_oi": released_oi, "oi_job_unfinished": unfinished}


if __name__ == "__main__":
    raise SystemExit(main())
