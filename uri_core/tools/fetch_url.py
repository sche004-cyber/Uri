"""Capability: fetch and read one web page/document by URL (M19).

Closes the audit's #5 gap: web_search can find a source, but URI had
no way to actually open it - so "public documents/PDFs and meeting
minutes" was limited to whatever short snippet Tavily returned. This
tool fetches the URL and extracts its readable text, reusing
file_extraction.py's existing PDF/text/spreadsheet/docx extractors
(the identical machinery read_attached_file.py already uses for user
uploads) rather than adding a second extraction path.

Argument boundary, unchanged from every other capability (see
orchestrator.py's "only a plain capability-name string ever crosses
this boundary" - the model's own proposed arguments are never read):
this tool takes NO model-supplied url argument. The URL is extracted
deterministically from request_text - the runtime-supplied user/goal
text - via a plain regex, exactly the same discipline
draft_institutional_note.py already uses to extract a subject from
request_text. If the Brain wants URI to read a specific page, the user
(or the Brain's own workflow goal, which always originates from the
user's real text - see orchestrator.py's fallback_goal) must actually
say the URL; URI never lets a model choose what to fetch.

Bounded and safe: a strict http(s)-only scheme check, a content-length
cap enforced on real bytes received (never a client-declared header),
a short timeout, and no redirect to a non-http(s) scheme. Never
invents content when a fetch fails - reports the real reason.

SSRF-1 (owner decision D2): the network hop goes through W1's
uri_web.safe_fetch.SafeFetcher instead of `requests`. Every hop is
checked by uri_web.netpolicy (public http(s) only: no loopback,
private, link-local/metadata, CGNAT, multicast or reserved address, no
userinfo, allowed ports only), the name is resolved once and refused if
ANY answer is non-public, the connection is pinned to the checked
address (no DNS rebinding), at most 5 redirects are followed and each
is re-checked, and environment proxies, cookies and credentials are
never used. A refused target returns "unavailable" with a refusal code
and nothing about the internal address. robots.txt is not applied: this
is one user-directed read, not a crawler (as before).
"""

import os
import re
import tempfile
from html.parser import HTMLParser
from typing import Optional

from uri_core.services.file_extraction import extract_file_text
from uri_web import records as R
from uri_web.safe_fetch import SafeFetcher

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

_TIMEOUT_SECONDS = 15
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB - a research fetch, not a big-file store.

# Content-types this tool knows how to turn into readable text. Anything
# else is reported honestly as unsupported rather than guessed at.
_EXTENSION_BY_CONTENT_TYPE = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


# SSRF-1 refusal codes (uri_web.netpolicy / safe_fetch) -> the real reason, worded for the user. Only the
# address-class codes say "private or local network"; a DNS failure is "could not reach", as before SSRF-1.
# Never includes the address itself.
_PRIVATE_MESSAGE = "URI will not fetch that address (private or local network)."
_REFUSAL_MESSAGES = {
    "ADDRESS_NOT_PUBLIC": _PRIVATE_MESSAGE,
    "ADDRESS_TRANSITION_REFUSED": _PRIVATE_MESSAGE,
    "HOST_LOCAL_NAME": _PRIVATE_MESSAGE,
    "HOST_NUMERIC_AMBIGUOUS": _PRIVATE_MESSAGE,
    "HOST_SINGLE_LABEL": _PRIVATE_MESSAGE,
    "DNS_FAILED": "URI could not reach that URL.",
    "DNS_EMPTY": "URI could not reach that URL.",
    "USERINFO_REFUSED": "URI will not fetch a URL that contains a username or password.",
    "PORT_REFUSED": "URI only fetches web pages on the standard ports (80 and 443).",
    "SCHEME_REFUSED": "Only http(s) URLs can be fetched.",
    "URL_INVALID": "That URL is not valid.",
    "HOST_INVALID": "That URL is not valid.",
    "HOST_MISSING": "That URL is not valid.",
    "ADDRESS_INVALID": "That URL is not valid.",
}
_REFUSAL_FALLBACK = "URI refused to fetch that URL."


