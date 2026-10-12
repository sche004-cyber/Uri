"""W1-A0 closure review round 8 regressions (reviewer findings R7-01 and R7-02 at f604e7cd).

R7-01: the R1-01 link class was still open. A dot inside a bracket or quote pair of another script with spaces
('refunds-portal 【.】 com/claim', '「.」', '〔.〕', '«.»', '⟨.⟩', '"."', "'.'"), a spaced dot run
('refunds-portal . . com/claim'), a So-category bullet ('◦' U+25E6, '●'), a spelt-out '(d o t)', and a mark then a
space before a generic top-level domain ('refunds-portal; com/claim', 'portal, com') passed has_link_or_contact,
verify(), extractive(), the research surface and the A2UI validator.

R7-02: verify() kept, in the Brain's words, a claim that added or dropped the determiner before a quantifier
('Little progress was made' cited to 'A little progress was made'), which reverses scarcity and presence.

The bracket and quote pairs are GENERATED from the Unicode database (every Ps/Pe neighbour pair and every Pi/Pf
pair), so they do not depend on a typed list. Self-contained: no fixture files.
"""
import json
import sys
import unicodedata

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

SENT = "Claim your energy rebate refund at {} before the deadline."


def _kept_by_nfkc(ch: str) -> bool:
    return unicodedata.normalize("NFKC", ch) == ch


def _pairs() -> list:
    """(open, close): every Ps code point followed by a Pe one (the Unicode bracket pairs), every Pi x Pf quote pair,
    and the ASCII quotes, all left unchanged by NFKC."""
    out = []
    for cp in range(sys.maxunicode):
        a, b = chr(cp), chr(cp + 1)
        if (unicodedata.category(a) == "Ps" and unicodedata.category(b) == "Pe"
                and _kept_by_nfkc(a) and _kept_by_nfkc(b)):
            out.append((a, b))
    pi = [chr(cp) for cp in range(sys.maxunicode + 1) if unicodedata.category(chr(cp)) == "Pi"]
    pf = [chr(cp) for cp in range(sys.maxunicode + 1) if unicodedata.category(chr(cp)) == "Pf"]
    out += [(a, b) for a in pi for b in pf if _kept_by_nfkc(a) and _kept_by_nfkc(b)]
    out += [('"', '"'), ("'", "'"), ("`", "`")]
    return out


PAIRS = _pairs()
REVIEWER_LINKS = ["refunds-portal 【.】 com/claim", "refunds-portal 「.」 com", "refunds-portal 〔.〕 com",
                  "refunds-portal «.» com", "refunds-portal ⟨.⟩ com", 'refunds-portal "." com',
                  "refunds-portal '.' com", "refunds-portal . . com/claim", "refunds-portal ◦ com",
                  "refunds-portal ● com", "refunds-portal (d o t) com", "refunds-portal; com/claim",
                  "refunds-portal! com/claim", "refunds-portal, com", "refunds-portal: com"]


def test_r7_01_generated_pairs_cover_the_reviewer_cases():
    assert len(PAIRS) > 60
    for pair in [("【", "】"), ("「", "」"), ("〔", "〕"), ("⟨", "⟩"), ("«", "»"), ('"', '"'), ("(", ")")]:
        assert pair in PAIRS, pair


@pytest.mark.parametrize("inner", [".", " . ", "..", ". .", "dot", " d o t "])
def test_r7_01_every_spaced_bracket_or_quote_pair_around_a_dot_is_a_link(inner):
    missed = []
    for a, b in PAIRS:
        s = "refunds-portal " + a + inner + b + " com/claim"
        if not U.has_link_or_contact(s) or "portal" in U.mask_links(s, "[link removed]"):
            missed.append(a + b)
    assert not missed, missed[:40]


@pytest.mark.parametrize("run", [". .", ". . .", ".  .", "· ·", "。 。", "… .", "• •"])
@pytest.mark.parametrize("space", [(" ", " "), ("", " "), (" ", "")])
def test_r7_01_a_spaced_dot_run_is_a_link(run, space):
    s = "refunds-portal" + space[0] + run + space[1] + "com/claim"
    assert U.has_link_or_contact(s), s
    assert "portal" not in U.mask_links(SENT.format(s), "[link removed]")


@pytest.mark.parametrize("ch", ["◦", "●", "○", "◯", "⚫", "⚪", "∘", "◘"])
def test_r7_01_a_symbol_bullet_or_circle_is_a_link(ch):
    for s in ("refunds-portal " + ch + " com", "refunds-portal" + ch + " com", "refunds-portal " + ch + "com"):
        assert U.has_link_or_contact(s), s


@pytest.mark.parametrize("mark", [",", ";", ":", "!", "?", "|", "،"])
@pytest.mark.parametrize("tld", ["com", "net", "org", "Com", "shop/claim", "co/claim"])
def test_r7_01_a_mark_and_a_space_before_a_generic_tld_is_a_link(mark, tld):
    assert U.has_link_or_contact("refunds-portal" + mark + " " + tld), mark + tld


def _surface_json(texts, title):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": t, "citations": [1], "quoted": True} for t in texts],
         "sources": [{"number": 1, "title": title, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    return json.dumps(s.messages(), ensure_ascii=False)


@pytest.mark.parametrize("link", REVIEWER_LINKS)
def test_r7_01_reviewer_links_end_to_end(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    assert U.has_link_or_contact(src)
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not any("portal" in c.text for c in v.claims), v.claims
    e = SY.extractive("energy rebate refund deadline", [src])
    assert not any("portal" in c.text for c in e.claims), e.claims
    assert "portal" not in _surface_json([SENT.format(link)], "Rebates via " + link)


@pytest.mark.parametrize("text", [
    "red, blue and green", "Note: the deadline moved.", 'He said "stop." Then he left.',
    "It ended (badly.) The next day was calm.", "Wait... then it rained.", "yes, and/or no",
    "The report (published in May) was clear.", "Prices rose; the index fell.",
])
def test_r7_01_ordinary_prose_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text


@pytest.mark.parametrize("source, claim", [
    ("A little progress was made on the energy rebate bill this session.",
     "Little progress was made on the energy rebate bill this session [1]."),
    ("Little progress was made on the energy rebate bill this session.",
     "A little progress was made on the energy rebate bill this session [1]."),
    ("Lawmakers expect a little support for the energy rebate bill.",
     "Lawmakers expect little support for the energy rebate bill [1]."),
    ("Regulators found little evidence of fraud in the rebate program.",
     "Regulators found a little evidence of fraud in the rebate program [1]."),
    ("Regulators found a bit of evidence of fraud in the rebate program.",
     "Regulators found bit of evidence of fraud in the rebate program [1]."),
    ("The agency received a lot of complaints about the rebate program.",
     "The agency received lot of complaints about the rebate program [1]."),
])
def test_r7_02_a_determiner_before_a_quantifier_is_never_added_or_dropped(source, claim):
    v = SY.verify(claim, [source])
    assert v.claims, v.dropped
    for c in v.claims:
        assert c.quoted and c.text == source, (c.text, c.quoted)


def test_r7_02_ordinary_determiner_changes_still_paraphrase():
    # Guard: a determiner before an ordinary noun may still be added or left out (no new quoting there).
    v = SY.verify("Regulators approved rebate program [1].", ["Regulators approved the rebate program."])
    assert v.claims and not v.claims[0].quoted
