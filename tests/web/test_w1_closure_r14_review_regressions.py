"""W1-A0 closure review round 14 finding R14-01 (D17). Each R14 link case fails on da10d0b8.

R14-01: the D17 stroke and dot allow-list was written in raw code points (the Kangxi Radicals block) that never occur in
        the checked text: normalise() applies NFKC, which maps '⼁' to '丨', and the unified one-stroke radicals
        ('一', '丨', '乙') were missing. So 'refunds-portal 丨丶 shop/claim' read '丨丶' as the name and passed every check.
        The repair kept the allow-list in canonical form; the owner then tightened D17 back (every short word of
        another script is a separator unless bracketed), which removes the allow-list. This test checks the rule over
        every pair of stroke and dot letters (unified and Kangxi spellings), not only the reviewer's strings.

Self-contained: no fixture files; everything is built here.
"""
import itertools
import json
import unicodedata

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

# One-stroke radicals and stroke variants, stroke-and-dot radicals, Hangul araea, and the Kangxi spellings U+2F00-2F05.
STROKES = "一丨丶丿乙亅乀乁乚乛二亠ᆞᆢ" + "".join(chr(c) for c in range(0x2F00, 0x2F06))
PAIRS = sorted({a + b for a, b in itertools.product(STROKES, repeat=2)})
REVIEWER = ("refunds-portal 丨丶 shop/claim", "refunds-portal 一丶 shop/claim", "refunds-portal ⼁⼂ shop/claim",
            "refunds-portal ⼀⼂ shop/claim", "refunds-portal 丶一 shop/claim", "refunds-portal 乙丶 shop",
            "refunds-portal 二丶 shop", "refunds-portal 亠丶 shop")
SENT = "Claim your energy rebate refund at {} before the deadline."


def test_r14_01_kangxi_spellings_are_covered():
    """The Kangxi spellings normalise to the unified radicals, so the pairs below cover both. (The stroke allow-list
    this test first checked was removed when the owner tightened D17 back: every short foreign word is a separator.)"""
    assert {unicodedata.normalize("NFKC", chr(c)) for c in range(0x2F00, 0x2F06)} <= set(STROKES)


@pytest.mark.parametrize("pair", PAIRS)
def test_r14_01_every_stroke_pair_is_a_separator(pair):
    text = SENT.format("refunds-portal " + pair + " shop/claim")
    assert U.has_link_or_contact(text), pair
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), pair


@pytest.mark.parametrize("link", REVIEWER)
def test_r14_01_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert link.split()[0] not in U.mask_links(SENT.format(link), "[link removed]"), link


@pytest.mark.parametrize("link", REVIEWER)
def test_r14_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", REVIEWER)
def test_r14_01_surface_masks_it(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False).lower()
    assert "refunds-portal" not in dump, link


@pytest.mark.parametrize("text", ("Tokyo (東京) in Japan.", "Yamaguchi (山口) is in Japan.", "Seoul (서울) is cold."))
def test_r14_01_ordinary_text_is_not_a_link(text):
    """D17 tightened back by the owner: a short foreign word is readable only as a bracketed gloss
    ('Tokyo 東京 is big' unbracketed is masked, an owner-accepted precision cost)."""
    assert not U.has_link_or_contact(text), text


def test_r14_01_recorded_residuals_unchanged():
    """Owner-accepted D17 residual: a bracketed gloss is not a separator. A real short foreign word is a separator
    since the owner tightened D17 back."""
    assert U.has_link_or_contact(SENT.format("refunds-portal 中国 shop"))
    assert not U.has_link_or_contact(SENT.format("refunds-portal (丨丶) shop"))