class _TextExtractingHTMLParser(HTMLParser):
    """A minimal, dependency-free HTML-to-text reader - deliberately
    not a full renderer, just enough to turn a page into readable
    prose for the Brain to cite, without adding a new parsing library
    (no BeautifulSoup/lxml) for what is otherwise a small, bounded
    need."""

    _SKIP_TAGS = {"script", "style", "noscript", "head"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self.chunks.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.chunks)


def _extract_url(request_text: str) -> Optional[str]:
    match = _URL_RE.search(request_text or "")
    if not match:
        return None
    url = match.group(0).rstrip(").,;:!?")
    return url


class FetchUrlTool:
    """Fetches one URL and returns its readable text as evidence. Pure
    machinery, exactly like web_search.py/read_attached_file.py: it
    never decides what a page means, never drafts an answer from it,
    and never invents content when a fetch fails."""

    def __init__(self, fetcher: Optional[SafeFetcher] = None, timeout: int = _TIMEOUT_SECONDS):
        # `fetcher` is a test seam (an injected SafeFetcher with a fake resolver/transport); production builds its own.
        self._timeout = timeout
        self._fetcher = fetcher

    def _new_fetcher(self) -> SafeFetcher:
        types = {mime: "document" for mime in _EXTENSION_BY_CONTENT_TYPE}
        types.update({"": "html"})          # no Content-Type: read as HTML, as before
        return SafeFetcher(honour_robots=False, max_bytes=_MAX_BYTES, total_timeout=float(self._timeout),
                           extra_types=types)

    def execute(self, **kwargs) -> dict:
        request_text = kwargs.get("request_text", "") or ""

        url = _extract_url(request_text)

        if url is None:
            return {
                "status": "input_required",
                "message": (
                    "No URL was found in the request, so URI does not "
                    "know what to fetch."
                ),
            }

        if not url.lower().startswith(("http://", "https://")):
            return {
                "status": "input_required",
                "message": "Only http(s) URLs can be fetched.",
                "url": url,
            }

        fetcher = self._fetcher or self._new_fetcher()
        result = fetcher.fetch(url, robots=False)
        rec = result.record

        if rec.fetch_status == R.REFUSED:
            return {
                "status": "unavailable",
                "message": _REFUSAL_MESSAGES.get(rec.refusal_code, _REFUSAL_FALLBACK),
                "refusal_code": rec.refusal_code,
                "url": url,
            }

        if rec.fetch_status == R.HTTP_ERROR:
            return {
                "status": "unavailable",
                "message": f"The page returned HTTP {rec.http_status}.",
                "url": url,
            }

        if rec.fetch_status == R.TOO_LARGE:
            return {
                "status": "unavailable",
                "message": (
                    f"The page exceeded the {_MAX_BYTES // (1024 * 1024)} MB "
                    "fetch limit."
                ),
                "url": url,
            }

        content_type = (rec.content_type or "").lower()

        if rec.fetch_status == R.UNSUPPORTED_CONTENT_TYPE:
            return {
                "status": "unsupported",
                "message": (
                    f"URI has no reader for content type '{content_type or 'unknown'}'."
                ),
                "url": url,
                "content_type": content_type,
            }

        if rec.fetch_status != R.OK:
            return {
                "status": "unavailable",
                "message": "URI could not reach that URL.",
                "error": rec.fetch_status,
                "url": url,
            }

        if rec.http_status != 200:
            return {
                "status": "unavailable",
                "message": f"The page returned HTTP {rec.http_status}.",
                "url": url,
            }

        content = result.body

        if result.kind == "html":
            parser = _TextExtractingHTMLParser()
            parser.feed(result.text)
            text = parser.text().strip()

            if not text:
                return {
                    "status": "empty",
                    "message": "The page was fetched but contained no readable text.",
                    "url": url,
                }

            return {
                "status": "success",
                "url": url,
                "content_type": content_type or "text/html",
                "text": text[:8000],
                "truncated": len(text) > 8000,
            }

        extension = _EXTENSION_BY_CONTENT_TYPE.get(content_type)

        if extension is None:
            return {
                "status": "unsupported",
                "message": (
                    f"URI has no reader for content type '{content_type or 'unknown'}'."
                ),
                "url": url,
                "content_type": content_type,
            }

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as handle:
                handle.write(bytes(content))
                tmp_path = handle.name

            extraction = extract_file_text(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        extraction["url"] = url
        extraction["content_type"] = content_type
        return extraction
