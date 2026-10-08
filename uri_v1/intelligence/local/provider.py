"""Local Agentic Intelligence provider slot (Step 3, second tier).

Optional 2B-4B local model. No concrete implementation here — interface
only, and the local model itself must remain replaceable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from uri_v1.turn.contracts import ContextPack, EdgeOutcome


class LocalIntelligenceProvider(ABC):
    """Replaceable provider slot: attempt to handle a turn, or escalate."""

    @abstractmethod
    def attempt(self, context_pack: ContextPack) -> EdgeOutcome:
        raise NotImplementedError
