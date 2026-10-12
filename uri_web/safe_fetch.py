"""SafeFetcher: the only way W1 reads the public web.

Per hop (the first request and every redirect):
  1. `netpolicy.check_url` (scheme, userinfo, port, local names, numeric-ambiguous hosts, literal addresses);
  2. resolve the host ONCE and refuse the hop if ANY answer is not a public unicast address (the lookup runs under the
     same total deadline and cancel flag, R9-06);
  3. connect to the validated address (pinned): the request goes to that IP with the original Host header and TLS
     SNI/certificate name, so a second DNS answer (rebinding) is never used.
Redirects are handled here (never by the HTTP library), at most `max_redirects`. Bodies are streamed with a byte cap,
a total deadline and cooperative cancellation. The deadline and the cancel flag are enforced on the whole request by a
watchdog that shuts the hop's sockets down (R4-03), so a server that drips header bytes or chunk framing slower than
the read timeout cannot hold a fetch past its budget. No cookies, no credentials, no proxies from the environment.

Egress modes:
  * "direct" (default, production): pinned connection as above.
  * "proxy": an explicitly configured forward proxy does the resolution and connection. URL checks still apply and
    local resolution is attempted when available, but rebinding protection then depends on the proxy. Records say
    `egress="proxy"`. Used only where direct egress is impossible (e.g. a cloud development container).
"""
from __future__ import annotations

import re
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpcore
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


class _WatchedStream(httpcore.NetworkStream):
    """A network stream whose socket the watchdog can shut down from another thread (TLS keeps the registration)."""

    def __init__(self, inner, backend):
        self.inner, self.backend = inner, backend
        backend.streams.append(self)

    def read(self, max_bytes, timeout=None):
        return self.inner.read(max_bytes, timeout)

    def write(self, buffer, timeout=None):
        self.inner.write(buffer, timeout)

    def close(self):
        self.inner.close()

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.inner = self.inner.start_tls(ssl_context, server_hostname, timeout)
        return self

    def get_extra_info(self, info):
        return self.inner.get_extra_info(info)

    def kill(self):
        sock = self.inner.get_extra_info("socket")
        if sock is not None:
            try:      # socket.socket.shutdown, not SSLSocket's: wake a recv blocked in the request thread now
                socket.socket.shutdown(sock, socket.SHUT_RDWR)
            except OSError:
                pass


class _WatchedBackend(httpcore.NetworkBackend):
    def __init__(self):
        self.inner, self.streams, self.killed = httpcore.SyncBackend(), [], False

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        stream = _WatchedStream(self.inner.connect_tcp(host, port, timeout, local_address, socket_options), self)
        if self.killed:           # the deadline passed while connecting
            stream.kill()
        return stream

    def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise httpcore.ConnectError("UNIX_SOCKET_REFUSED")

    def sleep(self, seconds):
        self.inner.sleep(seconds)

    def kill(self):
        self.killed = True
        for s in list(self.streams):
            s.kill()


