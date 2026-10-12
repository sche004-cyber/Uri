"""The W1 research pipeline: Search -> Retrieve -> Extract -> Evaluate -> Synthesize -> Cite.

Authority rules (prompt-injection resistance by construction):
  * The pages to retrieve come ONLY from (a) URLs the user typed into the request and (b) hits returned by a
    configured search provider for the user's query. Links, redirects-to-elsewhere aside, inside retrieved pages are
    never followed, and feed items are reported, not fetched.
  * The query, providers, budget and URL list are fixed when the job starts. Nothing a source says can change them.
  * Source text reaches a model only inside untrusted data blocks (`untrusted.py`), and model output is verified
    against the sources before it is shown (`synthesize.verify`).

Bounded: page, byte and wall-clock budgets; cooperative cancellation between and during retrievals; progress
callbacks. It never captures the screen.

Terminal status (fixed vocabulary): COMPLETED_WITH_RESULT, NO_RESULT, PROVIDER_UNAVAILABLE, CANCELLED, TIMED_OUT,
FAILED. Only COMPLETED_WITH_RESULT carries an answer.
"""
from __future__ import annotations

import inspect
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from . import evaluate as EV
from . import feeds as FD
from . import netpolicy as NP
from . import records as R
from . import search as S
from . import synthesize as SY
from . import untrusted as U
from .extract import extract_html, extract_text
from .safe_fetch import CancelFlag, SafeFetcher

COMPLETED_WITH_RESULT = "COMPLETED_WITH_RESULT"
NO_RESULT = "NO_RESULT"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
CANCELLED = "CANCELLED"
TIMED_OUT = "TIMED_OUT"
FAILED = "FAILED"
TERMINAL = (COMPLETED_WITH_RESULT, NO_RESULT, PROVIDER_UNAVAILABLE, CANCELLED, TIMED_OUT, FAILED)

MAX_USER_URLS = 5
MAX_FEEDS = 3


@dataclass
class Budget:
    max_pages: int = 6
    max_total_bytes: int = 8_000_000
    deadline_s: float = 90.0
    max_results_per_provider: int = 6

    def clamp(self):
        self.max_pages = max(1, min(int(self.max_pages), 12))
        self.max_total_bytes = max(100_000, min(int(self.max_total_bytes), 20_000_000))
        self.deadline_s = max(5.0, min(float(self.deadline_s), 300.0))
        self.max_results_per_provider = max(1, min(int(self.max_results_per_provider), 10))
        return self


@dataclass
class ResearchRequest:
    query: str
    urls: list = field(default_factory=list)        # typed by the user
    feeds: list = field(default_factory=list)       # feed URLs typed by the user
    use_search: bool = True
    use_brain: bool = False
    budget: Budget = field(default_factory=Budget)


@dataclass
class Source:
    number: int                 # citation number [n]
    title: str
    url: str
    record: dict
    analysed_scope: str
    text: str
    injection_flags: list
    relevance: float = 0.0
    near_duplicate_of: Optional[int] = None


