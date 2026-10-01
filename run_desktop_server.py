"""Starts the real URI backend with Canonical Desktop Intelligence (M36-M39) mounted.

Authoritative server runner for the Windows Desktop application.
- Loopback-only binding (127.0.0.1) by default per M22.3 security invariants.
- Manages process PID in uri_workspace/uri_server.pid for coordinated shutdown.
- Mounts uri_desktop_adapter onto uri_core.app.server:app.
"""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import socket
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("URI_PROVIDER_KEY_SECRET", "uri_local_dev_secret_key_v1")
os.environ.setdefault("URI_EXTERNAL_CREDENTIAL_SECRET", "uri_local_dev_credential_secret_v1")

LOG_FILE = REPO_ROOT / "uri_workspace" / "logs" / "uri_server.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
try:
    log_handle = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None or not hasattr(sys.stdout, "write"):
        sys.stdout = log_handle
    if sys.stderr is None or not hasattr(sys.stderr, "write"):
        sys.stderr = log_handle
except Exception:
    pass

import uvicorn
from uri_core.app.server import app
import uri_desktop_adapter

# Mount the canonical desktop intelligence adapter
uri_desktop_adapter.mount_desktop_adapter(app)

PID_FILE = REPO_ROOT / "uri_workspace" / "uri_server.pid"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


def _cleanup_pid() -> None:
    try:
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _record_pid() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(_cleanup_pid)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run URI Desktop Server with Canonical Intelligence.")
    parser.add_argument("--host", default=os.environ.get("URI_SERVER_HOST", DEFAULT_HOST), help=f"Bind address (default: {DEFAULT_HOST}).")
    parser.add_argument("--port", type=int, default=int(os.environ.get("URI_SERVER_PORT", str(DEFAULT_PORT))), help=f"Bind port (default: {DEFAULT_PORT}).")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    if not is_loopback_host(args.host):
        print(f"ERROR: Non-loopback host {args.host!r} is refused for desktop launcher.", file=sys.stderr)
        sys.exit(1)

    _record_pid()

    print("=" * 60)
    print("URI Canonical Desktop Server (M36-M39 Integrated)")
    print(f"Local:  http://127.0.0.1:{args.port}")
    print(f"PID:    {os.getpid()} (recorded in {PID_FILE})")
    print("Health: GET /health")
    print("Ask:    POST /ask (Canonical v1 Pipeline Active)")
    print("=" * 60, flush=True)

    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
        )
    finally:
        _cleanup_pid()


if __name__ == "__main__":
    main()