class _Watchdog:
    """Shuts the hop's sockets down once the total deadline passes or the cancel flag is set (R4-03)."""

    POLL = 0.05

    def __init__(self, backend, deadline, cancel, clock):
        self.backend, self.deadline, self.cancel, self.clock = backend, deadline, cancel, clock
        self.reason, self._done = None, threading.Event()
        self._thread = threading.Thread(target=self._run, name="safe-fetch-watchdog", daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._done.set()
        self._thread.join()

    def _run(self):
        while not self._done.wait(self.POLL):
            if self.cancel is not None and self.cancel.cancelled:
                self.reason = R.CANCELLED
            elif self.clock() > self.deadline:
                self.reason = R.TIMED_OUT
            if self.reason is not None:
                if self.backend is not None:
                    self.backend.kill()
                return


class _Stop(Exception):
    def __init__(self, status):
        super().__init__(status)
        self.status = status


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
                 clock: Callable = time.monotonic, proxy_unresolved_ok=(), extra_types=None):
        if egress not in ("direct", "proxy"):
            raise ValueError("EGRESS_MODE")
        if egress == "proxy" and not proxy and transport is None:
            raise ValueError("PROXY_REQUIRED")
        self.resolver, self.egress, self.proxy = resolver, egress, proxy
        self._transport = transport
        self.timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=read_timeout, pool=connect_timeout)
        self.total_timeout, self.max_bytes, self.max_redirects = total_timeout, max_bytes, max_redirects
        self.honour_robots, self.allowed_ports, self.clock = honour_robots, frozenset(allowed_ports), clock
        # Proxy mode only: public host names the operator allows even when they cannot be resolved locally (the
        # proxy resolves them; rebinding protection then depends on the proxy). Empty by default.
        self.proxy_unresolved_ok = frozenset(h.lower() for h in proxy_unresolved_ok)
        # SSRF-1: content types a caller can also receive (mime -> kind), e.g. documents for uri_core fetch_url. Empty by
        # default, so W1 behaviour is unchanged. Bodies of these kinds are returned as bytes, not decoded to text.
        self.extra_types = dict(extra_types or {})
        self._robots: dict = {}
        self.connections: list = []    # (host, address) per hop, for audit and tests

    # ---- transport -----------------------------------------------------------------------------
    def _inner(self):
        """(transport, watched backend or None). Our own transports open sockets through a backend the watchdog can
        shut down; an injected transport (tests) has none, and the chunk-loop checks still apply to it."""
        if self._transport is not None:
            return self._transport, None
        if self.egress == "proxy":
            t = httpx.HTTPTransport(proxy=self.proxy, retries=0, trust_env=False)
        else:
            t = httpx.HTTPTransport(retries=0, trust_env=False)
        backend = _WatchedBackend()
        pool = getattr(t, "_pool", None)
        if not hasattr(pool, "_network_backend"):     # httpx/httpcore layout changed: refuse rather than run unbounded
            raise RuntimeError("SAFE_FETCH_WATCHDOG_UNAVAILABLE")
        pool._network_backend = backend
        return t, backend

    def _resolve_checked(self, target: NP.Target) -> Optional[str]:
        """Return the pinned address (direct) or None (proxy). Raises EgressRefused."""
        if target.is_literal:
            return target.host
        if self.egress == "proxy" and "." not in target.host:
            raise NP.EgressRefused("HOST_SINGLE_LABEL")     # e.g. "internal-svc": only the proxy could resolve it
        try:
            addresses = list(self.resolver(target.host, target.port))
        except OSError:
            if self.egress == "proxy" and target.host in self.proxy_unresolved_ok:
                return None          # explicitly allow-listed: the proxy resolves it
            raise NP.EgressRefused("DNS_FAILED") from None
        if not addresses:
            raise NP.EgressRefused("DNS_EMPTY")
        for a in addresses:          # ANY non-public answer refuses the hop (no "pick the good one")
            NP.check_address(a)
        return addresses[0] if self.egress == "direct" else None

    def _resolve_bounded(self, target: NP.Target, deadline: float, cancel) -> Optional[str]:
        """`_resolve_checked` under the fetch's budget and cancel flag (R9-06). A resolver (system DNS or a hostile
        authoritative server) can block far longer than the budget; it runs on a helper thread that is waited for at
        most min(remaining budget, connect timeout) while cancel is polled. Raises _Stop(TIMED_OUT | CANCELLED)."""
        if target.is_literal or (self.egress == "proxy" and "." not in target.host):
            return self._resolve_checked(target)              # nothing to look up
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise _Stop(R.TIMED_OUT)                           # e.g. robots.txt used the whole budget
        box = {}

        def run():
            try:
                box["address"] = self._resolve_checked(target)
            except BaseException as exc:                      # re-raised on the caller's thread
                box["error"] = exc
        t = threading.Thread(target=run, name="safe-fetch-dns", daemon=True)
        t.start()
        limit = time.monotonic() + min(remaining, self.timeout.connect)
        while True:
            t.join(_Watchdog.POLL)
            if not t.is_alive():
                break
            if cancel is not None and cancel.cancelled:
                raise _Stop(R.CANCELLED)
            if time.monotonic() > limit or self.clock() > deadline:
                raise _Stop(R.TIMED_OUT)                       # the lookup thread is abandoned (daemon)
        if "error" in box:
            raise box["error"]
        return box.get("address")

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
                address = self._resolve_bounded(target, deadline, cancel)
            except NP.EgressRefused as exc:
                rec.fetch_status, rec.refusal_code = R.REFUSED, exc.code
                rec.redirect_chain = chain
                return FetchResult(rec)
            except _Stop as stop:
                rec.fetch_status, rec.redirect_chain = stop.status, chain
                return FetchResult(rec)
            inner, backend = self._inner()
            transport = _Pinned(inner, address, target.host) if address is not None else inner
            self.connections.append((target.host, address))
            rec.connected_address = address
            try:
                result = self._one(current, transport, deadline, cancel, rec, max_bytes, backend)
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
            extra = self.extra_types.get(mime)
            kind = extra or TEXT_TYPES.get(mime)
            rec.content_type, rec.bytes, rec.sha256 = mime or None, len(body), R.sha256_bytes(body)
            if kind is None:
                rec.fetch_status, rec.analysed_scope = R.UNSUPPORTED_CONTENT_TYPE, R.METADATA_ONLY
                return FetchResult(rec)
            rec.fetch_status = R.OK
            if extra is not None and extra not in ("html", "text", "feed", "json"):
                return FetchResult(rec, body=body, kind=kind)        # a document: bytes for the caller's extractor
            return FetchResult(rec, body=body, text=_decode(body, ctype), kind=kind)
        rec.fetch_status, rec.redirect_chain = R.TOO_MANY_REDIRECTS, chain
        return FetchResult(rec)

    def _one(self, url, transport, deadline, cancel, rec, max_bytes, backend=None):
        remaining = deadline - self.clock()
        if remaining <= 0:
            rec.fetch_status = R.TIMED_OUT
            return None
        watchdog = _Watchdog(backend, deadline, cancel, self.clock)
        with watchdog:
            result = self._exchange(url, transport, deadline, cancel, rec, max_bytes)
        if result is None and watchdog.reason is not None and rec.fetch_status in (R.UNREACHABLE, R.TIMED_OUT):
            rec.fetch_status = watchdog.reason       # the watchdog cut the connection: say why
        return result

    def _exchange(self, url, transport, deadline, cancel, rec, max_bytes):
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "text/plain;q=0.8,application/json;q=0.5", "Accept-Encoding": "identity"}
        try:
            # A connect cannot be cut by the watchdog (no socket yet), so it gets at most the remaining budget.
            remaining = max(0.01, deadline - self.clock())
            timeout = httpx.Timeout(connect=min(self.timeout.connect, remaining), read=self.timeout.read,
                                    write=self.timeout.write, pool=min(self.timeout.pool, remaining))
            with httpx.Client(transport=transport, timeout=timeout, follow_redirects=False, trust_env=False,
                              cookies=None) as client:
                with client.stream("GET", url, headers=headers) as resp:
                    status = resp.status_code
                    if status in REDIRECT_CODES:
                        return status, resp.headers.get("location"), b"", None
                    enc = (resp.headers.get("content-encoding") or "identity").strip().lower()
                    if enc not in ("identity", ""):
                        rec.http_status, rec.fetch_status = status, R.UNSUPPORTED_CONTENT_TYPE
                        rec.refusal_code = "CONTENT_ENCODING_" + enc.upper()[:20]
                        return None
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        rec.http_status, rec.fetch_status = status, R.TOO_LARGE
                        return None
                    buf = bytearray()
                    for chunk in _raw_chunks(resp):
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
        except (httpx.HTTPError, httpx.InvalidURL, OSError, ValueError):
            # R11-02: InvalidURL (a host that netpolicy accepts but httpx does not, '\u2603.com') is not an HTTPError;
            # uncaught, it ended the whole research job as INTERNAL_ERROR. It fails this one source only.
            rec.fetch_status = R.UNREACHABLE
        return None


def _raw_chunks(resp):
    """Bytes as received (no decompression), so the byte cap counts what is on the wire. A response whose body is
    already in memory (no stream) yields that body once."""
    try:
        yield from resp.iter_raw()
    except httpx.StreamConsumed:
        yield resp.content


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
