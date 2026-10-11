"""W1-A0 closure review round 31 finding R31-01. Each R31 link case fails on 87bd6aa7.

R31-01: ASCII look-alikes listed in the Unicode confusables data ('0' ~ 'o'; '1', 'I', '|' ~ 'l') were not read as
        letters, so 'refunds-portal.c0m', '~ g0v', 'miI' passed. A same-length variant of the text reads them as the
        letter they pass for, inside runs of at least two letters ('I' never first in a word), and every check also
        runs on it. Version numbers, codes and sentence-initial 'In'/'It' keep their meaning.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal.c0m/claim", "refunds-portal c0m/claim", "refunds-portal ~ g0v", "refunds-portal miI/claim",
         "refunds-portal.0rg", "refunds-portal.mi1", "refunds-portal.b1z", "refundsportal.C0M", "refunds-portal . c0m",
         "refunds-portal [.] c0m")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r31_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r31_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Version v1.0 shipped.", "Python 3.10 is out.", "Grade A1 and B12 rooms.",
                                  "MIT and COVID-19 data.", "H1N1 cases rose.", "Win10 users.", "I bought corn today.",
                                  "The top 10 sites.", "Room 101 is open.", "The board met. In 2020 it changed.",
                                  "It is fine. Is it?"))
def test_r31_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
