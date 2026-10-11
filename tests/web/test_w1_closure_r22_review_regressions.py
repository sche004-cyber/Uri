"""W1-A0 closure review round 22 finding R22-01. Each R22 link case fails on 57ccdd22.

R22-01: marks hidden on a filler letter ('ـِٜٕ', tatweel + Arabic marks) or marks of another script than their letter
        ('x़', 'ʘัิ', 'ニハト़') kept a separator word from being read as one, or left the name visible after masking.
        A word is now reduced to its real letters first: a mark is kept only on a letter of its own script.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ـِٜٕ shop", "refunds-portal ـٖٜٕ cash",
         "refunds-portal ـِٜٕـ shop", "refunds-portal ـِـٜـٕ shop",
         "refunds-portal x़ shop", "refunds-portal ʘ़ shop", "refunds-portal 丶丿़ shop",
         "refunds-portal 丶़ँं shop", "refunds-portal ʘัิ shop",
         "refunds-portal o༷ shop", "refunds-portal ニハト़ shop")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r22_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r22_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Sikkim (སི་ཀིམ།) in India.", "NIT Sikkim (सिक्किम) in Ravangla.",
                                  "Cairo (القاهرة) is old.", "Delhi (दिल्ली), in India.", "A plain English sentence."))
def test_r22_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
