"""W1-A0 closure review round 37 finding R37-01. Each R37 link case fails on fc7bbf7b.

R37-01: an ending mixing Cyrillic look-alikes with ASCII ones ('с0м', 'ӏ0ӏ', '|оІ', 'ѕ|') was folded by neither the
        Unicode fold nor the ASCII fold. A mixed group is now read with both at once, and replaced only when the
        reading spells a listed top-level domain; the name is masked with it.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ с0м", "refunds-portal . с0м", "refunds-portal [.] с0м", "refunds-portal с0м",
         "refunds-portal ~ ӏ0ӏ", "refunds-portal . ӏ0ӏ", "refunds-portal ~ |оІ", "refunds-portal ~ ѕ|",
         "refunds-portal с0м/claim")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r37_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r37_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Рыба сом живёт в реке.", "Москва2020 прошла.", "Это мой дом.",
                                  "He said спасибо to me."))
def test_r37_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
