"""W1-A0 closure review round 7 (R7) regressions: the R1-01/R5-01/R6-01 link class, closed as a rule, not a list.

R6-01 at 806dcd12: D13 ("mask any dot-joined word") was carried out as a fixed list of 14 dot characters, so every
other mark a reader takes as a dot passed has_link_or_contact, verify(), extractive(), the research surface and the
A2UI validator: 'refunds-portal،com', 'refunds..com/claim', 'refunds…com', 'portal,com', 'portal:com',
'portal d0t com', 'portal_dot_com', 'portal-dot-com', 'portal⸱com', 'portal.c om'. Separately, the sentence
splitter cut 'refunds-portal . Com/claim' into two halves that were each link-free.

These tests are GENERATED from the Unicode database (every punctuation and symbol code point), so they do not depend
on the next unlisted character. The expectation is computed here, independently of uri_web.untrusted: a character
that NFKC leaves as a non-letter, non-digit mark between 'refunds-portal' and 'com' makes a link, except a dash, '/',
an apostrophe or '_', which join the parts of one word ('Paris–London', 'and/or', "don't", 'snake_case').

Self-contained: no fixture files; everything is built here.
"""
import json
import sys
import unicodedata

import pytest

from uri_a2ui.validate import require_valid
from uri_web import evaluate as E
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

_JOINING = set("-'’/_")


