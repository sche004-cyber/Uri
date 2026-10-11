"""W1-A0 closure review round 28 finding R28-01. Each R28 link case fails on 0fcc39d4.

R28-01: a domain ending spelt with Latin letters whose Unicode name holds no plain letter (U+0251 LATIN SMALL LETTER
        ALPHA 'ɑ', U+0269 IOTA 'ɩ', U+0196 'Ɩ', U+0185 TONE SIX 'ƅ') was not an ending. Such letters are now read by the
        letter they are drawn like, and any other letter through the confusables skeleton.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import surface as SF
from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal bɩz/claim", "refunds-portal ɩo/claim", "refunds-portal ~ cɑsh", "refunds-portal ~ ɑpp",
         "refunds-portal ~ ɩnfo", "refunds-portal ~ cɑsh/claim", "refunds-portal ~ ɑpp/claim",
         "refunds-portal ƅiz/claim", "refunds-portal ~ Ɩnfo", "refunds-portal ~ ꞵiz")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r28_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link
    assert "refunds-portal" not in SF.clean(text), link


@pytest.mark.parametrize("link", LINKS)
def test_r28_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Den store sø er smuk.", "Ærø is an island.", "Þetta er gott.", "Við erum hér.",
                                  "Straße und Weg.", "The ŋ sound and the ə vowel."))
def test_r28_01_ordinary_latin_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
