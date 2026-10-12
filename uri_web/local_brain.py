"""Adapter from the research synthesizer to the resident Brain (Runtime v1) through the existing OI BrainClient.

Local only: the base URL must be loopback, so retrieved web text is never sent to an external model provider by this
path. Parameters come from the server-side FAST tier (`reasoning_policy.tier_params`), never from content. The call is
streamed and cancellable (BrainClient), with a bounded deadline.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


class NotLocal(ValueError):
    pass


def require_loopback(base_url: str) -> None:
    host = urlsplit(base_url).hostname or ""
    try:
        ok = ipaddress.ip_address(host).is_loopback
    except ValueError:
        ok = False
    if not ok:
        raise NotLocal("BRAIN_ENDPOINT_NOT_LOOPBACK")


def loopback_client(base_url: str):
    """A BrainClient that never routes through a proxy (interim review F7).

    The accepted OI BrainClient builds its httpx client with the default `trust_env=True`; on Windows a registry
    system proxy without a bypass list could then carry a loopback request (and the shared content in it) off the
    machine. This subclass pins `trust_env=False`; the accepted class is not modified."""
    import httpx
    from uri_operational_intelligence import brain_client as BC
    require_loopback(base_url)

    class LoopbackBrainClient(BC.BrainClient):
        def _get(self):
            with self._lock:
                if self._client is None:
                    self._client = httpx.Client(
                        base_url=self.base_url, http2=False, trust_env=False,
                        timeout=httpx.Timeout(connect=self.connect_timeout, read=None, write=30.0, pool=10.0),
                        limits=httpx.Limits(max_keepalive_connections=2, max_connections=4, keepalive_expiry=300.0))
                return self._client
    return LoopbackBrainClient(base_url)


def make_complete(client, *, max_tokens: int = 700, timeout_s: float = 60.0):
    """client: uri_operational_intelligence.brain_client.BrainClient bound to Runtime v1."""
    from uri_operational_intelligence.reasoning_policy import FAST, tier_params
    require_loopback(client.base_url)

    def complete(messages):
        body = {"model": "local", "messages": messages, **tier_params(FAST, use="answer", max_tokens=max_tokens)}
        res = client.complete_json(body, timeout_s=timeout_s)
        return res.status, res.text
    return complete
