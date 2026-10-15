"""Device model (A1 §A6)."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

KINDS = ("printer", "scanner")
CONNECTIONS = ("usb", "network", "virtual", "unknown")
STATUSES = ("ready", "offline", "error", "busy", "unknown")


@dataclass
class Device:
    id: str
    kind: str
    name: str                        # untrusted text (a network printer can carry any name); shown, never interpreted
    connection: str = "unknown"
    is_default: bool = False
    status: str = "unknown"
    status_detail: str = ""
    capabilities: dict = field(default_factory=dict)
    port: str = ""
    server: str = ""
    first_seen: float | None = None
    last_seen: float | None = None
    new: bool = False

    def __post_init__(self):
        if self.kind not in KINDS or self.connection not in CONNECTIONS or self.status not in STATUSES:
            raise ValueError("bad device")

    def view(self) -> dict:
        return asdict(self)


def device_id(kind: str, name: str) -> str:
    """A stable id from the kind and name (names are unique per Windows print queue)."""
    return hashlib.sha256(f"{kind}\x00{name}".encode("utf-8")).hexdigest()[:16]
