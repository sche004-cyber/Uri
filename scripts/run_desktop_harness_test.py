"""Opt-in URI Core composition root. No frozen Core/M38 code modified."""
import argparse
import os
import secrets
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--enable-subscription-test', action='store_true', required=True)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--state-dir', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'scratch' / 'desktop_harness_test_state')
    args = parser.parse_args()
    # All Core relative stores belong to this explicit test installation.
    # Never copy, reset or open the installed application's account database.
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)
    os.chdir(state)
    # Test process only: normal per-user connection initialization requires it.
    # No external credentials are configured in this qualification environment.
    os.environ.setdefault('URI_EXTERNAL_CREDENTIAL_SECRET', secrets.token_urlsafe(48))
    import uvicorn
    from uri_core.app.server import app, _resolve_authenticated_principal
    from uri_v1.desktop_harness.routes import router_for
    from uri_v1.desktop_harness.service import DesktopHarnessService
    # Keep verified work/checkpoints after interruption/restart. Separate from
    # installed production accounts and originals; never replay pending work.
    service = DesktopHarnessService(state / 'harness')
    app.include_router(router_for(service, _resolve_authenticated_principal))
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
