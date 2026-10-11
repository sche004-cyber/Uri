"""W1-A0 closure review round 30 finding R30-01 (and owner decision D29). Each R30 link case fails on c5fe6351.

R30-01: Cyrillic look-alikes of non-ASCII Latin letters ('ћ' ~ 'ħ', 'ҫ' ~ 'ç', 'ө' ~ 'ɵ', 'ӎ' ~ 'ʍ') had no fold, because the
        generated data kept only ASCII prototypes. The data now also keeps Latin prototypes (CONFUSABLE_LATIN), read
        further through the Latin rules. D29: the Unicode confusables data is final; a look-alike it does not list is
        owner-accepted residual risk.

Self-contained: no fixture files; everything is built here.
"""
import pytest

from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ~ ѕћор", "refunds-portal ~ ҫом", "refunds-portal ~ сөм", "refunds-portal ~ соӎ",
         "refunds-portal ~ ѕһөр", "refunds-portal ҫом/claim", "refunds-portal ~ ѕћор/claim")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r30_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r30_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("text", ("Рыба сом живёт в реке.", "He said спасибо to me.", "Это мой дом.",
                                  "Den store sø er smuk."))
def test_r30_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
