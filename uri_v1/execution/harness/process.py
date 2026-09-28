"""Harness process supervision: process group, total timeout, output-inactivity
watchdog, verified settlement and a hashed run log (Paperclip §16 items 9–11)."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import threading
import time

from uri_v1.execution.verify import kill_group

# Nesting guards and URI-private variables are never forwarded to a harness.
NEVER_FORWARD = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED",
                 "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "URI_PROVIDER_KEY_SECRET")


def harness_env(extra: dict | None = None) -> dict:
    """The user's environment minus nesting guards and URI secrets.

    The harness authenticates itself (subscription login or its own API key,
    ruling OD-2); URI forwards the environment it runs in and never reads or
    stores harness credentials.
    """
    env = {k: v for k, v in os.environ.items() if k not in NEVER_FORWARD}
    env.update(extra or {})
    return env


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    timed_out: bool
    inactivity_killed: bool
    cancelled: bool
    settled: bool
    duration_ms: float
    log_path: str
    log_sha256: str
    log_bytes: int
    stderr_tail: str


def supervise(argv, *, cwd: Path, env: dict, stdin_bytes: bytes | None, timeout_s: float, inactivity_s: float,
              log_path: Path, cancel: threading.Event | None = None) -> ProcessResult:
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    started = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, **kwargs)
    last = [time.monotonic()]
    digest = hashlib.sha256(); size = [0]; err = bytearray()
    log = open(log_path, "wb")

    def pump_out():
        for line in iter(proc.stdout.readline, b""):
            last[0] = time.monotonic(); digest.update(line); size[0] += len(line); log.write(line)

    def pump_err():
        for chunk in iter(lambda: proc.stderr.read(4096), b""):
            last[0] = time.monotonic(); err.extend(chunk); del err[:-4096]

    threads = [threading.Thread(target=pump_out, daemon=True), threading.Thread(target=pump_err, daemon=True)]
    for t in threads: t.start()
    try:
        if stdin_bytes: proc.stdin.write(stdin_bytes)
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    timed_out = inactive = cancelled = False
    while proc.poll() is None:
        now = time.monotonic()
        if now - started > timeout_s: timed_out = True
        elif now - last[0] > inactivity_s: inactive = True
        elif cancel is not None and cancel.is_set(): cancelled = True
        else:
            time.sleep(0.05); continue
        kill_group(proc)
        break
    proc.wait()
    for t in threads: t.join(timeout=5)
    log.close()
    settled = proc.returncode is not None and not any(t.is_alive() for t in threads)
    return ProcessResult(proc.returncode, timed_out, inactive, cancelled, settled, round((time.monotonic() - started) * 1000, 1),
                         str(log_path), digest.hexdigest(), size[0], bytes(err).decode("utf-8", "replace"))
