"""Egress policy: which URLs and which resolved addresses W1 may connect to.

Pure functions, no I/O. The fetcher calls `check_url` before resolving and `check_address` on EVERY resolved address
of EVERY hop (redirects included). An address is allowed only if it is a public unicast address; embedded IPv4
addresses inside IPv6 transition forms (mapped, NAT64, 6to4) are unwrapped and checked as IPv4, and Teredo is refused
outright because its embedded server/client addresses cannot be validated reliably.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

ALLOWED_SCHEMES = ("http", "https")
DEFAULT_PORTS = {"http": 80, "https": 443}
ALLOWED_PORTS = frozenset({80, 443})
MAX_URL_LENGTH = 2048
HOST_NON_ENGLISH = "HOST_NON_ENGLISH"
# IDN-1 (D21, D18): what the user is told when a site is refused with HOST_NON_ENGLISH.
NON_ENGLISH_MESSAGE = ("Blocked: this site's address uses non-English letters. Scam sites use them to copy real sites."
                       " If you trust it, open it yourself in your browser.")

_NAT64 = (ipaddress.ip_network("64:ff9b::/96"),)
# R16-02: the RFC 8215 local-use NAT64 prefix may embed IPv4 at any RFC 6052 offset; it is never needed for public
# fetches, so it is refused outright.
_NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")
_SIX_TO_FOUR = ipaddress.ip_network("2002::/16")
_TEREDO = ipaddress.ip_network("2001::/32")
_LDH = __import__("re").compile(r"^[a-z0-9.-]+$")
# Explicit refusals on top of `is_global` (defence in depth; `is_global` semantics differ across Python versions).
_V4_REFUSED = tuple(ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24",
    "192.0.2.0/24", "192.88.99.0/24", "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24",
    "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32"))
_V6_REFUSED = tuple(ipaddress.ip_network(n) for n in (
    "::/128", "::1/128", "::ffff:0:0/96", "100::/64", "2001:db8::/32", "fc00::/7", "fe80::/10", "fec0::/10", "ff00::/8"))


class EgressRefused(ValueError):
    """A URL or address the policy refuses. `code` is a stable, content-free reason."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str          # lower-case, IDNA-encoded host name or a literal address without brackets
    port: int
    is_literal: bool


def _embedded_v4(ip: ipaddress.IPv6Address):
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    for net in _NAT64:
        if ip in net:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip in _SIX_TO_FOUR:
        return ip.sixtofour
    return None


def check_address(address) -> None:
    """Raise EgressRefused unless `address` is a public unicast address."""
    try:
        ip = ipaddress.ip_address(str(address).split("%", 1)[0])
    except ValueError:
        raise EgressRefused("ADDRESS_INVALID") from None
    if isinstance(ip, ipaddress.IPv6Address):
        if ip in _TEREDO:
            raise EgressRefused("ADDRESS_TRANSITION_REFUSED", "teredo")
        if ip in _NAT64_LOCAL:
            raise EgressRefused("ADDRESS_TRANSITION_REFUSED", "nat64-local-use")
        inner = _embedded_v4(ip)
        if inner is not None:
            try:
                check_address(inner)
            except EgressRefused as exc:
                raise EgressRefused(exc.code, "embedded:" + exc.detail) from None
            if ip.ipv4_mapped is not None or any(ip in n for n in _NAT64):
                return          # judged by the embedded IPv4 alone; 6to4 continues and is refused below
        if any(ip in n for n in _V6_REFUSED):
            raise EgressRefused("ADDRESS_NOT_PUBLIC", "v6-range")
    else:
        if any(ip in n for n in _V4_REFUSED):
            raise EgressRefused("ADDRESS_NOT_PUBLIC", "v4-range")
    if ip.is_multicast or ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_reserved \
            or ip.is_unspecified or not ip.is_global:
        raise EgressRefused("ADDRESS_NOT_PUBLIC", "flags")


