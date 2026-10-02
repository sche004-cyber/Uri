"""Deterministic transcript cleanup. No model is involved here."""

from __future__ import annotations

import re
from collections.abc import Mapping


_SIMPLE_FILLERS = re.compile(r"\b(?:um+|uh+|erm)\b", re.IGNORECASE)
_YOU_KNOW_START = re.compile(r"(?:(?<=^)|(?<=[.!?]))\s*you\s+know\s*,\s*", re.IGNORECASE)
_YOU_KNOW_MIDDLE = re.compile(r",\s*you\s+know\s*,\s*", re.IGNORECASE)
_YOU_KNOW_END = re.compile(r",\s*you\s+know(?=\s*(?:$|[.!?]))", re.IGNORECASE)
_WORD = re.compile(r"\b[\w']+\b", re.UNICODE)
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")
_MULTISPACE = re.compile(r"\s{2,}")


def cleanup_transcript(text: str, replacements: Mapping[str, str] | None = None) -> str:
    """Remove fillers/repetitions and apply literal whole-word dictionary entries."""
    capitalise_first_word = bool(text[:1].isupper())
    cleaned = _SIMPLE_FILLERS.sub("", text)
    # "you know" is removed only when punctuation makes it an aside/filler.
    cleaned = _YOU_KNOW_START.sub("", cleaned)
    cleaned = _YOU_KNOW_MIDDLE.sub(", ", cleaned)
    cleaned = _YOU_KNOW_END.sub("", cleaned)
    words: list[str] = []
    cursor = 0
    for match in _WORD.finditer(cleaned):
        between = cleaned[cursor:match.start()]
        word = match.group(0)
        if words and words[-1].casefold() == word.casefold() and not between.strip():
            cleaned = cleaned[:match.start()] + cleaned[match.end():]
            cleaned = cleanup_transcript(cleaned, replacements)
            if capitalise_first_word:
                first_letter = re.search(r"[A-Za-z]", cleaned)
                if first_letter:
                    index = first_letter.start()
                    cleaned = cleaned[:index] + cleaned[index].upper() + cleaned[index + 1 :]
            return cleaned
        words.append(word)
        cursor = match.end()

    for source, target in (replacements or {}).items():
        if source:
            cleaned = re.sub(r"\b" + re.escape(source) + r"\b", target, cleaned, flags=re.IGNORECASE)

    cleaned = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = _MULTISPACE.sub(" ", cleaned)
    cleaned = re.sub(r"^[,\s]+", "", cleaned).strip()
    if capitalise_first_word:
        first_letter = re.search(r"[A-Za-z]", cleaned)
        if first_letter:
            index = first_letter.start()
            cleaned = cleaned[:index] + cleaned[index].upper() + cleaned[index + 1 :]
    return cleaned
