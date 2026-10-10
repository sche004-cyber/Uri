"""Deterministic HTML content and metadata extraction (CPU only, standard library).

Main text: block-level text, preferring <article>/<main> when they carry enough text. Dropped: scripts, styles,
templates, navigation, headers/footers, asides, forms, iframes, SVG, and HIDDEN content (`hidden`, `aria-hidden`,
inline `display:none` / `visibility:hidden` / zero font size or opacity). Hidden text is a classic carrier for
instructions aimed at an assistant; it is counted, never returned.

Metadata: <title>, Open Graph, `article:published_time` / `modified_time`, Dublin Core and `date` metas, JSON-LD
(`datePublished`, `dateModified`, `headline`), the first `<time datetime>`, `rel=canonical`, `<html lang>`, and
RSS/Atom alternate links (feed discovery).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

METHOD = "uri_web.extract/1"
MAX_TEXT_CHARS = 60_000
MAX_BLOCKS = 600

_SKIP = {"script", "style", "noscript", "template", "svg", "nav", "footer", "aside", "form", "iframe", "button",
         "select", "textarea", "object", "embed", "canvas", "dialog", "header", "menu"}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track",
         "wbr"}
_BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "td", "th", "dd", "dt", "figcaption",
          "div", "section", "article", "main", "tr", "caption", "address"}
_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*(hidden|collapse)|font-size\s*:\s*(0(?![.\d]*[1-9])|0?\.\d+px|1px)|"
    r"opacity\s*:\s*0(?:\.0+)?\s*(?:!important\s*)?(?:;|$)|(?:height|width)\s*:\s*0(?:px)?\s*(?:!important\s*)?;.*overflow\s*:\s*hidden|"
    r"(?:left|top|right|text-indent|margin-left)\s*:\s*-\d{3,}(?:\.\d+)?(?:px|em|rem|%)|"
    r"clip\s*:\s*rect\(\s*0|clip-path\s*:\s*inset\(\s*(?:50|100)%|transform\s*:\s*scale\(\s*0\s*\)",
    re.I)
# Common "visually hidden" utility classes (screen-reader-only text is still not visible to the user).
_HIDDEN_CLASS = re.compile(r"(?:^|\s)(sr-only|visually-hidden|visuallyhidden|screen-reader-text|screen-reader-only|"
                           r"hidden|d-none|is-hidden|invisible|offscreen|a11y-hidden)(?:\s|$)", re.I)
_WS = re.compile(r"\s+")
_FEED_TYPES = {"application/rss+xml", "application/atom+xml", "application/feed+json"}


def normalise_date(value) -> Optional[str]:
    """ISO-8601 UTC 'YYYY-MM-DDTHH:MM:SSZ' or None. Accepts ISO dates/times and RFC 2822."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    dt = None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(v)
        except (TypeError, ValueError, IndexError):
            dt = None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Extracted:
    title: Optional[str] = None
    site_name: Optional[str] = None
    description: Optional[str] = None
    canonical_url: Optional[str] = None
    published_at: Optional[str] = None
    modified_at: Optional[str] = None
    language: Optional[str] = None
    blocks: list = field(default_factory=list)
    feed_links: list = field(default_factory=list)
    hidden_dropped: int = 0
    method: str = METHOD

    @property
    def text(self) -> str:
        return "\n".join(self.blocks)