@dataclass
class ResearchResult:
    job_id: str
    query: str
    status: str
    answer: list = field(default_factory=list)          # [{"text", "citations": [n]}]
    sources: list = field(default_factory=list)          # Source (as dict)
    conflicts: list = field(default_factory=list)        # {"a", "b", "statement_a", "statement_b", "values_a", "values_b"}
    dropped_claims: list = field(default_factory=list)
    feed_items: list = field(default_factory=list)
    providers: list = field(default_factory=list)        # {"provider", "status", "error_code", "hits"}
    attempts: list = field(default_factory=list)         # SourceRecord dicts of failed/refused retrievals
    blocked_non_english: int = 0                         # IDN-1: sites refused because the address uses non-English letters
    synthesis_method: str = "none"
    brain_status: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""
    elapsed_s: float = 0.0
    error_code: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class ResearchJob:
    def __init__(self, request: ResearchRequest, *, fetcher: SafeFetcher, providers: list,
                 complete: Optional[Callable] = None, progress: Optional[Callable] = None,
                 clock: Callable = time.monotonic):
        self.req, self.fetcher, self.providers = request, fetcher, list(providers)
        self.req.budget.clamp()
        self.complete = complete if request.use_brain else None
        self.progress = progress or (lambda **_: None)
        self.cancel_flag = CancelFlag()
        self.brain_yield = CancelFlag()     # R1-05: the user's turn takes the Brain; the job goes on without it
        self.clock = clock
        self.job_id = str(uuid.uuid4())
        self._blocked_sites = set()          # R1-02: sites refused for non-English letters (NP.site_key)

    def cancel(self):
        self.cancel_flag.cancel()

    def yield_brain(self):
        """Stop this job's Brain call now (or skip it); the extractive answer is used instead."""
        self.brain_yield.cancel()

    def _brain_call(self, t0):
        """The Brain callable for synthesis, bounded by what is left of the deadline and stopped by Cancel or by
        yield_brain() during the call (R1-05); None when there is no Brain, no time left or the slot was yielded."""
        left = self.req.budget.deadline_s - (self.clock() - t0)
        if self.complete is None or left <= 0 or self.brain_yield.cancelled:
            return None
        stop = _Either(self.cancel_flag, self.brain_yield)
        return lambda messages: call_brain(self.complete, messages, cancel=stop, timeout_s=left)

    def _p(self, stage, **kw):
        try:
            self.progress(job_id=self.job_id, stage=stage, **kw)
        except Exception:
            pass

    def run(self) -> ResearchResult:
        t0 = self.clock()
        res = ResearchResult(self.job_id, " ".join((self.req.query or "").split())[:400], FAILED,
                             started_at=R.utc_now())
        try:
            self._run(res, t0)
        except Exception:
            res.status, res.error_code = FAILED, "INTERNAL_ERROR"
        # R1-02: one count per site, across search providers, user URLs, feeds and redirects.
        res.blocked_non_english = len(self._blocked_sites)
        res.finished_at, res.elapsed_s = R.utc_now(), round(self.clock() - t0, 3)
        self._p("finished", status=res.status)
        return res

    def _note_blocked(self, fr):
        if fr.record.refusal_code == NP.HOST_NON_ENGLISH:
            url = getattr(fr, "refused_url", None) or fr.record.requested_url
            self._blocked_sites.add(NP.site_key(url) or url)

    def _expired(self, t0):
        return self.clock() - t0 > self.req.budget.deadline_s

    def _run(self, res: ResearchResult, t0):
        b = self.req.budget
        if not res.query and not self.req.urls and not self.req.feeds:
            res.status, res.error_code = FAILED, "EMPTY_REQUEST"
            return
        # 1. Search (leads only).
        leads, snippets = [], {}
        for u in self.req.urls[:MAX_USER_URLS]:
            leads.append((u, None, "user"))
        any_provider_ok = False
        if self.req.use_search and res.query:
            self._p("search", providers=[p.name for p in self.providers])
            for p in self.providers:
                if self.cancel_flag.cancelled:
                    res.status = CANCELLED
                    return
                sr = p.search(res.query, max_results=b.max_results_per_provider)
                res.providers.append({"provider": p.name, "status": sr.status, "error_code": sr.error_code,
                                      "hits": len(sr.hits)})
                self._blocked_sites.update(getattr(sr, "blocked_sites", None) or ())
                if sr.status in (S.OK, S.NO_RESULTS):
                    any_provider_ok = True
                for h in sr.hits:
                    leads.append((h.url, h.title, p.name))
                    snippets.setdefault(EV.normalise_url(h.url), (h.title, h.snippet, p.name, h.url))
                if sr.status == S.OK:
                    break           # first configured provider with results wins; the rest stay as reported
        # 2. Feeds (reported items; never fetched further).
        for fu in self.req.feeds[:MAX_FEEDS]:
            fr = self.fetcher.fetch(fu, cancel=self.cancel_flag)
            if not fr.ok or fr.kind not in ("feed", "html"):
                self._note_blocked(fr)
                res.attempts.append(fr.record.to_dict())
                continue
            try:
                feed = FD.parse_feed(fr.text, fr.record.final_url or fu)
            except FD.FeedRefused as exc:
                fr.record.refusal_code = exc.code
                res.attempts.append(fr.record.to_dict())
                continue
            for it in feed.items[:20]:
                res.feed_items.append({"feed": feed.title, "title": it.title, "url": it.url,
                                       "published_at": it.published_at, "summary": it.summary[:400],
                                       "injection_flags": _flags(it.title, it.summary)})
        if not leads and not res.feed_items:
            if self.req.use_search and res.query and not any_provider_ok:
                res.status, res.error_code = PROVIDER_UNAVAILABLE, "NO_PROVIDER_AVAILABLE"
            else:
                res.status = NO_RESULT
            return
        # 3. Retrieve + extract (bounded).
        seen, raw, total_bytes = set(), [], 0
        for i, (url, title, origin) in enumerate(leads):
            if self.cancel_flag.cancelled:
                res.status = CANCELLED
                return
            if self._expired(t0):
                res.status = TIMED_OUT
                break
            if len(raw) >= b.max_pages or total_bytes >= b.max_total_bytes:
                break
            key = EV.normalise_url(url)
            if key in seen:
                continue
            seen.add(key)
            self._p("retrieve", done=len(raw), total=min(len(leads), b.max_pages), host=_host(url))
            fr = self.fetcher.fetch(url, cancel=self.cancel_flag)
            rec = fr.record
            rec.provider = origin if origin != "user" else None
            if fr.record.fetch_status == R.CANCELLED:
                res.status = CANCELLED
                return
            if not fr.ok or fr.kind not in ("html", "text"):
                self._note_blocked(fr)
                res.attempts.append(rec.to_dict())
                sn = snippets.get(key)
                if sn and sn[1]:
                    rec.analysed_scope = R.SNIPPET_ONLY
                    rec.injection_flags = _flags(sn[0], sn[1])
                    raw.append({"title": sn[0] or sn[3], "url": sn[3], "text": sn[1], "record": rec,
                                "sha256": None})
                continue
            total_bytes += rec.bytes
            ex = extract_html(fr.text, rec.final_url or url) if fr.kind == "html" else extract_text(fr.text)
            rec.extraction_method, rec.analysed_scope = ex.method, R.FULL_TEXT
            rec.title, rec.site_name, rec.language = ex.title, ex.site_name, ex.language
            rec.published_at, rec.modified_at = ex.published_at, ex.modified_at
            text = ex.text
            if not text.strip():
                rec.analysed_scope = R.METADATA_ONLY
            rec.injection_flags = _flags(ex.title or title, text)
            raw.append({"title": ex.title or title or _host(url), "url": rec.final_url or url, "text": text,
                        "record": rec, "sha256": rec.sha256})
        if res.status in (CANCELLED,):
            return
        timed_out = res.status == TIMED_OUT
        # 4. Evaluate.
        self._p("evaluate", sources=len(raw))
        ev = EV.evaluate([{"url": r["url"], "text": r["text"], "sha256": r["sha256"]} for r in raw], res.query)
        kept = [i for i in ev.kept]
        number_of = {}
        for n, i in enumerate(kept, 1):
            r = raw[i]
            number_of[i] = n
            res.sources.append(asdict(Source(n, r["title"][:300], r["url"], r["record"].to_dict(),
                                             r["record"].analysed_scope, r["text"][:20000],
                                             r["record"].injection_flags, ev.relevance.get(i, 0.0))))
        for i, j in ev.near_duplicates.items():
            if i in number_of:
                res.sources[number_of[i] - 1]["near_duplicate_of"] = number_of.get(j)
        for c in ev.conflicts:
            res.conflicts.append({"a": number_of[c.source_a], "b": number_of[c.source_b],
                                  "statement_a": c.statement_a, "statement_b": c.statement_b,
                                  "values_a": c.values_a, "values_b": c.values_b})
        # 5. Synthesize + 6. cite (verified).
        if self.cancel_flag.cancelled:
            res.status = CANCELLED
            return
        syn = None
        timed_out = timed_out or self._expired(t0)   # R1-05: then the Brain is not called (_brain_call)
        if res.sources:
            self._p("synthesize", method="brain" if self.complete else "extractive")
            # Numbering matches res.sources; metadata-only sources get empty text so nothing can cite them.
            numbered = [(s["title"], U.evidence_text(s["text"]) if s["analysed_scope"] in (R.FULL_TEXT, R.SNIPPET_ONLY)
                         else "") for s in res.sources]
            syn = SY.synthesize(res.query or "summary", numbered, complete=self._brain_call(t0))
        if self.cancel_flag.cancelled:              # R1-05: Cancel during synthesis ends the job without an answer
            res.status = CANCELLED
            return
        if syn is not None:
            res.synthesis_method, res.brain_status = syn.method, syn.brain_status
            res.answer = [{"text": c.text, "citations": c.citations, "quoted": c.quoted} for c in syn.verified.claims]
            res.dropped_claims = syn.verified.dropped
        if timed_out:
            res.status = TIMED_OUT
        elif res.answer or res.feed_items:
            res.status = COMPLETED_WITH_RESULT
        else:
            res.status = NO_RESULT


