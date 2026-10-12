"""C4 client-side external harness runtime, provider-neutral.

Everything that is the same for every external harness lives here: the bounded task capsule,
environment allow-listing, the bypass-flag refusal applied to EVERY argv, Windows Job Object
supervision (client_runtime.process_tree), claim normalisation, and the registry that decides
usability (install + authentication evidence + explicit qualification; no fallback).

Provider-specific knowledge (command lines, output formats, native-login hints, refused
products) lives only in the adapter boundary package `uri_harness_adapters`, which Core never
imports; the client worker composes it. This keeps the M31 invariant intact: Core/Brain code
does not name or shell out to development agents. Harness output is a CLAIM; URI verifies.

Donor: minimal port of M38 argv/env/parse logic (Uri/_V1 @ 379769f, uri_v1/execution/harness/
adapters.py sha256 325bd63c960067da2177444a6c5c4a4fa5f66f6e788df6bbada03c775a30c46b, process.py
sha256 b41351b6d421726908c9adca77c1295b14d21cde46ec6d638f8044ffb884bdf9), split during C4 cleanup.
Nothing here logs in, installs, updates or reads another installation's credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

from uri_core.client_runtime import process_tree

FORBIDDEN_FLAGS = frozenset({"--dangerously-skip-permissions", "--allow-dangerously-skip-permissions", "bypassPermissions",
                             "--dangerously-bypass-approvals-and-sandbox", "--yolo", "danger-full-access"})
BASE_ENV_ALLOW = frozenset({"PATH", "HOME", "USERPROFILE", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "TEMP",
                            "TMP", "TZ", "USER", "USERNAME", "SHELL", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR"})
NEVER_FORWARD = frozenset({"ANTHROPIC_API_KEY", "OPENAI_API_KEY"})
FIXTURE_ENV_PREFIX = "URI_FAKE_"
UNAVAILABLE = "UNAVAILABLE"


class HarnessError(ValueError):
    """Typed failure: the reason code is the message."""


def harness_env(auth_vars=(), environ=None):
    environ = os.environ if environ is None else environ
    allow = (BASE_ENV_ALLOW | set(auth_vars)) - NEVER_FORWARD
    return {k: v for k, v in environ.items() if k in allow or k.startswith(FIXTURE_ENV_PREFIX)}


def check_argv(argv):
    """Applied to every adapter's argv by build_invocation: no permission/sandbox bypass, ever."""
    if FORBIDDEN_FLAGS.intersection(argv):
        raise HarnessError("BYPASS_FLAG_REFUSED")
    return argv


_check = check_argv


def resolve_command(executable):
    if isinstance(executable, (list, tuple)):
        first = shutil.which(executable[0]) if executable else None
        return [first, *executable[1:]] if first else None
    exe = shutil.which(executable) if executable else None
    return [exe] if exe else None


def probe_version(executable, timeout_s=20):
    """Installed version via `--version` only; never logs in, updates or prompts."""
    cmd = resolve_command(executable)
    if not cmd:
        return {"installed": False, "version": None, "executable": None}
    try:
        out = subprocess.run([*cmd, "--version"], capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL,
                             env=harness_env())
        m = re.search(r"\d+\.\d+\.\d+", out.stdout.decode("utf-8", "replace"))
        return {"installed": True, "version": m.group(0) if m else None, "executable": cmd[0]}
    except (OSError, subprocess.TimeoutExpired):
        return {"installed": True, "version": None, "executable": cmd[0]}


@dataclass(frozen=True)
class Capsule:
    """Bounded task package: workspace copy, instruction bytes, limits. No capability grants."""
    run_id: str
    workspace: str
    instructions: bytes
    network: bool = False
    timeout_s: float = 900
    inactivity_s: float = 300
    max_budget_usd: float | None = 2.0

    def __post_init__(self):
        if not 1 <= self.timeout_s <= 7200 or not 1 <= self.inactivity_s <= self.timeout_s:
            raise HarnessError("INVALID_LIMITS")
        if self.max_budget_usd is not None and not 0 < self.max_budget_usd <= 100:
            raise HarnessError("INVALID_LIMITS")
        if not Path(self.workspace).is_absolute():
            raise HarnessError("WORKSPACE_NOT_ABSOLUTE")

    @property
    def instructions_sha256(self):
        return hashlib.sha256(self.instructions).hexdigest()


