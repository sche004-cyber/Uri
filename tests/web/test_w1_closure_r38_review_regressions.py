"""W1-A0 closure review round 38 findings R38-01 and R38-02. Each R38 link case fails on c8e48f43.

R38-01: a spelt-out ending with an ASCII look-alike ('c 0 m', 'g 0 v', 'i 0', 'с 0 м') was not read, because each
        lone digit is its own run. Single characters separated by single spaces are now read together with every fold
        set, and replaced only when they spell a listed top-level domain.
R38-02: '_' after a mixed look-alike group ('с0м_') stopped the R37 reading; '_' now splits the group.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ c 0 m", "refunds-portal . c 0 m", "refunds-portal c 0 m/claim", "refunds-portal ~ g 0 v",
         "refunds-portal ~ i 0", "refunds-portal с 0 м/claim", "refunds-portal ~ с0м_")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r38_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r38_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Options a, b, c apply.", "Score 1 0 2 today.", "Plan A or plan B.",
                                  "I am a co founder.", "snake_case words here"))
def test_r38_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
