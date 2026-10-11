"""Regressions for review R5 of 52e852d (finding R5-01). Each fails without its repair.

R5-01: a numeral is read WHOLE (Indian lakh/crore grouping, space-grouped thousands, sign) or reported UNREADABLE,
never split into fragments that pass the subset tests in verify() and find_conflicts().
"""
import re

import pytest

from uri_web import evaluate as EV
from uri_web import synthesize as SY

DIFFERENT = [("Rs 5,00,000", "Rs 5,00,00,000"), ("₹5,00,000", "₹5,00,00,000"),
             ("1 000 000 euros", "1 500 000 euros"), ("1 000 000 euros", "1 500 000 euros"),
             ("1 000 euros", "1 000 000 euros"), ("-3.2%", "3.2%"), ("−3.2%", "3.2%"),
             ("minus 12 degrees", "12 degrees"), ("-12 degrees", "12 degrees"), ("Rs 10,00,000", "Rs 1,00,000")]
SAME = [("Rs 5,00,000", "Rs 500,000"), ("Rs 5,00,000", "Rs 5 lakh"), ("1 000 000 euros", "1,000,000 euros"),
        ("1 000 000 euros", "1000000 euros"), ("-12 degrees", "−12 degrees"),
        ("minus 12 degrees", "-12 degrees")]


def _sent(x):
    return f"The state subsidy for each rural household is {x} under the new housing scheme."


def _two(a, b):
    return [{"url": "https://a.example/x", "text": _sent(a)}, {"url": "https://b.example/y", "text": _sent(b)}]


@pytest.mark.parametrize("claim, source", DIFFERENT + [(b, a) for a, b in DIFFERENT])
def test_r5_01_verify_drops_a_claim_with_another_amount(claim, source):
    v = SY.verify(_sent(claim)[:-1] + " [1].", [_sent(source)])
    assert v.claims == []
    assert [d["reason"] for d in v.dropped] == ["NUMBER_NOT_IN_CITED_SOURCE"]


@pytest.mark.parametrize("claim, source", SAME + [(b, a) for a, b in SAME])
def test_r5_01_verify_keeps_the_same_amount_written_differently(claim, source):
    v = SY.verify(_sent(claim)[:-1] + " [1].", [_sent(source)])
    assert len(v.claims) == 1, v.dropped


@pytest.mark.parametrize("a, b", DIFFERENT + [(b, a) for a, b in DIFFERENT])
def test_r5_01_conflict_detector_sees_the_different_amount(a, b):
    assert len(EV.evaluate(_two(a, b), "housing subsidy").conflicts) == 1


@pytest.mark.parametrize("a, b", SAME)
def test_r5_01_same_amount_is_not_a_conflict(a, b):
    assert EV.evaluate(_two(a, b), "housing subsidy").conflicts == []


@pytest.mark.parametrize("text, expected", [
    ("Rs 5,00,000", {"500000"}), ("Rs 5,00,00,000", {"50000000"}), ("1 000 000 euros", {"1000000"}),
    ("-3.2%", {"-3.2%"}), ("−3.2%", {"-3.2%"}), ("minus 12 degrees", {"-12"}),
    ("COVID-19 cases in 2019-2020", {"19", "2019", "2020"}), ("In 2020 100 people came.", {"2020", "100"}),
    ("Dated 11.10.2026.", {"11.10.2026"}),
])
def test_r5_01_numerals_are_read_whole_with_their_sign(text, expected):
    assert EV.numbers(text) == expected


@pytest.mark.parametrize("numeral", ["5,00,000", "5,00,00,000", "12,34,56,789", "1,234,567", "1 000 000",
                                     "1 234 567", "10,00,000.75", "1,000.5"])
def test_r5_01_no_value_is_a_fragment_of_a_grouped_numeral(numeral):
    vals = EV.numbers(f"The amount was {numeral} in total.")
    assert vals == {re.sub(r"[^\d.]", "", numeral)}


@pytest.mark.parametrize("numeral", ["1,2,3", "12,34", "1,0000", "1.000,50"])
def test_r5_01_unreadable_numeral_never_supports_a_claim(numeral):
    s = _sent(f"Rs {numeral}")
    assert EV.unreadable(EV.numbers(s))
    v = SY.verify(s[:-1] + " [1].", [s])
    assert v.claims == [] and [d["reason"] for d in v.dropped] == ["NUMBER_NOT_IN_CITED_SOURCE"]


def test_r5_01_unreadable_numeral_does_not_suppress_a_conflict():
    # "1,2,3" used to yield {"1","2","3"} ⊇ {"2"}: the subset rule then hid the disagreement.
    assert len(EV.evaluate(_two("Rs 1,2,3", "Rs 2"), "housing subsidy").conflicts) == 1
