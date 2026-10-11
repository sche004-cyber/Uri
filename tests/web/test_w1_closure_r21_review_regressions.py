"""W1-A0 closure review round 21 finding R21-01. Each link case fails on 68feb3e7.

R21-01: the R20-01 repair classified a word without its marks named 'COMBINING ...' only, so a run of script marks
        with no base letter (Devanagari nukta/candrabindu/anusvara, Tibetan, Arabic, Thai, Telugu signs) between the
        name and a non-core ending was read as the name. Marks with no base letter before them are now dropped
        whatever their name, so a word made only of marks is a separator again (R19-01).

Self-contained: no fixture files; everything is built here (characters as escapes).
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal \u093c\u0901\u0902 shop", "refunds-portal \u0f39\u0f37\u0f35 shop",
         "refunds-portal \u0650\u065c\u0655 shop", "refunds-portal \u0e31\u0e34\u0e47 shop",
         "refunds-portal \u0c3c\u0c00\u0c01 shop", "refunds-portal \u093c\u0901\u0902\u0903 cash")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r21_is_a_link(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), ascii(link)
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), ascii(link)


@pytest.mark.parametrize("link", LINKS)
def test_r21_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", ascii(link)
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), ascii(link)


@pytest.mark.parametrize("text", ("\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u0941\u0928\u093f\u092f\u093e shop",
                                  "A plain English sentence about the shop.",
                                  "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35 shop today"))
def test_r21_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), ascii(text)
