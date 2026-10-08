"""Extended Intelligence provider slot (Step 3, final tier).

Local/cloud/provider-neutral. No concrete implementation here — interface
only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from uri_v1.turn.contracts import ContextPack, IntelligenceResult


class ExtendedIntelligenceProvider(ABC):
    """Replaceable provider slot: handle a turn that escalated all the way up."""

    @abstractmethod
    def handle(self, context_pack: ContextPack) -> IntelligenceResult:
        raise NotImplementedError
