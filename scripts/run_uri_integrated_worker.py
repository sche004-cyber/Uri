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
WS_PACKAGES = ("uri_operational_intelligence",
               # Web Intelligence (W1) and URI Assist (A0), docs/assist/00_PLAN_AND_ACCEPTANCE_CRITERIA.md. uri_a2ui is
               # read by uri_web.surface (research results render through the existing catalog).
               "uri_web", "uri_assist", "uri_a2ui",
               # M95 privacy gateway (docs/privacy/00_PLAN_AND_ACCEPTANCE_CRITERIA.md): uri_web sends every search
               # query through it.
               "uri_privacy")
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
        frozen_cfg = cfg = R.load_config()
        # Resource profile (RUNTIME-PROFILES-INTEG): verify the Brain against the same derived config its host was
        # started with, named by control/oi/brain_profile.json. Absent or invalid file = the frozen config. The
        # follower re-reads it on change, so a profile switch keeps this worker (and its conversation history).
        from uri_operational_intelligence import runtime_profile_selection as PS
        oi_state = root / "control" / "oi"
        profile = PS.ProfileFollower(frozen_cfg, PS.selection_path(root),
                                     lambda c: R.RuntimeManager(c, state_dir=oi_state),
                                     on_change=lambda c, _note: [setattr(t, "cfg", c) for t in profile_sinks])
        profile_sinks = []          # the IntegratedTurns instance once built (its health/catalog follow the profile)
        cfg, brain_profile = profile.cfg, profile.note
        safe = child_environment(root, Path(m["interpreter"]))
        os.environ.clear()
        os.environ.update(safe)
        from uri_supervisor_bridge.qualification import client_cli_homes, RecordTrust
        os.environ.update(client_cli_homes(root))
        # M95: the privacy gateway's value-free audit and disclosure grants live with this client's state.
        os.environ["URI_PRIVACY_HOME"] = str(root / "control" / "privacy")
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
        # The frozen config's artifacts are a superset of every derived profile's (profiles only drop the projector
        # and/or the MTP draft), so a later profile switch never needs a file the guard does not allow.
        for art in R.pinned_artifacts(frozen_cfg):
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
                "execution_lifecycle": True, "oi": True, "brain_profile": brain_profile})
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

            manager = profile                    # readiness follows the selected profile (status() only)
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

            # Brain host link (WS hardening): the host's report and this worker's explicit requests live in the
            # client's control/oi directory, inside the guard's state root.
            from uri_operational_intelligence import brain_health as BH
            oi = WB.IntegratedTurns(orchestrator=orch, cfg=cfg, status=manager.status,
                                    write_event=lambda ev: write({"event": ev}), memory=memory, defer_start=True,
                                    host_report=lambda: BH.read_host_report(oi_state),
                                    transcript=oi_state / "conversation" / "transcript.sqlite3",
                                    host_request=lambda action, profile=None: BH.write_host_request(oi_state, action, profile))
            profile_sinks.append(oi)
            # W1 / A0 (additive): research and Assist commands. Both yield the single Brain slot to the user's turn
            # (BRAIN_TURNS below cancels their Brain work in flight).
            # A failure to load them never takes the OI worker down: their commands are then refused (COMMAND_SCHEMA).
            web = assist = None
            WEB_COMMANDS = ASSIST_COMMANDS = frozenset()
            try:
                from uri_web import bridge as WEB
                from uri_web import search as WEB_SEARCH
                from uri_web.local_brain import loopback_client, make_complete
                from uri_assist import bridge as ASSIST
                # Loopback-only client that ignores proxy settings (Codex-pending interim review F7).
                assist_brain = loopback_client(R.base_url(cfg))
                # Search keys: an owner-placed file under the client state root (the environment is cleared, F2).
                web_keys = WEB_SEARCH.load_search_keys(root / "control" / "web" / "search_keys.json")
                # Owner decision D3: the Tavily key in the URI development folder's .env (the source checkout the
                # runtime was materialized from, recorded in its receipt), then the runtime source root's .env.
                env_files = [Path(m["source_root"]) / ".env"]
                try:
                    import json as _json
                    rcpt = _json.loads((Path(m["source_root"]) / "OI_MATERIALIZATION_RECEIPT.json").read_text(encoding="utf-8"))
                    if rcpt.get("candidate_source"):
                        env_files.insert(0, Path(rcpt["candidate_source"]) / ".env")
                except (OSError, ValueError, AttributeError):
                    pass
                web_keys = WEB_SEARCH.merge_keys(web_keys, WEB_SEARCH.load_env_keys(env_files))
                web = WEB.WebResearch(write_event=lambda ev: write({"event": ev}),
                                      brain_complete=make_complete(assist_brain), brain_idle=lambda: not oi.busy,
                                      providers_factory=lambda: WEB_SEARCH.providers_from_keys(web_keys),
                                      defer_start=True)
                assist = ASSIST.AssistCommands(brain_client=assist_brain, brain_idle=lambda: not oi.busy,
                                               write_event=lambda ev: write({"event": ev}), defer_start=True)
                # Brain Quick Controls closure (D2/D6): the controls keep vision on while Assist holds a grant.
                oi.assist_state = lambda: WB.assist_state_of(assist)
                WEB_COMMANDS, ASSIST_COMMANDS = frozenset(WEB.COMMANDS), frozenset(ASSIST.COMMANDS)
            except Exception:
                web = assist = None
            BRAIN_TURNS = frozenset({"oi_turn", "oi_confirm", "oi_decide"})   # OI commands that start Brain work
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
                        if kind in BRAIN_TURNS and WB.valid(kind, command):
                            # The user's turn, and a confirmation or decision that resumes it, get the single Brain
                            # slot: research and Assist Brain work in flight is stopped (R1-05).
                            if web is not None:
                                web.cancel_brain_work("user_turn")
                            if assist is not None:
                                assist.cancel_brain_work("user_turn")
                        try:
                            result = oi.handle(kind, command)
                        except WB.BridgeRefused as exc:
                            raise TurnError(exc.code) from None
                        write({"result": "OK", "value": result})
                        oi.release()          # the reply (with the turn id) is out before any event of that turn
                        continue
                    if kind in WEB_COMMANDS or kind in ASSIST_COMMANDS:
                        handler = web if kind in WEB_COMMANDS else assist
                        if kind in ("assist_ask", "assist_grant") and oi.switch_pending():
                            # Closure QCC-R1-04: no Assist answer or new grant on a Brain that is being reloaded.
                            raise TurnError("BRAIN_RESTARTING")
                        try:
                            result = handler.handle(kind, command)
                        except (WEB.Refused, ASSIST.Refused) as exc:
                            raise TurnError(exc.code) from None
                        write({"result": "OK", "value": result})
                        handler.release()     # the reply (with the job / ask id) is out before any of its events
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
                                  "oi_busy": oi.busy, "web_commands": sorted(WEB_COMMANDS),
                                  "assist_commands": sorted(ASSIST_COMMANDS)}
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
            if web is not None:
                web.close()
            if assist is not None:
                assist.close()        # Assist grants never outlive the worker
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
