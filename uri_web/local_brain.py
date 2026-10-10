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


def make_complete(client, *, max_tokens: int = 700, timeout_s: float = 60.0):
    """client: uri_operational_intelligence.brain_client.BrainClient bound to Runtime v1."""
    from uri_operational_intelligence.reasoning_policy import FAST, tier_params
    require_loopback(client.base_url)

    def complete(messages):
        body = {"model": "local", "messages": messages, **tier_params(FAST, use="answer", max_tokens=max_tokens)}
        res = client.complete_json(body, timeout_s=timeout_s)
        return res.status, res.text
    return complete
