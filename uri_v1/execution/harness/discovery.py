"""Read-only discovery of a harness's native capabilities (plugins, skills, MCP
servers, agents, hooks, prompts), with secrets redacted by construction.

Only descriptor files are read. Credential files are never opened; their
existence alone sets `auth_mode`. For each item the inventory keeps name,
kind, scope, transport, a command basename or URL host, and a fingerprint of
that redacted descriptor. `env`, `headers`, `args`, URL paths and queries are
never copied out of the source files.
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
from urllib.parse import urlsplit

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

from .contracts import HarnessType, canonical

MAX_DESCRIPTOR_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 500
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:@/\-]{0,127}$")


@dataclass(frozen=True)
class CapabilityItem:
    kind: str          # MCP_SERVER | PLUGIN | SKILL | AGENT | HOOK | PROMPT
    name: str
    scope: str         # user | project | plugin
    transport: str | None
    target: str | None  # command basename or URL host; never args, env, headers or URL path
    origin: str        # descriptor file, relative to the scanned home or project
    install_path: str | None = None   # plugin/skill directory, for per-run injection only

    def redacted(self) -> dict:
        return {"kind": self.kind, "name": self.name, "scope": self.scope, "transport": self.transport,
                "target": self.target, "origin": self.origin}

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(canonical(self.redacted())).hexdigest()[:16]


@dataclass(frozen=True)
class Inventory:
    harness_type: HarnessType
    items: tuple
    auth_mode: str
    warnings: tuple

    def find(self, kind, name):
        return next((i for i in self.items if i.kind == kind and i.name == name), None)

    def to_dict(self) -> dict:
        return {"harness_type": self.harness_type.value, "auth_mode": self.auth_mode, "warnings": list(self.warnings),
                "items": [dict(i.redacted(), fingerprint=i.fingerprint) for i in self.items]}

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical(self.to_dict())).hexdigest()


def _safe_name(value) -> str | None:
    value = str(value).strip()
    return value if _NAME.fullmatch(value) else None


def _read(path: Path, warnings: list):
    try:
        if not path.is_file() or path.is_symlink(): return None
        if path.stat().st_size > MAX_DESCRIPTOR_BYTES:
            warnings.append(f"DESCRIPTOR_TOO_LARGE:{path.name}"); return None
        return path.read_bytes()
    except OSError:
        warnings.append(f"DESCRIPTOR_UNREADABLE:{path.name}"); return None


def _json(path: Path, warnings: list):
    data = _read(path, warnings)
    if data is None: return None
    try: return json.loads(data)
    except ValueError:
        warnings.append(f"DESCRIPTOR_MALFORMED:{path.name}"); return None


def _target(cfg: dict) -> tuple:
    """(transport, target) with nothing beyond a command basename or a URL host."""
    if not isinstance(cfg, dict): return None, None
    url = cfg.get("url")
    if isinstance(url, str):
        host = urlsplit(url).hostname
        return (str(cfg.get("type") or cfg.get("transport") or "http"))[:16], host
    command = cfg.get("command")
    if isinstance(command, str):
        return "stdio", os.path.basename(command.replace("\\", "/"))[:64] or None
    return None, None


def _frontmatter_name(path: Path, warnings: list, fallback: str) -> str | None:
    data = _read(path, warnings)
    if data is None: return None
    text = data.decode("utf-8", "replace")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if m:
        n = re.search(r"^name:\s*['\"]?([^'\"\n]+)", m.group(1), re.M)
        if n: return _safe_name(n.group(1)) or _safe_name(fallback)
    return _safe_name(fallback)


def _mcp_items(servers, scope, origin) -> list:
    out = []
    if isinstance(servers, dict):
        for name, cfg in servers.items():
            n = _safe_name(name)
            if n:
                transport, target = _target(cfg)
                out.append(CapabilityItem("MCP_SERVER", n, scope, transport, target, origin))
    return out


def discover_claude_code(home: Path, project: Path | None = None) -> Inventory:
    home = Path(home); warnings, items = [], []
    claude = home / ".claude"
    settings = _json(claude / "settings.json", warnings) or {}
    for key, enabled in (settings.get("enabledPlugins") or {}).items():
        n = _safe_name(key)
        if n and enabled: items.append(CapabilityItem("PLUGIN", n, "user", None, None, ".claude/settings.json"))
    for event in (settings.get("hooks") or {}):
        n = _safe_name(event)
        if n: items.append(CapabilityItem("HOOK", n, "user", None, None, ".claude/settings.json"))
    installed = _json(claude / "plugins" / "installed_plugins.json", warnings) or {}
    plugins = installed.get("plugins") if isinstance(installed.get("plugins"), dict) else {}
    for key, entries in plugins.items():
        n = _safe_name(key)
        entry = entries[0] if isinstance(entries, list) and entries else entries if isinstance(entries, dict) else {}
        path = entry.get("installPath") if isinstance(entry, dict) else None
        if n:
            existing = next((i for i in items if i.kind == "PLUGIN" and i.name == n), None)
            if existing: items.remove(existing)
            items.append(CapabilityItem("PLUGIN", n, "user", None, None, ".claude/plugins/installed_plugins.json",
                                        str(path) if isinstance(path, str) else None))
    user_json = _json(home / ".claude.json", warnings) or {}
    items += _mcp_items(user_json.get("mcpServers"), "user", ".claude.json")
    if project is not None:
        items += _mcp_items((_json(Path(project) / ".mcp.json", warnings) or {}).get("mcpServers"), "project", ".mcp.json")
        proj = (user_json.get("projects") or {}).get(str(Path(project).resolve())) or {}
        items += _mcp_items(proj.get("mcpServers"), "project", ".claude.json#projects")
    for d in sorted((claude / "skills").glob("*/SKILL.md")) if (claude / "skills").is_dir() else ():
        n = _frontmatter_name(d, warnings, d.parent.name)
        if n: items.append(CapabilityItem("SKILL", n, "user", None, None, f".claude/skills/{d.parent.name}/SKILL.md", str(d.parent)))
    for a in sorted((claude / "agents").glob("*.md")) if (claude / "agents").is_dir() else ():
        n = _frontmatter_name(a, warnings, a.stem)
        if n: items.append(CapabilityItem("AGENT", n, "user", None, None, f".claude/agents/{a.name}"))
    auth = "api" if os.environ.get("ANTHROPIC_API_KEY") else "subscription" if (claude / ".credentials.json").exists() else "unknown"
    return Inventory(HarnessType.CLAUDE_CODE, tuple(items[:MAX_ITEMS]), auth, tuple(warnings))


def discover_codex(home: Path, codex_home: Path | None = None) -> Inventory:
    home = Path(codex_home) if codex_home else Path(home) / ".codex"
    warnings, items = [], []
    data = _read(home / "config.toml", warnings)
    if data is not None:
        if tomllib is None: warnings.append("TOML_PARSER_UNAVAILABLE")
        else:
            try:
                cfg = tomllib.loads(data.decode("utf-8", "replace"))
                items += _mcp_items(cfg.get("mcp_servers"), "user", ".codex/config.toml")
            except (tomllib.TOMLDecodeError, ValueError):
                warnings.append("DESCRIPTOR_MALFORMED:config.toml")
    for d in sorted((home / "skills").glob("*/SKILL.md")) if (home / "skills").is_dir() else ():
        n = _frontmatter_name(d, warnings, d.parent.name)
        if n: items.append(CapabilityItem("SKILL", n, "user", None, None, f".codex/skills/{d.parent.name}/SKILL.md", str(d.parent)))
    for p in sorted((home / "prompts").glob("*.md")) if (home / "prompts").is_dir() else ():
        n = _safe_name(p.stem)
        if n: items.append(CapabilityItem("PROMPT", n, "user", None, None, f".codex/prompts/{p.name}"))
    auth = "api" if os.environ.get("OPENAI_API_KEY") or os.environ.get("CODEX_API_KEY") else "login" if (home / "auth.json").exists() else "unknown"
    return Inventory(HarnessType.CODEX_CLI, tuple(items[:MAX_ITEMS]), auth, tuple(warnings))


def resolve_command(executable) -> list | None:
    """`claude` / a path / an argv prefix such as [python, fake_harness.py]."""
    if isinstance(executable, (list, tuple)):
        first = shutil.which(executable[0]) if executable else None
        return [first, *executable[1:]] if first else None
    exe = shutil.which(executable) if executable else None
    return [exe] if exe else None


def probe_version(executable, timeout_s: float = 20) -> dict:
    """Installed version via `--version`; never installs, updates or logs in."""
    cmd = resolve_command(executable)
    if not cmd: return {"installed": False, "version": None, "executable": None}
    exe = cmd[0]
    try:
        out = subprocess.run([*cmd, "--version"], capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL,
                             env={k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")})
        m = re.search(r"\d+\.\d+\.\d+", out.stdout.decode("utf-8", "replace"))
        return {"installed": True, "version": m.group(0) if m else None, "executable": exe}
    except (OSError, subprocess.TimeoutExpired):
        return {"installed": True, "version": None, "executable": exe}
