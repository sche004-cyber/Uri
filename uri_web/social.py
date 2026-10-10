"""Read-only social sources through their legitimate public APIs, retrieved with SafeFetcher.

  * Mastodon (docs.joinmastodon.org/api): public hashtag timeline and an account's public statuses on a named
    instance. Instances may require authentication for these; then the status is UNAVAILABLE, never a guess.
  * Bluesky (AT Protocol public AppView, public.api.bsky.app): an actor's public author feed.

No login, no posting, no following, no scraping of HTML pages. Post text is UNTRUSTED evidence.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote, urlencode

from . import netpolicy as NP
from . import records as R
from .extract import extract_html, normalise_date
from .safe_fetch import SafeFetcher

OK = "OK"
UNAVAILABLE = "UNAVAILABLE"
REFUSED = "REFUSED"
FAILED = "FAILED"
BSKY_APPVIEW = "https://public.api.bsky.app"
_TAG = re.compile(r"^[A-Za-z0-9_]{1,100}$")
_ACCT = re.compile(r"^@?[A-Za-z0-9_.]{1,64}(@[A-Za-z0-9.-]{1,253})?$")
_HANDLE = re.compile(r"^(?:did:plc:[a-z2-7]{24}|[A-Za-z0-9][A-Za-z0-9.-]{0,252})$")


@dataclass
class SocialPost:
    network: str
    author: str
    url: Optional[str]
    published_at: Optional[str]
    text: str


@dataclass
class SocialResult:
    network: str
    status: str
    posts: list = field(default_factory=list)
    record: Optional[R.SourceRecord] = None
    error_code: Optional[str] = None


def _plain(html: str) -> str:
    return extract_html(html or "", "about:blank").text[:2000] if "<" in (html or "") else (html or "")[:2000]


def _json(fetcher, url, network, cancel):
    res = fetcher.fetch(url, cancel=cancel, robots=False)
    res.record.access_basis = "official_api"
    res.record.provider = network
    if not res.ok:
        status = UNAVAILABLE if res.record.http_status in (401, 403, 404, 410, 422) else FAILED
        if res.record.fetch_status == R.REFUSED:
            status = REFUSED
        return None, SocialResult(network, status, record=res.record,
                                  error_code=res.record.refusal_code or res.record.fetch_status)
    if res.kind != "json":
        return None, SocialResult(network, FAILED, record=res.record, error_code="NOT_JSON")
    try:
        return json.loads(res.text), res
    except ValueError:
        return None, SocialResult(network, FAILED, record=res.record, error_code="BAD_JSON")


def mastodon_tag(fetcher: SafeFetcher, instance: str, tag: str, *, limit=20, cancel=None) -> SocialResult:
    tag = (tag or "").lstrip("#")
    if not _TAG.match(tag):
        return SocialResult("mastodon", REFUSED, error_code="TAG_INVALID")
    try:
        t = NP.check_url(f"https://{instance}/")
    except NP.EgressRefused as exc:
        return SocialResult("mastodon", REFUSED, error_code=exc.code)
    url = f"https://{t.host}/api/v1/timelines/tag/{quote(tag)}?" + urlencode({"limit": max(1, min(int(limit), 40))})
    data, res = _json(fetcher, url, "mastodon", cancel)
    if data is None:
        return res
    posts = [SocialPost("mastodon", str((s.get("account") or {}).get("acct") or ""), s.get("url"),
                        normalise_date(s.get("created_at")), _plain(s.get("content") or ""))
             for s in data if isinstance(s, dict)] if isinstance(data, list) else []
    return SocialResult("mastodon", OK, posts=posts, record=res.record)


def mastodon_account(fetcher: SafeFetcher, instance: str, acct: str, *, limit=20, cancel=None) -> SocialResult:
    if not _ACCT.match(acct or ""):
        return SocialResult("mastodon", REFUSED, error_code="ACCOUNT_INVALID")
    try:
        t = NP.check_url(f"https://{instance}/")
    except NP.EgressRefused as exc:
        return SocialResult("mastodon", REFUSED, error_code=exc.code)
    look, res = _json(fetcher, f"https://{t.host}/api/v1/accounts/lookup?" + urlencode({"acct": acct.lstrip("@")}),
                      "mastodon", cancel)
    if look is None:
        return res
    acc_id = str(look.get("id", "")) if isinstance(look, dict) else ""
    if not acc_id.isdigit():
        return SocialResult("mastodon", FAILED, record=res.record, error_code="ACCOUNT_LOOKUP")
    data, res = _json(fetcher, f"https://{t.host}/api/v1/accounts/{acc_id}/statuses?" +
                      urlencode({"limit": max(1, min(int(limit), 40)), "exclude_replies": "true"}), "mastodon", cancel)
    if data is None:
        return res
    posts = [SocialPost("mastodon", acct.lstrip("@"), s.get("url"), normalise_date(s.get("created_at")),
                        _plain(s.get("content") or "")) for s in data if isinstance(s, dict)] if isinstance(data, list) else []
    return SocialResult("mastodon", OK, posts=posts, record=res.record)


def bluesky_author(fetcher: SafeFetcher, actor: str, *, limit=20, cancel=None) -> SocialResult:
    actor = (actor or "").lstrip("@")
    if not _HANDLE.match(actor):
        return SocialResult("bluesky", REFUSED, error_code="ACTOR_INVALID")
    url = BSKY_APPVIEW + "/xrpc/app.bsky.feed.getAuthorFeed?" + urlencode(
        {"actor": actor, "limit": max(1, min(int(limit), 50)), "filter": "posts_no_replies"})
    data, res = _json(fetcher, url, "bluesky", cancel)
    if data is None:
        return res
    posts = []
    for item in (data.get("feed") or []) if isinstance(data, dict) else []:
        post = (item or {}).get("post") or {}
        rec = post.get("record") or {}
        author = (post.get("author") or {}).get("handle") or actor
        uri = post.get("uri") or ""
        rkey = uri.rsplit("/", 1)[-1] if uri.startswith("at://") else None
        web = f"https://bsky.app/profile/{author}/post/{rkey}" if rkey and re.match(r"^[A-Za-z0-9]+$", rkey) else None
        posts.append(SocialPost("bluesky", author, web, normalise_date(rec.get("createdAt")),
                                str(rec.get("text") or "")[:2000]))
    return SocialResult("bluesky", OK, posts=posts, record=res.record)
