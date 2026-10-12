"""Regressions for review R9 of 3dd9cde (findings R9-02, R9-06). Each fails without its repair.

R9-02  D7 quantity detection was a word list: ordinals past "tenth", "hundredth"/"thousandth", Unicode vulgar fractions
       and Roman numerals were shown in the Brain's words. Those forms are now quantities, and - not decided by a
       list - a Brain sentence that adds any non-function word to its supporting source sentence is quoted instead.
R9-06  Name resolution ran outside the total deadline and the cancel flag: a slow resolver held a fetch past its
       budget (twice with robots).
"""
import threading
import time

import httpx
import pytest

from uri_web import safe_fetch as SF
from uri_web import synthesize as SY
from tests.web.d7_invariant import only_source_quotes

SRC = ("The runner finished eleventh in the final race of the season. "
       "The museum celebrated its hundredth anniversary with a public exhibition. "
       "Regulators said the levy rose by ¼ after the review. "
       "Officials said the company filed for Chapter VII protection.")
CHANGED = [
    "The runner finished twelfth in the final race of the season [1].",
    "The museum celebrated its thousandth anniversary with a public exhibition [1].",
    "Regulators said the levy rose by ¾ after the review [1].",
    "Officials said the company filed for Chapter XI protection [1].",
]


@pytest.mark.parametrize("claim", CHANGED)
def test_r9_02_changed_value_is_never_shown_in_the_brains_words(claim):
    syn = SY.synthesize("q", [("Source", SRC)], complete=lambda _m: ("COMPLETE", claim))
    assert syn.method == "brain"
    body = claim.replace(" [1]", "")
    assert all(c.text != body for c in syn.verified.claims)
    assert only_source_quotes(syn.verified, [SRC], claim)


@pytest.mark.parametrize("text", ["finished eleventh", "the twenty-third time", "its hundredth year",
                                  "a thousandth of it", "rose by ¾", "Chapter XI", "Louis XIV", "Ⅷ items",
                                  "x² more", "cost ₩ 50"])
def test_r9_02_number_forms_are_quantities(text):
    assert SY.states_quantity(text)


@pytest.mark.parametrize("text", ["The district board approved the rules and the plan",
                                  "Officials met with the board in the north", "I said it was over"])
def test_r9_02_ordinary_words_are_not_quantities(text):
    assert not SY.states_quantity(text)


def test_r9_02_any_added_content_word_means_the_source_is_quoted():
    src = "The bridge reopened to traffic after repairs were completed by the city."
    v = SY.verify("The bridge reopened to heavy traffic after repairs were completed by the city [1].", [src])
    assert [(c.text, c.quoted) for c in v.claims] == [(src, True)]
    # Only function words differ: still the Brain's sentence, checked lexically.
    v = SY.verify("The bridge reopened to traffic after the repairs were completed by the city [1].", [src])
    assert len(v.claims) == 1 and v.claims[0].quoted is False


# ---- R9-06 ------------------------------------------------------------------------------------------------------------

def _slow_resolver(seconds, calls):
    def resolve(host, port):
        calls.append(host)
        time.sleep(seconds)
        return ["93.184.216.34"]
    return resolve


def _fetcher(resolver, **kw):
    return SF.SafeFetcher(resolver=resolver, transport=httpx.MockTransport(
        lambda r: httpx.Response(200, headers={"content-type": "text/plain"}, text="ok")), **kw)


@pytest.mark.parametrize("robots", [False, True])
def test_r9_06_slow_dns_is_bounded_by_the_total_timeout(robots):
    calls = []
    f = _fetcher(_slow_resolver(3.0, calls), total_timeout=1.0, honour_robots=robots)
    t0 = time.monotonic()
    res = f.fetch("https://slow-dns.example/page")
    elapsed = time.monotonic() - t0
    assert res.record.fetch_status == "TIMED_OUT" and elapsed < 1.6, elapsed
    assert len(calls) == 1               # robots used the budget: the page lookup is not started


def test_r9_06_slow_dns_is_bounded_by_the_connect_timeout():
    f = _fetcher(_slow_resolver(3.0, []), total_timeout=20.0, connect_timeout=0.5, honour_robots=False)
    t0 = time.monotonic()
    res = f.fetch("https://slow-dns.example/page")
    assert res.record.fetch_status == "TIMED_OUT" and time.monotonic() - t0 < 1.2


def test_r9_06_cancel_cuts_a_slow_lookup():
    flag = SF.CancelFlag()
    f = _fetcher(_slow_resolver(3.0, []), total_timeout=20.0, connect_timeout=10.0, honour_robots=False)
    threading.Timer(0.3, flag.cancel).start()
    t0 = time.monotonic()
    res = f.fetch("https://slow-dns.example/page", cancel=flag)
    assert res.record.fetch_status == "CANCELLED" and time.monotonic() - t0 < 1.0


def test_r9_06_fast_dns_and_refusals_unchanged():
    assert _fetcher(lambda h, p: ["93.184.216.34"], honour_robots=False).fetch("https://ok.example/").record.ok
    res = _fetcher(lambda h, p: ["10.0.0.1"], honour_robots=False).fetch("https://internal.example/")
    assert res.record.fetch_status == "REFUSED"
