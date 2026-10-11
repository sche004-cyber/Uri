"""W1-A0 closure review round 19 findings R19-01 and R19-02. Each R19 link case fails on 0577aeb6.

R19-01: a run of combining marks with no base letter ('refunds-portal ̣̇̈ shop') was read as the name. A word made only
        of marks is now a separator, whatever its length.
R19-02: a core domain written in look-alike letters of another script ('refunds-portal сом', 'іо') was not an ending.
        An ending is now also matched on its skeleton, but only after a name in a different script, so ordinary
        Cyrillic text ('Рыба сом живёт в реке.') stays readable.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ̣̇̈ shop", "refunds-portal ̣̇̈̄ shop",
         "refunds-portal ̣̇̈ cash", "refunds-portal сом", "refunds-portal іо", "refunds-portal сом/claim")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r19_is_a_link(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r19_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Рыба сом живёт в реке.", "Он сказал сом и ушёл.", "A plain English sentence."))
def test_r19_02_same_script_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
