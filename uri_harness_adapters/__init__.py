"""Provider adapter boundary for client-side external harnesses (Claude Code, Codex CLI).

The ONLY place that knows provider command lines, output formats, native-login hints and which
products are refused. Core (uri_core) never imports this package; the paired client worker
composes it into the provider-neutral `uri_core.client_runtime.harness.HarnessRegistry`.

Moved here unchanged in behaviour from uri_core/client_runtime/harness.py (C4 cleanup, M31
invariant restored): the original guard forbids development-agent knowledge inside Core.
Every argv still passes the registry's bypass-flag refusal; nothing here logs in or installs.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from uri_core.client_runtime.harness import (UNAVAILABLE, HarnessAdapter, HarnessRegistry, _events, _num,
                                             build_invocation, claim)

FILE_TOOLS = ("Read", "Edit", "Write", "Glob", "Grep")
AUTH_VARS = {"claude_code": ("CLAUDE_CODE_OAUTH_TOKEN",), "codex_cli": ("CODEX_API_KEY", "CODEX_HOME")}
AUTH_ACTIONS = {
    "claude_code": "Run `claude` in the URI client profile terminal and sign in with your subscription (native login).",
    "codex_cli": "Run `codex login` in the URI client profile terminal (native login).",
}


def build_claude(cmd, capsule, model=None):
    # `//` prefix makes the scope an absolute path rule; bare tool names are never
    # denied because a bare deny overrides every scoped allow (M38 D-1).
    scope = str(Path(capsule.workspace).resolve()).replace("\\", "/").lstrip("/")
    allowed = [f"{tool}(//{scope}/**)" for tool in FILE_TOOLS]
    disallowed = ["Bash"] + ([] if capsule.network else ["WebFetch", "WebSearch"])
    if capsule.network:
        allowed += ["WebFetch", "WebSearch"]
    argv = [*cmd, "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
            "--setting-sources", "", "--permission-mode", "dontAsk", "--tools", ",".join(FILE_TOOLS),
            "--allowedTools", *allowed, "--disallowedTools", *disallowed, "--strict-mcp-config"]
    if capsule.max_budget_usd is not None:
        argv += ["--max-budget-usd", str(capsule.max_budget_usd)]
    if model:
        argv += ["--model", model]
    return argv, AUTH_VARS["claude_code"], capsule.instructions


def build_codex(cmd, capsule, model=None):
    net = "true" if capsule.network else "false"
    argv = [*cmd, "exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check", "-C", capsule.workspace,
            "-c", 'approval_policy="never"', "-c", f"sandbox_workspace_write.network_access={net}"]
    if model:
        argv += ["-m", model]
    argv.append("-")
    return argv, AUTH_VARS["codex_cli"], capsule.instructions


def parse_claude(proc):
    """Return a claim dict. Never trusted as success; URI verifies the workspace itself."""
    result, tool_calls = None, 0
    for ev in _events(proc):
        if ev.get("type") == "assistant":
            tool_calls += sum(1 for c in (ev.get("message") or {}).get("content") or []
                              if isinstance(c, dict) and c.get("type") == "tool_use")
        elif ev.get("type") == "result":
            result = ev
    return claim(proc, result is not None and not result.get("is_error") and result.get("subtype") == "success",
                 result, tool_calls, str((result or {}).get("subtype") or "")[:64],
                 text=(result or {}).get("result"),
                 usage=(result or {}).get("usage"), cost=_num(result or {}, "total_cost_usd"))


def parse_codex(proc):
    text, failed, usage, tools, seen = None, None, {}, 0, False
    for ev in _events(proc):
        t = ev.get("type")
        if t == "turn.completed": usage, seen = ev.get("usage") or {}, True
        elif t in ("turn.failed", "error"):
            err = ev.get("error")
            failed = str(err.get("message", t) if isinstance(err, dict) else ev.get("message", t))[:200]
        elif t == "item.completed":
            item = ev.get("item") or {}
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str): text = item["text"]
            elif item.get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search"): tools += 1
    ok = seen and failed is None and proc.exit_code == 0 and text is not None
    # A result record exists only if the harness reported a terminal turn event.
    result = {"failure": failed} if failed else ({"completed": True} if seen else None)
    return claim(proc, ok, result, tools, failed or "", text=text, usage=usage, cost=UNAVAILABLE)


ADAPTERS = (
    HarnessAdapter("claude_code", "claude", build_claude, parse_claude, AUTH_ACTIONS["claude_code"]),
    HarnessAdapter("codex_cli", "codex", build_codex, parse_codex, AUTH_ACTIONS["codex_cli"]),
    HarnessAdapter("antigravity", "agy", refused="Antigravity execution is refused until separately qualified."),
)
_BY_ID = {a.harness_id: a for a in ADAPTERS}


def default_registry(executables=None, auth_probe=None):
    """The client's harness registry: all known adapters, none qualified, nothing usable by default."""
    return HarnessRegistry(ADAPTERS, executables=executables, auth_probe=auth_probe)


# Direct builders kept for adapter-level tests (same checks as the registry path).
def claude_invocation(executable, capsule, model=None):
    return build_invocation(_BY_ID["claude_code"], executable, capsule, model)


def codex_invocation(executable, capsule, model=None):
    return build_invocation(_BY_ID["codex_cli"], executable, capsule, model)
