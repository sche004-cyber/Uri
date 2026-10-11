"""W1-A0 closure review round 34 finding R34-01. Each R34 link case fails on bdc82ef1.

R34-01: capital 'I' as 'l' was not read in all-capital runs, and the R33 leading-I step made the per-letter fold turn a
        second 'I' into 'l' ('IIVE' -> 'llVE'). Every reading of a run is now tried ('I'/'|' kept or read as 'l', '0'/'1'
        as 'o'/'l'); a reading that spells a listed domain is used. Sentence-initial 'It', 'In' and numbers are unchanged.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ IIVE", "refunds-portal ~ IINK", "refunds-portal ~ IOI", "refunds-portal ~ PI",
         "refunds-portal ~ II", "refunds-portal MII/claim", "refunds-portal ~ Iy", "refunds-portal.c0m/claim")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r34_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r34_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("The board met. It is fine.", "In 2020 it changed.", "World War II ended.",
                                  "The PI said yes.", "MIT and COVID-19 data.", "Grade A1 and B12 rooms.",
                                  "Version v1.0 shipped.", "Fees: Rs 5,000 per year; see the table.",
                                  "About $1,000,000,000 in 2020, prices rose."))
def test_r34_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
