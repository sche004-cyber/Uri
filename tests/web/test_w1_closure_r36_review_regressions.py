"""W1-A0 closure review round 36 finding R36-01. Each R36 link case fails on 9f7b9b2a.

R36-01: a top-level domain spelt only with ASCII look-alikes including '|' ('.|0|' = .lol, '.0||0' = .ollo) was never
        read, because a run needed a letter. Only runs made entirely of digits are now skipped as numbers.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal.|0|/claim", "refunds-portal.0||0/claim", "refunds-portal.|0|", "refunds-portal ~ |0|",
         "refunds-portal.10|/claim")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r36_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r36_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Name | Age | City", "Score 10 | 20 | 30", "Fees: Rs 5,000 per year.",
                                  "Room 101 is open."))
def test_r36_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
