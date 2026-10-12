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
    blocked_non_english: int = 0        # IDN-1: hits dropped because the site's address uses non-English letters


class SearchProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def search(self, query: str, *, max_results: int = 5) -> SearchResult: ...


def _clean_query(q):
    if not isinstance(q, str):
        return None
    q = " ".join(q.split())
    return q[:MAX_QUERY] if q else None


def _hit_refusal(url) -> Optional[str]:
    """None when the hit's URL passes the egress policy, else the refusal code."""
    try:
        NP.check_url(url)
        return None
    except NP.EgressRefused as exc:
        return exc.code


def _public_hit_url(url) -> bool:
    return _hit_refusal(url) is None


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
        kept, blocked = [], 0
        for h in self._hits(data):
            code = _hit_refusal(h.url)
            if code is None:
                kept.append(h)
            elif code == NP.HOST_NON_ENGLISH:
                blocked += 1
        hits = kept[:MAX_HITS]
        for i, h in enumerate(hits, 1):
            h.rank = i
        return SearchResult(self.name, q, OK if hits else NO_RESULTS, hits=hits, http_status=resp.status_code,
                            blocked_non_english=blocked)

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


def load_search_keys(path) -> dict:
    """Read provider settings from a file the owner placed under the client's state root (interim review F2).

    The integrated worker replaces its environment with a minimal one, so `TAVILY_API_KEY` etc. never reach it.
    Format: {"tavily_api_key": "...", "brave_api_key": "...", "searxng_url": "..."} (all optional). Unknown keys
    are ignored; values are never logged or returned to the UI. A missing or unreadable file means "no keys".
    """
    import json
    from pathlib import Path
    p = Path(path)
    try:
        if not p.is_file() or p.stat().st_size > 16_384:
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for k in ("tavily_api_key", "brave_api_key", "searxng_url"):
        v = data.get(k)
        if isinstance(v, str) and 0 < len(v.strip()) <= 512:
            out[k] = v.strip()
    return out


_ENV_NAMES = {"TAVILY_API_KEY": "tavily_api_key", "BRAVE_API_KEY": "brave_api_key", "SEARXNG_URL": "searxng_url"}


def load_env_keys(paths) -> dict:
    """Read search provider settings from ``.env`` files (owner decision D3, 2026-10-11).

    Same KEY=VALUE convention as ``uri_core/tools/web_search.py`` (``TAVILY_API_KEY``); only the three provider
    names above are read, nothing else from the file is kept, and the process environment is never modified.
    Earlier paths win. A missing, oversized or unreadable file is skipped. Values are never logged or returned
    to the UI.
    """
    from pathlib import Path
    out = {}
    for path in paths or []:
        try:
            p = Path(path)
            if not p.is_file() or p.stat().st_size > 65_536:
                continue
            text = p.read_text(encoding="utf-8-sig")
        except (OSError, ValueError):
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            if name.startswith("export "):
                name = name[7:].strip()
            key = _ENV_NAMES.get(name)
            value = value.strip().strip('"').strip("'").strip()
            if key and key not in out and 0 < len(value) <= 512:
                out[key] = value
    return out


def merge_keys(primary: dict, fallback: dict) -> dict:
    """``search_keys.json`` (primary) wins over ``.env`` values per provider."""
    return {**fallback, **primary}


def providers_from_keys(keys: dict, **kw) -> list:
    """Providers configured ONLY from `keys` (never from the environment)."""
    return [TavilyProvider(api_key=keys.get("tavily_api_key", ""), **kw),
            BraveProvider(api_key=keys.get("brave_api_key", ""), **kw),
            SearxngProvider(base_url=keys.get("searxng_url", ""), **kw)]
