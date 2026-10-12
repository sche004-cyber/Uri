"""W1-A0 closure review round 18 finding R18-01, repaired under owner decision D20 ("add kana, then close").
Each R18 case fails on b7b93e7c.

R18-01: stroke-shaped kana ('ニハト', 'ヘレフ', 'くしへ') were missing from the D19 list, so the word was read as the
        name. D20: all hiragana and katakana (full and half width) join the list, and the list is final; a look-alike
        outside its groups is owner-accepted residual risk.

Self-contained: no fixture files; everything is built here.
"""
import itertools

import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

WORDS = ["ニハト", "ヘレフ", "くしへ", "丶ニ丿", "丶ヘ丿", "ﾆﾊﾄ"] + sorted(
    {"".join(t) for t in itertools.permutations("ニハトヘレフイエロカへくしつこいり", 3)})[::61]
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("word", WORDS)
def test_r18_01_kana_word_is_a_separator(word):
    text = SENT.format("refunds-portal " + word + " shop/claim")
    assert U.has_link_or_contact(text), word
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), word


@pytest.mark.parametrize("word", ["ニハト", "くしへ"])
def test_r18_01_verify_and_extractive_never_keep_it(word):
    src = SENT.format("refunds-portal " + word + " shop/claim")
    v = SY.verify(src[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", word
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), word


@pytest.mark.parametrize("text", ("Tokyo (東京都) is big.", "Osaka (おおさか) is busy.", "A plain English sentence."))
def test_r18_01_bracketed_gloss_stays_readable(text):
    assert not U.has_link_or_contact(text), text
