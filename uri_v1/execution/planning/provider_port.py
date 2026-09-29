"""Proposal provider and advisor ports (Stage 2 §2.8, §2.9; F5, F9).

Slice 1 ships only test doubles: `FixtureProvider` returns a recorded or
hand-authored proposal, and `NullAdvisor` is the default (bypassed) advisor.
No real provider adapter exists in this step. Malformed output, a transport
failure or a timeout is a typed no-completion, never a default CAN_DO.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Protocol

from .contracts import MAX_PROPOSAL_BYTES, nesting_exceeds

# Raw provider text is refused before parsing above this size. Canonical proposals are capped at
# MAX_PROPOSAL_BYTES; the raw cap leaves room for whitespace and escapes.
MAX_RAW_BYTES = 4 * MAX_PROPOSAL_BYTES


@dataclass(frozen=True)
class ProviderResult:
    raw_text: str | None
    parsed: dict | None
    provider_id: str
    model_id: str
    config_sha256: str
    latency_ms: float
    error: str | None = None          # PROPOSAL_INVALID | PROVIDER_UNAVAILABLE

    @property
    def raw_sha256(self) -> str | None:
        return hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest() if self.raw_text is not None else None


@dataclass(frozen=True)
class AdvisoryReport:
    flags: tuple
    ranking: tuple | None
    raw_sha256: str | None


class ProposalProvider(Protocol):
    def propose(self, goal_context, snapshot_view, candidates) -> ProviderResult: ...


class ProposalAdvisor(Protocol):
    def advise(self, proposal, snapshot) -> AdvisoryReport: ...


def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys): raise ValueError("DUPLICATE_KEY")
    return dict(pairs)


def parse_raw(raw_text):
    """Strict JSON: one object, no duplicate keys, bounded size and nesting. None on anything else."""
    if not isinstance(raw_text, str) or len(raw_text) > MAX_RAW_BYTES: return None
    if len(raw_text.encode("utf-8", "surrogatepass")) > MAX_RAW_BYTES: return None
    try: value = json.loads(raw_text, object_pairs_hook=_no_duplicate_keys)
    except (ValueError, RecursionError): return None
    return value if isinstance(value, dict) and not nesting_exceeds(value) else None


class FixtureProvider:
    """TEST DOUBLE. Returns a fixed proposal text, or simulates a provider failure."""
    provider_id = "fixture"
    model_id = "fixture-test-double"

    def __init__(self, raw_text: str | None = None, *, fail: str | None = None):
        if fail not in (None, "timeout", "unavailable"): raise ValueError("FIXTURE_FAIL_MODE")
        self.raw_text, self.fail = raw_text, fail
        self.config_sha256 = hashlib.sha256(json.dumps({"raw": raw_text, "fail": fail}, sort_keys=True).encode()).hexdigest()

    def propose(self, goal_context, snapshot_view, candidates) -> ProviderResult:
        started = time.perf_counter()
        ms = lambda: round((time.perf_counter() - started) * 1000, 3)
        if self.fail is not None:
            return ProviderResult(None, None, self.provider_id, self.model_id, self.config_sha256, ms(), "PROVIDER_UNAVAILABLE")
        parsed = parse_raw(self.raw_text)
        return ProviderResult(self.raw_text, parsed, self.provider_id, self.model_id, self.config_sha256, ms(),
                              None if parsed is not None else "PROPOSAL_INVALID")


class NullAdvisor:
    """Default advisor: bypassed. It can add no flag and admits nothing."""

    def advise(self, proposal, snapshot) -> AdvisoryReport:
        return AdvisoryReport((), None, None)
