"""W1-A0 closure review round 29 finding R29-01. Each R29 link case fails on 6c51965f.

R29-01: look-alike endings were read through a 58-character hand-made table, so 'ѕһор', 'miǀ', 'coʍ' and 'ϲοΜ' were not
        endings, and a detected 'ѕһор/claim' left the name on screen. Endings are now read through the full Unicode
        confusables data (uri_web/confusables_ascii.py, generated from UTS #39 confusables.txt), each letter's Latin
        name, and the older table; a Latin letter with no plain look-alike ('ʍ', turned w) matches any letter. A
        cross-script look-alike counts even where ordinary prose would not ('refunds-portal ѕһор').

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.confusables_ascii import CONFUSABLE_ASCII

LINKS = ("refunds-portal ~ ѕһор", "refunds-portal ѕһор", "refunds-portal miǀ/claim", "refunds-portal miǀ",
         "refunds-portal coʍ/claim", "refunds-portal ~ coʍ", "refunds-portal ~ ϲοΜ", "refunds-portal ~ ѕһор/claim",
         "refunds-portal ~ һоѕt")
SENT = "Claim your energy rebate refund at {} before the deadline."


def test_r29_01_data_is_the_full_unicode_set():
    assert len(CONFUSABLE_ASCII) > 1500
    assert CONFUSABLE_ASCII["ѕ"] == "s" and CONFUSABLE_ASCII["һ"] == "h" and CONFUSABLE_ASCII["ǀ"] == "l"


@pytest.mark.parametrize("link", LINKS)
def test_r29_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r29_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Рыба сом живёт в реке.", "Den store sø er smuk.", "Byłem w domu.",
                                  "Moscow (Москва) is big.", "He said спасибо to me.", "Γεια σου κόσμε.",
                                  "Ærø is an island."))
def test_r29_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