# --- supervised run ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    timed_out: bool
    inactivity_killed: bool
    cancelled: bool
    contained: bool
    duration_ms: float
    log_path: str
    log_sha256: str
    log_bytes: int
    stderr_tail: str


def supervise(argv, *, cwd, env, stdin_bytes, timeout_s, inactivity_s, log_path, cancel=None):
    started = time.monotonic()
    proc = process_tree.spawn(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    last = [time.monotonic()]
    digest, size, err = hashlib.sha256(), [0], bytearray()
    log = open(log_path, "wb")

    def pump_out():
        for line in iter(proc.stdout.readline, b""):
            last[0] = time.monotonic(); digest.update(line); size[0] += len(line); log.write(line)

    def pump_err():
        for chunk in iter(lambda: proc.stderr.read(4096), b""):
            last[0] = time.monotonic(); err.extend(chunk); del err[:-4096]

    def pump_in():
        try:
            if stdin_bytes:
                proc.stdin.write(stdin_bytes)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    threads = [threading.Thread(target=f, daemon=True) for f in (pump_out, pump_err, pump_in)]
    for t in threads:
        t.start()
    timed_out = inactive = cancelled = False
    contained = True
    try:
        while proc.poll() is None:
            now = time.monotonic()
            if now - started > timeout_s: timed_out = True
            elif now - last[0] > inactivity_s: inactive = True
            elif cancel is not None and cancel.is_set(): cancelled = True
            else:
                time.sleep(0.05); continue
            contained = process_tree.kill_tree(proc)
            break
        proc.wait()
        contained = process_tree.kill_tree(proc) and contained  # always sweep descendants
    finally:
        process_tree.release(proc)
        for t in threads:
            t.join(timeout=5)
        log.close()
    return ProcessResult(proc.returncode, timed_out, inactive, cancelled, contained and not any(t.is_alive() for t in threads),
                         round((time.monotonic() - started) * 1000, 1), str(log_path), digest.hexdigest(), size[0],
                         bytes(err).decode("utf-8", "replace"))


# --- claim normalisation (claims only) ---------------------------------------------------------------

def _num(d, key):
    v = d.get(key) if isinstance(d, dict) else None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else UNAVAILABLE


QUOTA_MARKERS = ("rate_limit", "rate limit", "quota", "usage limit", "insufficient_quota", "limit reached")


def _events(proc):
    for line in Path(proc.log_path).read_bytes().splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            yield ev


def claim(proc, ok, result, tool_calls, family, *, text, usage, cost):
    """Normalise an adapter parse into the common claim shape (never success evidence)."""
    blob = (family + " " + json.dumps(result or {}, default=str) + " " + proc.stderr_tail).lower()
    killed = proc.timed_out or proc.inactivity_killed or proc.cancelled
    if killed or result is None:
        outcome = "outcome_unknown"
        family = "TIMEOUT" if proc.timed_out else "INACTIVITY" if proc.inactivity_killed else "CANCELLED" if proc.cancelled else "NO_RESULT"
        if not killed and any(m in blob for m in QUOTA_MARKERS):
            outcome, family = "quota_exhausted", "QUOTA"
    elif not ok:
        outcome, family = ("quota_exhausted", "QUOTA") if any(m in blob for m in QUOTA_MARKERS) else ("failed", family or "error")
    else:
        outcome, family = "completed_claimed", None
    return {"claimed_outcome": outcome, "exit_code": proc.exit_code, "error_family": family,
            "final_message_sha256": hashlib.sha256(text.encode()).hexdigest() if isinstance(text, str) and text else None,
            "usage": {"input_tokens": _num(usage or {}, "input_tokens"), "output_tokens": _num(usage or {}, "output_tokens"),
                      "cost_usd": cost, "tool_calls": tool_calls, "duration_ms": proc.duration_ms},
            "log_sha256": proc.log_sha256, "log_bytes": proc.log_bytes, "contained": proc.contained}


# --- registry -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class HarnessAdapter:
    """One provider's boundary: argv/env/stdin builder, output parser, native-login hint.

    `refused` set means the product is never executable (for example not separately qualified)."""
    harness_id: str
    executable: object
    build: object = None          # (resolved_cmd, capsule, model) -> (argv, auth_vars, stdin_bytes)
    parse: object = None          # (ProcessResult) -> claim dict built with claim()
    auth_action: str | None = None
    refused: str | None = None


def build_invocation(adapter, executable, capsule, model=None):
    """Resolve, build and bypass-check one adapter invocation -> (argv, env, stdin_bytes)."""
    if adapter.refused or adapter.build is None:
        raise HarnessError("HARNESS_REFUSED")
    cmd = resolve_command(executable)
    if not cmd:
        raise HarnessError("HARNESS_UNAVAILABLE")
    argv, auth_vars, stdin_bytes = adapter.build(cmd, capsule, model)
    return check_argv(argv), harness_env(auth_vars), stdin_bytes


class HarnessRegistry:
    """Discovery plus honest state. Native CLIs are never 'qualified' by this module.

    qualification: NATIVE_UNQUALIFIED (default), FIXTURE_ONLY (explicit test fixture), REFUSED
    (adapter.refused). Only an explicit `qualify()` call by trusted composition, after native-login
    and containment evidence exists, may change it. No adapters = no harness (Core default).
    """

    def __init__(self, adapters=(), executables=None, auth_probe=None):
        self.adapters = {a.harness_id: a for a in adapters}
        self.executables = {hid: a.executable for hid, a in self.adapters.items()}
        self.executables.update({k: v for k, v in (executables or {}).items() if k in self.adapters})
        self.qualified = {}
        self.auth_probe = auth_probe or (lambda harness: None)  # trusted native-status evidence; None = unknown

    def qualify(self, harness_id, level, evidence_sha256):
        if level not in {"FIXTURE_ONLY", "NATIVE_QUALIFIED"} or not re.fullmatch(r"[0-9a-f]{64}", evidence_sha256 or ""):
            raise HarnessError("QUALIFICATION_EVIDENCE_REQUIRED")
        if harness_id not in self.adapters or self.adapters[harness_id].refused:
            raise HarnessError("HARNESS_REFUSED")
        self.qualified[harness_id] = {"level": level, "evidence_sha256": evidence_sha256}

    def discover(self):
        rows = []
        for harness_id, adapter in self.adapters.items():
            probe = probe_version(self.executables[harness_id])
            if adapter.refused:
                state, qual, action = "EXECUTE_REFUSED", "REFUSED", adapter.refused
            else:
                auth = self.auth_probe(harness_id)
                state = ("NOT_INSTALLED" if not probe["installed"] else
                         "AUTHENTICATED" if auth is True else "NOT_AUTHENTICATED" if auth is False else "AUTH_UNVERIFIED")
                qual = (self.qualified.get(harness_id) or {}).get("level", "NATIVE_UNQUALIFIED")
                action = None if state == "AUTHENTICATED" else adapter.auth_action
            usable = (probe["installed"] and state == "AUTHENTICATED" and qual in {"NATIVE_QUALIFIED", "FIXTURE_ONLY"}
                      and not adapter.refused)
            rows.append({"harness_id": harness_id, "installed": probe["installed"], "version": probe["version"],
                         "auth_state": state, "qualification": qual, "usable": bool(usable), "required_user_action": action})
        return rows

    def selectable(self, harness_id):
        row = next((r for r in self.discover() if r["harness_id"] == harness_id), None)
        if row is None or not row["usable"]:
            raise HarnessError("HARNESS_NOT_USABLE")
        return row

    def invoke(self, harness_id, capsule, model=None):
        self.selectable(harness_id)
        return build_invocation(self.adapters[harness_id], self.executables[harness_id], capsule, model)

    def parse(self, harness_id, proc):
        return self.adapters[harness_id].parse(proc)
