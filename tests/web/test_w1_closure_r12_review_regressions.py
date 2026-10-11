"""W1-A0 closure review round 12 finding R12-01 (R1-01 class; coordinator repair after RETRY_LIMIT, D10 precedent).
Each R12 link case fails on 834c1c30.

R12-01: under D16 the name had to share the ending's script, so a name in another script ('пример com/claim',
        'возврат ~ ~ ~ com', 'refunds-portal ~ рф') passed every check. A real word of any script is now the name;
        only single or repeated letters count as part of the separator. Native sentence punctuation (danda, Tibetan
        shad, Arabic and CJK commas) counts as ordinary prose, so 'Tokyo (東京) in Japan.' stays readable.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

LINKS = ("пример com/claim", "пример com", "возврат-портал org/claim", "ελληνικά com/claim", "استرداد com/claim",
         "возврат ~ ~ ~ ~ ~ ~ com", "refunds-portal ~ рф", "refunds-portal ~ онлайн", "refunds-portal ~ ком/claim",
         "退税网站 com", "refunds-portal ~ 中国")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r12_01_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert link.split()[0] not in U.mask_links(SENT.format(link), "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r12_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", LINKS)
def test_r12_01_surface_masks_it(link):
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
        "Tokyo (東京) in Japan.", "NIT Sikkim (सिक्किम) in Ravangla.", "Moscow (Москва) is big.",
        "The word Москва means Moscow.", "He said спасибо to me.", "Sikkim (སི་ཀིམ།) in India.",
        "Delhi (दिल्ली), in India.", "Cairo (القاهرة) is old."))
def test_r12_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
