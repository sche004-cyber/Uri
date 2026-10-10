"""Public news/feed parsing: RSS 2.0, RSS 1.0 (RDF) and Atom, standard library only.

Refused before parsing: any DOCTYPE or ENTITY declaration (entity expansion / external entities), and documents
over MAX_FEED_BYTES. Item text is UNTRUSTED evidence like any page text.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin

from .extract import extract_html, normalise_date

MAX_FEED_BYTES = 2_000_000
MAX_ITEMS = 100
_DECL = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.I)
_ATOM = "{http://www.w3.org/2005/Atom}"
_RSS1 = "{http://purl.org/rss/1.0/}"
_DC = "{http://purl.org/dc/elements/1.1/}"
_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"


class FeedRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass
class FeedItem:
    title: Optional[str]
    url: Optional[str]
    published_at: Optional[str]
    summary: str = ""
    guid: Optional[str] = None


@dataclass
class Feed:
    kind: str                 # rss | atom | rdf
    title: Optional[str]
    site_url: Optional[str]
    items: list = field(default_factory=list)


def _txt(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _plain(html_or_text: str) -> str:
    if "<" in html_or_text:
        return extract_html(html_or_text, "about:blank").text[:2000]
    return html_or_text[:2000]


def parse_feed(text: str, base_url: str) -> Feed:
    if len(text.encode("utf-8", "ignore")) > MAX_FEED_BYTES:
        raise FeedRefused("FEED_TOO_LARGE")
    if _DECL.search(text):
        raise FeedRefused("FEED_DECLARATION_REFUSED")
    try:
        root = ET.fromstring(text.lstrip("﻿").strip())
    except ET.ParseError:
        raise FeedRefused("FEED_PARSE_ERROR") from None
    tag = root.tag.lower()
    if tag == "rss":
        ch = root.find("channel")
        if ch is None:
            raise FeedRefused("FEED_NO_CHANNEL")
        feed = Feed("rss", _txt(ch.find("title")) or None, urljoin(base_url, _txt(ch.find("link"))) or None)
        for it in ch.findall("item")[:MAX_ITEMS]:
            link = _txt(it.find("link"))
            body = _txt(it.find(_CONTENT + "encoded")) or _txt(it.find("description"))
            feed.items.append(FeedItem(_txt(it.find("title")) or None, urljoin(base_url, link) if link else None,
                                       normalise_date(_txt(it.find("pubDate")) or _txt(it.find(_DC + "date"))),
                                       _plain(body), _txt(it.find("guid")) or None))
        return feed
    if root.tag == _ATOM + "feed":
        def link_of(el):
            best = None
            for ln in el.findall(_ATOM + "link"):
                rel = ln.get("rel", "alternate")
                if rel == "alternate" and ln.get("href"):
                    return urljoin(base_url, ln.get("href"))
                best = best or (urljoin(base_url, ln.get("href")) if ln.get("href") else None)
            return best
        feed = Feed("atom", _txt(root.find(_ATOM + "title")) or None, link_of(root))
        for en in root.findall(_ATOM + "entry")[:MAX_ITEMS]:
            body = _txt(en.find(_ATOM + "summary")) or _txt(en.find(_ATOM + "content"))
            feed.items.append(FeedItem(_txt(en.find(_ATOM + "title")) or None, link_of(en),
                                       normalise_date(_txt(en.find(_ATOM + "published")) or _txt(en.find(_ATOM + "updated"))),
                                       _plain(body), _txt(en.find(_ATOM + "id")) or None))
        return feed
    if tag.endswith("rdf"):
        ch = root.find(_RSS1 + "channel")
        feed = Feed("rdf", _txt(ch.find(_RSS1 + "title")) if ch is not None else None,
                    _txt(ch.find(_RSS1 + "link")) if ch is not None else None)
        for it in root.findall(_RSS1 + "item")[:MAX_ITEMS]:
            link = _txt(it.find(_RSS1 + "link"))
            feed.items.append(FeedItem(_txt(it.find(_RSS1 + "title")) or None, urljoin(base_url, link) if link else None,
                                       normalise_date(_txt(it.find(_DC + "date"))), _plain(_txt(it.find(_RSS1 + "description")))))
        return feed
    raise FeedRefused("FEED_UNKNOWN_FORMAT")
