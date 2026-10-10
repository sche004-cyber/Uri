"""SourceRecord: the provenance of one retrieved source (M1 research P3-1 field set, trimmed to what W1 produces).

A record is created for every retrieval attempt, successful or not, so a research result can always say what was
tried and why something is missing. Text extracted from the body is UNTRUSTED (`trust` is fixed).
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

UNTRUSTED = "UNTRUSTED_EVIDENCE"

# Fetch outcomes (fixed vocabulary; only OK carries content).
OK = "OK"
REFUSED = "REFUSED"                      # egress policy refused the URL or an address (no connection was made)
HTTP_ERROR = "HTTP_ERROR"
TIMED_OUT = "TIMED_OUT"
TOO_LARGE = "TOO_LARGE"
UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
UNREACHABLE = "UNREACHABLE"
CANCELLED = "CANCELLED"
ROBOTS_DISALLOWED = "ROBOTS_DISALLOWED"
TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS"
FETCH_STATUSES = (OK, REFUSED, HTTP_ERROR, TIMED_OUT, TOO_LARGE, UNSUPPORTED_CONTENT_TYPE, UNREACHABLE, CANCELLED,
                  ROBOTS_DISALLOWED, TOO_MANY_REDIRECTS)

# What part of a source was actually analysed.
FULL_TEXT = "full_text"
SNIPPET_ONLY = "snippet_only"       # only a search-provider snippet; the page itself was not read
METADATA_ONLY = "metadata_only"
NONE = "none"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass
class SourceRecord:
    requested_url: str
    final_url: Optional[str] = None
    redirect_chain: list = field(default_factory=list)
    retrieved_at: str = field(default_factory=utc_now)
    fetch_status: str = UNREACHABLE
    refusal_code: Optional[str] = None
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    bytes: int = 0
    sha256: Optional[str] = None
    connected_address: Optional[str] = None   # the validated, pinned address (None in proxy egress mode)
    egress: str = "direct"                    # "direct" (pinned) or "proxy" (resolution by the configured proxy)
    robots_decision: str = "NOT_CHECKED"      # ALLOWED | DISALLOWED | UNAVAILABLE | NOT_CHECKED
    provider: Optional[str] = None            # search/social provider that surfaced it, if any
    access_basis: str = "public_web"          # public_web | official_api
    extraction_method: Optional[str] = None
    analysed_scope: str = NONE
    title: Optional[str] = None
    site_name: Optional[str] = None
    published_at: Optional[str] = None
    modified_at: Optional[str] = None
    language: Optional[str] = None
    injection_flags: list = field(default_factory=list)
    trust: str = UNTRUSTED

    def __post_init__(self):
        if self.trust != UNTRUSTED:
            raise ValueError("SOURCE_TRUST_FIXED")
        if self.fetch_status not in FETCH_STATUSES:
            raise ValueError("FETCH_STATUS_UNKNOWN")

    @property
    def ok(self) -> bool:
        return self.fetch_status == OK

    def to_dict(self) -> dict:
        return asdict(self)
