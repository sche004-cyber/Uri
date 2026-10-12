"""W1-A0 closure review round 39 finding R39-01. Each R39 link case fails on 2af8eeac.

R39-01: R38 read look-alike digits only in one spacing pattern, so 'g0 v', '0r g', 'c  0  m', '(c 0 m)', tab-spelt forms
        passed while their letter spellings were caught. A same-length copy of the text with '0'/'1'/'|' read as letters
        (in tokens that hold a letter, or lone characters; numbers keep their digits) now goes through the same ending
        check as the letter spellings, and the mask covers the whole ending.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ g 0v", "refunds-portal ~ g0 v", "refunds-portal g0 v/claim", "refunds-portal ~ 0r g",
         "refunds-portal ~ 0 rg", "refunds-portal ~ c  0  m", "refunds-portal (c 0 m)/claim", "refunds-portal ~ c\t0\tm",
         "refunds-portal ~ i  0", "refunds-portal ~ с0 м", "refunds-portal ~ sh 0p")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r39_01_is_a_link_and_the_whole_ending_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    masked = U.mask_links(text, "[link removed]")
    assert "refunds" not in masked and " м " not in masked and "0p" not in masked, link


@pytest.mark.parametrize("link", LINKS)
def test_r39_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Version v1.0 shipped.", "Room 101 is open.", "Score 1 0 2 today.",
                                  "COVID-19 cases rose 10% in 2020.", "Fees: Rs 5,00,000 per year.",
                                  "Meet at 10am on the 1st.", "Top 10 sites, 100% sure.", "A ratio of 3:1 and 1/2 cup."))
def test_r39_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
