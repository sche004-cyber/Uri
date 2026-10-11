"""W1-A0 closure review round 20 findings R20-01 and R20-02. Each R20 link case fails on eb4d676d.

R20-01: a separator word with a combining mark added ('丶丿̣', 'ニハト̣', 'ʘ̣') was read as the name. A word is now
        classified without its generic combining marks (named 'COMBINING ...'); script vowel signs ('སི') are kept.
R20-02: a look-alike core domain spelt with spaces ('с о м', 'со м') was not an ending. The spelt-out and split
        branches use the same skeleton match, still only after a name in a different script.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal 丶丿̣ shop", "refunds-portal ㆍᆢ̣ shop", "refunds-portal ニハト̣ shop",
         "refunds-portal 丨丶丿̣ shop", "refunds-portal ʘ̣ shop", "refunds-portal ǃ̣ shop",
         "refunds-portal 丶丿́ shop", "refunds-portal с о м", "refunds-portal со м", "refunds-portal с о м/claim",
         "refunds-portal c̣om")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r20_is_a_link(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    masked = U.mask_links(text, "[link removed]")
    assert "refunds-portal" not in masked and "с о" not in masked, link


@pytest.mark.parametrize("link", LINKS)
def test_r20_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Sikkim (སི་ཀིམ།) in India.", "Рыба сом живёт в реке.", "Я с о м спорю.",
                                  "Café crème is good."))
def test_r20_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
