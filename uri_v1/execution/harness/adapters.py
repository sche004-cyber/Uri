"""Harness adapters: Claude Code (live-qualifiable here) and Codex CLI (built, not executed here).

Each adapter turns a capsule into one restrictive invocation and turns the
harness's output into claims. No adapter ever emits a permission or sandbox
bypass flag; `FORBIDDEN_FLAGS` is checked on every invocation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from .contracts import UNAVAILABLE, ClaimedOutcome, ExecutionCapsule, HarnessError, HarnessRunResult, HarnessType
from .discovery import discover_claude_code, discover_codex, probe_version, resolve_command
from .process import ProcessResult, harness_env

FORBIDDEN_FLAGS = frozenset({"--dangerously-skip-permissions", "--allow-dangerously-skip-permissions", "bypassPermissions",
                             "--dangerously-bypass-approvals-and-sandbox", "--yolo", "danger-full-access"})


def _check(argv) -> list:
    if FORBIDDEN_FLAGS.intersection(argv): raise HarnessError("BYPASS_FLAG_REFUSED")
    return argv


def _num(d, key):
    v = d.get(key) if isinstance(d, dict) else None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else UNAVAILABLE


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        if os.name == "nt":
            identity = subprocess.run(["whoami"], check=True, capture_output=True, text=True).stdout.strip()
            if not identity:
                raise OSError("unable to identify current Windows principal")
            subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{identity}:(R,W)"],
                           check=True, capture_output=True, text=True)
        else:
            os.chmod(path, 0o600)
        path.write_bytes(data)
    except Exception:
        path.unlink(missing_ok=True)
        raise


class ClaudeCodeAdapter:
    harness_type = HarnessType.CLAUDE_CODE
    TOOLS = "Read,Edit,Write,Glob,Grep,Bash"

    def __init__(self, executable="claude", *, home: Path | None = None, project: Path | None = None, model: str | None = None):
        self.executable, self.home, self.project, self.model = executable, Path(home or Path.home()), project, model

    def describe(self) -> dict:
        return {"harness_type": self.harness_type.value, "capabilities": {"resume": "stored_not_used", "structured_events": True,
                "instructions": "stdin", "per_run_mcp": True, "per_run_plugins": True, "per_run_skills": True,
                "os_sandbox": False}, "default_posture": "dontAsk + path-scoped file tools; no web tools; no shell"}

    def inventory(self):
        return discover_claude_code(self.home, self.project)

    def probe(self) -> dict:
        p = probe_version(self.executable)
        return dict(p, auth_mode=self.inventory().auth_mode if p["installed"] else "none")

    # -- controlled capability injection ------------------------------------------------------
    def _raw_mcp(self, name):
        for path, key in ((self.home / ".claude.json", "mcpServers"),) + (((Path(self.project) / ".mcp.json", "mcpServers"),) if self.project else ()):
            try:
                cfg = json.loads(path.read_bytes()).get(key) or {}
            except (OSError, ValueError, AttributeError):
                continue
            if name in cfg: return cfg[name]
        raise HarnessError("GRANTED_MCP_NOT_FOUND")

    def _inject(self, capsule: ExecutionCapsule, bundle: Path, inventory) -> list:
        args, mcp = [], {}
        skills_root = bundle / "run-plugin"
        for kind, name in capsule.capabilities.items:
            item = inventory.find(kind, name)
            if item is None: raise HarnessError("GRANTED_CAPABILITY_NOT_DISCOVERED")
            if kind == "MCP_SERVER":
                mcp[name] = self._raw_mcp(name)
            elif kind == "PLUGIN":
                if not item.install_path or not Path(item.install_path).is_dir(): raise HarnessError("PLUGIN_PATH_UNAVAILABLE")
                args += ["--plugin-dir", item.install_path]
            elif kind == "SKILL":
                if not item.install_path: raise HarnessError("SKILL_PATH_UNAVAILABLE")
                if not skills_root.exists():
                    (skills_root / ".claude-plugin").mkdir(parents=True)
                    (skills_root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "uri-run-skills", "version": "0.0.0",
                                                                                        "description": "Per-run skills granted by URI"}))
                    args += ["--plugin-dir", str(skills_root)]
                shutil.copytree(item.install_path, skills_root / "skills" / Path(item.install_path).name, symlinks=False)
            else:
                raise HarnessError("UNSUPPORTED_GRANT_KIND")
        mcp_path = bundle / "mcp.json"
        _write_private(mcp_path, json.dumps({"mcpServers": mcp}).encode())
        return ["--strict-mcp-config", "--mcp-config", str(mcp_path)] + args

    # Auth variables Claude Code needs for its own authentication (OD-2). Never
    # includes a URI provider key: the harness authenticates itself. Deliberately
    # excludes ANTHROPIC_API_KEY (spend policy, 2026-09-28): that would switch Claude
    # Code from the user's subscription to metered API billing, which is never
    # authorized here; `harness_env()` also strips it as a hard denial either way.
    AUTH_VARS = ("CLAUDE_CODE_OAUTH_TOKEN",)
    FILE_TOOLS = ("Read", "Edit", "Write", "Glob", "Grep")

    def invocation(self, capsule: ExecutionCapsule, bundle: Path, inventory=None):
        if not capsule.capabilities.valid(): raise HarnessError("CAPABILITY_GRANT_INVALID")
        inventory = inventory or self.inventory()
        posture = capsule.posture
        # File tools are path-scoped to the workspace (H-1): a bare `Read`/`Edit`/… allow
        # rule has no path bound at all, so it can reach any file the user can. Elevated
        # `extra_dirs` (each backed by an ElevationGrant) are scoped in the same way rather
        # than opened up wholesale.
        #
        # D-1: an absolute path rule needs Claude Code's `//` prefix -- a single leading
        # `/` is read relative to the settings root, not as an absolute path, so the old
        # rule never matched anything at all. And the bare tool name must never also be
        # denied: `--disallowedTools` overrides every scoped `--allowedTools` rule for
        # that tool, so a bare `Read` deny left the harness with no usable file tool at
        # all regardless of the scoped allow above it. The workspace/extra_dir scoping
        # above is the containment boundary; the bare names are not separately denied.
        scopes = [str(Path(capsule.workspace_files).resolve()), *posture.extra_dirs]
        allowed = [f"{tool}(//{scope.lstrip('/')}/**)" for scope in scopes for tool in self.FILE_TOOLS]
        # No shell in the default posture (Chetan, 2026-09-28): the harness can edit
        # files but not run them. URI's own verifier does all execution, so it, not
        # an unsandboxed harness process, is what actually runs any script.
        disallowed = ["WebFetch", "WebSearch", "Bash"]
        if posture.package_install: allowed += ["Bash(pip *)", "Bash(pip3 *)", "Bash(python -m pip *)", "Bash(python3 -m pip *)"]
        if posture.network:
            allowed += ["WebFetch", "WebSearch"]
            disallowed = [t for t in disallowed if t not in ("WebFetch", "WebSearch")]
        cmd = resolve_command(self.executable)
        if not cmd: raise HarnessError("HARNESS_UNAVAILABLE")
        argv = [*cmd, "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
                "--setting-sources", "", "--permission-mode", "dontAsk", "--tools", self.TOOLS,
                "--allowedTools", *allowed]
        if disallowed: argv += ["--disallowedTools", *disallowed]
        for d in posture.extra_dirs: argv += ["--add-dir", d]
        if capsule.limits.max_budget_usd is not None: argv += ["--max-budget-usd", str(capsule.limits.max_budget_usd)]
        if self.model: argv += ["--model", self.model]
        argv += self._inject(capsule, bundle, inventory)
        prompt = Path(capsule.instructions_path).read_bytes()
        if hashlib.sha256(prompt).hexdigest() != capsule.instructions_sha256: raise HarnessError("INSTRUCTIONS_TAMPERED")
        return _check(argv), harness_env(self.AUTH_VARS), prompt

    def parse(self, proc: ProcessResult, capsule: ExecutionCapsule, harness_version) -> HarnessRunResult:
        result, tool_calls, models = None, 0, set()
        for line in Path(proc.log_path).read_bytes().splitlines():
            try: ev = json.loads(line)
            except ValueError: continue
            if not isinstance(ev, dict): continue
            if ev.get("type") == "assistant":
                msg = ev.get("message") or {}
                if msg.get("model"): models.add(str(msg["model"])[:64])
                tool_calls += sum(1 for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "tool_use")
            elif ev.get("type") == "result":
                result = ev
        usage = {"input_tokens": UNAVAILABLE, "output_tokens": UNAVAILABLE, "cache_read_input_tokens": UNAVAILABLE,
                 "cache_creation_input_tokens": UNAVAILABLE, "cost_usd": UNAVAILABLE, "num_turns": UNAVAILABLE,
                 "tool_calls": tool_calls, "models": sorted(models) or UNAVAILABLE, "duration_ms": proc.duration_ms}
        if result:
            u = result.get("usage") or {}
            usage.update(input_tokens=_num(u, "input_tokens"), output_tokens=_num(u, "output_tokens"),
                         cache_read_input_tokens=_num(u, "cache_read_input_tokens"),
                         cache_creation_input_tokens=_num(u, "cache_creation_input_tokens"),
                         cost_usd=_num(result, "total_cost_usd"), num_turns=_num(result, "num_turns"))
            if isinstance(result.get("modelUsage"), dict): usage["models"] = sorted(str(k)[:64] for k in result["modelUsage"])
        killed = proc.timed_out or proc.inactivity_killed or proc.cancelled
        if killed or result is None:
            outcome, family = ClaimedOutcome.OUTCOME_UNKNOWN, (
                "TIMEOUT" if proc.timed_out else "INACTIVITY" if proc.inactivity_killed else "CANCELLED" if proc.cancelled else "NO_RESULT")
        elif result.get("is_error") or result.get("subtype") != "success":
            outcome, family = ClaimedOutcome.FAILED, str(result.get("subtype") or "error")[:64]
        else:
            outcome, family = ClaimedOutcome.COMPLETED_CLAIMED, None
        text = result.get("result") if result and isinstance(result.get("result"), str) else None
        session = {"codec_version": 1, "harness_type": self.harness_type.value, "harness_version": harness_version,
                   "opaque": str(result.get("session_id"))[:128] if result and result.get("session_id") else None,
                   "bound_to": {"files": capsule.workspace_files}} if result else None
        return HarnessRunResult(outcome, proc.exit_code, proc.timed_out, proc.inactivity_killed, family, None,
                                hashlib.sha256(text.encode()).hexdigest() if text else None, session, usage,
                                proc.log_sha256, proc.log_bytes)


class CodexCliAdapter:
    """Built from documented `codex exec` flags. Not executed in this environment: UNQUALIFIED."""
    harness_type = HarnessType.CODEX_CLI
    # Codex's own auth (OD-2). Deliberately excludes OPENAI_API_KEY: that name is
    # also read as a URI Brain provider key elsewhere, so it is never forwarded here.
    AUTH_VARS = ("CODEX_API_KEY", "CODEX_HOME")

    def __init__(self, executable="codex", *, home: Path | None = None, model: str | None = None):
        self.executable, self.home, self.model = executable, Path(home or Path.home()), model

    def describe(self) -> dict:
        return {"harness_type": self.harness_type.value, "capabilities": {"resume": "stored_not_used", "structured_events": True,
                "instructions": "stdin", "per_run_mcp": False, "per_run_plugins": False, "per_run_skills": False, "os_sandbox": True},
                "default_posture": "sandbox workspace-write; network off; approval never"}

    def inventory(self):
        return discover_codex(self.home, Path(os.environ["CODEX_HOME"]) if os.environ.get("CODEX_HOME") else None)

    def probe(self) -> dict:
        p = probe_version(self.executable)
        return dict(p, auth_mode=self.inventory().auth_mode if p["installed"] else "none")

    def invocation(self, capsule: ExecutionCapsule, bundle: Path, inventory=None):
        if capsule.capabilities.items: raise HarnessError("CODEX_CAPABILITY_INJECTION_UNSUPPORTED_IN_MINIMUM")
        if capsule.posture.extra_dirs: raise HarnessError("CODEX_EXTRA_DIRS_UNSUPPORTED_IN_MINIMUM")
        net = "true" if capsule.posture.network else "false"
        cmd = resolve_command(self.executable)
        if not cmd: raise HarnessError("HARNESS_UNAVAILABLE")
        argv = [*cmd, "exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check",
                "-C", capsule.workspace_files, "-c", 'approval_policy="never"', "-c", f"sandbox_workspace_write.network_access={net}"]
        if self.model: argv += ["-m", self.model]
        argv.append("-")
        prompt = Path(capsule.instructions_path).read_bytes()
        if hashlib.sha256(prompt).hexdigest() != capsule.instructions_sha256: raise HarnessError("INSTRUCTIONS_TAMPERED")
        return _check(argv), harness_env(self.AUTH_VARS), prompt

    def parse(self, proc: ProcessResult, capsule: ExecutionCapsule, harness_version) -> HarnessRunResult:
        thread, text, failed, usage_raw, tools = None, None, None, {}, 0
        for line in Path(proc.log_path).read_bytes().splitlines():
            try: ev = json.loads(line)
            except ValueError: continue
            if not isinstance(ev, dict): continue
            t = ev.get("type")
            if t == "thread.started": thread = ev.get("thread_id")
            elif t == "turn.completed": usage_raw = ev.get("usage") or {}
            elif t in ("turn.failed", "error"): failed = str((ev.get("error") or {}).get("message", t) if isinstance(ev.get("error"), dict) else t)[:64]
            elif t == "item.completed":
                item = ev.get("item") or {}
                if item.get("type") == "agent_message" and isinstance(item.get("text"), str): text = item["text"]
                elif item.get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search"): tools += 1
        usage = {"input_tokens": _num(usage_raw, "input_tokens"), "output_tokens": _num(usage_raw, "output_tokens"),
                 "cache_read_input_tokens": _num(usage_raw, "cached_input_tokens"), "cache_creation_input_tokens": UNAVAILABLE,
                 "cost_usd": UNAVAILABLE, "num_turns": UNAVAILABLE, "tool_calls": tools, "models": UNAVAILABLE,
                 "duration_ms": proc.duration_ms}
        killed = proc.timed_out or proc.inactivity_killed or proc.cancelled
        if killed: outcome, family = ClaimedOutcome.OUTCOME_UNKNOWN, "TIMEOUT" if proc.timed_out else "INACTIVITY" if proc.inactivity_killed else "CANCELLED"
        elif failed or proc.exit_code != 0: outcome, family = ClaimedOutcome.FAILED, failed or "EXIT_NONZERO"
        elif text is None: outcome, family = ClaimedOutcome.OUTCOME_UNKNOWN, "NO_RESULT"
        else: outcome, family = ClaimedOutcome.COMPLETED_CLAIMED, None
        session = {"codec_version": 1, "harness_type": self.harness_type.value, "harness_version": harness_version,
                   "opaque": str(thread)[:128] if thread else None, "bound_to": {"files": capsule.workspace_files}}
        return HarnessRunResult(outcome, proc.exit_code, proc.timed_out, proc.inactivity_killed, family, None,
                                hashlib.sha256(text.encode()).hexdigest() if text else None, session, usage,
                                proc.log_sha256, proc.log_bytes)
