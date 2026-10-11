"""W1-A0 closure review round 13 finding R13-01, repaired under owner decision D17 ("brackets + odd letters").
Each R13 link case fails on eedbc639.

R13-01: the R12 repair read a short word of another script ('丶丿', 'ㆍᆢ') or a doubled odd Latin letter ('ʘʘ') as the
        name, so 'refunds-portal 丶丿 shop/claim' passed every check. D17: a short word of another script (at most two
        distinct letters) stands between the name and the ending like a dot unless it is alone in brackets as a gloss
        ('Tokyo (東京) in Japan'); a word made only of odd Latin letters (IPA, clicks, letters without case) does too.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

LINKS = ("refunds-portal 丶丿 shop/claim", "refunds-portal ㆍᆢ shop/claim", "refunds-portal ʘʘ shop/claim",
         "refunds-portal ~ ʘʘ shop", "пример ʘʘ shop", "refunds-portal 丶 丿 ㆍ shop", "refunds-portal ǃǃ shop")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r13_01_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert link.split()[0] not in U.mask_links(SENT.format(link), "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r13_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", LINKS)
def test_r13_01_surface_masks_it(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False).lower()
    assert link.split()[0].lower() not in dump, link


@pytest.mark.parametrize("text", (
        "Tokyo (東京) in Japan.", "Moscow (Москва) is big.", "NIT Sikkim (सिक्किम) in Ravangla.",
        "The ɛ sound is open.", "Delhi (दिल्ली), in India.", "Beijing [北京] is large."))
def test_r13_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text


def test_d17_recorded_residual_bracketed_separator_is_not_masked():
    """Recorded residual (owner, D17): a separator word alone in brackets reads as a gloss."""
    assert not U.has_link_or_contact(SENT.format("refunds-portal (丶丿) shop"))
