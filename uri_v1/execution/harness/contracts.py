"""External execution-harness contracts (M38, PROVISIONAL / NOT FROZEN).

A harness (Claude Code, Codex CLI, a future compatible harness) is an external
worker, not URI's Brain (ruling D-A). It receives a bounded Execution Capsule,
works inside URI's workspace and permission boundaries, and returns claims.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re

from uri_v1.memory.contracts import TrustedInput
from ..approval import approval_declined


def _whole_token(text: str, token: str) -> bool:
    """True only if `token` appears in `text` as a standalone token, not as a
    substring of a longer word (an incidental letter or fragment must not
    satisfy an explicit grant)."""
    if not token: return False
    return re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", text) is not None


# A path the user actually wrote: starting with a drive letter, a UNC/root separator or
# `~`, either bare (up to whitespace/quote) or quoted (may contain spaces). A bare word
# ("reports") is never read as a path. The two scans run independently so an
# apostrophe elsewhere in the sentence ("it's", "Chetan's") cannot swallow a bare path.
_ANCHOR = r"(?:[A-Za-z]:[\\/]|[\\/]|~)"
_BARE_PATH = re.compile(_ANCHOR + r"[^\s\"'<>|,;]*")
_QUOTED_PATH = re.compile(r'"(' + _ANCHOR + r'[^"]*)"|\'(' + _ANCHOR + r"[^']*)'")


def _resolve_dir(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def _named_paths(text: str):
    for m in _BARE_PATH.finditer(text): yield m.group(0).rstrip(".:!?)")  # sentence punctuation
    for m in _QUOTED_PATH.finditer(text): yield (m.group(1) or m.group(2)).strip()


def _names_same_path(text: str, granted: str, *, resolve=_resolve_dir, normcase=os.path.normcase) -> bool:
    """True iff some path the user wrote in `text` resolves to the same directory as
    `granted` (an already-resolved path).

    The comparison is semantic, never textual (Antigravity a87e158 F-3): each path the
    user typed is resolved exactly the way the grant itself was, then compared with the
    platform's own case/separator rules. The earlier literal search looked for the
    *resolved* form in the user's words, so on Windows "allow access to /home/someone/e"
    was checked for "c:\\home\\someone\\e" (a drive letter the user never typed) and
    refused; "D:/Reports" vs "d:\\reports" failed the same way. Equality, not prefix,
    keeps round 3's finding-3 guarantee: naming `.../reports/2026` never authorizes
    `.../reports`, and naming a parent never authorizes a child.
    """
    target = normcase(granted)
    for raw in _named_paths(text):
        try:
            if normcase(resolve(raw)) == target: return True
        except (OSError, RuntimeError, ValueError):
            continue
    return False


CAPSULE_SCHEMA_VERSION = "m38.capsule.v1"


class HarnessType(str, Enum):
    CLAUDE_CODE = "CLAUDE_CODE"
    CODEX_CLI = "CODEX_CLI"


class ClaimedOutcome(str, Enum):
    COMPLETED_CLAIMED = "completed_claimed"
    FAILED = "failed"
    STOPPED = "stopped"
    OUTCOME_UNKNOWN = "outcome_unknown"
    QUESTION = "question"


class HarnessError(ValueError):
    """Typed failure: the reason code is the message."""


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# -- permissions (OD-4) ---------------------------------------------------------------------------

_ELEVATIONS = {"network": ("network", "internet", "web"), "package_install": ("install", "pip", "package", "packages")}
# Directories whose exposure would defeat the point of scoping at all, even though
# they are not $HOME itself (D-5/M-4): a parent of $HOME (e.g. `/home`) grants
# everything under every user's home the same way `/` would, and a well-known
# credential directory directly under $HOME (e.g. `~/.ssh`) is exactly the kind of
# thing an "allow access to my files" grant must never quietly cover.
_SENSITIVE_HOME_CHILDREN = frozenset({".ssh", ".gnupg", ".aws", ".docker", ".kube", ".config", ".netrc"})


# Issued only by the `from_user` constructors below. A grant built directly (or copied
# with `dataclasses.replace`) never validates, whatever its text: `from_user` is the only
# place the full consent bar is applied -- trusted, not declined, an approval word, the
# elevation word, and the extra_dir path rule (Codex audit, requalification of 6420f3e:
# ElevationGrant("network", ..., intake("thanks")) validated and elevated to network).
_ISSUED = object()


@dataclass(frozen=True)
class ElevationGrant:
    """One explicit per-run elevation, issued only from a trusted user turn that names it."""
    elevation: str
    run_scope: str
    intake: TrustedInput
    _issued: object = field(default=None, init=False, compare=False, repr=False)

    @classmethod
    def from_user(cls, intake, elevation: str, run_scope: str) -> "ElevationGrant":
        if not isinstance(intake, TrustedInput) or not intake.trusted: raise HarnessError("TRUSTED_USER_INPUT_REQUIRED")
        if not run_scope: raise HarnessError("RUN_SCOPE_REQUIRED")
        words = set(re.findall(r"\w+", intake.raw_text.casefold()))
        if elevation.startswith("extra_dir:"):
            resolved = _resolve_dir(elevation.split(":", 1)[1])
            resolved_path = Path(resolved)
            home = Path.home().resolve()
            # D-5/M-4: reject the granted path itself, any filesystem root (`/`, or any
            # Windows drive root such as `D:\\`, not only the one holding $HOME), any
            # ancestor of $HOME (which would expose $HOME and everything alongside it the
            # same way `/` would), and any well-known credential directory directly under
            # $HOME. A Windows UNC/network path is refused too: no file-tool permission
            # rule form for it has been confirmed against Claude Code, so it fails closed.
            if (resolved_path.parent == resolved_path or resolved_path == home or resolved_path in home.parents
                    or resolved.startswith("\\\\")
                    or (resolved_path.parent == home and resolved_path.name.casefold() in _SENSITIVE_HOME_CHILDREN)):
                raise HarnessError("EXTRA_DIR_NOT_ALLOWED")
            # The user's own words must name the literal directory being granted, not
            # merely an incidental word that happens to match its last path segment
            # (D-5/M-4): matching on the basename alone let a sentence that never
            # mentioned the real path at all still satisfy the grant.
            ok = _names_same_path(intake.raw_text, resolved)
            elevation = f"extra_dir:{resolved}"
        else:
            ok = elevation in _ELEVATIONS and bool(words & set(_ELEVATIONS[elevation]))
        if approval_declined(intake.raw_text) or not ok or not ({"allow", "permit", "enable", "yes", "approve"} & words):
            raise HarnessError("EXPLICIT_ELEVATION_REQUIRED")
        grant = cls(elevation, run_scope, intake)
        object.__setattr__(grant, "_issued", _ISSUED)
        return grant

    def valid_for(self, run_scope: str) -> bool:
        # Re-checks the same decline test `from_user` applies (Codex audit, 2026-09-28):
        # a grant built directly, bypassing `from_user`, from declined text must not
        # pass this gate either.
        return (self._issued is _ISSUED and isinstance(self.intake, TrustedInput) and self.intake.trusted
                and self.run_scope == run_scope and not approval_declined(self.intake.raw_text))

    def __reduce__(self): raise TypeError("grants cannot be serialized")


@dataclass(frozen=True)
class PermissionProfile:
    """Default is the most restrictive posture that can do a script repair.

    Every elevated field must be backed by a matching `ElevationGrant` in
    `grants` (H-3/P3): a profile cannot be built with `network`,
    `package_install` or `extra_dirs` set unless `elevate()` put it there.
    """
    network: bool = False
    package_install: bool = False
    extra_dirs: tuple = ()
    grants: tuple = field(default=(), compare=False, repr=False)

    def __post_init__(self):
        if not all(isinstance(g, ElevationGrant) and g._issued is _ISSUED for g in self.grants):
            raise HarnessError("ELEVATION_GRANT_INVALID")
        granted_dirs = {g.elevation.split(":", 1)[1] for g in self.grants if g.elevation.startswith("extra_dir:")}
        if self.network and not any(g.elevation == "network" for g in self.grants): raise HarnessError("ELEVATION_GRANT_INVALID")
        if self.package_install and not any(g.elevation == "package_install" for g in self.grants): raise HarnessError("ELEVATION_GRANT_INVALID")
        if set(self.extra_dirs) - granted_dirs: raise HarnessError("ELEVATION_GRANT_INVALID")

    def elevate(self, grant: ElevationGrant, run_scope: str) -> "PermissionProfile":
        if not isinstance(grant, ElevationGrant) or not grant.valid_for(run_scope): raise HarnessError("ELEVATION_GRANT_INVALID")
        if grant.elevation == "network": return PermissionProfile(True, self.package_install, self.extra_dirs, self.grants + (grant,))
        if grant.elevation == "package_install": return PermissionProfile(self.network, True, self.extra_dirs, self.grants + (grant,))
        if grant.elevation.startswith("extra_dir:"):
            return PermissionProfile(self.network, self.package_install, self.extra_dirs + (grant.elevation.split(":", 1)[1],), self.grants + (grant,))
        raise HarnessError("UNKNOWN_ELEVATION")

    def to_dict(self) -> dict:
        return {"network": self.network, "package_install": self.package_install, "extra_dirs": list(self.extra_dirs),
                "elevations": [g.elevation for g in self.grants]}


# -- controlled capability use ----------------------------------------------------------------------

@dataclass(frozen=True)
class CapabilityGrant:
    """Discovered native capabilities the user explicitly allows for this one run (default: none)."""
    items: tuple = ()            # ((kind, name), ...)
    intake: TrustedInput | None = field(default=None, compare=False, repr=False)
    _issued: object = field(default=None, init=False, compare=False, repr=False)

    @classmethod
    def none(cls) -> "CapabilityGrant":
        return cls()

    @classmethod
    def from_user(cls, intake, items) -> "CapabilityGrant":
        if not isinstance(intake, TrustedInput) or not intake.trusted: raise HarnessError("TRUSTED_USER_INPUT_REQUIRED")
        items = tuple(sorted({(str(k), str(n)) for k, n in items}))
        text = intake.raw_text.casefold()
        if not items or approval_declined(intake.raw_text) or any(not _whole_token(text, n.casefold()) for _, n in items):
            raise HarnessError("EXPLICIT_CAPABILITY_GRANT_REQUIRED")
        grant = cls(items, intake)
        object.__setattr__(grant, "_issued", _ISSUED)
        return grant

    def valid(self) -> bool:
        # Re-checks the same decline test `from_user` applies (Codex audit, 2026-09-28):
        # a grant built directly, bypassing `from_user`, from declined text must not
        # pass this gate either.
        if not self.items: return True
        return (self._issued is _ISSUED and isinstance(self.intake, TrustedInput) and self.intake.trusted
                and not approval_declined(self.intake.raw_text))

    def to_dict(self) -> dict:
        return {"items": [list(x) for x in self.items]}


# -- capsule and result -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Limits:
    timeout_s: float = 900
    inactivity_s: float = 300
    max_budget_usd: float | None = 2.0

    def __post_init__(self):
        if not 1 <= self.timeout_s <= 7200 or not 1 <= self.inactivity_s <= self.timeout_s: raise HarnessError("INVALID_LIMITS")
        if self.max_budget_usd is not None and not 0 < self.max_budget_usd <= 100: raise HarnessError("INVALID_LIMITS")


@dataclass(frozen=True)
class ExecutionCapsule:
    """Everything a harness may see, by value or by hash."""
    capsule_id: str
    run_id: str
    task_id: str
    trace_id: str
    harness_type: HarnessType
    workspace_files: str
    input_manifest: tuple
    instructions_path: str
    instructions_sha256: str
    acceptance: dict
    acceptance_sha256: str
    posture: PermissionProfile
    capabilities: CapabilityGrant
    limits: Limits
    schema_version: str = CAPSULE_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "capsule_id": self.capsule_id, "run_id": self.run_id,
                "task_id": self.task_id, "trace_id": self.trace_id, "harness_type": self.harness_type.value,
                "workspace": {"strategy": "COPY_IN_COPY_OUT", "files": self.workspace_files},
                "input_manifest": list(self.input_manifest),
                "instructions": {"path": self.instructions_path, "sha256": self.instructions_sha256},
                "acceptance": self.acceptance, "acceptance_sha256": self.acceptance_sha256,
                "posture": self.posture.to_dict(), "capabilities": self.capabilities.to_dict(),
                "limits": {"timeout_s": self.limits.timeout_s, "inactivity_s": self.limits.inactivity_s,
                           "max_budget_usd": self.limits.max_budget_usd}}

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical(self.to_dict())).hexdigest()


UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class HarnessRunResult:
    """Claims only. `changed_artifacts` is never taken from here; URI computes it."""
    claimed_outcome: ClaimedOutcome
    exit_code: int | None
    timed_out: bool
    inactivity_killed: bool
    error_family: str | None
    question: str | None
    final_message_sha256: str | None
    session_ref: dict | None             # opaque, non-authoritative; never enters Memory
    usage: dict                          # harness-reported only; missing -> UNAVAILABLE
    log_sha256: str
    log_bytes: int

    def to_claim(self) -> dict:
        return {"claimed_outcome": self.claimed_outcome.value, "exit_code": self.exit_code, "timed_out": self.timed_out,
                "inactivity_killed": self.inactivity_killed, "error_family": self.error_family,
                "question_sha256": hashlib.sha256(self.question.encode()).hexdigest() if self.question else None,
                "final_message_sha256": self.final_message_sha256, "usage": self.usage,
                "log_sha256": self.log_sha256, "log_bytes": self.log_bytes, "session_ref": self.session_ref}
