"""W1-A0 closure review round 32 finding R32-01. Each R32 link case fails on 1525b10d.

R32-01: two-character endings with one ASCII look-alike ('i0' for 'io', 'c0', 't0', '1y', 'm0', '|y') were not read,
        because the R31 variant skipped runs with fewer than two letters. A one-letter run is now read too, but only
        when it then spells a listed top-level domain; codes such as 'A1', 'v1.0', 'C0', '1y ago' are unchanged.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal.i0/claim", "refunds-portal.c0/claim", "refunds-portal.t0", "refunds-portal.1y/claim",
         "refunds-portal.m0/claim", "refunds-portal.|y/claim", "refunds-portal i0/claim", "refunds-portal ~ i0",
         "refunds-portal . i0")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r32_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r32_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Grade A1 and B12 rooms.", "Posted 1y ago by Sam.", "Version v1.0 shipped.",
                                  "Grade C0 steel.", "Use 2x speed."))
def test_r32_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
