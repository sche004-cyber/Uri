"""IDN-1b (owner decision D33, 2026-10-12): the block message says it was for security and that the site can be opened in
the user's own browser, in the research result and in the chat fetch tool; and the two refusal forms IDN-1's review
left without a reason (R1-03 / R2-01) now carry HOST_NON_ENGLISH.

Each test fails on 368188b7 (after IDN-1, before IDN-1b) except the guards marked as such. Self-contained.
"""
import httpx
import pytest

from uri_web import netpolicy as N
from uri_web import pipeline as P
from uri_web.safe_fetch import SafeFetcher
from uri_web.surface import blocked_note

_PAGE = (b"<html><head><title>Good</title></head><body><p>"
         + b"The Eiffel Tower is 330 metres tall and located in Paris. " * 20 + b"</p></body></html>")


def test_d33_message_wording():
    m = N.NON_ENGLISH_MESSAGE
    assert m.startswith("For security reasons, URI did not open this site.")
    assert "non-English letters" in m and "scam" in m.lower()
    assert m.endswith("You can open it in your web browser instead.")
    assert all(len(x.split()) <= 12 for x in m.split(". ")), m          # D18: short sentences
    assert blocked_note(1) == m
    assert blocked_note(2).startswith("For security reasons, URI did not open 2 sites.")
    assert blocked_note(2).endswith("You can open them in your web browser instead.")


def test_d33_chat_fetch_tool_says_why():
    from uri_core.tools import fetch_url as F
    assert F._REFUSAL_MESSAGES[N.HOST_NON_ENGLISH] == N.NON_ENGLISH_MESSAGE


@pytest.mark.parametrize("url", ("http://%D1%80aypal.com/", "http://%D1%80%D0%B0%D1%83%D1%80%D0%B0l.com/x",
                                 "https://example.%D1%80%D1%84/", "http://b%C3%BCcher.de/"))
def test_r1_03_percent_encoded_non_english_host_gets_the_reason(url):
    with pytest.raises(N.EgressRefused) as e:
        N.check_url(url)
    assert e.value.code == N.HOST_NON_ENGLISH, url


@pytest.mark.parametrize("url", ("http://exa%41mple.com/", "http://%2e.com/", "http://a%20b.com/"))
def test_guard_other_percent_hosts_stay_invalid(url):
    # Guard (holds before and after): '%' that decodes to ASCII is still refused, as HOST_INVALID.
    with pytest.raises(N.EgressRefused) as e:
        N.check_url(url)
    assert e.value.code == "HOST_INVALID", url


def _fetcher(seen, location):
    def handler(req):
        host = req.headers["host"]
        seen.append(host)
        if host == "hop.example":
            return httpx.Response(302, headers=[(b"location", location.encode("utf-8"))])
        return httpx.Response(200, headers={"content-type": "text/html"}, content=_PAGE)
    return SafeFetcher(resolver=lambda host, port: ["93.184.215.14"], transport=httpx.MockTransport(handler),
                       honour_robots=False)


@pytest.mark.parametrize("location", ("http://ｐａｙｐａｌ.com/",
                                      "http://%D1%80aypal.com/"))
def test_r2_01_redirect_httpx_rejects_keeps_the_reason(location):
    seen = []
    r = _fetcher(seen, location).fetch("http://hop.example/")
    assert (r.record.fetch_status, r.record.refusal_code) == ("REFUSED", N.HOST_NON_ENGLISH)
    assert seen == ["hop.example"]                      # the target is never contacted


def test_r2_01_counted_and_job_completes():
    seen = []
    job = P.ResearchJob(P.ResearchRequest(query="eiffel tower height",
                                          urls=["http://hop.example/", "http://good.example/"], use_search=False),
                        fetcher=_fetcher(seen, "http://ｐａｙｐａｌ.com/"), providers=[])
    r = job.run()
    assert r.status == P.COMPLETED_WITH_RESULT and r.answer
    assert r.blocked_non_english == 1


def test_guard_ordinary_redirect_still_followed():
    # Guard (holds before and after): the Location tap does not change a normal redirect.
    seen = []
    r = _fetcher(seen, "http://good.example/page").fetch("http://hop.example/")
    assert r.record.fetch_status == "OK" and seen == ["hop.example", "good.example"]
