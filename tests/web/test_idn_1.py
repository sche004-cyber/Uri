"""IDN-1 (owner decision D21, 2026-10-11): site addresses with non-English letters are blocked on every route, and the
user is told why in plain words (D18). Also O2: Hebrew points on Hebrew letters read as ordinary text.

Each test fails on e761ce8f (before IDN-1). Self-contained: everything is built here.
"""
import json

import httpx
import pytest

from uri_a2ui.validate import require_valid
from uri_web import netpolicy as N
from uri_web import pipeline as P
from uri_web import search as S
from uri_web import untrusted as U
from uri_web.safe_fetch import SafeFetcher
from uri_web.surface import build_surface

IDN_URLS = ("http://раураl.com/", "http://xn--80ak6aa92e.com/", "http://bücher.de/",
            "http://例え.jp/", "https://example.xn--p1ai/", "http://XN--80ak6aa92e.com/x",
            "http://exa​mple.com/", "https://аpple.com/login")


@pytest.mark.parametrize("url", IDN_URLS)
def test_ac1_non_english_hosts_are_refused(url):
    with pytest.raises(N.EgressRefused) as e:
        N.check_url(url)
    assert e.value.code == N.HOST_NON_ENGLISH, url


@pytest.mark.parametrize("url", ("https://example.com/a", "http://a.b-c.org/", "https://xn.example.com/",
                                 "https://axn--b.example.com/", "http://93.184.215.14/"))
def test_ac1_english_hosts_are_unchanged(url):
    N.check_url(url)


_PAGE = (b"<html><head><title>Good</title></head><body><p>"
         + b"The Eiffel Tower is 330 metres tall and located in Paris. " * 20 + b"</p></body></html>")


def _fetcher(seen):
    def handler(req):
        host = req.headers["host"]
        seen.append(host)
        if host == "good.example":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=_PAGE)
        if host == "hop.example":
            return httpx.Response(302, headers=[(b"location", "http://раураl.com/".encode())])
        return httpx.Response(200, headers={"content-type": "text/html"}, content=_PAGE)
    return SafeFetcher(resolver=lambda host, port: ["93.184.215.14"], transport=httpx.MockTransport(handler),
                       honour_robots=False)


def _tavily(urls):
    def handler(req):
        return httpx.Response(200, json={"results": [
            {"url": u, "title": "Eiffel tower facts", "content": "The Eiffel Tower is 330 metres tall."} for u in urls]})
    return S.TavilyProvider(api_key="k", transport=httpx.MockTransport(handler))


def test_ac2_search_hits_with_such_hosts_are_dropped_and_counted():
    sr = _tavily(["http://good.example/", "http://раураl.com/", "http://xn--p1ai.example/",
                  "http://10.0.0.1/"]).search("eiffel tower")
    assert [h.url for h in sr.hits] == ["http://good.example/"]
    assert sr.blocked_non_english == 2      # the private address is dropped too but is not counted as non-English


def test_ac2_user_url_redirect_and_search_hit_are_refused_and_job_completes():
    seen = []
    job = P.ResearchJob(P.ResearchRequest(query="eiffel tower height",
                                          urls=["http://bücher.de/", "http://hop.example/"], use_search=True),
                        fetcher=_fetcher(seen), providers=[_tavily(["http://good.example/",
                                                                    "http://xn--80ak6aa92e.com/"])])
    r = job.run()
    assert r.status == P.COMPLETED_WITH_RESULT and r.error_code is None and r.answer
    assert not any(h for h in seen if not h.isascii() or h.startswith("xn--")), seen   # never contacted
    codes = [a.get("refusal_code") for a in r.attempts]
    assert codes.count(N.HOST_NON_ENGLISH) == 2, codes          # the user URL and the redirect target
    assert r.blocked_non_english == 3                           # + the search hit


def _result(blocked, sources=True):
    return {"job_id": "j1", "query": "eiffel", "status": P.COMPLETED_WITH_RESULT if sources else P.NO_RESULT,
            "answer": [{"text": "The Eiffel Tower is 330 metres tall.", "citations": [1], "quoted": True}] if sources else [],
            "sources": [{"number": 1, "title": "Good", "url": "https://good.example/",
                         "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}]
            if sources else [],
            "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "extractive", "elapsed_s": 1,
            "blocked_non_english": blocked}


@pytest.mark.parametrize("blocked,sources", ((1, True), (1, False), (3, True)))
def test_ac3_ac4_the_user_is_told_why(blocked, sources):
    s = build_surface(_result(blocked, sources))
    require_valid(s.messages(), set(s.actions))
    texts = [c.get("text", "") for c in s.components]
    note = [t for t in texts if "non-English letters" in t]
    assert len(note) == 1, texts
    # Wording D33 (IDN-1b): security reason, not opened in URI, can be opened in the user's own browser.
    assert note[0].startswith("For security reasons, URI did not open") and "web browser instead" in note[0]
    assert ("open this site" in note[0]) if blocked == 1 else (f"open {blocked} sites" in note[0])
    # D18: short sentences, plain words; no address in the note.
    assert all(len(x.split()) <= 12 for x in note[0].split(". ")), note[0]
    assert "://" not in json.dumps(s.messages(), ensure_ascii=False) and "xn--" not in note[0]


def test_ac3_no_note_when_nothing_was_blocked():
    s = build_surface(_result(0))
    assert not any("non-English" in c.get("text", "") for c in s.components)


# O2: Hebrew points (SHIN DOT U+05C1, SIN DOT U+05C2) on Hebrew letters are ordinary text.
@pytest.mark.parametrize("text", ("שָׁלוֹם עֲלֵיכֶם",
                                  "בְּרֵאשִׁית בָּרָא",
                                  "שׂמחה רבה היום"))
def test_o2_pointed_hebrew_reads_normally(text):
    assert not U.has_link_or_contact(text)
    assert U.mask_links(text, "[link removed]") == U.normalise(text)


@pytest.mark.parametrize("text", ("refunds-portal ׁ com", "refunds-portal cׁom", "refunds-portalׁcom",
                                  "refunds-portalׂshop", "refunds-portal שׁ com"))
def test_o2_a_point_alone_or_on_another_script_is_still_a_link(text):
    assert U.has_link_or_contact(text), text
    assert "portal" not in U.mask_links(text, "[link removed]"), text
