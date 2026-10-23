"""Working-system paired server: the accepted Phase 2 server profile plus the Runtime v1 Brain row
(WS blueprint W3; the owner's mandate makes Runtime v1 the default local Brain, OI readiness section 4 item 1).

COMPOSITION PROFILE, not a cutover. The frozen `scripts/run_uri_isolated_server.py` and the accepted
`scripts/run_uri_phase2_server.py` are unchanged. This script accepts the same manifest, applies the same gates
(isolated mode, C1 bootstrap, source pin, state cwd, sanitized environment, fixture guard, named instance mutex,
`c2-paired-core` composition) and differs only in the composition passed to `create_app`:
`uri_operational_intelligence.integrated_composition.integrated_server_composition`. That composition is the Phase 2
policy rows (accepted loader, so a malformed policy file still refuses startup) plus the single Runtime v1 row, with
the OI proposer and interpreter seams for that row only.

The server connects to Runtime v1 on 127.0.0.1:18470 after startup (the guard blocks connections only while
starting). It never starts, stops or adopts Runtime v1.
"""
import sys

if not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
import argparse
import asyncio
import importlib.util
import os
from pathlib import Path
import secrets

_C1_BOOT = Path(__file__).resolve().parents[1] / "scripts" / "c1_bootstrap.py"
c1_bootstrap = type(sys)("c1_bootstrap")
c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_C1_BOOT), _C1_BOOT.read_bytes()
exec(compile(c1_bootstrap.SOURCE, str(_C1_BOOT), "exec"), c1_bootstrap.__dict__)
sys.modules["c1_bootstrap"] = c1_bootstrap
c1_bootstrap.install(_C1_BOOT.parents[1])

PACKAGES = ("uri_supervisor", "uri_supervisor_bridge", "uri_operational_intelligence")


class SourceFinder:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] not in PACKAGES:
            return None
        base = os.path.join(self.root, *fullname.split("."))
        package, module = os.path.join(base, "__init__.py"), base + ".py"
        is_package, is_module = os.path.isfile(package), os.path.isfile(module)
        if is_package and is_module:
            raise ImportError("WS_SOURCE_AMBIGUOUS", name=fullname)
        if not (is_package or is_module):
            raise ImportError("WS_SOURCE_NOT_FOUND", name=fullname)
        origin = package if is_package else module
        return importlib.util.spec_from_file_location(fullname, origin, loader=c1_bootstrap.SourceOnlyLoader(fullname, origin),
                                                      submodule_search_locations=[base] if is_package else None)


sys.meta_path.insert(1, SourceFinder(_C1_BOOT.parents[1]))

from uri_core.core.runtime_identity import RuntimeManifest, RuntimeIdentity, RuntimeIdentityError, FixtureGuard, absolute, child_environment, dpapi, install_source_pin  # noqa: E402
from scripts.uri_server_launcher import NamedMutex  # noqa: E402
from uri_supervisor_bridge.composition import PolicyError, policy_path  # noqa: E402
from uri_supervisor_bridge.refusal_log import RefusalLog  # noqa: E402
from uri_operational_intelligence import brain_client as BC, runtime_v1 as R  # noqa: E402
from uri_operational_intelligence.integrated_composition import integrated_server_composition  # noqa: E402


def persistent_secret(path: Path) -> str:
    """The key-store secret for this state root, DPAPI-protected for the current user (M95, P0 defect D10).

    A new random secret on every start made every saved provider key and credential unreadable after a restart. It is
    now created once and read back afterwards. A file that exists but cannot be unprotected stops startup
    (PROTECTED_KEY_UNAVAILABLE) instead of being replaced, because a replaced secret silently orphans the stored keys.
    Same logic as `uri_privacy.keys.persistent_key`, inline because this hardened entrypoint imports only its
    pinned packages."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = dpapi(secrets.token_bytes(32))
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_bytes(blob)
        try:
            os.link(tmp, path)             # exclusive create: two first starts cannot keep different secrets
        except FileExistsError:
            pass
        except OSError:                    # no hard links on this volume: exclusive create instead (review S1-08)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "wb") as f:
                    f.write(blob)
                    f.flush()
                    os.fsync(f.fileno())
        finally:
            tmp.unlink(missing_ok=True)
    raw = dpapi(path.read_bytes(), True)
    if len(raw) != 32:
        raise RuntimeIdentityError("PROTECTED_KEY_UNAVAILABLE")
    return raw.hex()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        manifest = RuntimeManifest(args.manifest)
        m = manifest.data
        state = absolute(m["state_root"])
        install_source_pin(absolute(m["source_root"]), m["source_files"])
        if Path.cwd().resolve() != state:
            raise RuntimeIdentityError("STATE_CWD_MISMATCH")
        try:
            cfg = R.load_config()          # frozen local_brain.json, read before the guard
        except R.RuntimeError_ as exc:
            raise RuntimeIdentityError("RUNTIME_V1_" + exc.code) from None
        safe = child_environment(state, absolute(m["interpreter"]))
        os.environ.clear()
        os.environ.update(safe)
        os.environ["URI_PROVIDER_KEY_SECRET"] = persistent_secret(state / "secure" / "provider-key-secret.dpapi")
        os.environ["URI_EXTERNAL_CREDENTIAL_SECRET"] = persistent_secret(state / "secure" / "external-credential-secret.dpapi")
        if m["composition_id"] != "c2-paired-core":
            raise RuntimeIdentityError("PHASE2_PAIRED_COMPOSITION_REQUIRED")
        try:
            composition, _provider = integrated_server_composition(policy_path(state), cfg, BC.BrainClient(R.base_url(cfg)))
        except PolicyError as exc:
            raise RuntimeIdentityError(str(exc)) from None
        runtime = RuntimeIdentity(manifest)
        guard = FixtureGuard(manifest)
        runtime.guard = guard
        for pkg in PACKAGES:
            guard.read_roots.append((absolute(m["source_root"]) / pkg).resolve())
        with NamedMutex("Local\\URI_Instance_" + m["server_id"], 0), asyncio.Runner() as runner:
            runner.get_loop()
            sys.addaudithook(guard)
            from uri_core.app.paired_server import create_app
            app = create_app(runtime, composition=composition)
            import uvicorn
            config = uvicorn.Config(RefusalLog(app), host=m["host"], port=m["port"], reload=False, workers=1, access_log=True, log_level="warning")
            runner.run(uvicorn.Server(config).serve())
        return 0
    except RuntimeIdentityError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print("RUNTIME_BOOTSTRAP_FAILED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
