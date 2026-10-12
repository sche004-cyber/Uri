"""IDN-1 repair round 1 (review findings R1-01, R1-02).

R1-01: KELVIN SIGN (U+212A) lower-cases to ASCII 'k', so the non-ASCII test must look at the raw address.
R1-02: blocked_non_english counts sites, not hits or refused fetches: one blocked site is counted once.

Each test fails on 21ad9409 (before the repair). Self-contained: everything is built here.
"""
import httpx
import pytest

from uri_web import netpolicy as N
from uri_web import pipeline as P
from uri_web import search as S
from uri_web.safe_fetch import SafeFetcher

_PAGE = (b"<html><head><title>Good</title></head><body><p>"
         + b"The Eiffel Tower is 330 metres tall and located in Paris. " * 20 + b"</p></body></html>")


@pytest.mark.parametrize("url", ("http://Kelvin.com/", "https://KELVIN.com/x", "http://a.K.example/"))
def test_r1_01_kelvin_sign_is_refused(url):
    with pytest.raises(N.EgressRefused) as e:
        N.check_url(url)
    assert e.value.code == N.HOST_NON_ENGLISH, url


def test_r1_01_kelvin_sign_is_never_contacted_on_any_route():
    seen = []

    def handler(req):
        host = req.headers["host"]
        seen.append(host)
        if host == "hop.example":
            return httpx.Response(302, headers=[(b"location", "http://Kelvin.com/".encode())])
        return httpx.Response(200, headers={"content-type": "text/html"}, content=_PAGE)

    fetcher = SafeFetcher(resolver=lambda host, port: ["93.184.215.14"], transport=httpx.MockTransport(handler),
                          honour_robots=False)
    job = P.ResearchJob(P.ResearchRequest(query="eiffel tower height",
                                          urls=["http://Kelvin.com/a", "http://hop.example/"], use_search=True),
                        fetcher=fetcher, providers=[_tavily(["http://good.example/", "http://Kelvin.com/b"])])
    r = job.run()
    assert "kelvin.com" not in seen, seen
    assert r.status == P.COMPLETED_WITH_RESULT
    assert r.blocked_non_english == 1


def _tavily(urls):
    def handler(req):
        return httpx.Response(200, json={"results": [
            {"url": u, "title": "Eiffel tower facts", "content": "The Eiffel Tower is 330 metres tall."} for u in urls]})
    return S.TavilyProvider(api_key="k", transport=httpx.MockTransport(handler))


def _fetcher(redirects=None):
    redirects = redirects or {}

    def handler(req):
        host = req.headers["host"]
        if host in redirects:
            return httpx.Response(302, headers=[(b"location", redirects[host].encode())])
        return httpx.Response(200, headers={"content-type": "text/html"}, content=_PAGE)
    return SafeFetcher(resolver=lambda host, port: ["93.184.215.14"], transport=httpx.MockTransport(handler),
                       honour_robots=False)


def _run(urls=(), providers=(), redirects=None):
    job = P.ResearchJob(P.ResearchRequest(query="eiffel tower height", urls=list(urls), use_search=bool(providers)),
                        fetcher=_fetcher(redirects), providers=list(providers))
    return job.run()


def test_r1_02_a_one_provider_two_pages_of_one_site():
    sr = _tavily(["http://good.example/", "http://bücher.de/1", "http://bücher.de/2"]).search("eiffel")
    assert sr.blocked_non_english == 1
    r = _run(providers=[_tavily(["http://good.example/", "http://bücher.de/1", "http://bücher.de/2"])])
    assert r.blocked_non_english == 1


def test_r1_02_b_two_providers_return_the_same_site():
    site = "http://раураl.com/"
    r = _run(urls=["http://good.example/"], providers=[_tavily([site]), _tavily([site, "http://good.example/x"])])
    assert r.blocked_non_english == 1


def test_r1_02_c_user_url_and_search_hit_of_one_site():
    r = _run(urls=["http://bücher.de/", "http://good.example/"],
             providers=[_tavily(["http://bücher.de/", "http://good.example/x"])])
    assert r.blocked_non_english == 1


def test_r1_02_c2_unicode_and_ascii_spellings_are_one_site():
    r = _run(urls=["http://bücher.de/", "http://good.example/"],
             providers=[_tavily(["http://xn--bcher-kva.de/", "http://good.example/x"])])
    assert r.blocked_non_english == 1


def test_r1_02_d_two_redirects_to_one_site():
    r = _run(urls=["http://hop1.example/", "http://hop2.example/", "http://good.example/"],
             redirects={"hop1.example": "http://bücher.de/", "hop2.example": "http://bücher.de/other"})
    assert r.status == P.COMPLETED_WITH_RESULT
    assert r.blocked_non_english == 1


def test_r1_02_distinct_sites_are_still_each_counted():
    r = _run(urls=["http://bücher.de/", "http://hop.example/", "http://good.example/"],
             providers=[_tavily(["http://xn--80ak6aa92e.com/", "http://good.example/x"])],
             redirects={"hop.example": "http://раураl.com/"})
    assert r.blocked_non_english == 3
