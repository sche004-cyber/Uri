"""W1-A0 closure review round 35 finding R35-01. Each R35 link case fails on dfad82d1.

R35-01: after '. ', ': ', '! ' or '? ' a leading 'I' look-alike of 'l' was never read (sentence-start exemption), so
        'refunds-portal. Iy' and 'refunds-portal: Iink/claim' passed while their 'l' spellings were caught. The exemption
        now protects only the ordinary words whose 'l' reading is a domain ('It', 'Is'); look-alike endings behave
        exactly like their plain spelling.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal. Iive", "refunds-portal. Iy", "refunds-portal. Iondon", "refunds-portal: Iink/claim",
         "refunds-portal? Iy/claim", "refunds-portal! Ioan/claim")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r35_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r35_01_matches_the_plain_spelling(link):
    assert U.has_link_or_contact(SENT.format(link)) == U.has_link_or_contact(SENT.format(link.replace("I", "l")))


@pytest.mark.parametrize("link", ("refunds-portal: Iink/claim", "refunds-portal? Iy/claim"))
def test_r35_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("The board met. It is fine.", "In 2020 it changed.", "Yes. I like it.",
                                  "Note: Item 3 applies.", "We met. Ink was spilled.", "He left. Italy won.",
                                  "Done. Is it ready?"))
def test_r35_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
