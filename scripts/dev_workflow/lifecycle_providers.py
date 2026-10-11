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
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from scripts.dev_workflow import containment

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
    """End a worker's process group (POSIX) or tree (Windows); never raises, also for an exited pid (DEV-LIFECYCLE-2
    F1: os.killpg and signal.SIGKILL do not exist on Windows)."""
    containment.kill_pid_tree(pid)


# Worker containment (DEV-LIFECYCLE-1 R8-01). A worker child that calls setsid() leaves the killed process group; as an
# orphan it would be adopted by init and outlive the worker, e.g. to write ``env`` into the next reviewer's fresh config
# dir and remove it once the CLI has read it. On Linux the driver makes itself the child subreaper: every orphan in its
# process tree is re-parented to the driver instead, and sweep_orphans() kills them all after each worker and command and
# before each worker starts. Elsewhere there is no containment and a real milestone's review does not count.
_PR_SET_CHILD_SUBREAPER, _PR_GET_CHILD_SUBREAPER = 36, 37
_SUBREAPER: bool | None = None


def enable_containment() -> bool:
    """Make this process the child subreaper (Linux; idempotent). True only when the kernel confirms it."""
    global _SUBREAPER
    if _SUBREAPER is None:
        _SUBREAPER = False
        if sys.platform.startswith("linux"):
            try:
                import ctypes
                libc = ctypes.CDLL(None, use_errno=True)
                flag = ctypes.c_int(0)
                _SUBREAPER = libc.prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0 and \
                    libc.prctl(_PR_GET_CHILD_SUBREAPER, ctypes.byref(flag), 0, 0, 0) == 0 and flag.value == 1
            except (OSError, AttributeError):
                _SUBREAPER = False
    return _SUBREAPER