class _Parser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.stack = []            # [tag, skip(bool), hidden(bool), region(str|None)]
        self.cur = []              # text of the current block
        self.blocks = []           # (region, text)
        self.meta = {}
        self.title_parts = []
        self.in_title = False
        self.jsonld = []
        self.in_jsonld = False
        self.jsonld_buf = []
        self.first_time = None
        self.canonical = None
        self.lang = None
        self.feeds = []
        self.hidden_dropped = 0

    # state helpers
    def _skipping(self):
        return any(s[1] or s[2] for s in self.stack)

    def _region(self):
        for s in reversed(self.stack):
            if s[3]:
                return s[3]
        return None

    def _flush(self):
        text = _WS.sub(" ", "".join(self.cur)).strip()
        self.cur = []
        if text and len(self.blocks) < MAX_BLOCKS:
            self.blocks.append((self._region(), text))

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"].strip()[:16]
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").strip().lower()
            if key and "content" in a and key not in self.meta:
                self.meta[key] = a["content"].strip()
            return
        if tag == "link":
            rel = a.get("rel", "").lower().split()
            href = a.get("href", "").strip()
            if "canonical" in rel and href and self.canonical is None:
                self.canonical = urljoin(self.base, href)
            if "alternate" in rel and a.get("type", "").lower() in _FEED_TYPES and href:
                self.feeds.append({"url": urljoin(self.base, href), "type": a.get("type").lower(),
                                   "title": a.get("title", "")[:200]})
            return
        if tag == "title" and not self.stack_has("svg"):
            self.in_title = True
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.in_jsonld, self.jsonld_buf = True, []
        if tag == "time" and self.first_time is None and a.get("datetime") and not self._skipping():
            self.first_time = a["datetime"]
        if tag in _VOID:
            if tag == "br":
                self.cur.append(" ")
            return
        hidden = ("hidden" in a or a.get("aria-hidden", "").lower() == "true"
                  or bool(_HIDDEN_STYLE.search(a.get("style", ""))) or bool(_HIDDEN_CLASS.search(a.get("class", ""))))
        if hidden and not self._skipping():
            self.hidden_dropped += 1
        region = tag if tag in ("article", "main") else None
        if tag in _BLOCK:
            self._flush()
        self.stack.append([tag, tag in _SKIP, hidden, region])

    def stack_has(self, tag):
        return any(s[0] == tag for s in self.stack)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_jsonld:
            self.in_jsonld = False
            self.jsonld.append("".join(self.jsonld_buf))
        if not any(s[0] == tag for s in self.stack):
            return
        if tag in _BLOCK:
            self._flush()
        while self.stack:
            s = self.stack.pop()
            if s[0] == tag:
                break
        if tag in _BLOCK:
            self._flush()

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
            return
        if self.in_jsonld:
            if sum(len(x) for x in self.jsonld_buf) < 200_000:
                self.jsonld_buf.append(data)
            return
        if self._skipping():
            return
        self.cur.append(data)

    def close(self):
        super().close()
        self._flush()


def _jsonld_values(raw_items):
    out = {}

    def walk(o, depth=0):
        if depth > 6:
            return
        if isinstance(o, list):
            for x in o[:50]:
                walk(x, depth + 1)
        elif isinstance(o, dict):
            for k in ("datePublished", "dateModified", "headline", "name"):
                v = o.get(k)
                if isinstance(v, str) and k not in out:
                    out[k] = v
            if "@graph" in o:
                walk(o["@graph"], depth + 1)
    for raw in raw_items:
        try:
            walk(json.loads(raw))
        except (ValueError, RecursionError):
            continue
    return out


def extract_html(html: str, base_url: str) -> Extracted:
    p = _Parser(base_url)
    try:
        p.feed(html)
        p.close()
    except (AssertionError, ValueError):     # pathological markup: keep what was parsed
        p._flush()
    ld = _jsonld_values(p.jsonld)
    m = p.meta
    main_blocks = [t for r, t in p.blocks if r in ("article", "main")]
    use = main_blocks if sum(len(t) for t in main_blocks) >= 200 else [t for _r, t in p.blocks]
    # Drop exact repeats (menus repeated in the body, cookie banners) while keeping order.
    seen, blocks, total = set(), [], 0
    for t in use:
        if t in seen:
            continue
        seen.add(t)
        if total + len(t) > MAX_TEXT_CHARS:
            break
        blocks.append(t)
        total += len(t)
    title = (m.get("og:title") or ld.get("headline") or _WS.sub(" ", "".join(p.title_parts)).strip() or None)
    published = (normalise_date(m.get("article:published_time")) or normalise_date(ld.get("datePublished"))
                 or normalise_date(m.get("dc.date")) or normalise_date(m.get("dcterms.created"))
                 or normalise_date(m.get("date")) or normalise_date(m.get("pubdate"))
                 or normalise_date(p.first_time))
    modified = (normalise_date(m.get("article:modified_time")) or normalise_date(ld.get("dateModified"))
                or normalise_date(m.get("og:updated_time")) or normalise_date(m.get("dcterms.modified")))
    return Extracted(title=title[:500] if title else None, site_name=(m.get("og:site_name") or None),
                     description=(m.get("og:description") or m.get("description") or None),
                     canonical_url=p.canonical, published_at=published, modified_at=modified, language=p.lang,
                     blocks=blocks, feed_links=p.feeds[:20], hidden_dropped=p.hidden_dropped)


def extract_text(text: str) -> Extracted:
    blocks = [b for b in (_WS.sub(" ", x).strip() for x in re.split(r"\n\s*\n", text)) if b][:MAX_BLOCKS]
    return Extracted(blocks=blocks, method="uri_web.extract/text")
