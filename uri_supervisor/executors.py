"""Declarative executor specs. Provider names live HERE (data), never in scheduler/ledger logic.

A spec says how to build argv, how to read the executor's event stream into semantic labels, and
which markers mean quota exhaustion. Adding a harness or a local model = adding a spec; the
admission/recovery code paths do not change.

Event schemas for Codex/Claude are only partly documented; rules therefore match on a small set of
fields and are covered by golden fixtures (tests/phase2a/fixtures/streams). Two of those are REAL
captures from this machine (auth/model failure paths); the success-path fixtures are SYNTHETIC,
derived from documented shapes, and labelled as such.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field

from .stream import EventRule

# Same refusal list as frozen Phase-1 harness (uri_core.client_runtime.harness.FORBIDDEN_FLAGS);
# duplicated by value so Phase 2A never weakens it and never imports Core internals at runtime.
FORBIDDEN_FLAGS = frozenset({"--dangerously-skip-permissions", "--allow-dangerously-skip-permissions",
                             "bypassPermissions", "--dangerously-bypass-approvals-and-sandbox", "--yolo",
                             "danger-full-access"})
ENV_ALLOW = frozenset({"PATH", "HOME", "USERPROFILE", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "TEMP", "TMP", "TZ",
                       "USER", "USERNAME", "SHELL", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT"})
NEVER_FORWARD = frozenset({"ANTHROPIC_API_KEY", "OPENAI_API_KEY"})
FIXTURE_ENV_PREFIX = "URI_FAKE_"


FORBIDDEN_SUBSTRINGS = ("dangerously", "danger-full-access", "bypasspermissions", "--yolo")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ExecutorSpecError(ValueError):
    pass


def valid_session_id(value) -> bool:
    """Executor-supplied session ids go into argv on resume: they must look like ids and never like flags."""
    return isinstance(value, str) and SESSION_ID_RE.match(value) is not None


def check_final_argv(argv):
    """Refuse permission/sandbox bypass anywhere in the FINAL argv: exact flags and embedded substrings."""
    if FORBIDDEN_FLAGS.intersection(argv):
        raise ExecutorSpecError("BYPASS_FLAG_REFUSED")
    for tok in argv:
        low = str(tok).lower()
        if any(f in low for f in FORBIDDEN_SUBSTRINGS):
            raise ExecutorSpecError("BYPASS_FLAG_REFUSED")
    return argv


@dataclass(frozen=True)
class ExecutorSpec:
    executor_id: str
    executable: str | None
    argv: tuple                          # tokens; "{workspace}" / "{model}" / "{session}" substituted
    stdin: str = "instructions"          # "instructions" | "none"
    version_argv: tuple = ("--version",)
    auth_env: tuple = ()
    rules: tuple = ()
    quota_markers: tuple = ("rate_limit", "rate limit", "quota", "usage limit", "insufficient_quota", "limit reached")
    resume_argv: tuple | None = None     # tokens used when resuming a recorded session (see resume_mode)
    reset_regex: str | None = None       # optional: group 1 = provider-stated reset (epoch seconds)
    rule_set_id: str = "v1"
    # "append": resume_argv is appended to argv (Claude: `--resume <id>`). "replace": resume_argv is the complete
    # token list instead of argv (Codex: `exec resume <id> ...`, a different subcommand grammar). Phase 2C.
    resume_mode: str = "append"

    def to_json(self):
        return {"executor_id": self.executor_id, "executable": self.executable, "argv": list(self.argv), "stdin": self.stdin,
                "version_argv": list(self.version_argv), "auth_env": list(self.auth_env),
                "quota_markers": list(self.quota_markers), "resume_argv": list(self.resume_argv or []),
                "rules": [{"when": r.when, "emit": r.emit, "extract": r.extract} for r in self.rules],
                "reset_regex": self.reset_regex, "rule_set_id": self.rule_set_id, "resume_mode": self.resume_mode}

    @staticmethod
    def from_json(d):
        return ExecutorSpec(d["executor_id"], d["executable"], tuple(d["argv"]), d.get("stdin", "instructions"),
                            tuple(d.get("version_argv", ("--version",))), tuple(d.get("auth_env", ())),
                            tuple(EventRule(r["when"], r["emit"], r.get("extract", {})) for r in d.get("rules", [])),
                            tuple(d.get("quota_markers", ())), tuple(d["resume_argv"]) if d.get("resume_argv") else None,
                            d.get("reset_regex"), d.get("rule_set_id", "v1"), d.get("resume_mode", "append"))

    def spec_sha256(self):
        return hashlib.sha256(json.dumps(self.to_json(), sort_keys=True).encode()).hexdigest()

    def build_argv(self, *, workspace="", model=None, session=None, resolved_executable=None):
        exe = resolved_executable or (shutil.which(self.executable) if self.executable else None)
        if not exe:
            raise ExecutorSpecError("EXECUTABLE_UNAVAILABLE")
        if self.resume_mode not in ("append", "replace"):
            raise ExecutorSpecError("BAD_RESUME_MODE")
        resuming = bool(session and self.resume_argv)
        if resuming and not valid_session_id(session):
            raise ExecutorSpecError("BAD_SESSION_ID")
        tokens = self.resume_argv if resuming and self.resume_mode == "replace" else self.argv
        out = [exe]
        for tok in tokens:
            if tok == "{model_args}":
                if model:
                    out += ["-m", model]
                continue
            out.append(tok.replace("{workspace}", workspace).replace("{model}", model or "").replace("{session}", session or ""))
        if resuming and self.resume_mode == "append":
            out += [t.replace("{session}", session) for t in self.resume_argv]
        return check_final_argv(out)

    def build_env(self, environ):
        allow = (ENV_ALLOW | set(self.auth_env)) - NEVER_FORWARD
        return {k: v for k, v in environ.items() if k in allow or k.startswith(FIXTURE_ENV_PREFIX)}

    def probe_version(self, timeout_s=20):
        exe = shutil.which(self.executable) if self.executable else None
        if not exe:
            return None
        try:
            out = subprocess.run([exe, *self.version_argv], capture_output=True, timeout=timeout_s,
                                 stdin=subprocess.DEVNULL, env=self.build_env(__import__("os").environ))
            m = re.search(r"\d+\.\d+\.\d+", out.stdout.decode("utf-8", "replace"))
            return m.group(0) if m else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    def quota_hit(self, text: str) -> bool:
        low = text.lower()
        return any(m in low for m in self.quota_markers)

    def provider_reset_wall_us(self, text: str):
        if not self.reset_regex:
            return None
        m = re.search(self.reset_regex, text)
        if not m:
            return None
        try:
            return int(float(m.group(1)) * 1_000_000)
        except (ValueError, IndexError):
            return None


# ---------------------------------------------------------------------------------------------
# Rule sets. First matching rules all emit; order is irrelevant but each label is specific.
# ---------------------------------------------------------------------------------------------

CLAUDE_RULES = (
    EventRule({"type": "system", "subtype": "init"}, "session", {"session_id": "session_id", "model": "model"}),
    # NB real capture: an auth failure arrives as result{subtype:"success", is_error:true}. subtype alone is NOT success.
    EventRule({"type": "result", "subtype": "success", "is_error": {"falsy_or_absent": True}}, "terminal_success_claim",
              {"session_id": "session_id", "result_text": "result"}),
    EventRule({"type": "result", "is_error": True}, "terminal_error_claim",
              {"session_id": "session_id", "result_text": "result", "terminal_reason": "terminal_reason"}),
    EventRule({"type": "result", "subtype": {"not": "success"}}, "terminal_error_claim",
              {"session_id": "session_id", "subtype": "subtype"}),
    EventRule({"type": "assistant"}, "agent_message", {"text": "message.content"}),
    EventRule({"type": "user", "message.content": {"present": True}}, "tool_result_batch", {}),
)

CODEX_RULES = (
    EventRule({"type": "thread.started"}, "session", {"session_id": "thread_id"}),
    EventRule({"type": "turn.completed"}, "terminal_success_claim", {"usage": "usage"}),
    EventRule({"type": "turn.failed"}, "terminal_error_claim", {"message": "error.message"}),
    EventRule({"type": "error"}, "error_event", {"message": "message"}),
    EventRule({"type": "item.completed", "item.type": "agent_message"}, "agent_message", {"text": "item.text"}),
    EventRule({"type": "item.completed", "item.type": "command_execution"}, "tool_result",
              {"command": "item.command", "exit_code": "item.exit_code", "status": "item.status"}),
    EventRule({"type": "item.completed", "item.type": "file_change"}, "file_change", {"changes": "item.changes"}),
    EventRule({"type": "item.completed", "item.type": "error"}, "warning", {"message": "item.message"}),
)

# Generic NDJSON executor used by the fixture executor and as a template for local models/harnesses.
GENERIC_RULES = (
    EventRule({"type": "session"}, "session", {"session_id": "session_id"}),
    EventRule({"type": "done", "ok": True}, "terminal_success_claim", {"summary": "summary"}),
    EventRule({"type": "done", "ok": {"not": True}}, "terminal_error_claim", {"message": "message"}),
    EventRule({"type": "tool_result"}, "tool_result", {"command": "command", "exit_code": "exit_code"}),
    EventRule({"type": "message"}, "agent_message", {"text": "text"}),
    EventRule({"type": "safe_point"}, "safe_point", {}),
    EventRule({"type": "file_change"}, "file_change", {"count": "count"}),
)

CLAUDE_CODE = ExecutorSpec(
    "claude_code", "claude",
    ("-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--setting-sources", "",
     "--permission-mode", "dontAsk", "--tools", "Read,Edit,Write,Glob,Grep", "--strict-mcp-config"),
    auth_env=("CLAUDE_CODE_OAUTH_TOKEN",), rules=CLAUDE_RULES, resume_argv=("--resume", "{session}"))

CODEX_CLI = ExecutorSpec(
    "codex_cli", "codex",
    ("exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check", "-C", "{workspace}",
     "-c", 'approval_policy="never"', "{model_args}", "-"),
    auth_env=("CODEX_API_KEY", "CODEX_HOME"), rules=CODEX_RULES,
    # `codex exec resume` (0.158.0) has no `--sandbox`/`-C`: the sandbox is set by config override and the cwd is
    # the supervised workspace (run_attempt checks cwd against the authorization scope). Instructions on stdin again.
    resume_argv=("exec", "resume", "{session}", "--json", "--skip-git-repo-check", "-c", 'approval_policy="never"',
                 "-c", 'sandbox_mode="workspace-write"', "{model_args}", "-"),
    resume_mode="replace")

GENERIC_NDJSON = ExecutorSpec("generic_ndjson", None, (), rules=GENERIC_RULES, stdin="none")

BUILTIN_SPECS = {s.executor_id: s for s in (CLAUDE_CODE, CODEX_CLI, GENERIC_NDJSON)}
