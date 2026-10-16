"""Device providers (A1 §A6). A provider lists devices of one kind and reports their capabilities and status. The
registry maps a kind to its provider; only `printer` is registered. A later `scanner` provider (Windows WIA 2.0,
built into Windows) implements the same protocol without changing callers."""
from __future__ import annotations

from typing import Protocol

from .model import Device


class DeviceProvider(Protocol):
    kind: str

    def list(self) -> list[Device]: ...

    def capabilities(self, device_id: str) -> dict: ...

    def status(self, device_id: str) -> tuple[str, str]: ...


class Registry:
    def __init__(self):
        self._by_kind: dict[str, DeviceProvider] = {}

    def register(self, provider: DeviceProvider):
        self._by_kind[provider.kind] = provider

    def get(self, kind: str) -> DeviceProvider | None:
        return self._by_kind.get(kind)

    def kinds(self) -> list[str]:
        return sorted(self._by_kind)
