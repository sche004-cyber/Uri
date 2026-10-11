"""Regressions for review R1 of 8019d41 (finding R1-01). Each fails without its repair."""
import pytest

from uri_web import evaluate as EV
from uri_web import synthesize as SY


@pytest.mark.parametrize("text, expected", [
    ("Onions cost Rs.500 per kilogram.", {"500"}), ("It took approx.900 days.", {"900"}), ("See No.5 below.", {"5"}),
    ("Fees are Rs.1,250.50 now.", {"1250.50"}), ("Pi is 3.14 and 2.5% more.", {"3.14", "2.5%"}),
])
def test_r1_01_numbers_after_letters_or_dots_are_extracted(text, expected):
    assert EV.numbers(text) == expected


@pytest.mark.parametrize("claim_num, source_num", [("Rs.900", "Rs.500"), ("approx.900", "approx.100"), ("No.5", "No.6")])
def test_r1_01_unsupported_number_is_dropped(claim_num, source_num):
    claim = f"Prices in the city market rose sharply and onions now cost {claim_num} per kilogram this week [1]."
    source = f"Prices in the city market rose sharply and onions now cost {source_num} per kilogram this week."
    v = SY.verify(claim, [source])
    assert v.claims == []
    assert [d["reason"] for d in v.dropped] == ["NUMBER_NOT_IN_CITED_SOURCE"]


def test_r1_01_supported_number_still_kept():
    s = "Prices in the city market rose sharply and onions now cost Rs.500 per kilogram this week."
    v = SY.verify(s[:-1] + " [1].", [s])
    assert len(v.claims) == 1 and v.dropped == []


def test_r1_01_differing_prefixed_numbers_are_a_conflict():
    pages = [{"url": "https://a.example/x", "text": "Onions in the city market now cost Rs.500 per kilogram this week."},
             {"url": "https://b.example/y", "text": "Onions in the city market now cost Rs.900 per kilogram this week."}]
    ev = EV.evaluate(pages, "onion price city market")
    assert len(ev.conflicts) == 1
