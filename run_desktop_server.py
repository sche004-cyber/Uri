"""Authoritative server runner for URI Desktop on Windows.

Starts the real URI backend (uri_core.app.server:app) with:
- Pre-startup validation: Ollama health, model availability, port conflicts.
- Loopback-only binding (127.0.0.1) per M22.3 security invariants.
- PID file written AFTER uvicorn successfully binds (not before).
- Desktop status endpoint registered (GET /desktop/status).
- No middleware interception of POST /ask — requests flow through the
  canonical URI Core handler.

The canonical POST /ask handler reads model configuration from
uri_workspace/model_roles.json via uri_core.config.model_roles.load_model_roles().
"""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

_LEGACY_PROVIDER_KEY_SECRET = "uri_local_dev_secret_key_v1"  # scripts/run_uri_server.py's default
import hashlib as _hashlib

# One secrets file per checkout, outside the repository, so the legacy
# provider-key decision below is made for this checkout's own data.
SECRETS_FILE = (
    Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "URI"
    / f"desktop_secrets_{_hashlib.sha256(str(REPO_ROOT).lower().encode('utf-8')).hexdigest()[:12]}.json"
)


def _load_or_create_desktop_secrets() -> dict:
    """Per-install encryption secrets, kept outside the repository.

    Created once with random values. The provider-key secret keeps the
    legacy literal only when this checkout already holds provider keys
    encrypted with it (re-keying would make them unreadable); that is a
    disclosed, pre-existing limitation. Environment variables still win.
    """
    import json
    import secrets

    if SECRETS_FILE.exists():
        # Never silently regenerate: new keys would make every credential
        # already encrypted with the old ones unreadable. Fail loudly instead.
        try:
            data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"ERROR: {SECRETS_FILE} is unreadable ({type(exc).__name__}). "
                             "Restore it from backup or remove it deliberately (stored keys will be lost).")
        if not (isinstance(data, dict) and isinstance(data.get("provider_key_secret"), str)
                and isinstance(data.get("external_credential_secret"), str)):
            raise SystemExit(f"ERROR: {SECRETS_FILE} is malformed. "
                             "Restore it from backup or remove it deliberately (stored keys will be lost).")
        return data
    users = REPO_ROOT / "uri_workspace" / "users"
    legacy_provider_keys = users.is_dir() and any(users.glob("*/provider_keys.enc"))
    data = {
        "provider_key_secret": _LEGACY_PROVIDER_KEY_SECRET if legacy_provider_keys else secrets.token_urlsafe(32),
        "provider_key_secret_is_legacy": bool(legacy_provider_keys),
        "external_credential_secret": secrets.token_urlsafe(32),
    }
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SECRETS_FILE.with_name(f"{SECRETS_FILE.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    try:
        # O_EXCL-style: if another launch created the file first, keep theirs.
        os.link(tmp, SECRETS_FILE)
    except FileExistsError:
        pass
    finally:
        tmp.unlink(missing_ok=True)
    return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))


if not (os.environ.get("URI_PROVIDER_KEY_SECRET") and os.environ.get("URI_EXTERNAL_CREDENTIAL_SECRET")):
    _secrets = _load_or_create_desktop_secrets()
    os.environ.setdefault("URI_PROVIDER_KEY_SECRET", _secrets["provider_key_secret"])
    os.environ.setdefault("URI_EXTERNAL_CREDENTIAL_SECRET", _secrets["external_credential_secret"])
    del _secrets
# Desktop default: the EXPERIMENTAL harness-first social seam is on, so purely
# social turns ("hi", "thanks") are answered by the local Edge chat model
# instead of two Main Brain calls. Set URI_HARNESS_FIRST=0 to turn it off.
os.environ.setdefault("URI_HARNESS_FIRST", "1")
# Desktop default: cap the Ollama context window URI requests. Without it URI
# asks for the model's maximum (qwen3.5:9b: 262,144 tokens), which made the
# model take 14.2 GB of a 16 GB GPU and evict every other model. URI's largest
# observed prompt is ~10k tokens; prompts that would not fit are trimmed or
# refused by the existing budget checks, never silently cut by Ollama.
os.environ.setdefault("OLLAMA_NUM_CTX", "16384")

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
    """Write PID file. Called AFTER uvicorn binds successfully."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(_cleanup_pid)


def _check_port_conflict(host: str, port: int) -> bool:
    """Return True if the port is already in use. Aborts startup if so."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        result = sock.connect_ex((host, port))
        return result == 0  # True = conflict
    except Exception:
        return False
    finally:
        sock.close()


def _this_process_listens_on(port: int) -> bool:
    """True only when *this* process owns a listening socket on `port`
    (not merely when something answers on it)."""
    import psutil

    try:
        conns = psutil.Process(os.getpid()).net_connections(kind="inet")
    except Exception:
        return False
    return any(c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port for c in conns)


