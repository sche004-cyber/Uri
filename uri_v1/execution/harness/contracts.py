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
import re

from uri_v1.memory.contracts import TrustedInput, negated

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


@dataclass(frozen=True)
class ElevationGrant:
    """One explicit per-run elevation, issued only from a trusted user turn that names it."""
    elevation: str
    run_scope: str
    intake: TrustedInput

    @classmethod
    def from_user(cls, intake, elevation: str, run_scope: str) -> "ElevationGrant":
        if not isinstance(intake, TrustedInput) or not intake.trusted: raise HarnessError("TRUSTED_USER_INPUT_REQUIRED")
        words = set(re.findall(r"\w+", intake.raw_text.casefold()))
        if elevation.startswith("extra_dir:"):
            named = elevation.split(":", 1)[1].replace("\\", "/").rstrip("/").split("/")[-1].casefold()
            ok = bool(named) and named in intake.raw_text.casefold()
        else:
            ok = elevation in _ELEVATIONS and bool(words & set(_ELEVATIONS[elevation]))
        if negated(intake.raw_text) or not ok or not ({"allow", "permit", "enable", "yes", "approve"} & words):
            raise HarnessError("EXPLICIT_ELEVATION_REQUIRED")
        return cls(elevation, run_scope, intake)

    def valid_for(self, run_scope: str) -> bool:
        return isinstance(self.intake, TrustedInput) and self.intake.trusted and self.run_scope == run_scope

    def __reduce__(self): raise TypeError("grants cannot be serialized")


@dataclass(frozen=True)
class PermissionProfile:
    """Default is the most restrictive posture that can do a script repair."""
    network: bool = False
    package_install: bool = False
    extra_dirs: tuple = ()
    grants: tuple = field(default=(), compare=False, repr=False)

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

    @classmethod
    def none(cls) -> "CapabilityGrant":
        return cls()

    @classmethod
    def from_user(cls, intake, items) -> "CapabilityGrant":
        if not isinstance(intake, TrustedInput) or not intake.trusted: raise HarnessError("TRUSTED_USER_INPUT_REQUIRED")
        items = tuple(sorted({(str(k), str(n)) for k, n in items}))
        if not items or negated(intake.raw_text) or any(n.casefold() not in intake.raw_text.casefold() for _, n in items):
            raise HarnessError("EXPLICIT_CAPABILITY_GRANT_REQUIRED")
        return cls(items, intake)

    def valid(self) -> bool:
        return not self.items or (isinstance(self.intake, TrustedInput) and self.intake.trusted)

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
