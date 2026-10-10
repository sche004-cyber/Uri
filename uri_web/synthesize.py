"""Synthesize a citation-backed answer and verify every citation.

Two synthesizers, one verifier:
  * `extractive(...)`: deterministic, CPU only. Picks query-relevant sentences from the sources; each sentence cites
    its own source. Always available (the Brain may be stopped, busy or degraded).
  * `with_brain(...)`: asks the resident Brain (Runtime v1 via an injected `complete` callable) to write the summary
    from numbered, untrusted data blocks. Its output is NEVER shown unverified.
  * `verify(...)`: a sentence survives only if every citation index exists, the cited sources contain every number
    it states, and enough of its content words occur in the cited sources. Anything else is dropped and reported.
If verification leaves nothing, the extractive answer is used and the fallback is recorded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import untrusted as U
from .evaluate import content_words, numbers, sentences

MIN_SUPPORT = 0.6
MAX_ANSWER_SENTENCES = 8
NO_ANSWER = "NO_ANSWER"
_CITE = re.compile(r"\[(\d{1,3})\]")
_CITE_GROUP = re.compile(r"(?:\s*\[\d{1,3}\])+\s*$")


@dataclass
class Claim:
    text: str
    citations: list


@dataclass
class Verified:
    claims: list = field(default_factory=list)
    dropped: list = field(default_factory=list)       # {"text", "reason"}
    no_answer: bool = False


@dataclass
class Synthesis:
    method: str                      # extractive | brain | extractive_fallback | none
    verified: Verified
    brain_status: Optional[str] = None


def _split_answer(text: str) -> list:
    text = (text or "").strip()
    parts = re.split(r"(?<=[.!?\]])\s+(?=[A-Z0-9\"'(])", text)
    return [p.strip() for p in parts if p.strip()]


def verify(answer: str, source_texts: list) -> Verified:
    """`source_texts[i]` is the text of citation number i+1."""
    v = Verified()
    if (answer or "").strip().upper().startswith(NO_ANSWER):
        v.no_answer = True
        return v
    n = len(source_texts)
    words_of = [content_words(t) for t in source_texts]
    nums_of = [numbers(t) for t in source_texts]
    for sent in _split_answer(answer)[: MAX_ANSWER_SENTENCES * 2]:
        cites = [int(c) for c in _CITE.findall(sent)]
        body = _CITE.sub("", sent).strip()
        if U.flags(body):
            v.dropped.append({"text": sent, "reason": "INSTRUCTION_LIKE"})
            continue
        if U.has_link_or_contact(body):
            v.dropped.append({"text": sent, "reason": "LINK_OR_CONTACT"})
            continue
        if not cites:
            v.dropped.append({"text": sent, "reason": "NO_CITATION"})
            continue
        if any(c < 1 or c > n for c in cites):
            v.dropped.append({"text": sent, "reason": "CITATION_OUT_OF_RANGE"})
            continue
        cited = sorted(set(cites))
        claim_nums = numbers(body)
        avail_nums = set().union(*(nums_of[c - 1] for c in cited))
        if not claim_nums <= avail_nums:
            v.dropped.append({"text": sent, "reason": "NUMBER_NOT_IN_CITED_SOURCE"})
            continue
        cw = content_words(body)
        avail = set().union(*(words_of[c - 1] for c in cited))
        support = len(cw & avail) / len(cw) if cw else 0.0
        if support < MIN_SUPPORT:
            v.dropped.append({"text": sent, "reason": "INSUFFICIENT_SUPPORT"})
            continue
        if len(v.claims) < MAX_ANSWER_SENTENCES:
            v.claims.append(Claim(body, cited))
    return v


def extractive(query: str, source_texts: list, *, max_sentences: int = 6, per_source: int = 2) -> Verified:
    q = content_words(query)
    scored = []
    for i, t in enumerate(source_texts):
        for pos, s in enumerate(sentences(t, limit=200)):
            w = content_words(s)
            if not w or not q or U.flags(s) or U.has_link_or_contact(s):
                continue
            score = len(q & w) / len(q) - pos * 0.001
            if q & w:
                scored.append((score, i, pos, s))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    used, picked = {}, []
    for score, i, pos, s in scored:
        if used.get(i, 0) >= per_source:
            continue
        used[i] = used.get(i, 0) + 1
        picked.append(Claim(s, [i + 1]))
        if len(picked) >= max_sentences:
            break
    v = Verified(claims=picked)
    if not picked:
        v.no_answer = True
    return v


def brain_messages(query: str, sources: list) -> list:
    """`sources`: list of (title, text). Query goes in the user turn; sources only inside data blocks."""
    blocks = "\n\n".join(U.data_block(i + 1, t, x[:6000]) for i, (t, x) in enumerate(sources))
    rules = U.SYSTEM_RULES + f" If the sources do not answer the question, reply exactly {NO_ANSWER}."
    return [{"role": "system", "content": rules},
            {"role": "user", "content": "QUESTION: " + U.neutralise(query)[:400] + "\n\nSOURCES:\n" + blocks}]


def synthesize(query: str, sources: list, *, complete: Optional[Callable] = None) -> Synthesis:
    """`sources`: list of (title, text) numbered 1..N. `complete(messages) -> (status, text)` uses the Brain;
    status 'COMPLETE' is the only success."""
    texts = [t for _title, t in sources]
    if not sources:
        return Synthesis("none", Verified(no_answer=True))
    if complete is None:
        return Synthesis("extractive", extractive(query, texts))
    try:
        status, text = complete(brain_messages(query, sources))
    except Exception:            # the Brain is optional; its failure is reported, never fatal
        status, text = "FAILED", ""
    if status != "COMPLETE":
        return Synthesis("extractive_fallback", extractive(query, texts), brain_status=status)
    v = verify(text, texts)
    if v.no_answer or v.claims:
        return Synthesis("brain", v, brain_status=status)
    fb = extractive(query, texts)
    fb.dropped = v.dropped
    return Synthesis("extractive_fallback", fb, brain_status="ALL_CLAIMS_DROPPED")
