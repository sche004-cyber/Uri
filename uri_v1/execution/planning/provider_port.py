"""Ports and test doubles for semantic proposal providers and advisors (Stage 2, Slice 1).

Untrusted proposal emission and optional advisory feedback. Model outputs are data,
never execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Protocol, Sequence

from .contracts import CapabilitySnapshot, ProposalInvalid, SemanticProposal


@dataclass(frozen=True)
class ProviderResult:
    """Result from a semantic proposal provider call."""
    raw_text: str
    parsed: SemanticProposal | None
    provider_id: str
    model_id: str
    config_sha256: str
    latency_ms: float
    error: str | None = None


class ProposalProvider(Protocol):
    """Protocol for semantic planning providers (configurable Main Brain or specialist)."""
    def propose(
        self,
        goal_context: str,
        snapshot_view: list[dict[str, Any]],
        candidates: Sequence[str] | Mapping[str, str],
    ) -> ProviderResult:
        ...


class FixtureProvider:
    """Test double providing pre-recorded or hand-authored proposals for deterministic qualification."""

    def __init__(
        self,
        fixtures: Mapping[str, dict[str, Any]],
        *,
        provider_id: str = "fixture_provider_test_double",
        model_id: str = "fixture_v1",
    ):
        self.fixtures = dict(fixtures)
        self.provider_id = provider_id
        self.model_id = model_id
        self.config_sha256 = hashlib.sha256(b"fixture_config_v1").hexdigest()

    def propose(
        self,
        goal_context: str,
        snapshot_view: list[dict[str, Any]],
        candidates: Sequence[str] | Mapping[str, str],
    ) -> ProviderResult:
        if goal_context not in self.fixtures:
            return ProviderResult(
                raw_text="",
                parsed=None,
                provider_id=self.provider_id,
                model_id=self.model_id,
                config_sha256=self.config_sha256,
                latency_ms=1.0,
                error="FIXTURE_NOT_FOUND",
            )

        fixture_data = self.fixtures[goal_context]
        raw_text = json.dumps(fixture_data, sort_keys=True, separators=(",", ":"))
        try:
            parsed = SemanticProposal.parse(fixture_data)
            return ProviderResult(
                raw_text=raw_text,
                parsed=parsed,
                provider_id=self.provider_id,
                model_id=self.model_id,
                config_sha256=self.config_sha256,
                latency_ms=1.0,
                error=None,
            )
        except ProposalInvalid as exc:
            return ProviderResult(
                raw_text=raw_text,
                parsed=None,
                provider_id=self.provider_id,
                model_id=self.model_id,
                config_sha256=self.config_sha256,
                latency_ms=1.0,
                error=exc.code,
            )


@dataclass(frozen=True)
class AdvisoryReport:
    """Advisory flags emitted by a proposal advisor (e.g. Needle)."""
    flags: tuple[str, ...]
    ranking: tuple[str, ...] | None
    raw_sha256: str
    advisor_invalid: bool = False


class ProposalAdvisor(Protocol):
    """Protocol for optional advisory checks (bypassed by default)."""
    def advise(
        self,
        proposal: SemanticProposal,
        snapshot: CapabilitySnapshot,
    ) -> AdvisoryReport:
        ...


class NullAdvisor:
    """Default bypassed advisor emitting no flags and granting no authority."""
    def advise(
        self,
        proposal: SemanticProposal,
        snapshot: CapabilitySnapshot,
    ) -> AdvisoryReport:
        return AdvisoryReport(
            flags=(),
            ranking=None,
            raw_sha256=hashlib.sha256(b"null_advisor").hexdigest(),
            advisor_invalid=False,
        )