def site_key(url) -> Optional[str]:
    """R1-02: one name per site for counting blocked sites ('b\u00fccher.de' and 'xn--bcher-kva.de' are one site);
    None when the URL has no host."""
    try:
        host = (urlsplit(url).hostname or "").rstrip(".")
    except (ValueError, TypeError, AttributeError):
        return None
    if not host:
        return None
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return host.lower()


def check_url(url: str, *, allowed_ports=ALLOWED_PORTS) -> Target:
    """Parse and check a URL. Returns the connection target. Refuses anything but plain public http(s)."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        raise EgressRefused("URL_INVALID")
    if any(ord(c) < 0x21 or c in "\\" for c in url):
        raise EgressRefused("URL_INVALID", "control-or-backslash")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise EgressRefused("URL_INVALID") from None
    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise EgressRefused("SCHEME_REFUSED", scheme)
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise EgressRefused("USERINFO_REFUSED")
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise EgressRefused("HOST_MISSING")
    port = port if port is not None else DEFAULT_PORTS[scheme]
    if port not in allowed_ports:
        raise EgressRefused("PORT_REFUSED", str(port))
    literal = True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        literal = False
    if literal:
        check_address(host)
    else:
        # Numeric-looking hosts that are not canonical dotted quads (e.g. "2130706433", "0x7f.1", "127.1") are
        # refused: resolvers and browsers disagree on them.
        if all(ch in "0123456789abcdefx." for ch in host.lower()) and any(ch.isdigit() for ch in host):
            labels = host.split(".")
            if all(lab.isdigit() or lab.lower().startswith("0x") for lab in labels if lab):
                raise EgressRefused("HOST_NUMERIC_AMBIGUOUS")
        # R1-01: tested on the raw authority, because urlsplit lower-cases the host and KELVIN SIGN (U+212A)
        # lower-cases to ASCII 'k'.
        non_ascii = not host.isascii() or not parts.netloc.isascii()
        try:
            host = host.encode("idna").decode("ascii").lower()
        except UnicodeError:
            raise EgressRefused(HOST_NON_ENGLISH if non_ascii else "HOST_INVALID") from None
        # R11-02: IDNA maps full-width digits and dots to ASCII ('\uff10x5d.184.215.14' -> '0x5d.184.215.14'), so the
        # numeric checks run again on the ASCII host; a host that becomes an IP literal is checked as one.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise EgressRefused("HOST_NUMERIC_AMBIGUOUS", "idna-literal")
        if all(ch in "0123456789abcdefx." for ch in host) and any(ch.isdigit() for ch in host):
            if all(lab.isdigit() or lab.startswith("0x") for lab in host.split(".") if lab):
                raise EgressRefused("HOST_NUMERIC_AMBIGUOUS")
        # IDN-1 (owner decision D21, 2026-10-11): a host name with any character outside ASCII, or an IDNA label
        # ('xn--...', the same name in its ASCII form), is refused before DNS on every route (user URLs, search hits,
        # redirects). Look-alike letters let a scam site copy a real one ('\u0440\u0430\u0443\u0440\u0430l.com'). Full-width digits that
        # spell an IP address keep HOST_NUMERIC_AMBIGUOUS (checked above).
        if non_ascii or any(lab.startswith("xn--") for lab in host.split(".")):
            raise EgressRefused(HOST_NON_ENGLISH)
        # After IDNA only letters, digits, hyphens and dots may remain (no '%', '_' or anything a proxy might
        # decode into a different host), labels 1-63 characters (interim review F6).
        if not _LDH.match(host) or any(not 0 < len(lab) <= 63 for lab in host.split(".")):
            raise EgressRefused("HOST_INVALID", "ldh")
        if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal", ".lan", ".home.arpa")):
            raise EgressRefused("HOST_LOCAL_NAME")
    return Target(scheme=scheme, host=host.lower(), port=port, is_literal=literal)
