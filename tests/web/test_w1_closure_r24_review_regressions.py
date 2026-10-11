"""W1-A0 closure review round 24 finding R24-01. Each R24 link case fails on d51207ea.

R24-01: a listed non-Latin top-level domain written with optional vowel marks (Arabic harakat 'مِصْر', 'شَبَكة'; Hebrew
        points 'קוֹם') did not match the list, although the unmarked spelling does. Endings are now also matched with
        that optional vocalisation removed.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ مِصْر", "refunds-portal ~ مَصر", "refunds-portal ~ عُمان", "refunds-portal ~ السُّعُودِيَّة",
         "refunds-portal ~ ایرانْ", "refunds-portal ~ شَبَكة", "refunds-portal ~ مَوقِع", "refunds-portal ~ קוֹם",
         "refunds-portal/claim * شَبَكَة")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r24_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r24_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Cairo (القاهرة) is old.", "Egypt (مِصْر) is in Africa.", "Shalom (שלום) means peace.",
                                  "A plain English sentence."))
def test_r24_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
