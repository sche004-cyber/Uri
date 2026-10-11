"""W1-A0 closure review round 27 finding R27-01. Each R27 link case fails on be7cdecf.

R27-01: a domain ending spelt with Latin look-alike letters (script g 'ɡov', small capitals 'ᴄᴏᴍ', letters with strokes
        or hooks 'cøm', 'ȼom', 'ƈom', 'sħop') was not an ending. Each Latin letter is now also read as the plain letter
        its Unicode name says it is drawn from, for the whole Latin range by rule.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ɡov/claim", "refunds-portal ɡov", "refunds-portal ᴄᴏᴍ/claim",
         "refunds-portal ~ cøm/claim", "refunds-portal ~ sħop", "refunds-portal ~ ƈom",
         "refunds-portal ~ ȼom", "refunds-portal ~ ʃħop")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS[:-1])
def test_r27_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS[:-1])
def test_r27_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Den store sø er smuk.", "Byłem w domu.", "Le café est bon.", "Straße und Weg.",
                                  "Ærø is an island."))
def test_r27_01_ordinary_latin_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
