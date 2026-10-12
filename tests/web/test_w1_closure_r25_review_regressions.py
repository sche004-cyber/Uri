"""W1-A0 closure review round 25 finding R25-01. Each R25 link case fails on 0adc9541.

R25-01: the R24 vowel-mark ranges were hand-picked and missed Arabic small vowels (U+0618-061A), honorific signs
        (U+0610-0617) and Extended-A marks (U+08D3-08FF). An ending is now compared with every non-spacing or
        enclosing mark removed; spacing vowel signs stay part of the spelling.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ مؘصر", "refunds-portal ~ مࣰصر",
         "refunds-portal ~ شَبَكةࣲ", "refunds-portal ~ عُمانؗ",
         "refunds-portal/claim * مࣤصر", "refunds-portal ~ مؐصر",
         "refunds-portal ~ مؙصرؚ")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r25_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r25_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Cairo (القاهرة) is old.", "India (भारत) is large.", "NIT Sikkim (सिक्किम) in Ravangla.",
                                  "A plain English sentence."))
def test_r25_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
