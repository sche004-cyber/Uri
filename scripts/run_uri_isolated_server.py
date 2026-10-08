"""C1 bootstrap: contain legacy initialization before importing Core."""
import sys

# C1 isolated-mode gate FIRST: without -I the script directory is sys.path[0] and any module imported
# below (argparse, asyncio, secrets, pathlib, ...) could be shadowed by a file planted there.
if not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
import argparse
import asyncio
import os
from pathlib import Path
import secrets

# C1 import gate, loaded by exact path BEFORE anything from the source root: the root never goes on
# sys.path, and pinned packages compile only from plain source files (see scripts/c1_bootstrap.py).
_C1_BOOT = Path(__file__).resolve().parents[1] / "scripts" / "c1_bootstrap.py"
c1_bootstrap = type(sys)("c1_bootstrap")
c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_C1_BOOT), _C1_BOOT.read_bytes()
exec(compile(c1_bootstrap.SOURCE, str(_C1_BOOT), "exec"), c1_bootstrap.__dict__)
sys.modules["c1_bootstrap"] = c1_bootstrap
c1_bootstrap.install(_C1_BOOT.parents[1])
from uri_core.core.runtime_identity import RuntimeManifest,RuntimeIdentity,RuntimeIdentityError,FixtureGuard,absolute,child_environment,install_source_pin
from scripts.uri_server_launcher import NamedMutex


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--manifest",required=True)
    args=parser.parse_args()
    try:
        manifest=RuntimeManifest(args.manifest)
        m=manifest.data;state=absolute(m["state_root"])
        # Every later import from the pinned packages must execute exactly the validated bytes.
        install_source_pin(absolute(m["source_root"]),m["source_files"])
        if Path.cwd().resolve()!=state:raise RuntimeIdentityError("STATE_CWD_MISMATCH")
        # Direct invocation gets the same sanitized environment as the launcher.
        safe=child_environment(state,absolute(m["interpreter"]))
        os.environ.clear();os.environ.update(safe)
        os.environ["URI_PROVIDER_KEY_SECRET"]=secrets.token_hex(32)
        os.environ["URI_EXTERNAL_CREDENTIAL_SECRET"]=secrets.token_hex(32)
        runtime=RuntimeIdentity(manifest)
        guard=FixtureGuard(manifest);runtime.guard=guard
        with NamedMutex("Local\\URI_Instance_"+m["server_id"],0), asyncio.Runner() as runner:
            # Windows asyncio creates an internal loopback socket pair. Create
            # that event-loop plumbing before blocking Core startup connections.
            runner.get_loop()
            sys.addaudithook(guard)
            if m["composition_id"] == "c2-paired-core":
                from uri_core.app.paired_server import create_app, default_composition
                app = create_app(runtime, composition=default_composition())
            else:
                from uri_core.app import server
                app = server.app
                app.state.runtime_identity=runtime
            import uvicorn
            config=uvicorn.Config(app,host=m["host"],port=m["port"],reload=False,workers=1,
                                  access_log=False,log_level="warning")
            runner.run(uvicorn.Server(config).serve())
        return 0
    except RuntimeIdentityError as exc:
        print(str(exc),file=sys.stderr);return 1
    except Exception:
        print("RUNTIME_BOOTSTRAP_FAILED",file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