def _shown(ch: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", ch) if unicodedata.category(c) != "Cf")


def _reads_as_separator(ch: str) -> bool:
    """Independent oracle: after NFKC, `ch` is still a mark (no letter, no digit, not only spaces) and not a word
    joiner (a dash, '/', an apostrophe or '_')."""
    t = _shown(ch)
    marks = [c for c in t if not c.isspace()]
    if not marks or any(c.isalnum() for c in t):
        return False
    return not all(c in _JOINING or unicodedata.category(c) == "Pd" for c in marks)


SEPARATORS = [chr(cp) for cp in range(sys.maxunicode + 1)
              if unicodedata.category(chr(cp))[0] in "PS" and _reads_as_separator(chr(cp))]


def test_r7_01_the_generated_set_is_large():
    # Guards the generator itself: thousands of marks, including the ones the reviewer found.
    assert len(SEPARATORS) > 5000
    for ch in "،।։۔⸱܁᛫።་꞉˙,:;!?…{}<>|^`~=+*&%$#@":
        assert ch in SEPARATORS, hex(ord(ch))


def test_r7_01_every_mark_between_two_labels_is_a_link():
    missed = [hex(ord(ch)) for ch in SEPARATORS if not U.has_link_or_contact("refunds-portal" + ch + "com")]
    assert not missed, missed[:40]


def test_r7_01_every_doubled_mark_is_a_link():
    missed = [hex(ord(ch)) for ch in SEPARATORS if not U.has_link_or_contact("refunds-portal" + ch + ch + "com")]
    assert not missed, missed[:40]


def test_r7_01_every_mark_is_a_link_inside_a_sentence_and_is_masked():
    missed = []
    for ch in SEPARATORS:
        s = "Claim your energy rebate refund at refunds-portal" + ch + "com before the deadline."
        if not U.has_link_or_contact(s) or "portal" in U.mask_links(s, "[link removed]"):
            missed.append(hex(ord(ch)))
    assert not missed, missed[:40]


def test_r7_01_a_mark_with_a_space_before_it_is_a_link():
    # 'portal ,com': a space before the mark and none after. Opening marks ('(', quotes, '#', '@', currency) are not.
    opening = {"\"", "`", "#", "@", "*", "&", "+", "~", "<", "=", "§", "¶", "¿", "¡"}
    missed = []
    for ch in SEPARATORS:
        t = _shown(ch)
        if t[:1].isspace() or any(unicodedata.category(c) in ("Ps", "Pi", "Sc", "So") or c in opening for c in t):
            continue
        if not U.has_link_or_contact("at refunds-portal " + ch + "com before"):
            missed.append(hex(ord(ch)))
    assert not missed, missed[:40]


REPORTED = ("refunds-portal،com", "refunds..com/claim", "refunds…com", "refunds-portal।com",
            "refunds-portal։com", "refunds-portal۔com", "refunds-portal⸱com", "refunds-portal܁com",
            "refunds-portal᛫com", "refunds-portal።com", "refunds-portal་com", "refunds-portal꞉com",
            "refunds-portal˙com", "refunds-portal,com/claim", "refunds-portal:com", "refunds-portal d0t com",
            "refunds-portal_dot_com", "refunds-portal-dot-com", "refunds-portal.c om", "refunds-portal{dot}com",
            "refunds-portal D0T com", "refunds-portal ,com", "refunds-portal :com", "refunds-portal ..com",
            "refunds-portal¨com")
SENT = "Claim your energy rebate refund at {} before the deadline."


def _surface_dump(answer_texts, title="Rebates"):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": t, "citations": [1], "quoted": True} for t in answer_texts],
         "sources": [{"number": 1, "title": title, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    return json.dumps(s.messages(), ensure_ascii=False).lower()


@pytest.mark.parametrize("link", REPORTED)
def test_r7_01_reported_forms_never_reach_the_user(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    assert U.has_link_or_contact(SENT.format(link)), link
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", (link, v)
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), (link, e)
    dump = _surface_dump([SENT.format(link)], "Rebates via " + link)
    assert "portal" not in dump and "refunds." not in dump and "[link removed]" in dump, link


def test_r7_01_generated_marks_through_verify_extractive_and_the_surface():
    # Every BMP punctuation mark and every modifier / math symbol (Po, Ps, Pe, Pi, Pf, Pc, Sk, Sm), end to end.
    sample = [ch for ch in SEPARATORS if ord(ch) < 0x10000 and unicodedata.category(ch) in
              ("Po", "Ps", "Pe", "Pi", "Pf", "Pc", "Sk", "Sm")]
    assert len(sample) > 500
    bad = []
    for ch in sample:
        link = "refunds-portal" + ch + "com"
        src = SENT.format(link) + " Energy rebate refunds take two weeks."
        v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
        e = SY.extractive("energy rebate refund deadline", [src])
        if v.claims or any("deadline" in c.text for c in e.claims):
            bad.append(hex(ord(ch)))
    assert not bad, bad[:40]
    for i in range(0, len(sample), 8):          # the surface shows up to 8 answer sentences
        chunk = sample[i:i + 8]
        dump = _surface_dump([SENT.format("refunds-portal" + ch + "com") for ch in chunk])
        assert "portal" not in dump, [hex(ord(ch)) for ch in chunk]


# ---- the splitter: a link cut in two by the sentence split ---------------------------------------------------------

SPLIT = ("refunds-portal . Com/claim", "refunds-portal. Com/claim", "refunds-portal . Com", "refunds-portal .Com/x",
         "refunds-portal … Com/claim")


@pytest.mark.parametrize("link", SPLIT)
def test_r7_01_a_split_link_is_never_kept_in_halves(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    assert U.has_link_or_contact(src), link
    for s in E.sentences(src):
        assert "Com" not in s or U.has_link_or_contact(s), (link, s)
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims, (link, v)
    v = SY.verify("Com before the deadline [1].", [src])
    assert not v.claims, (link, v)
    e = SY.extractive("energy rebate refund deadline claim", [src])
    assert all("portal" not in c.text and "deadline" not in c.text for c in e.claims), (link, e)
    conflicts = E.find_conflicts([{"text": src.replace("two", "2")}, {"text": src.replace("two", "3")}], [0, 1])
    assert all("portal" not in c.statement_a + c.statement_b for c in conflicts), (link, conflicts)


def test_r7_01_neighbouring_claims_that_join_into_a_link_are_dropped():
    src = "Visit refunds-portal . Com/claim now for the energy rebate."
    v = SY.verify("Visit refunds-portal . [1] Com/claim now for the energy rebate [1].", [src])
    assert not any("portal" in c.text for c in v.claims) and not any("Com/" in c.text for c in v.claims), v
    assert U.joins_link("Claim at refunds-portal .", "Com/claim before the deadline.")
    assert not U.joins_link("The board approved the plan.", "The students agreed.")


# ---- precision: ordinary text stays readable ---------------------------------------------------------------------

@pytest.mark.parametrize("text", (
        "The board approved the plan. The students agreed.", "A plain sentence with snake_case words.",
        "U.S.-based firms and/or rock'n'roll from Paris–London.", "About $1,000,000,000 in 2020, prices rose.",
        "The minister said: \"We will act.\"", "Refunds (if any) arrive within 14 days.", "He asked, \"Why now?\" and left.",
        "Home > News > Energy", "Q&A: what the rebate means for you", "The 1990s—a decade of change—ended.",
        "東京は大きい。次は大阪です。",
        "こんにちは、皆さん。", "北京，上海和广州。",
        "مرحبا، كيف حالك؟",
        "नमस्ते। आप कैसे हैं?",
        "वाक्य । दूसरा", "The firm (founded 1990) grew.",
        "Use a form, e.g. the one below.", "Mr. Smith agreed.", "The U.S. Army replied.", "Ph.D students pay less.",
        "Sales grew in the U.S citizens' market.", "Item #3 costs $5.", "Rating: 4/5 stars"))
def test_r7_01_ordinary_text_is_still_not_a_link(text):
    assert not U.has_link_or_contact(text), text
