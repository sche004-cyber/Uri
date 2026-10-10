"""SafeFetcher: the only way W1 reads the public web.

Per hop (the first request and every redirect):
  1. `netpolicy.check_url` (scheme, userinfo, port, local names, numeric-ambiguous hosts, literal addresses);
  2. resolve the host ONCE and refuse the hop if ANY answer is not a public unicast address;
  3. connect to the validated address (pinned): the request goes to that IP with the original Host header and TLS
     SNI/certificate name, so a second DNS answer (rebinding) is never used.
Redirects are handled here (never by the HTTP library), at most `max_redirects`. Bodies are streamed with a byte cap,
a total deadline and cooperative cancellation. No cookies, no credentials, no proxies from the environment.

Egress modes:
  * "direct" (default, production): pinned connection as above.
  * "proxy": an explicitly configured forward proxy does the resolution and connection. URL checks still apply and
    local resolution is attempted when available, but rebinding protection then depends on the proxy. Records say
    `egress="proxy"`. Used only where direct egress is impossible (e.g. a cloud development container).
"""
from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from . import netpolicy as NP
from . import records as R

USER_AGENT = "URI-WebIntelligence/1.0 (read-only research; +local)"
REDIRECT_CODES = (301, 302, 303, 307, 308)
TEXT_TYPES = {
    "text/html": "html", "application/xhtml+xml": "html", "text/plain": "text",
    "application/rss+xml": "feed", "application/atom+xml": "feed", "application/xml": "feed", "text/xml": "feed",
    "application/feed+json": "json", "application/json": "json",
}
_CHARSET = re.compile(r"charset=([A-Za-z0-9_.:-]+)", re.I)
_META_CHARSET = re.compile(rb"<meta[^>]+charset=[\"']?([A-Za-z0-9_.:-]+)", re.I)


def system_resolver(host: str, port: int) -> list:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    seen = []
    for info in infos:
        addr = info[4][0]
        if addr not in seen:
            seen.append(addr)
    return seen


class _Pinned(httpx.BaseTransport):
    """Send the request to a validated address while keeping the original Host and TLS server name."""

    def __init__(self, inner: httpx.BaseTransport, address: str, host: str):
        self.inner, self.address, self.host = inner, address, host

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self.host:
            raise httpx.ConnectError("PIN_HOST_MISMATCH", request=request)
        default = NP.DEFAULT_PORTS[request.url.scheme]
        port = request.url.port
        host_header = self.host if port in (None, default) else f"{self.host}:{port}"
        request.headers["Host"] = host_header
        request.url = request.url.copy_with(host=self.address)
        request.extensions = dict(request.extensions, sni_hostname=self.host)
        return self.inner.handle_request(request)

    def close(self):
        self.inner.close()


class CancelFlag:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


@dataclass
class FetchResult:
    record: R.SourceRecord
    body: bytes = b""
    text: str = ""
    kind: Optional[str] = None     # html | text | feed | json

    @property
    def ok(self):
        return self.record.ok


