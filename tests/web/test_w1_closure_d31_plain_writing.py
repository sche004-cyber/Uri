"""Owner decision D31 (2026-10-12): "only plain writing can be quoted".

Instead of recognising every way to disguise a link (rounds 11-43 found one more each time), a source sentence is used,
shown or quoted only if every token is ordinary writing: words of one script, ordinary numbers, codes and punctuation.
Anything else (symbols stuck to letters, digits inside Latin words, odd letters, runs of single characters that mix
letters with digits or symbols) is masked and the sentence is never support. The link checks stay as a second layer.

The stress test below generates disguised endings from the Unicode confusables data (D29) and ASCII look-alikes, with
many separators, spacings, marks and tails, and requires every one to be blocked. The only allowed misses are a plain
word after a comma ('refunds-portal , shop'), the residual the owner accepted in D16, which its plain spelling shares.

Self-contained: no fixture files; everything is built here.
"""
import random

import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.confusables_ascii import CONFUSABLE_ASCII

SENT = "Claim your energy rebate refund at {} before the deadline."
TLDS = ["com", "org", "gov", "edu", "io", "biz", "xyz", "net", "info", "shop", "site", "online", "live", "link", "loan",
        "claim"]
SEPS = [".", " . ", " [.] ", " (.) ", " ~ ", " · ", " 丶 ", "·", " * ", " ٠ ", " • ", ",", " , "]
SPACINGS = ["", " ", "  ", "\t"]
TAILS = ["", "/claim", ",", ")", ".", "?x=1"]


def _look_alikes():
    look = {}
    for k, v in CONFUSABLE_ASCII.items():
        if len(v) == 1 and v.isalpha() and U.normalise(k) == k:
            look.setdefault(v, []).append(k)
    for a, b in (("o", "0"), ("l", "1"), ("l", "I"), ("l", "|"), ("i", "1")):
        look.setdefault(a, []).append(b)
    return look


def _generated(seed, n):
    rnd, look, cases = random.Random(seed), _look_alikes(), set()
    for _ in range(n):
        tld, sep = rnd.choice(TLDS), rnd.choice(SEPS)
        chars = [rnd.choice(look[c]) if c in look and rnd.random() < 0.5 else c for c in tld]
        ending = rnd.choice(SPACINGS).join(chars)
        if rnd.random() < 0.2:
            ending = ending[:1] + "̣" + ending[1:]
        cases.add("refunds-portal" + sep + ending + rnd.choice(TAILS))
    return sorted(cases)


@pytest.mark.parametrize("seed", (7, 11, 23))
def test_d31_generated_disguises_are_blocked(seed):
    cases = _generated(seed, 2000)
    missed = [c for c in cases if not U.has_link_or_contact(SENT.format(c))]
    unexpected = [c for c in missed if not c.startswith(("refunds-portal , ", "refunds-portal,"))]
    assert len(cases) > 1800
    assert not unexpected, unexpected[:10]
    assert len(missed) <= len(cases) // 200            # the accepted D16 comma residual stays rare


@pytest.mark.parametrize("text", (
        "refunds-portal ~ c 0 m", "refunds-portal.c0m/claim", "refunds-portal ~ с0м", "refunds-portal ~ | о",
        "refunds-portal • ¡ o/claim", "refunds-portal . 1 o/claim", "refunds-portal.1 o/claim", "refunds-portal · 1൦)",
        "refunds-portal.၊ o a n)", "refunds-portal ~ $ite", "refunds-portal ~ |o"))
def test_d31_unusual_writing_is_never_used(text):
    src = SENT.format(text)
    assert U.has_link_or_contact(src), text
    v = SY.verify(src[:-1] + " [1].", [src])
    assert not v.claims, text


@pytest.mark.parametrize("text", (
        "東京は大きい。次は大阪。", "東京は100円です。", "नमस्ते। आप कैसे हैं?", "Sikkim (སི་ཀིམ།) in India.",
        "Price: £3½ or €4 × 2.", "A plain sentence with snake_case words.", "The ɛ sound is open.", "Я и с ним спорю.",
        "Москва2020 прошла.", "The well-known rose.The end.", "U.S.-based firms and/or rock'n'roll from Paris–London.",
        "Q&A: what the rebate means for you", "The 1990s—a decade of change—ended.", "Ph.D students pay less.",
        "Fees are ₹5,000 (approx.) — see § 3.", "Score 10 | 20 | 30", "The trail is 5 km long.", "For e.g. this case.",
        "Grade A1 and B12 rooms.", "COVID-19 cases rose 10% in 2020.", "Runtime v1 and M30.7C.", "Options a, b, c apply.",
        "I am a co founder.", "Meet at 10am on the 1st.", "He said \"hello\" — and left…", "Done: 3 of 4 items."))
def test_d31_ordinary_writing_is_used(text):
    assert not U.has_link_or_contact(text), text
