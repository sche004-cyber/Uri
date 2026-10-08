"""Edge Intelligence provider slot (Step 3, first tier).

No concrete implementation here — interface only. Needle 3 is the planned
first implementation but must occupy this slot, not be hard-coded into it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from uri_v1.turn.contracts import ContextPack, EdgeOutcome


class EdgeIntelligenceProvider(ABC):
    """Replaceable provider slot: attempt to handle a turn, or escalate."""

    @abstractmethod
    def attempt(self, context_pack: ContextPack) -> EdgeOutcome:
        raise NotImplementedError
