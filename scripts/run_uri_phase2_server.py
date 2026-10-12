"""Phase 2D opt-in paired server: the frozen C1/C2 server bootstrap with the explicit Phase 2 reasoning policy.

COMPOSITION PROFILE, not a cutover: the frozen `scripts/run_uri_isolated_server.py` remains the entrypoint named by
every server manifest and started by the frozen launcher. This script accepts the same manifest and applies the
same gates; it differs only in the composition passed to `create_app`:
`uri_supervisor_bridge.composition.phase2_server_composition(<state_root>/control/phase2_reasoning_policy.json)`.
An absent policy file yields exactly the frozen default (deterministic row only). A malformed file refuses startup.
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

PHASE2_PACKAGES = ("uri_supervisor", "uri_supervisor_bridge")


class Phase2SourceFinder:
    def __init__(self, root):
        self.root = os.path.abspath(root)

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
        return importlib.util.spec_from_file_location(fullname, origin, loader=c1_bootstrap.SourceOnlyLoader(fullname, origin),
                                                      submodule_search_locations=[base] if is_package else None)


sys.meta_path.insert(1, Phase2SourceFinder(_C1_BOOT.parents[1]))

from uri_core.core.runtime_identity import RuntimeManifest, RuntimeIdentity, RuntimeIdentityError, FixtureGuard, absolute, child_environment, install_source_pin  # noqa: E402
from scripts.uri_server_launcher import NamedMutex  # noqa: E402
from uri_supervisor_bridge.composition import PolicyError, phase2_server_composition, policy_path  # noqa: E402
from uri_supervisor_bridge.refusal_log import RefusalLog  # noqa: E402


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
        safe = child_environment(state, absolute(m["interpreter"]))
        os.environ.clear()
        os.environ.update(safe)
        os.environ["URI_PROVIDER_KEY_SECRET"] = secrets.token_hex(32)
        os.environ["URI_EXTERNAL_CREDENTIAL_SECRET"] = secrets.token_hex(32)
        if m["composition_id"] != "c2-paired-core":
            raise RuntimeIdentityError("PHASE2_PAIRED_COMPOSITION_REQUIRED")
        try:
            composition = phase2_server_composition(policy_path(state))
        except PolicyError as exc:
            raise RuntimeIdentityError(str(exc)) from None
        runtime = RuntimeIdentity(manifest)
        guard = FixtureGuard(manifest)
        runtime.guard = guard
        for pkg in PHASE2_PACKAGES:
            guard.read_roots.append((absolute(m["source_root"]) / pkg).resolve())
        with NamedMutex("Local\\URI_Instance_" + m["server_id"], 0), asyncio.Runner() as runner:
            runner.get_loop()
            sys.addaudithook(guard)
            from uri_core.app.paired_server import create_app
            app = create_app(runtime, composition=composition)
            import uvicorn
            # UI/operations slice (review rounds 3-5, VAL-1/LOG-1): the PROFILE (not the frozen app) logs refusals on
            # /client/v1 as `CLIENT_REFUSAL <METHOD> <route shape> <status> <CODE>` only; see uri_supervisor_bridge/refusal_log.py.
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
