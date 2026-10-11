"""Synthesize a citation-backed answer and check every citation LEXICALLY.

The check is lexical, not semantic: it proves that a cited source contains a sentence that states the claim's
words and numbers with the same polarity. It cannot prove that a paraphrase means the same thing; the UI therefore
says "citations checked against the sources", never "verified true".

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
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import untrusted as U
from .evaluate import content_words, numbers, sentences, unreadable

MIN_SUPPORT = 0.6
# Polarity: a claim and its best supporting sentence must agree on negation (interim review F3).
_NEG = re.compile(r"(?i)\b(not|no|never|none|neither|nor|without|cannot|isn't|wasn't|aren't|weren't|doesn't|didn't|"
                  r"don't|won't|hasn't|haven't|hadn't|shouldn't|couldn't|wouldn't)\b|n't\b")
_ANTONYMS = [("approved", "rejected"), ("approved", "denied"), ("safe", "unsafe"), ("effective", "ineffective"),
             ("increase", "decrease"), ("increased", "decreased"), ("rise", "fall"), ("rose", "fell"),
             ("legal", "illegal"), ("allowed", "banned"), ("allowed", "prohibited"), ("open", "closed"),
             ("higher", "lower"), ("more", "less"), ("gain", "loss"), ("passed", "failed"), ("true", "false"),
             ("accepted", "rejected"), ("valid", "invalid"), ("confirmed", "denied")]
MAX_ANSWER_SENTENCES = 8
NO_ANSWER = "NO_ANSWER"
_CITE = re.compile(r"\[(\d{1,3})\]")
_CITE_GROUP = re.compile(r"(?:\s*\[\d{1,3}\])+\s*$")


@dataclass
class Claim:
    text: str
    citations: list
    quoted: bool = False      # D7: the text is a source sentence, word for word


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


# Owner decision D7 (2026-10-11): an answer sentence that states a quantity - digits, a number word, a fraction,
# an ordinal, a percentage or a currency - is never shown in the Brain's words. It is replaced by the cited source
# sentence that supports it best, word for word, or dropped. Over-detection only means more quoting, so the word
# list is deliberately broad.
_QUANTITY = re.compile(
    r"\d|[$€£₹¥%]|\b(?:rs|inr|usd|eur|gbp|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|"
    r"ninety|hundreds?|thousands?|millions?|billions?|trillions?|lakhs?|lacs?|crores?|dozens?|half|halves|halved|"
    r"thirds?|quarters?|fifths?|tenths?|percent|per\s*cent|twice|thrice|double[ds]?|triple[ds]?|quadrupled?|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|once|single|dozen|score|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday|today|tomorrow|annual|annually|"
    r"daily|weekly|monthly|yearly|majority|minority|most|all|none|every|several|few|many|"
    # R1-02: multiplicative and grouping words ("tenfold", "percentage points", "a decade", "a couple of").
    r"\w+fold|percentages?|decades?|centur(?:y|ies)|millenni(?:um|a)|couples?|pairs?|dual|both|"
    r"(?:phase|part|class|grade|stage|tier|level|chapter|section|schedule|article|book|volume|act|title)\s+[ivxlcdm])\b",
    re.I)


# R9-02: a word list alone always misses the next form ("eleventh", "hundredth", "¾", "Chapter XI"). Any Unicode
# number character (vulgar fractions, Roman numeral letters, superscripts: categories Nd/Nl/No), any currency symbol
# (Sc), any ordinal built from a number stem ("eleventh", "twenty-third", "hundredth", "thousandth") and upper-case
# Roman numerals are quantities too. A plain -th/-st/-nd/-rd suffix rule is not used: it matches "and", "board",
# "most", "with" and would quote almost every sentence. The structural rule below (_novel_words) is the backstop for
# everything a list misses.
_ORDINAL = re.compile(r"(?i)\b\w*(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|"
                      r"twelfth|teenth|tieth|hundredth|thousandth|millionth|billionth|trillionth|lakhth|croreth|zeroth|"
                      r"umpteenth|nth)s?\b")
_ROMAN = re.compile(r"\b(?=[MDCLXVI]{2,}\b)M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})\b")


def states_quantity(text: str) -> bool:
    text = text or ""
    return bool(_QUANTITY.search(text) or _ORDINAL.search(text) or _ROMAN.search(text)
                or any(unicodedata.category(ch) in ("Nd", "Nl", "No", "Sc") for ch in text))


# R9-02: a sentence in the Brain's own words is shown only if every word it adds to its supporting source sentence is
# one of these function words. Any other new word (a value, a name, an ordinal, a qualifier) means the source
# sentence is quoted instead, word for word, or the claim is dropped - not decided by a list of quantity forms.
_FUNCTION_WORDS = frozenset("""
a an the of in on at to for from by with as and or but that this these those it its they their them he she his her
him we our us you your i is are was were be been being has have had do does did will would shall should can could
which who whom whose what when where how there here than then so also about into onto over under after before
between during while if because although though such per via said says according reported reports
""".split())
_TOKEN = re.compile(r"[^\W_]+")


def _words_of(text: str) -> set:
    return {w.lower() for w in _TOKEN.findall(text or "")}


def _novel_words(claim: str, source: str) -> set:
    return _words_of(claim) - _words_of(source) - _FUNCTION_WORDS


def _in_order(claim: str, source: str) -> bool:
    """R1-02: the claim's words (function words aside) occur in the source sentence in the same order. Words that are
    all present but recombined ("rents ... rose" + "wages rose tenfold") are not the source's statement."""
    src = iter(w.lower() for w in _TOKEN.findall(source or ""))
    return all(any(w == s for s in src) for w in (w.lower() for w in _TOKEN.findall(claim or ""))
               if w not in _FUNCTION_WORDS)


