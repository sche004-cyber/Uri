"""Separate-process workers for the uri-development-lifecycle driver.

Every reviewer and implementer runs as its own OS process with its own session identity. Nothing here shares
context with the coordinator: the prompt is the only input, stdout is the only output.

Providers:
- ``claude_cli``: ``claude -p`` (Claude Code headless), fresh ``--session-id``, tools restricted per role.
- ``codex_cli``: ``codex exec`` when installed (optional; never required).
- ``command``: an arbitrary executable reading the prompt on stdin. Used by the tool's own tests. A ``command``
  reviewer is never an independent review of a real milestone (see ``lifecycle.is_independent``).

Boundary Guarantee: Development tooling only. Not part of the URI runtime.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import uuid
from pathlib import Path

INDEPENDENT_PROVIDERS = ("claude_cli", "codex_cli")
# A worker that failed for one of these reasons is resumable later; the attempt is not counted against the repair.
QUOTA_RE = re.compile(r"rate.?limit|usage limit|quota|overloaded|too many requests|\b429\b|\b529\b|credit balance")

# Tool policy per role. Prefix rules are a convenience, not the boundary: the driver re-checks the checkout and
# every ref after the run and discards the result if anything changed.
GIT_WRITE_DENY = ["Bash(git commit*)", "Bash(git push*)", "Bash(git reset*)", "Bash(git checkout*)",
                  "Bash(git switch*)", "Bash(git branch*)", "Bash(git tag*)", "Bash(git update-ref*)",
                  "Bash(git worktree*)", "Bash(git rebase*)", "Bash(git merge*)", "Bash(git stash*)",
                  "Bash(git config*)", "Bash(git clean*)", "Bash(git restore*)", "Bash(git am*)",
                  "Bash(git cherry-pick*)", "Bash(git revert*)", "Bash(git rm*)", "Bash(git mv*)",
                  "Bash(git replace*)"]
ROLE_TOOLS = {
    "reviewer": {"allowed": ["Read", "Grep", "Glob", "Bash", "Agent"],
                 "disallowed": ["Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]},
    "implementer": {"allowed": ["Read", "Grep", "Glob", "Bash", "Edit", "Write", "Agent"],
                    "disallowed": ["NotebookEdit", "WebFetch", "WebSearch"]},
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _killpg(pid) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def provider_available(spec: dict) -> tuple[bool, str]:
    p = spec.get("provider")
    if p in ("claude_cli", "codex_cli"):
        name = "claude" if p == "claude_cli" else "codex"
        b = spec.get("binary") or shutil.which(name)
        ok = bool(b) and (Path(b).is_file() or bool(shutil.which(b)))
        return ok, (b if ok else f"{name} CLI not found ({b or 'not on PATH'})")
    if p == "command":
        argv = spec.get("argv") or []
        return (bool(argv) and bool(shutil.which(argv[0]) or Path(argv[0]).is_file()), " ".join(argv[:1]))
    return False, f"unknown provider {p!r}"


_HASH_CACHE: dict = {}


def _file_sha256(path: str) -> str | None:
    try:
        st = os.stat(path)
        key = (path, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if key not in _HASH_CACHE:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            _HASH_CACHE[key] = h.hexdigest()
        return _HASH_CACHE[key]
    except OSError:
        return None


def _interpreter(real: str) -> dict | None:
    """A script CLI (``#!/usr/bin/env node``) runs whatever interpreter PATH resolves: it is part of the identity."""
    try:
        with open(real, "rb") as fh:
            head = fh.readline(512)
    except OSError:
        return None
    if not head.startswith(b"#!"):
        return None
    parts = head[2:].decode("utf-8", "replace").split()
    if not parts:
        return None
    exe = parts[0]
    if os.path.basename(exe) == "env":
        names = [a for a in parts[1:] if not a.startswith("-") and "=" not in a]
        exe = (shutil.which(names[0]) if names else None) or (names[0] if names else exe)
    ireal = os.path.realpath(exe)
    return {"realpath": ireal, "sha256": _file_sha256(ireal)}


def reviewer_executable(spec: dict) -> dict | None:
    """Identity of the reviewer CLI: absolute path, realpath, SHA-256 (and a script's interpreter). It is bound at
    PLAN in the control state, launched by that absolute path and re-checked before every step and every round, so a
    ``claude`` planted earlier on PATH after the plan is never run and a replaced CLI is TAMPER (DEV-LIFECYCLE-1
    R6-01). Several different ``claude`` executables on PATH at once are ``ambiguous``: the driver refuses to review
    until the owner leaves one. ``None`` for providers that are not an installed CLI."""
    p = spec.get("provider")
    if p not in INDEPENDENT_PROVIDERS:
        return None
    name = "claude" if p == "claude_cli" else "codex"
    if spec.get("binary"):  # DEVTEST only (load_config refuses it for a real milestone)
        found = [spec["binary"]] if (Path(spec["binary"]).is_file() or shutil.which(spec["binary"])) else []
        found = [shutil.which(f) or f for f in found]
    else:
        found = []
        for d in os.environ.get("PATH", "").split(os.pathsep):
            c = shutil.which(name, path=d or ".")
            if c and os.path.realpath(c) not in {os.path.realpath(x) for x in found}:
                found.append(c)
    if not found:
        return {"name": name, "error": "not found"}
    path = os.path.abspath(found[0])
    real = os.path.realpath(path)
    ident = {"name": name, "path": path, "realpath": real, "sha256": _file_sha256(real),
             "interpreter": _interpreter(real)}
    if len(found) > 1:
        ident["ambiguous"] = sorted(os.path.realpath(f) for f in found)
    return ident


def claude_settings(role: str, worktree: Path, protected: list[str]) -> dict:
    deny = list(GIT_WRITE_DENY)
    if role == "reviewer":
        deny += ["Edit", "Write", "NotebookEdit"]
    else:
        wt = str(worktree.resolve()).lstrip("/")
        deny += [f"Edit(//{wt}/{p.rstrip('/')}{'/**' if p.endswith('/') else ''})" for p in protected]
        deny += [f"Write(//{wt}/{p.rstrip('/')}{'/**' if p.endswith('/') else ''})" for p in protected]
    return {"permissions": {"deny": deny}}


def build_argv(spec: dict, role: str, worktree: Path, protected: list[str], session_id: str) -> list[str]:
    p = spec["provider"]
    tools = ROLE_TOOLS[role]
    if p == "claude_cli":
        argv = [spec.get("binary") or shutil.which("claude") or "claude", "-p", "--output-format", "json",
                "--session-id", session_id, "--permission-mode", "dontAsk",
                "--allowedTools", *tools["allowed"], "--disallowedTools", *tools["disallowed"],
                "--settings", json.dumps(claude_settings(role, worktree, protected))]
        if role == "reviewer":
            # The reviewer runs in the candidate checkout: its CLAUDE.md, .claude/ settings, hooks, skills, agents and
            # MCP servers are implementer-authored and must not reach the reviewer outside the driver-built prompt
            # (R6-02). --safe-mode drops CLAUDE.md and all customizations; --settings and the tool flags still apply.
            argv[2:2] = ["--safe-mode", "--setting-sources", "user", "--strict-mcp-config"]
        if spec.get("model"):
            argv += ["--model", spec["model"]]
        if spec.get("max_turns"):
            argv += ["--max-turns", str(spec["max_turns"])]
        return argv
    if p == "codex_cli":
        sandbox = "read-only" if role == "reviewer" else "workspace-write"
        argv = [spec.get("binary") or shutil.which("codex") or "codex", "exec", "--sandbox", sandbox, "-"]
        if role == "reviewer":  # no candidate AGENTS.md as project instructions (R6-02)
            argv[2:2] = ["-c", "project_doc_max_bytes=0"]
        if spec.get("model"):
            argv[2:2] = ["--model", spec["model"]]
        return argv
    if p == "command":
        return list(spec["argv"])
    raise ValueError(f"unknown provider {p!r}")


def run_worker(spec: dict, role: str, prompt: str, worktree: Path, log_dir: Path, *,
               protected: list[str] = (), timeout_s: float = 3600, env_extra: dict | None = None) -> dict:
    """Run one worker process. Returns a record; never raises for worker failure."""
    log_dir.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    rec = {"provider": spec.get("provider"), "role": role, "model_requested": spec.get("model"),
           "session_id_requested": session_id, "cwd": str(worktree), "started_at": _now(),
           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    (log_dir / f"{role}_prompt.md").write_bytes(prompt.encode("utf-8"))
    ok, why = provider_available(spec)
    if not ok:
        rec.update(status="UNAVAILABLE", detail=why, ended_at=_now(), unavailable_reason="UNAVAILABLE")
        return rec
    argv = build_argv(spec, role, worktree, list(protected), session_id)
    if rec["provider"] in ("claude_cli", "codex_cli"):
        name = "claude" if rec["provider"] == "claude_cli" else "codex"
        real = os.path.realpath(shutil.which(argv[0]) or argv[0])
        default = shutil.which(name)
        rec["binary_realpath"] = real
        rec["binary_is_default"] = bool(default) and real == os.path.realpath(default)
        rec["binary_sha256"] = _file_sha256(real)
        anchor = spec.get("_anchor")  # the PLAN-bound identity (R6-01); the launched file must still match it
        if anchor is not None:
            rec["binary_anchor_ok"] = bool(anchor.get("sha256")) and not anchor.get("ambiguous") and \
                real == anchor.get("realpath") and rec["binary_sha256"] == anchor.get("sha256") and \
                _interpreter(real) == anchor.get("interpreter")
            if not rec["binary_anchor_ok"]:
                rec.update(status="REFUSED", detail="reviewer executable differs from the one bound at the plan",
                           ended_at=_now())
                return rec
    env = {k: v for k, v in os.environ.items() if not k.startswith("URI_LIFECYCLE_")}
    env.update({"URI_LIFECYCLE_ROLE": role, "PYTHONDONTWRITEBYTECODE": "1"}, **(env_extra or {}))
    rec["argv"] = [a if len(a) < 400 else a[:60] + "…" for a in argv]
    try:
        proc = subprocess.Popen(argv, cwd=worktree, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env, start_new_session=True)
        rec["pid"] = proc.pid
        out, err = proc.communicate(prompt, timeout=timeout_s)
        rec["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired:
        _killpg(proc.pid)
        out, err = proc.communicate()
        rec["exit_code"] = None
        rec.update(status="TIMED_OUT")
    except OSError as e:
        rec.update(status="FAILED", detail=f"spawn: {e}", ended_at=_now())
        return rec
    # Always end the worker's whole process group before anything is checked or committed: a detached child
    # must not write after the integrity snapshot (DEV-LIFECYCLE-1 R1-06). A child that calls setsid() itself
    # escapes the group; the driver's later checks (clean worktree before the next step) still catch its writes.
    _killpg(proc.pid)
    rec["ended_at"] = _now()
    # Hashed files are written as exact bytes: no newline translation on Windows (R2-02).
    (log_dir / f"{role}_stdout.txt").write_bytes((out or "").encode("utf-8"))
    (log_dir / f"{role}_stderr.txt").write_bytes((err or "").encode("utf-8"))
    rec["stdout_sha256"] = hashlib.sha256((out or "").encode()).hexdigest()
    text, meta = out or "", {}
    if rec["provider"] == "claude_cli":
        try:
            meta = json.loads(out)
            text = meta.get("result") or ""
            rec["session_id"] = meta.get("session_id")
            rec["models_used"] = sorted((meta.get("modelUsage") or {}).keys())
            rec["cost_usd"] = meta.get("total_cost_usd")
            rec["num_turns"] = meta.get("num_turns")
            if meta.get("is_error"):
                rec.setdefault("status", "FAILED")
                rec["detail"] = (meta.get("result") or "")[:300]
        except ValueError:
            rec.setdefault("status", "FAILED")
            rec["detail"] = "claude output is not JSON"
    else:
        rec["session_id"] = f"{rec['provider']}-{session_id}"
    rec["result_text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (log_dir / f"{role}_result.txt").write_bytes(text.encode("utf-8"))
    if "status" not in rec:
        rec["status"] = "COMPLETED" if rec.get("exit_code") == 0 else "FAILED"
    if rec["status"] != "COMPLETED":
        blob = " ".join([text[-2000:], (err or "")[-2000:], str(rec.get("detail", ""))]).lower()
        if QUOTA_RE.search(blob):
            rec["unavailable_reason"] = "QUOTA"
        elif rec["status"] == "TIMED_OUT":
            rec["unavailable_reason"] = "TIMEOUT"
    rec["result_text"] = text
    return rec
