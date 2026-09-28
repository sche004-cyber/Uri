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

# Generic process environment a harness needs to run at all. Nothing named here
# can carry a secret. Anything else, including URI's own provider keys and the
# user's unrelated tokens, is never forwarded (OD-2): the harness authenticates
# itself, and only the auth variables an adapter names for its own harness are
# added on top of this base.
BASE_ENV_ALLOW = frozenset({"PATH", "HOME", "USERPROFILE", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "TEMP",
                            "TMP", "TZ", "USER", "USERNAME", "SHELL", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR"})

# Test-only control channels for the fake/probe harness fixtures (never present
# outside a test run, never a secret name). A real harness never reads these.
_TEST_FIXTURE_PREFIXES = ("URI_FAKE_", "URI_PROBE_")


def harness_env(auth_vars: tuple = ()) -> dict:
    """A minimal, allowlisted environment: generic runtime variables plus the
    named auth variables the harness needs for its own authentication.

    `auth_vars` must name only the harness's own credentials; passing URI's
    provider keys or the user's unrelated secrets here would defeat OD-2.
    """
    allow = BASE_ENV_ALLOW | set(auth_vars)
    return {k: v for k, v in os.environ.items() if k in allow or k.startswith(_TEST_FIXTURE_PREFIXES)}


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

    def pump_in():
        try:
            if stdin_bytes: proc.stdin.write(stdin_bytes)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    threads = [threading.Thread(target=pump_out, daemon=True), threading.Thread(target=pump_err, daemon=True),
              threading.Thread(target=pump_in, daemon=True)]
    for t in threads: t.start()
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
    kill_group(proc)  # always sweep the process group, even after a clean exit (H-2): a same-group
                       # background child with stdio closed would otherwise outlive the run undetected.
                       # A child that escaped into its own session (setsid) is not reachable this way;
                       # containing that needs OS support (a Linux subreaper/cgroup or a Windows job
                       # object) that is out of scope for this minimum and stays disclosed.
    for t in threads: t.join(timeout=5)
    log.close()
    settled = proc.returncode is not None and not any(t.is_alive() for t in threads)
    return ProcessResult(proc.returncode, timed_out, inactive, cancelled, settled, round((time.monotonic() - started) * 1000, 1),
                         str(log_path), digest.hexdigest(), size[0], bytes(err).decode("utf-8", "replace"))
