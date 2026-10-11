"""Adapter from the research synthesizer to the resident Brain (Runtime v1) through the existing OI BrainClient.

Local only: the base URL must be loopback, so retrieved web text is never sent to an external model provider by this
path. Parameters come from the server-side FAST tier (`reasoning_policy.tier_params`), never from content. The call is
streamed and cancellable (BrainClient), with a bounded deadline.
"""
from __future__ import annotations

import ipaddress
import threading
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
    default_timeout_s = timeout_s
    from uri_operational_intelligence.reasoning_policy import FAST, tier_params
    require_loopback(client.base_url)

    def complete(messages, *, cancel=None, timeout_s=None):
        """cancel: an object with `.cancelled` (the research job's Cancel or a user turn taking the Brain, R1-05);
        timeout_s: what is left of the job's deadline. Either closes the stream, which frees the Brain's slot."""
        body = {"model": "local", "messages": messages, **tier_params(FAST, use="answer", max_tokens=max_tokens)}
        limit = default_timeout_s if timeout_s is None else max(0.0, min(float(timeout_s), default_timeout_s))
        if cancel is None:
            res = client.complete_json(body, timeout_s=limit)
            return res.status, res.text
        from uri_operational_intelligence import brain_client as BC
        token, done = BC.CancelToken(), threading.Event()

        def watch():
            while not done.wait(0.05):
                if cancel.cancelled:
                    token.cancel("research_cancelled")
                    return
        threading.Thread(target=watch, daemon=True).start()
        try:
            res = client.stream_chat(body, cancel=token, deadlines=BC.Deadlines(
                first_token_s=limit, idle_s=min(30.0, limit), total_s=limit))
        finally:
            done.set()
        status = BC.DEADLINE_EXCEEDED if res.status in (BC.TIMEOUT_FIRST_TOKEN, BC.STALLED) else res.status
        return status, res.text
    return complete
