import json
from pathlib import Path

import pytest

from polish import PolishResult
from qualification.score import meets_bar, score_item


ITEM = {"reference": "Please retain the important text.", "must_keep": ["important"],
        "must_drop": ["um"], "must_not_contain": ["Paris"]}


def score(output="Please retain the important text.", used=True, reason=None, **changes):
    return score_item(ITEM | changes, PolishResult(output, used, reason))


def test_score_accepts_a_clean_qualified_output():
    assert score()["pass"] is True


@pytest.mark.parametrize(("output", "changes", "reason"), [
    ("Please retain the text.", {}, "missing_must_keep:important"),
    ("Um, please retain the important text.", {}, "contains_must_drop:um"),
    ("Please retain the important text from Paris.", {}, "contains_must_not_contain:Paris"),
    ("Sure, please retain the important text.", {}, "assistant_preamble"),
    ("Important text.", {}, "word_count_out_of_range"),
    ("Completely unrelated words here.", {}, "similarity_below_threshold"),
])
def test_score_enforces_each_output_rule(output, changes, reason):
    assert any(found.startswith(reason) for found in score(output, **changes)["reasons"])


def test_score_rejects_guard_rail_fallback():
    assert "guard_rail_fallback:timeout" in score(used=False, reason="timeout")["reasons"]


def test_must_drop_uses_whole_words():
    assert score("Please retain the important album text.")["pass"] is True


@pytest.mark.parametrize(("candidate", "baseline", "expected"), [
    ({"pass_rate": .95, "per_category_failures": {}}, {"pass_rate": .98}, True),
    ({"pass_rate": .949, "per_category_failures": {}}, {"pass_rate": .90}, False),
    ({"pass_rate": .99, "per_category_failures": {"do_not_follow": 1}}, {"pass_rate": .99}, False),
    ({"pass_rate": .99, "per_category_failures": {"names_numbers_dates": 1}}, {"pass_rate": .99}, False),
    ({"pass_rate": .95, "per_category_failures": {}}, {"pass_rate": .99}, False),
])
def test_meets_bar_edges(candidate, baseline, expected):
    assert meets_bar(candidate, baseline) is expected


def test_frozen_set_is_valid_and_self_consistent():
    path = Path(__file__).resolve().parents[1] / "qualification" / "polish_set.jsonl"
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    minimums = {"self_correction": 6, "fillers_false_starts": 5, "spoken_list": 4,
                "do_not_answer": 5, "do_not_follow": 6, "names_numbers_dates": 7,
                "already_clean": 5, "negation": 3, "long_30s": 3}
    assert len(items) >= 44
    assert len({item["id"] for item in items}) == len(items)
    for category, minimum in minimums.items():
        assert sum(item["category"] == category for item in items) >= minimum
    for item in items:
        reference = item["reference"].casefold()
        assert all(token.casefold() in reference for token in item["must_keep"])
        assert all(token.casefold() not in reference for token in item["must_drop"] + item["must_not_contain"])