def _orphans() -> list[int]:
    """Direct children of this process outside its session: adopted orphans of workers and commands (all of them run
    in their own session and are waited for before a sweep, so no legitimate child is in another session then)."""
    me, sid = os.getpid(), os.getsid(0)
    found = []
    for e in os.scandir("/proc"):
        if not e.name.isdigit():
            continue
        try:
            with open(f"/proc/{e.name}/stat", "rb") as fh:
                fields = fh.read().rsplit(b")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if int(fields[1]) == me and int(fields[3]) != sid:
            found.append(int(e.name))
    return found


def sweep_orphans(max_passes: int = 500) -> dict:
    """Kill every adopted orphan until none is left (their own children are adopted in turn). ``contained`` is True
    only when containment is active and the sweep converged. On Windows: every earlier job must be empty
    (containment.precheck, DEV-LIFECYCLE-2 F2)."""
    if containment.WINDOWS:
        return containment.precheck()
    if not enable_containment():
        return {"contained": False, "killed": 0, "reason": f"no child-subreaper containment on {sys.platform}"}
    killed = 0
    for _ in range(max_passes):
        pids = _orphans()
        if not pids:
            return {"contained": True, "killed": killed}
        for pid in pids:  # a child's pid cannot be reused before it is reaped: no race with an unrelated process
            try:
                os.kill(pid, signal.SIGKILL)
                killed += 1
            except OSError:
                pass
        for pid in pids:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
    return {"contained": False, "killed": killed, "reason": "orphans kept respawning"}


def drain_after_timeout(proc, grace: float = 5.0) -> tuple:
    """End a timed-out worker or command without blocking on its pipes (R10-01): kill its group, reap it, sweep the
    orphans that may still hold stdout/stderr (a setsid() child is outside the group), then read what is left for at
    most ``grace`` seconds. A holder outside the driver's tree cannot block the driver either: the pipes are closed.
    On Windows the worker's job is terminated instead (DEV-LIFECYCLE-2)."""
    containment.kill_tree(proc)
    try:
        proc.wait(timeout=grace)  # reaped before the sweep, which treats every child outside our session as an orphan
    except subprocess.TimeoutExpired:
        pass
    sweep_orphans()
    try:
        return proc.communicate(timeout=grace)
    except subprocess.TimeoutExpired as e:
        def text(b):
            return b.decode("utf-8", "replace") if isinstance(b, bytes) else (b or "")
        for f in (proc.stdout, proc.stderr):
            try:
                if f:
                    f.close()
            except OSError:
                pass
        return text(e.output), text(e.stderr)


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
        found = _path_candidates(name)
    if not found:
        return {"name": name, "error": "not found"}
    path = os.path.abspath(found[0])
    ident = {"name": name, "path": path, **resolve_cli(path)}
    # Several different programs on PATH (W-2: every PATHEXT variant of every folder on Windows) are ambiguous.
    targets, bad = {}, []
    for f in found:
        r = resolve_cli(f)
        if "error" in r:
            bad.append(f"{os.path.abspath(f)}: {r['error']}")
        else:
            targets.setdefault(tuple(os.path.realpath(x) for x in r["launch"]), os.path.abspath(f))
    if bad:
        ident["unlaunchable"] = bad
    if len(targets) > 1:
        ident["ambiguous"] = sorted(" ".join(t) for t in targets)
    return ident


def _path_candidates(name: str) -> list[str]:
    """Every file on PATH that a lookup of ``name`` could run, in lookup order. On Windows that is each PATHEXT
    variant in each folder (``claude.exe`` planted beside ``claude.cmd`` wins the lookup); a variant this driver never
    launches (``.ps1``, a bare POSIX script) is not a candidate."""
    found, seen = [], set()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if WINDOWS:
            exts = [e.lower() for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
            cands = [os.path.join(d or ".", name + e) for e in exts if e in _WIN_LAUNCHABLE]
            cands = [c for c in cands if os.path.isfile(c)]
        else:
            c = shutil.which(name, path=d or ".")
            cands = [c] if c else []
        for c in cands:
            key = os.path.normcase(os.path.realpath(c))
            if key not in seen:
                seen.add(key)
                found.append(c)
    return found


WINDOWS = sys.platform == "win32"
_WIN_LAUNCHABLE = (".exe", ".com", ".cmd", ".bat")
_DP0 = re.compile(r"%~?dp0%?", re.IGNORECASE)


def _win_launcher_target(shim: str) -> dict:
    """W-2: the program a ``.cmd``/``.bat`` launcher (npm shim) runs, so that program is what is bound and launched
    directly. Never cmd.exe: it would re-parse every argument. The quoted paths of the launcher are read with
    ``%~dp0`` replaced by its folder; other variables are not evaluated. Exactly one program and at most one script
    must remain, otherwise the launcher is refused (fail closed)."""
    d = os.path.dirname(os.path.abspath(shim))
    try:
        text = Path(shim).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"error": f"launcher not readable: {e}"}
    exes, scripts = [], []
    for tok in re.findall(r'"([^"]+)"', text):
        t = _DP0.sub(lambda m: d + os.sep, tok)
        if "%" in t:
            continue  # e.g. npm's "%_prog%": resolved below from the script type
        t = os.path.normpath(t)
        if not os.path.isfile(t) or t in exes or t in scripts:
            continue
        (exes if t.lower().endswith((".exe", ".com")) else scripts).append(t)
    if len(scripts) > 1 or len(exes) > 1:
        return {"error": f"launcher names several programs ({', '.join(exes + scripts)})"}
    if scripts and not exes and scripts[0].lower().endswith((".js", ".mjs", ".cjs")):
        node = shutil.which("node")  # npm: "%_prog%" is node.exe beside the launcher (found above) or on PATH
        if node and os.path.splitext(node)[1].lower() in (".exe", ".com"):
            exes = [os.path.abspath(node)]
    if len(exes) != 1:
        return {"error": "launcher does not name one executable it runs"}
    if not text.count("%*"):
        return {"error": "launcher does not pass its arguments on (%*)"}
    return {"launch": exes + scripts}


def resolve_cli(path: str) -> dict:
    """What actually runs when the reviewer CLI at ``path`` is launched (W-2), as the identity that is bound at PLAN
    and checked before every round: ``realpath``/``sha256`` of the program (the script, when an interpreter runs
    one), ``interpreter`` (the program that runs it), ``launch`` (the argv prefix the driver starts directly) and on
    Windows ``launcher`` (the shim's own path and hash). ``{"error": ...}`` when it cannot be bound."""
    ap = os.path.abspath(path)
    real = os.path.realpath(ap)
    launcher = None
    if WINDOWS:
        ext = os.path.splitext(real)[1].lower()
        if ext in (".exe", ".com"):
            launch = [real]
        elif ext in (".cmd", ".bat"):
            t = _win_launcher_target(real)
            if "error" in t:
                return t
            launch = t["launch"]
            launcher = {"realpath": real, "sha256": _file_sha256(real)}
        else:
            return {"error": "not a .exe, or a .cmd/.bat launcher that names one"}
    else:
        launch = [ap]
    prog = os.path.realpath(launch[-1])
    if len(launch) == 2:
        ireal = os.path.realpath(launch[0])
        interp = {"realpath": ireal, "sha256": _file_sha256(ireal)}
    else:
        interp = None if WINDOWS else _interpreter(prog)
    ident = {"realpath": prog, "sha256": _file_sha256(prog), "interpreter": interp, "launch": launch}
    if launcher:
        ident["launcher"] = launcher
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
        head = cli_launch(spec, "claude")  # the bound program itself, never a .cmd launcher (W-2)
        argv = [*head, "-p", "--output-format", "json",
                "--session-id", session_id, "--permission-mode", "dontAsk",
                "--allowedTools", *tools["allowed"], "--disallowedTools", *tools["disallowed"],
                "--settings", json.dumps(claude_settings(role, worktree, protected))]
        if role == "reviewer":
            # The reviewer runs in the candidate checkout: its CLAUDE.md, .claude/ settings, hooks, skills, agents and
            # MCP servers are implementer-authored and must not reach the reviewer outside the driver-built prompt
            # (R6-02). --safe-mode drops CLAUDE.md and all customizations; --settings and the tool flags still apply.
            # No setting source at all: user settings are as worker-writable as the checkout (R7-01); run_worker also
            # points CLAUDE_CONFIG_DIR at a driver-made directory, since ~/.claude.json "env" loads regardless.
            argv[len(head) + 1:len(head) + 1] = ["--safe-mode", "--setting-sources", "", "--strict-mcp-config"]
        if spec.get("model"):
            argv += ["--model", spec["model"]]
        if spec.get("max_turns"):
            argv += ["--max-turns", str(spec["max_turns"])]
        return argv
    if p == "codex_cli":
        sandbox = "read-only" if role == "reviewer" else "workspace-write"
        head = cli_launch(spec, "codex")
        k = len(head) + 1  # after "exec"
        argv = [*head, "exec", "--sandbox", sandbox, "-"]
        if role == "reviewer":  # no candidate AGENTS.md as project instructions (R6-02)
            argv[k:k] = ["-c", "project_doc_max_bytes=0"]
        if spec.get("model"):
            argv[k:k] = ["--model", spec["model"]]
        return argv
    if p == "command":
        return list(spec["argv"])
    raise ValueError(f"unknown provider {p!r}")


def cli_launch(spec: dict, name: str) -> list[str]:
    """The argv prefix that starts the reviewer/implementer CLI: the program ``resolve_cli`` binds (W-2), so a Windows
    ``.cmd`` launcher is never run through cmd.exe. A CLI that cannot be resolved is passed as found; run_worker then
    refuses it as a reviewer (no anchor match) and provider_available reports it."""
    b = spec.get("binary") or shutil.which(name) or name
    f = b if Path(b).is_file() else shutil.which(b)
    r = resolve_cli(f) if f else {}
    if "launch" in r:
        return list(r["launch"])
    return [f or b]


# The only parts of the user's Claude config a reviewer gets: credentials (they authenticate, they cannot redirect).
_CREDENTIAL_FILES = (".credentials.json",)
_GLOBAL_CONFIG_KEYS = ("primaryApiKey", "oauthAccount", "customApiKeyResponses", "userID", "hasCompletedOnboarding")


def user_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


# System-wide managed policy: the CLIs load it whatever --setting-sources says, and a worker with root can write it.
MANAGED_POLICY_DIRS = ("/etc/claude-code", "/Library/Application Support/ClaudeCode", r"C:\Program Files\ClaudeCode",
                       r"C:\ProgramData\ClaudeCode", "/etc/codex")


def managed_policy_state() -> list[str]:
    """Path and SHA-256 of every file under the managed-policy directories ("-" for an absent directory), bound in the
    PLAN control state: a worker-written managed ``env`` would redirect the reviewer like user settings (R7-01)."""
    parts = []
    for d in MANAGED_POLICY_DIRS:
        root = Path(d)
        if not root.is_dir():
            parts.append(f"{d}:-")
            continue
        for f in sorted(root.rglob("*"), key=str):
            if f.is_file() or f.is_symlink():
                parts.append(f"{f}:{_file_sha256(str(f)) or '-'}")
    return parts


def reviewer_config_dir() -> Path:
    """A fresh, driver-made CLAUDE_CONFIG_DIR for a ``claude`` reviewer. Workers share the driver's HOME, so
    ~/.claude/settings*.json and ~/.claude.json are worker-writable; their ``env`` (ANTHROPIC_BASE_URL, ...) would route
    the genuine CLI to a scripted endpoint (DEV-LIFECYCLE-1 R7-01). Only credentials are copied in: the credentials
    file and an allowlist of ~/.claude.json account keys; settings, env, hooks, plugins, agents and MCP config are not."""
    src = user_config_dir()
    d = Path(tempfile.mkdtemp(prefix="uri-reviewer-claude-"))
    for name in _CREDENTIAL_FILES:
        f = src / name
        if f.is_file():
            shutil.copyfile(f, d / name)
            os.chmod(d / name, 0o600)
    gsrc = src / ".claude.json" if os.environ.get("CLAUDE_CONFIG_DIR") else Path.home() / ".claude.json"
    try:
        g = json.loads(gsrc.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        g = {}
    keep = {k: g[k] for k in _GLOBAL_CONFIG_KEYS if isinstance(g, dict) and k in g}
    (d / ".claude.json").write_bytes(json.dumps(keep).encode("utf-8"))
    return d


def reviewer_codex_home() -> Path:
    """The same for a ``codex`` reviewer: ~/.codex/config.toml can redefine the model provider's base URL. Only
    ``auth.json`` is copied into a fresh CODEX_HOME (not verified against a real codex here: none is installed)."""
    src = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    d = Path(tempfile.mkdtemp(prefix="uri-reviewer-codex-"))
    if (src / "auth.json").is_file():
        shutil.copyfile(src / "auth.json", d / "auth.json")
        os.chmod(d / "auth.json", 0o600)
    return d


def config_dir_clean(d: Path) -> bool:
    """After the run: no settings file appeared and the global config carries no ``env`` (a lingering worker could
    write into the fresh directory; the empty ``--setting-sources`` ignores settings files anyway)."""
    if any((d / n).exists() for n in ("settings.json", "settings.local.json", "config.toml")):
        return False
    try:
        g = json.loads((d / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True  # absent or rewritten mid-write by the CLI itself: nothing it loads from there
    return not (isinstance(g, dict) and ("env" in g or "apiKeyHelper" in g))


class ConfigWatch:
    """Watches a reviewer's config dir for the whole run, not only its end state (R8-01): ``env``/``apiKeyHelper`` or a
    settings file present at any observed moment, even if removed before the run ends, makes the run not isolated."""

    def __init__(self, d: Path, interval: float = 0.01):
        self.d, self.interval, self.dirty, self._last = d, interval, False, None
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _sig(self):
        try:
            names = tuple(sorted(os.listdir(self.d)))
            st = os.stat(self.d / ".claude.json")
            return names, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns
        except OSError:
            return None

    def check(self):
        sig = self._sig()
        if sig is None or sig != self._last:
            self._last = sig
            if not config_dir_clean(self.d):
                self.dirty = True

    def _loop(self):
        while not self._stop.is_set():
            self.check()
            self._stop.wait(self.interval)

    def __enter__(self):
        self.check()
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join()
        self.check()


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
        # The program that actually runs (W-2: behind a Windows .cmd launcher), not the file found on PATH.
        src = spec.get("binary") or shutil.which(name) or argv[0]
        cur = resolve_cli(src if Path(src).is_file() else (shutil.which(src) or src))
        head = argv[:len(cur.get("launch") or [argv[0]])]
        real = cur.get("realpath") or os.path.realpath(shutil.which(argv[0]) or argv[0])
        default = shutil.which(name)
        rec["binary_realpath"] = real
        rec["binary_launch"] = head
        rec["binary_is_default"] = bool(default) and real == resolve_cli(default).get("realpath")
        rec["binary_sha256"] = cur.get("sha256") or _file_sha256(real)
        anchor = spec.get("_anchor")  # the PLAN-bound identity (R6-01); the launched file must still match it

        def same(a, b):
            return [os.path.normcase(os.path.realpath(x)) for x in a] == [os.path.normcase(os.path.realpath(x)) for x in b]
        if anchor is not None:
            rec["binary_anchor_ok"] = bool(anchor.get("sha256")) and not anchor.get("ambiguous") and \
                not anchor.get("unlaunchable") and "error" not in cur and \
                real == anchor.get("realpath") and rec["binary_sha256"] == anchor.get("sha256") and \
                cur.get("interpreter") == anchor.get("interpreter") and \
                cur.get("launcher") == anchor.get("launcher") and same(head, cur["launch"]) and \
                ("launch" not in anchor or same(head, anchor["launch"]))
            if not rec["binary_anchor_ok"]:
                rec.update(status="REFUSED", detail="reviewer executable differs from the one bound at the plan",
                           ended_at=_now())
                return rec
    env = {k: v for k, v in os.environ.items() if not k.startswith("URI_LIFECYCLE_")}
    env.update({"URI_LIFECYCLE_ROLE": role, "PYTHONDONTWRITEBYTECODE": "1"}, **(env_extra or {}))
    # No process left by an earlier worker or command may run alongside this one (R8-01).
    rec["containment_pre"] = sweep_orphans()
    cfg_dir = None
    if role == "reviewer" and rec["provider"] == "claude_cli":  # driver-made config, never the shared one (R7-01)
        cfg_dir = reviewer_config_dir()
        env["CLAUDE_CONFIG_DIR"] = str(cfg_dir)
    elif role == "reviewer" and rec["provider"] == "codex_cli":
        cfg_dir = reviewer_codex_home()
        env["CODEX_HOME"] = str(cfg_dir)
    try:
        return _run(argv, rec, role, prompt, worktree, log_dir, env, timeout_s, cfg_dir)
    finally:
        if cfg_dir is not None:
            shutil.rmtree(cfg_dir, ignore_errors=True)


def _run(argv, rec, role, prompt, worktree, log_dir, env, timeout_s, cfg_dir) -> dict:
    rec["argv"] = [a if len(a) < 400 else a[:60] + "…" for a in argv]
    watch = ConfigWatch(cfg_dir) if cfg_dir is not None else None
    if watch:
        watch.__enter__()
    try:
        proc = containment.spawn(argv, cwd=worktree, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, env=env)
        rec["pid"] = proc.pid
        out, err = proc.communicate(prompt, timeout=timeout_s)
        rec["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired:
        out, err = drain_after_timeout(proc)
        rec["exit_code"] = None
        rec.update(status="TIMED_OUT")
    except OSError as e:
        if watch:
            watch.__exit__(None, None, None)
        rec.update(status="FAILED", detail=f"spawn: {e}", ended_at=_now())
        return rec
    # Always end the worker's whole process group before anything is checked or committed: a detached child
    # must not write after the integrity snapshot (DEV-LIFECYCLE-1 R1-06). A child that calls setsid() itself
    # escapes the group but is adopted by the driver (child subreaper) and killed by the sweep (R8-01). On Windows
    # the worker's job is terminated and must report no active process (DEV-LIFECYCLE-2 F2).
    rec["containment_post"] = containment.finish(proc, sweep_orphans)
    rec["contained"] = rec["containment_pre"].get("contained") is True and rec["containment_post"]["contained"] is True
    rec["ended_at"] = _now()
    if watch:
        watch.__exit__(None, None, None)
        rec["config_isolated"] = not watch.dirty and config_dir_clean(cfg_dir)
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
        rec["session_id"] = f"{rec['provider']}-{rec['session_id_requested']}"
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
