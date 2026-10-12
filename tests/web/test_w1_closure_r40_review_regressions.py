"""W1-A0 closure review round 40 finding R40-01. Each R40 link case fails on df4fd084.

R40-01: a spelt ending whose last look-alike digit touches punctuation ('i 0,', 'i 0)', "'t 0'", 'i 0.') was not read,
        because the token was not a lone character. The test now uses the token's core without punctuation.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("(refunds-portal i 0)", "refunds-portal ~ i 0,", "refunds-portal ~ 't 0'", "refunds-portal ~ i 0;",
         "refunds-portal ~ i 0:", "refunds-portal ~ i 0!")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r40_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r40_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Score 1 0 2 today.", "It costs 1, 0 or 2.", "Ratio (1:0) wins.", "Room 1, floor 0."))
def test_r40_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
