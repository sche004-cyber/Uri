"""W1-A0 closure review round 17 finding R17-01 (D19). Each R17 case fails on 101bf972.

R17-01: the D19 stroke list was picked letter by letter and missed Hangul 'ㅡ'/'ㅣ', katakana 'ノ', '丷' and '三', so
        'refunds-portal 丶ㆍㅡ shop/claim' read the stroke word as the name. The list is now built from whole Unicode
        groups (1-2 stroke Kangxi radicals and the radical supplement, all Hangul jamo, Bopomofo, katakana stroke and
        iteration marks); this test tries 3-letter words over a sample of every group.

Self-contained: no fixture files; everything is built here.
"""
import itertools

import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

GROUPS = ("ㅡㅣㆍᆢㄱㄴ", "ノヽー〃", "丶丿丷三一二", "ㄧㄨㄚ", "⼀⼁⼂⼃⼄⼅⼆⼇⼈⼉⼊⼋⼌⼍⼎⼏⼐⼑⼒⼓⼔⼕⼖⼗⼘⼙⼚⼛⼜")
SAMPLE = "".join(GROUPS)
WORDS = ["丶ㆍㅡ", "ㅣㆍㅡ", "丶丿ノ", "丶丿丷", "一二三"] + sorted(
    {"".join(t) for t in itertools.permutations(SAMPLE, 3)})[::211]
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("word", WORDS)
def test_r17_01_stroke_word_is_a_separator(word):
    text = SENT.format("refunds-portal " + word + " shop/claim")
    assert U.has_link_or_contact(text), word
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), word


@pytest.mark.parametrize("word", ["丶ㆍㅡ", "丶丿ノ", "一二三"])
def test_r17_01_verify_and_extractive_never_keep_it(word):
    src = SENT.format("refunds-portal " + word + " shop/claim")
    v = SY.verify(src[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", word
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), word


def test_r17_01_every_group_letter_is_in_the_list():
    for ch in SAMPLE:                 # non-letters ('〃') are never part of a word: they are gap already
        if U._letter(ch):
            assert U.normalise(ch) in U._STROKES, hex(ord(ch))


@pytest.mark.parametrize("text", ("Tokyo (東京都) is big.", "Seoul (서울특별시) is cold."))
def test_r17_01_bracketed_gloss_stays_readable(text):
    assert not U.has_link_or_contact(text), text
