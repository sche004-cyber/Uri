"""W1-A0 closure review round 16: R16-01 (owner decision D19, "stroke list") and R16-02. Each R16 case fails on 9b6b4f27.

R16-01: a word of three or more distinct stroke and dot-shaped letters ('丶ㆍᆢ', '丨丶丿') between a name and a top-level
        domain was read as the name. D19: a word made only of stroke and dot-shaped letters is a separator whatever its
        length, unless it stands alone in brackets as a gloss (D17 residual).
R16-02: the RFC 8215 local-use NAT64 prefix 64:ff9b:1::/48 can embed a private IPv4 at offsets the policy did not read;
        it is refused outright.

Self-contained: no fixture files; everything is built here.
"""
import itertools

import pytest

from uri_web import netpolicy as N
from uri_web import synthesize as SY
from uri_web import untrusted as U

STROKES = "一丨丶丿乙亅乀乁乚乛二亠ᆞᆢ"
TRIPLES = sorted({"".join(t) for t in itertools.permutations(STROKES, 3)})[::7]
QUADS = sorted({"".join(t) for t in itertools.permutations(STROKES, 4)})[::97]
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("word", ["丶ㆍᆢ", "丶丿乀", "丨丶丿", "ㆍᆢ丶"] + TRIPLES + QUADS)
def test_r16_01_stroke_word_is_a_separator(word):
    text = SENT.format("refunds-portal " + word + " shop/claim")
    assert U.has_link_or_contact(text), word
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), word


@pytest.mark.parametrize("word", ["丶ㆍᆢ", "丨丶丿"])
def test_r16_01_verify_never_keeps_it(word):
    link = "refunds-portal " + word + " shop/claim"
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [SENT.format(link)])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", word


@pytest.mark.parametrize("text", ("Tokyo (東京都) is big.", "Beijing (北京市) is large."))
def test_r16_01_bracketed_gloss_stays_readable(text):
    assert not U.has_link_or_contact(text), text


@pytest.mark.parametrize("addr", ("64:ff9b:1:a00:0:100:808:808", "64:ff9b:1::a00:1", "64:ff9b:1:ffff::1"))
def test_r16_02_local_use_nat64_is_refused(addr):
    with pytest.raises(N.EgressRefused):
        N.check_address(addr)


def test_r16_02_well_known_nat64_still_judged_by_embedded_ipv4():
    N.check_address("64:ff9b::808:808")
    with pytest.raises(N.EgressRefused):
        N.check_address("64:ff9b::a00:1")