def _supported_by(body: str, cw: set, claim_nums: set, sentence) -> bool:
    """One source sentence states the claim in the claim's own words: enough shared content words, every number,
    the same polarity, no new word and the same word order."""
    s, w, nums = sentence
    return (bool(cw) and len(cw & w) / len(cw) >= MIN_SUPPORT and claim_nums <= nums
            and bool(_NEG.search(body)) == bool(_NEG.search(s)) and not _antonym_flip(body, s)
            and not _novel_words(body, s) and _in_order(body, s))


def verify(answer: str, source_texts: list) -> Verified:
    """`source_texts[i]` is the text of citation number i+1."""
    v = Verified()
    if (answer or "").strip().upper().startswith(NO_ANSWER):
        v.no_answer = True
        return v
    n = len(source_texts)
    sents_of = [[(s, content_words(s), numbers(s)) for s in sentences(t, limit=400)] for t in source_texts]
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

        def quote_instead():
            q = _quote(body, cited, sents_of)
            if q is None:
                v.dropped.append({"text": sent, "reason": "NO_SOURCE_SENTENCE_TO_QUOTE"})
            elif q[0] in {c.text for c in v.claims}:
                pass                                 # the same source sentence is shown once
            elif len(v.claims) < MAX_ANSWER_SENTENCES:
                v.claims.append(Claim(q[0], [q[1]], quoted=True))
        if states_quantity(body):
            quote_instead()
            continue
        claim_nums = numbers(body)
        cw = content_words(body)
        # The claim must be supported by ONE sentence of a cited source (not by words scattered over the page).
        best, best_s = None, 0.0
        for c in cited:
            for s, w, nums in sents_of[c - 1]:
                sc = len(cw & w) / len(cw) if cw else 0.0
                if sc > best_s:
                    best, best_s = (s, w, nums), sc
        # A numeral that cannot be read whole (R5-01) is unverifiable: the claim is dropped, never matched by text.
        if best is None or unreadable(claim_nums) or not claim_nums <= best[2]:
            v.dropped.append({"text": sent, "reason": "NUMBER_NOT_IN_CITED_SOURCE" if claim_nums
                              else "INSUFFICIENT_SUPPORT"})
            continue
        if best_s < MIN_SUPPORT:
            v.dropped.append({"text": sent, "reason": "INSUFFICIENT_SUPPORT"})
            continue
        if bool(_NEG.search(body)) != bool(_NEG.search(best[0])) or _antonym_flip(body, best[0]):
            v.dropped.append({"text": sent, "reason": "POLARITY_MISMATCH"})
            continue
        if _novel_words(body, best[0]) or not _in_order(body, best[0]):
            quote_instead()                          # R9-02 / R1-02: a word or word order the source does not have
            continue
        # R1-06: only the cited sources that themselves state the claim stay cited.
        kept = [c for c in cited if any(_supported_by(body, cw, claim_nums, x) for x in sents_of[c - 1])]
        if len(v.claims) < MAX_ANSWER_SENTENCES:
            v.claims.append(Claim(body, kept))
    return v


def _quote(body: str, cited: list, sents_of: list):
    """(source sentence, citation number) that best supports ``body`` - one sentence of one cited source, with enough
    shared content words and safe to show (no instruction-like text, link or contact) - else None."""
    cw = content_words(_QUANTITY.sub(" ", body)) or content_words(body)
    best, best_s = None, 0.0
    for c in cited:
        for s, w, _n in sents_of[c - 1]:
            sc = len(cw & w) / len(cw) if cw else 0.0
            if sc > best_s and not U.flags(s) and not U.has_link_or_contact(s):
                best, best_s = (s, c), sc
    return best if best is not None and best_s >= MIN_SUPPORT else None


def _antonym_flip(claim: str, source: str) -> bool:
    c = set(re.findall(r"[a-z]+", claim.lower()))
    s = set(re.findall(r"[a-z]+", source.lower()))
    for a, b in _ANTONYMS:
        if (a in c and b in s and a not in s) or (b in c and a in s and b not in s):
            return True
    return False


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