def _flags(*parts) -> list:
    """R41-04: instruction-like text is flagged wherever a source carries it: its title as well as its text."""
    out = []
    for p in parts:
        for f in U.flags(p or ""):
            if f not in out:
                out.append(f)
    return out


class _Either:
    def __init__(self, *flags):
        self.flags = flags

    @property
    def cancelled(self):
        return any(f.cancelled for f in self.flags)


def call_brain(complete, messages, *, cancel, timeout_s):
    """Call ``complete(messages)``, passing ``cancel`` (an object with ``.cancelled``) and ``timeout_s`` when it
    accepts them (`local_brain.make_complete` does)."""
    try:
        params = inspect.signature(complete).parameters
    except (TypeError, ValueError):
        params = {}
    if "cancel" in params or any(p.kind is p.VAR_KEYWORD for p in params.values()):
        return complete(messages, cancel=cancel, timeout_s=timeout_s)
    return complete(messages)


def _host(url):
    try:
        from urllib.parse import urlsplit
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def discover_feeds(fetcher: SafeFetcher, page_url: str, *, cancel=None) -> dict:
    """User-initiated feed discovery: read one page and list its RSS/Atom alternates. Nothing is fetched further."""
    fr = fetcher.fetch(page_url, cancel=cancel)
    if not fr.ok or fr.kind != "html":
        return {"status": "FAILED", "record": fr.record.to_dict(), "feeds": []}
    ex = extract_html(fr.text, fr.record.final_url or page_url)
    return {"status": "OK", "record": fr.record.to_dict(), "feeds": ex.feed_links}
