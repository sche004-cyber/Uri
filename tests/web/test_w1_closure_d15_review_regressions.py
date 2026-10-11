"""W1-A0 closure review round 8 finding R8-01, repaired under owner decision D15 (file named d15: the earlier repair
already used the round-8 file name). Each R8 case fails on 474adb84.

R8-01 / D15: letters drawn like a dot (U+A78F LATIN LETTER SINOLOGICAL DOT, U+1427 CANADIAN SYLLABICS FINAL MIDDLE
       DOT), U+A4F8, U+02D1 and U+0660 as separators, and a dash-wrapped dot ('-.-') were not links. D15: characters
       are checked against an allow-list; a token with an unlisted character, a letter named as a dot/colon/separator,
       or two script families is treated as a link. Spelt-out letters ('c o m') are owner-accepted residual risk.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

LINKS = ("refunds-portalꞏcom/claim", "refunds-portal ꞏ com", "refunds-portalᐧcom/claim",
         "refunds-portalꓸcom", "refunds-portalˑcom", "refunds-portal٠com", "refunds-portal -.- com",
         # beyond the reviewer's strings
         "refunds-portalːcom", "refunds-portal᛬com", "refunds-portal\U0001f534com", "refunds-portal —.— com",
         "refunds-portal०com")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r8_01_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert "portal" not in U.mask_links(SENT.format(link), "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r8_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", LINKS)
def test_r8_01_surface_masks_it(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False).lower()
    assert "portal" not in dump, link
    assert "[link removed]" in dump and "gov.example/rebates" in dump


@pytest.mark.parametrize("text", (
        "Café prices rose in Zürich.", "Москва большой город.", "東京は大きい。次は大阪です。", "東京は100円です。",
        "गंगटोक सिक्किम की राजधानी है।", "Fees are ₹5,000 (approx.) — see § 3.", "The rate is 4.5% at 10 a.m. today.",
        "ᰛᰩᰵ is written in Lepcha.", "འབྲས་ལྗོངས། is Sikkim in Tibetan.", "Price: £3½ or €4 × 2.",
        "He said “yes” – twice…", "Naïve résumé façade coöperate.", "Ελληνικά κείμενα.", "ᤕᤠᤰᤌᤢᤱ in Limbu."))
def test_d15_ordinary_text_in_listed_scripts_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
