"""W1-A0 closure review round 33 finding R33-01. Each R33 link case fails on fc3d6f42.

R33-01: a leading capital 'I' (a listed look-alike of 'l') was never read as 'l', so endings 'Iy', 'Ia', 'Iive', 'Iink'
        after a separator passed. A leading 'I' is now read as 'l' when the word then spells a listed top-level domain
        and does not start a sentence; 'It is', 'In 2020', 'I like', 'Italy' keep their meaning.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ Iy", "refunds-portal ~ Ia", "refunds-portal ~ Ii", "refunds-portal ~ Iu", "refunds-portal ~ Iv",
         "refunds-portal ~ Ik", "refunds-portal ~ Iol", "refunds-portal ~ Iive", "refunds-portal ~ Iink",
         "refunds-portal ~ Iat", "refunds-portal ~ Iaw", "refunds-portal ~ Iand", "refunds-portal ~ Iife",
         "refunds-portal ~ Ioan")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r33_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS[::3])
def test_r33_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("The board met. It is fine.", "In 2020 it changed.", "Yes, I like it.",
                                  "He said It was good.", "She moved to Italy and Iran."))
def test_r33_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
