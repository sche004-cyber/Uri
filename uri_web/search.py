"""Search provider abstraction.

Providers: Tavily (the provider URI already uses, `uri_core/tools/web_search.py`; same `TAVILY_API_KEY` convention),
Brave Search API (optional, `BRAVE_SEARCH_API_KEY`) and a self-hosted SearXNG (optional, `URI_SEARXNG_URL`).

Rules:
  * A provider endpoint comes from configuration, never from a page, a model or a query.
  * An unconfigured provider answers UNAVAILABLE; a failing one FAILED / RATE_LIMITED. Never an empty success.
  * API keys never appear in results, errors or records: errors carry a code and an HTTP status only.
  * Hits are leads, not evidence: a hit's snippet is `snippet_only` until the page itself is retrieved.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol
from urllib.parse import urlsplit

import httpx

from . import netpolicy as NP

OK = "OK"
NO_RESULTS = "NO_RESULTS"
UNAVAILABLE = "UNAVAILABLE"
FAILED = "FAILED"
RATE_LIMITED = "RATE_LIMITED"
REFUSED = "REFUSED"
MAX_QUERY = 400
MAX_HITS = 10


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    rank: int
    provider: str
    published_at: Optional[str] = None


@dataclass
class SearchResult:
    provider: str
    query: str
    status: str
    hits: list = field(default_factory=list)
    error_code: Optional[str] = None
    http_status: Optional[int] = None


class SearchProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def search(self, query: str, *, max_results: int = 5) -> SearchResult: ...


def _clean_query(q):
    if not isinstance(q, str):
        return None
    q = " ".join(q.split())
    return q[:MAX_QUERY] if q else None


def _public_hit_url(url) -> bool:
    try:
        NP.check_url(url)
        return True
    except NP.EgressRefused:
        return False


class _HttpProvider:
    name = "base"
    timeout = httpx.Timeout(10.0, connect=5.0)

    def __init__(self, *, transport: Optional[httpx.BaseTransport] = None, proxy: Optional[str] = None):
        self._transport, self._proxy = transport, proxy

    def _client(self):
        if self._transport is not None:
            return httpx.Client(transport=self._transport, timeout=self.timeout, trust_env=False, follow_redirects=False)
        return httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False, proxy=self._proxy)

    def _call(self, query, fn) -> SearchResult:
        q = _clean_query(query)
        if q is None:
            return SearchResult(self.name, "", REFUSED, error_code="QUERY_EMPTY")
        if not self.available():
            return SearchResult(self.name, q, UNAVAILABLE, error_code="NOT_CONFIGURED")
        try:
            with self._client() as c:
                resp = fn(c, q)
        except httpx.TimeoutException:
            return SearchResult(self.name, q, FAILED, error_code="TIMEOUT")
        except (httpx.HTTPError, OSError):
            return SearchResult(self.name, q, FAILED, error_code="UNREACHABLE")
        if resp.status_code == 429:
            return SearchResult(self.name, q, RATE_LIMITED, error_code="RATE_LIMITED", http_status=429)
        if resp.status_code in (401, 403):
            return SearchResult(self.name, q, UNAVAILABLE, error_code="AUTH_REJECTED", http_status=resp.status_code)
        if resp.status_code >= 400:
            return SearchResult(self.name, q, FAILED, error_code="HTTP_ERROR", http_status=resp.status_code)
        try:
            data = resp.json()
        except ValueError:
            return SearchResult(self.name, q, FAILED, error_code="BAD_RESPONSE", http_status=resp.status_code)
        hits = self._hits(data)
        hits = [h for h in hits if _public_hit_url(h.url)][:MAX_HITS]
        for i, h in enumerate(hits, 1):
            h.rank = i
        return SearchResult(self.name, q, OK if hits else NO_RESULTS, hits=hits, http_status=resp.status_code)

    def _hits(self, data) -> list:
        raise NotImplementedError


class TavilyProvider(_HttpProvider):
    name = "tavily"
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, api_key: Optional[str] = None, **kw):
        super().__init__(**kw)
        self._key = api_key if api_key is not None else os.environ.get("TAVILY_API_KEY", "").strip()

    def available(self):
        return bool(self._key)

    def search(self, query, *, max_results=5):
        n = max(1, min(int(max_results), MAX_HITS))
        return self._call(query, lambda c, q: c.post(self.ENDPOINT, json={
            "api_key": self._key, "query": q, "max_results": n, "search_depth": "basic",
            "include_answer": False, "include_raw_content": False}))

    def _hits(self, data):
        out = []
        for r in (data.get("results") or []) if isinstance(data, dict) else []:
            if isinstance(r, dict) and isinstance(r.get("url"), str):
                out.append(SearchHit(str(r.get("title") or "")[:300], r["url"], str(r.get("content") or "")[:600], 0,
                                     self.name, r.get("published_date") if isinstance(r.get("published_date"), str) else None))
        return out


class BraveProvider(_HttpProvider):
    name = "brave"
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: Optional[str] = None, **kw):
        super().__init__(**kw)
        self._key = api_key if api_key is not None else os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()

    def available(self):
        return bool(self._key)

    def search(self, query, *, max_results=5):
        n = max(1, min(int(max_results), MAX_HITS))
        return self._call(query, lambda c, q: c.get(self.ENDPOINT, params={"q": q, "count": n},
                                                    headers={"Accept": "application/json",
                                                             "X-Subscription-Token": self._key}))

    def _hits(self, data):
        out = []
        web = (data.get("web") or {}) if isinstance(data, dict) else {}
        for r in web.get("results") or []:
            if isinstance(r, dict) and isinstance(r.get("url"), str):
                out.append(SearchHit(str(r.get("title") or "")[:300], r["url"], str(r.get("description") or "")[:600],
                                     0, self.name, None))
        return out


class SearxngProvider(_HttpProvider):
    """A self-hosted SearXNG JSON endpoint (the owner's own instance; it may be on loopback by design)."""
    name = "searxng"

    def __init__(self, base_url: Optional[str] = None, **kw):
        super().__init__(**kw)
        raw = base_url if base_url is not None else os.environ.get("URI_SEARXNG_URL", "").strip()
        self._base = None
        if raw:
            parts = urlsplit(raw)
            if parts.scheme in ("http", "https") and parts.hostname and not parts.username and not parts.password:
                self._base = raw.rstrip("/")

    def available(self):
        return self._base is not None

    def search(self, query, *, max_results=5):
        self._n = max(1, min(int(max_results), MAX_HITS))
        return self._call(query, lambda c, q: c.get(self._base + "/search", params={"q": q, "format": "json"}))

    def _hits(self, data):
        out = []
        for r in (data.get("results") or []) if isinstance(data, dict) else []:
            if isinstance(r, dict) and isinstance(r.get("url"), str):
                out.append(SearchHit(str(r.get("title") or "")[:300], r["url"], str(r.get("content") or "")[:600], 0,
                                     self.name, r.get("publishedDate") if isinstance(r.get("publishedDate"), str) else None))
        return out[: getattr(self, "_n", MAX_HITS)]


def default_providers(**kw) -> list:
    """Configured order: Tavily (existing URI provider), then Brave, then SearXNG. Unconfigured ones stay listed so
    their UNAVAILABLE status is visible."""
    return [TavilyProvider(**kw), BraveProvider(**kw), SearxngProvider(**kw)]
