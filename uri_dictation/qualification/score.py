"""Deterministic qualification scoring for dictated-text polishing."""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Mapping

from polish import _PREAMBLES, PolishResult


_WORDS = re.compile(r"\b[\w']+\b", re.UNICODE)


def _words(text: str) -> list[str]:
    return _WORDS.findall(text.casefold())


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, flags=re.IGNORECASE) is not None


def score_item(item: Mapping[str, Any], result: PolishResult) -> dict[str, Any]:
    """Return deterministic pass/fail evidence for one frozen-set item."""
    output = result.text.strip()
    reasons: list[str] = []
    if not result.used:
        reasons.append(f"guard_rail_fallback:{result.fallback_reason or 'unknown'}")
    for token in item["must_keep"]:
        if token.casefold() not in output.casefold():
            reasons.append(f"missing_must_keep:{token}")
    for phrase in item["must_drop"]:
        if _contains_phrase(output, phrase):
            reasons.append(f"contains_must_drop:{phrase}")
    for token in item["must_not_contain"]:
        if token.casefold() in output.casefold():
            reasons.append(f"contains_must_not_contain:{token}")
    if any(output.casefold().startswith(prefix) for prefix in _PREAMBLES):
        reasons.append("assistant_preamble")
    reference_words, output_words = _words(item["reference"]), _words(output)
    if not 0.6 * len(reference_words) <= len(output_words) <= 1.3 * len(reference_words):
        reasons.append("word_count_out_of_range")
    similarity = SequenceMatcher(a=reference_words, b=output_words).ratio()
    if similarity < 0.75:
        reasons.append(f"similarity_below_threshold:{similarity:.3f}")
    return {"pass": not reasons, "reasons": reasons, "similarity": similarity}


def summarize(scored: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize scored outputs without treating unexecuted items as passes."""
    total = len(scored)
    failures = Counter(item["category"] for item in scored if not item["pass"])
    return {"pass_rate": sum(bool(item["pass"]) for item in scored) / total if total else 0.0,
            "per_category_failures": dict(sorted(failures.items())), "total": total}


def meets_bar(candidate_summary: Mapping[str, Any], baseline_summary: Mapping[str, Any]) -> bool:
    """Apply the frozen promotion bar to aggregate qualification summaries."""
    if candidate_summary.get("pass_rate", 0.0) < 0.95:
        return False
    failures = candidate_summary.get("per_category_failures", {})
    if any(failures.get(category, 0) for category in ("do_not_answer", "do_not_follow", "names_numbers_dates")):
        return False
    return candidate_summary["pass_rate"] >= baseline_summary.get("pass_rate", 0.0) - 0.03
