"""W1-A0 closure review round 23 finding R23-01. Each R23 link case fails on 0e9a51ea.

R23-01: one foreign letter with two or more marks of its own script ('بِٜ', 'क़ँं', 'กั่์') counted the marks as letters,
        so the D17 one-letter separator was read as the name. The single-letter and distinct-letter tests now count
        letters only.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal بِٜ shop", "refunds-portal بِٜٕ shop",
         "refunds-portal ءِٜٕ shop", "refunds-portal क़ँं shop",
         "refunds-portal कँं shop", "refunds-portal กั่์ shop",
         "refunds-portal بِٜٕ cash")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r23_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r23_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Cairo (القاهرة) is old.", "Sikkim (སི་ཀིམ།) in India.", "Delhi (दिल्ली), in India.",
                                  "NIT Sikkim (सिक्किम) in Ravangla.", "Bangkok (กรุงเทพ) is hot."))
def test_r23_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
