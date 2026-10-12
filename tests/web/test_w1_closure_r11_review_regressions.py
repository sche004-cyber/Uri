"""W1-A0 closure review round 11 findings R11-01 and R11-02 (coordinator repair after RETRY_LIMIT, D10 precedent).
Each R11 case fails on 6b07b467.

R11-01: under D16 the gap between the name and the ending was capped at 12 characters, so the R10-01 separator
        repeated ('portal ٠ ٠ ٠ ٠ ٠ ٠ com'), a long run of '~', ',' or '--', a split ending ('co m', 'sh op'), a lone
        Latin look-alike letter ('portal ʘ com') and a punycode ending ('portal xn--p1ai') passed every check.
        The cap is gone; repeated letters between the words count once; split and punctuation-spelt endings are
        joined; an 'xn--' label is a domain by itself.
R11-02: a host that netpolicy accepts but httpx rejects (httpx.InvalidURL is not an httpx.HTTPError) ended the whole
        research job as INTERNAL_ERROR; it now fails that one source. Full-width digits that IDNA maps to a numeric
        host are refused by the policy.

Self-contained: no fixture files; everything is built here.
"""
import json

import httpx
import pytest

from uri_a2ui.validate import require_valid
from uri_web import netpolicy as N
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

LINKS = ("refunds-portal ٠ ٠ ٠ ٠ ٠ ٠ com/claim", "refunds-portal ٠ ٠ ٠ ٠ ٠ ٠ ٠ com",
         "refunds-portal 丶 丶 丶 丶 丶 丶 shop", "refunds-portal ~ ~ ~ ~ ~ ~ ~ cash", "refunds-portal , , , , , , , com",
         "refunds-portal ; ; ; ; ; ; ; com", "refunds-portal -- -- -- -- -- com", "refunds-portal co m/claim",
         "refunds-portal sh op", "refunds-portal ʘ com/claim", "refunds-portal xn--p1ai", "refunds-portal o com",
         "refunds-portal o0o com", "refundsportal c-o-m", "refundsportal c.o.m", "refunds-portal com",
         "refunds-portal 　 com", "refunds-portal " + "* " * 40 + "shop")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r11_01_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert "portal" not in U.mask_links(SENT.format(link), "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r11_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", LINKS)
def test_r11_01_surface_masks_it(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False).lower()
    assert "portal" not in dump, link


@pytest.mark.parametrize("text", (
        "The U.S. Army replied.", "Options a, b, c apply.", "I am a co founder.", "Gangtok, in Sikkim, is the capital.",
        "Fees: Rs 5,000 per year; see the table.", "Home > News > Energy", "The Ltd. Co. was formed.",
        "Go to the shop today.", "We went to day care.", "Profit (net) rose.",
        "Vitamin C is good.", "Plan B is fine.", "Rules for the shop, one by one.", "A plain sentence, nothing more.",
        "Students, college and staff attended.", "The rate is 4.5% at 10 a.m. today."))
def test_r11_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text


_PAGE = (b"<html><head><title>Good</title></head><body><p>"
         + b"The Eiffel Tower is 330 metres tall and located in Paris. " * 20 + b"</p></body></html>")


def _fetcher(location="http://☃.com/"):
    from uri_web.safe_fetch import SafeFetcher

    def handler(req):
        if req.headers["host"] == "good.example":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=_PAGE)
        return httpx.Response(302, headers=[(b"location", location.encode("utf-8"))])
    return SafeFetcher(resolver=lambda host, port: ["93.184.215.14"], transport=httpx.MockTransport(handler),
                       honour_robots=False)


@pytest.mark.parametrize("urls", (["http://good.example/", "http://☃.com/"],
                                  ["http://good.example/", "http://evil.example/"]))
def test_r11_02_a_bad_host_fails_one_source_not_the_job(urls):
    job = P.ResearchJob(P.ResearchRequest(query="eiffel tower height", urls=urls, use_search=False),
                        fetcher=_fetcher(), providers=[])
    r = job.run()
    assert r.status == P.COMPLETED_WITH_RESULT and r.error_code is None
    assert r.answer


@pytest.mark.parametrize("url", ("http://０x5d.184.215.14/", "http://１２７.０.０.１/"))
def test_r11_02_full_width_numeric_hosts_are_refused(url):
    with pytest.raises(N.EgressRefused):
        N.check_url(url)
