"""W1-A0 closure review round 43 finding R43-01 (inside the class closed by owner decision D30; repaired anyway).
Each R43 link case fails on 304bdf70.

R43-01: a spelt-out ending mixing a Cyrillic/Greek look-alike with Latin letters ('о r g/claim', 'е d u', 'і o') or with
        wider spacing ('о  r  g') was not read. Spelt single characters are now read with any spacing and with a path or
        punctuation after the last one. A differential test checks that one look-alike substitution in a spelt core
        domain, under several spacings and endings, is a link whenever the Latin spelling is.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ о r g/claim", "refunds-portal ~ е d u/claim", "refunds-portal ~ і o/claim",
         "refunds-portal ~ о  r  g", "refunds-portal ~ g о v/claim")
SENT = "Claim your energy rebate refund at {} before the deadline."
LOOK = {"o": "о", "e": "е", "i": "і", "c": "с", "a": "а", "p": "р", "x": "х", "y": "у", "s": "ѕ"}


@pytest.mark.parametrize("link", LINKS)
def test_r43_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS[:3])
def test_r43_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


def _cases():
    for tld in ("com", "org", "gov", "edu", "io", "biz", "xyz"):
        for i, ch in enumerate(tld):
            if ch not in LOOK:
                continue
            look = tld[:i] + LOOK[ch] + tld[i + 1:]
            for sep in (" ", "  ", "\t"):
                for tail in ("", "/claim", ",", ")"):
                    for lead in ("refunds-portal ~ ", "refunds-portal . "):
                        yield lead + sep.join(tld) + tail, lead + sep.join(look) + tail


@pytest.mark.parametrize("latin,look", list(_cases()))
def test_r43_01_one_look_alike_letter_never_hides_a_spelt_domain(latin, look):
    if U.has_link_or_contact(SENT.format(latin)):
        assert U.has_link_or_contact(SENT.format(look)), look


@pytest.mark.parametrize("text", ("Options a, b, c apply.", "Score 1 0 2 today.", "Plan A or plan B.", "Он и я.",
                                  "Я с о м спорю."))
def test_r43_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