def _wait_for_bind_then_record_pid(host: str, port: int, timeout: float = 30.0) -> None:
    """Background thread: write the PID file only once this process itself
    owns the listening socket, so a listener that won a race for the port
    can never be recorded as ours."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        time.sleep(0.5)
        if _this_process_listens_on(port):
            _record_pid()
            print(f"PID {os.getpid()} recorded after successful bind to {host}:{port}", flush=True)
            return
    print(f"WARNING: PID file NOT written - this process did not bind {host}:{port} within {timeout}s", file=sys.stderr, flush=True)


def _warm_edge_chat_model() -> None:
    """Background thread: load the harness-first Edge chat model once at
    startup so the first social turn is not lost to a cold load (live
    2026-10-01: a cold qwen3:0.6b load exceeded the seam's 4 s budget and the
    first "Hi" fell back to the fixed line). Loopback Ollama only; any failure
    is logged and ignored - the seam still falls back safely."""
    try:
        try:
            from uri_desktop_seams.harness_first import edge_chat, seam
        except ImportError:
            return  # seam not present on this line: nothing to warm

        if not seam.enabled() or not seam._loopback(edge_chat.OLLAMA_URL):
            return
        import json
        import urllib.request

        started = time.monotonic()
        # Same endpoint and runner options as edge_chat.generate: a different
        # num_ctx makes Ollama reload the model on the first real turn.
        body = json.dumps({"model": edge_chat.DEFAULT_MODEL, "keep_alive": "30m", "stream": False,
                           "think": False, "messages": [{"role": "user", "content": "hi"}],
                           "options": {"num_predict": 1, "num_ctx": 1024}}).encode("utf-8")
        req = urllib.request.Request(f"{edge_chat.OLLAMA_URL}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
        print(f"Edge chat model {edge_chat.DEFAULT_MODEL} warmed in {time.monotonic() - started:.1f}s", flush=True)
    except Exception as exc:
        print(f"WARNING: Edge chat model warm-up failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run URI Desktop Server.")
    parser.add_argument("--host", default=os.environ.get("URI_SERVER_HOST", DEFAULT_HOST),
                        help=f"Bind address (default: {DEFAULT_HOST}).")
    parser.add_argument("--port", type=int, default=int(os.environ.get("URI_SERVER_PORT", str(DEFAULT_PORT))),
                        help=f"Bind port (default: {DEFAULT_PORT}).")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    if not is_loopback_host(args.host):
        print(f"ERROR: Non-loopback host {args.host!r} refused for desktop launcher.", file=sys.stderr)
        sys.exit(1)

    # Pre-startup port conflict check — abort if port is occupied
    if _check_port_conflict(args.host, args.port):
        # Check if it's a healthy URI instance
        import urllib.request
        import json
        try:
            with urllib.request.urlopen(f"http://{args.host}:{args.port}/health", timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ok":
                    print(f"URI backend already healthy at {args.host}:{args.port}. Exiting (no duplicate).", flush=True)
                    sys.exit(0)
        except Exception:
            pass
        print(f"ERROR: Port {args.port} is already in use by a non-URI process. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Pre-startup validation
    import uri_desktop_adapter
    report = uri_desktop_adapter.validate_desktop_readiness(host=args.host, port=args.port)

    print("=" * 60)
    print("URI Desktop Server — Pre-Startup Validation")
    print(f"  Ollama:  {'HEALTHY' if report['ollama']['healthy'] else 'UNREACHABLE'}")
    if report["model_roles"]["missing_from_ollama"]:
        print(f"  WARNING: Models missing from Ollama: {report['model_roles']['missing_from_ollama']}")
    else:
        print(f"  Models:  {report['model_roles']['configured_models']}")
    print(f"  Config:  {report['model_roles']['config_file']} (exists={report['model_roles']['config_file_exists']})")

    if not report["ollama"]["healthy"]:
        print("WARNING: Ollama is not reachable. Model calls will fail at runtime.", file=sys.stderr, flush=True)
        # Do NOT abort — the canonical handler will return honest errors.

    # Import the app — this triggers all uri_core initialization
    from uri_core.app.server import app

    # Mount the desktop status endpoint (no /ask interception)
    uri_desktop_adapter.mount_desktop_status_endpoint(app)
    # Timing only (pass-through): see RequestTimingMiddleware's docstring.
    app.add_middleware(uri_desktop_adapter.RequestTimingMiddleware)

    print("=" * 60)
    print("URI Desktop Server")
    print(f"  Bind:    http://{args.host}:{args.port}")
    print(f"  PID:     {os.getpid()} (will be recorded after bind)")
    print(f"  Health:  GET /health")
    print(f"  Ask:     POST /ask (canonical URI Core pipeline)")
    print(f"  Status:  GET /desktop/status (capability inventory)")
    print("=" * 60, flush=True)

    # Start PID recording thread — writes PID only after successful bind
    pid_thread = threading.Thread(
        target=_wait_for_bind_then_record_pid,
        args=(args.host, args.port),
        daemon=True,
    )
    pid_thread.start()
    threading.Thread(target=_warm_edge_chat_model, daemon=True).start()

    import uvicorn
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