class SafeFetcher:
    def __init__(self, *, resolver: Callable = system_resolver, transport: Optional[httpx.BaseTransport] = None,
                 egress: str = "direct", proxy: Optional[str] = None, connect_timeout: float = 5.0,
                 read_timeout: float = 10.0, total_timeout: float = 20.0, max_bytes: int = 3_000_000,
                 max_redirects: int = 5, honour_robots: bool = True, allowed_ports=NP.ALLOWED_PORTS,
                 clock: Callable = time.monotonic):
        if egress not in ("direct", "proxy"):
            raise ValueError("EGRESS_MODE")
        if egress == "proxy" and not proxy and transport is None:
            raise ValueError("PROXY_REQUIRED")
        self.resolver, self.egress, self.proxy = resolver, egress, proxy
        self._transport = transport
        self.timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=read_timeout, pool=connect_timeout)
        self.total_timeout, self.max_bytes, self.max_redirects = total_timeout, max_bytes, max_redirects
        self.honour_robots, self.allowed_ports, self.clock = honour_robots, frozenset(allowed_ports), clock
        self._robots: dict = {}
        self.connections: list = []    # (host, address) per hop, for audit and tests

    # ---- transport -----------------------------------------------------------------------------
    def _inner(self) -> httpx.BaseTransport:
        if self._transport is not None:
            return self._transport
        if self.egress == "proxy":
            return httpx.HTTPTransport(proxy=self.proxy, retries=0, trust_env=False)
        return httpx.HTTPTransport(retries=0, trust_env=False)

    def _resolve_checked(self, target: NP.Target) -> Optional[str]:
        """Return the pinned address (direct) or None (proxy). Raises EgressRefused."""
        if target.is_literal:
            return target.host
        try:
            addresses = list(self.resolver(target.host, target.port))
        except OSError:
            if self.egress == "proxy":
                return None          # the proxy resolves; URL-level checks already passed
            raise NP.EgressRefused("DNS_FAILED") from None
        if not addresses:
            raise NP.EgressRefused("DNS_EMPTY")
        for a in addresses:          # ANY non-public answer refuses the hop (no "pick the good one")
            NP.check_address(a)
        return addresses[0] if self.egress == "direct" else None

    # ---- robots --------------------------------------------------------------------------------
    def _robots_allows(self, url: str, deadline: float, cancel) -> str:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = None
            res = self._get(origin + "/robots.txt", deadline, cancel, robots=False, max_bytes=200_000)
            if res.record.ok and res.kind == "text":
                parser = RobotFileParser()
                parser.parse(res.text.splitlines())
            elif res.record.fetch_status == R.HTTP_ERROR and res.record.http_status in (401, 403):
                parser = "DISALLOW_ALL"
            self._robots[origin] = parser
        parser = self._robots[origin]
        if parser is None:
            return "UNAVAILABLE"
        if parser == "DISALLOW_ALL":
            return "DISALLOWED"
        return "ALLOWED" if parser.can_fetch(USER_AGENT, url) else "DISALLOWED"

    # ---- fetch ---------------------------------------------------------------------------------
    def fetch(self, url: str, *, cancel=None, robots: Optional[bool] = None) -> FetchResult:
        deadline = self.clock() + self.total_timeout
        return self._get(url, deadline, cancel, robots=self.honour_robots if robots is None else robots,
                         max_bytes=self.max_bytes)

    def _get(self, url, deadline, cancel, *, robots, max_bytes) -> FetchResult:
        rec = R.SourceRecord(requested_url=url, egress=self.egress)
        current, chain = url, []
        if robots:
            try:
                NP.check_url(url, allowed_ports=self.allowed_ports)
            except NP.EgressRefused as exc:
                rec.fetch_status, rec.refusal_code = R.REFUSED, exc.code
                return FetchResult(rec)
            rec.robots_decision = self._robots_allows(url, deadline, cancel)
            if rec.robots_decision == "DISALLOWED":
                rec.fetch_status = R.ROBOTS_DISALLOWED
                return FetchResult(rec)
        for _hop in range(self.max_redirects + 1):
            if cancel is not None and cancel.cancelled:
                rec.fetch_status = R.CANCELLED
                return FetchResult(rec)
            try:
                target = NP.check_url(current, allowed_ports=self.allowed_ports)
                address = self._resolve_checked(target)
            except NP.EgressRefused as exc:
                rec.fetch_status, rec.refusal_code = R.REFUSED, exc.code
                rec.redirect_chain = chain
                return FetchResult(rec)
            inner = self._inner()
            transport = _Pinned(inner, address, target.host) if address is not None else inner
            self.connections.append((target.host, address))
            rec.connected_address = address
            try:
                result = self._one(current, transport, deadline, cancel, rec, max_bytes)
            finally:
                if self._transport is None:
                    transport.close()
            if result is None:          # a terminal status was written into rec
                rec.redirect_chain = chain
                return FetchResult(rec)
            status, location, body, ctype = result
            if status in REDIRECT_CODES and location:
                chain.append({"url": current, "status": status})
                current = urljoin(current, location)
                continue
            rec.final_url, rec.redirect_chain, rec.http_status = current, chain, status
            if status >= 400:
                rec.fetch_status = R.HTTP_ERROR
                return FetchResult(rec)
            mime = (ctype or "").split(";", 1)[0].strip().lower()
            kind = TEXT_TYPES.get(mime)
            rec.content_type, rec.bytes, rec.sha256 = mime or None, len(body), R.sha256_bytes(body)
            if kind is None:
                rec.fetch_status, rec.analysed_scope = R.UNSUPPORTED_CONTENT_TYPE, R.METADATA_ONLY
                return FetchResult(rec)
            rec.fetch_status = R.OK
            return FetchResult(rec, body=body, text=_decode(body, ctype), kind=kind)
        rec.fetch_status, rec.redirect_chain = R.TOO_MANY_REDIRECTS, chain
        return FetchResult(rec)

    def _one(self, url, transport, deadline, cancel, rec, max_bytes):
        remaining = deadline - self.clock()
        if remaining <= 0:
            rec.fetch_status = R.TIMED_OUT
            return None
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "text/plain;q=0.8,application/json;q=0.5", "Accept-Encoding": "identity"}
        try:
            with httpx.Client(transport=transport, timeout=self.timeout, follow_redirects=False, trust_env=False,
                              cookies=None) as client:
                with client.stream("GET", url, headers=headers) as resp:
                    status = resp.status_code
                    if status in REDIRECT_CODES:
                        return status, resp.headers.get("location"), b"", None
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        rec.http_status, rec.fetch_status = status, R.TOO_LARGE
                        return None
                    buf = bytearray()
                    for chunk in resp.iter_bytes():
                        if cancel is not None and cancel.cancelled:
                            rec.fetch_status = R.CANCELLED
                            return None
                        if self.clock() > deadline:
                            rec.fetch_status = R.TIMED_OUT
                            return None
                        buf += chunk
                        if len(buf) > max_bytes:
                            rec.http_status, rec.fetch_status = status, R.TOO_LARGE
                            return None
                    return status, None, bytes(buf), resp.headers.get("content-type")
        except httpx.TimeoutException:
            rec.fetch_status = R.TIMED_OUT
        except (httpx.HTTPError, OSError, ValueError):
            rec.fetch_status = R.UNREACHABLE
        return None


def _decode(body: bytes, ctype: Optional[str]) -> str:
    m = _CHARSET.search(ctype or "")
    enc = m.group(1) if m else None
    if enc is None:
        mm = _META_CHARSET.search(body[:4096])
        enc = mm.group(1).decode("ascii", "ignore") if mm else "utf-8"
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
