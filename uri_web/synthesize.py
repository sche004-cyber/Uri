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
    # R7-01: a link cut in two by the split ('Visit refunds-portal . Com/claim') is joined again, so it is checked whole.
    return U.merge_split_links([p.strip() for p in parts if p.strip()])


# Owner decision D7 (2026-10-11): an answer sentence that states a quantity - digits, a number word, a fraction,
# an ordinal, a percentage or a currency - is never shown in the Brain's words. It is replaced by the cited source
# sentence that supports it best, word for word, or dropped. Over-detection only means more quoting, so the word
# list is deliberately broad.
_QUANTITY = re.compile(
    r"\d|[$€£₹¥%\u2030\u2031]|\b(?:rs|inr|usd|eur|gbp|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|"
    r"ninety|hundreds?|thousands?|millions?|billions?|trillions?|lakhs?|lacs?|crores?|dozens?|half|halves|halved|"
    r"thirds?|quarters?|fifths?|tenths?|percent|per\s*cent|twice|thrice|double[ds]?|triple[ds]?|quadrupled?|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|once|single|dozen|score|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday|today|tomorrow|annual|annually|"
    r"daily|weekly|monthly|yearly|majority|minority|most|all|none|every|several|few|many|"
    # R1-02: multiplicative and grouping words ("tenfold", "percentage points", "a decade", "a couple of").
    r"\w+fold|percentages?|decades?|centur(?:y|ies)|millenni(?:um|a)|couples?|pairs?|dual|both|"
    r"(?:phase|part|class|grade|stage|tier|level|chapter|section|schedule|article|book|volume|act|title)\s+[ivxlcdm]|"
    # R2-02: rates, periods, magnitudes and relative dates ("hourly", "per annum", "an order of magnitude", "basis
    # points", "in the nineties", "last year"). The list is a second check only: D7 rests on _excerpt below.
    r"hourly|nightly|quarterly|bi-?annual(?:ly)?|bi-?ennial(?:ly)?|fortnight(?:ly|s)?|semesters?|trimesters?|"
    r"per\s+annum|annum|p\.a|basis\s+points?|bps|orders?\s+of\s+magnitude|magnitudes?|handful|nil|nought|naught|"
    r"(?:twent|thirt|fort|fift|sixt|sevent|eight|ninet)ies|(?:hundred|thousand|million|billion)th|"
    r"last|next|ago|previous|recent(?:ly)?|tonight|overnight|weekends?|spring|summer|autumn|winter|seasons?|"
    r"years?|months?|weeks?|days?|hours?|minutes?|centenar(?:y|ies)|anniversar(?:y|ies)|"
    # R3-02: multiplicatives as verbs and rates ("doubling", "quintupled", "biweekly", "ppm"). Still a second check.
    r"doubling|halving|tripling|quadrupling|\w*tupl(?:e[ds]?|ing)|multipl(?:y|ies|ied|ying)|bi-?weekly|"
    r"bi-?monthly|semi-?annual(?:ly)?|tri-?ennial(?:ly)?|quadrennial(?:ly)?|ppm|ppb|pct|"
    # R4-02: periods and proportions ("decennial", "unanimous"). Still a second check only.
    r"\w+ennial(?:ly)?|unanimous(?:ly)?|unanimity|fractions?|trios?|quartets?|midnight|noon|gross)\b",
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


# R2-02: words that join or contrast clauses, and the punctuation between clauses. A claim may skip neither.
_CLAUSE_WORDS = frozenset("""
and or but nor yet so while whilst whereas although though because since unless until unlike than versus vs
respectively which who whom whose where when then after before whereby compared against instead rather
""".split())
_CLAUSE_MARK = re.compile(r"[,;:()\[\]{}\u2013\u2014!?\"\u201c\u201d]|\s-\s|\.\s")
# R3-02: the only words that open a noun phrase.
_DETERMINERS = frozenset("a an the this that these those its their his her our your my".split())
# R4-02: the ONLY modifiers a claim may leave out of a noun phrase, after its determiner ("after [a long public]
# consultation"). R3-02 let any two words that were not function words go, so a qualifier inside a noun phrase ("on [a
# roughly] decennial cycle", "a [near] unanimous decision", "a [barely] positive profit") was dropped unless
# states_quantity knew the next word. This is an allow-list: a word missing from it only means the source sentence is
# quoted (D7: over-quoting costs fluency, never safety). Keep it to descriptive adjectives that carry no quantity,
# degree, hedge, polarity or truth value.
_PLAIN_MODIFIERS = frozenset("long lengthy public formal official detailed".split())
MAX_GAP_WORDS = 2
# R7-02 (closure round 8): a determiner changes the meaning of the quantifier after it: 'a little progress' (some) is
# not 'little progress' (almost none), 'a few' is not 'few', 'the most' is not 'most'. Before these words the claim
# may neither add a determiner nor leave out one the source has: the determiners must match in place, or the source
# sentence is quoted (D7: over-quoting costs fluency, never safety).
_DETERMINER_SENSITIVE = frozenset("""
little less least few fewer fewest bit bits lot lots number numbers deal great good whole while couple handful
many much more most other others same several half
""".split())


def _excerpt(claim: str, source: str) -> bool:
    """R3-02: the claim is the source sentence's own run of words, and the rule fails closed. EVERY claim word,
    function words included, is matched to the source in order; the claim may add only a determiner ("the"). Between
    two matched words the source may leave out only (a) determiners ("after [the] repairs"), or (b) one determiner
    followed by at most MAX_GAP_WORDS words from the closed allow-list _PLAIN_MODIFIERS ("after [a long public]
    consultation"). Anything else left out - a qualifier before a verb or a quantity ("are [nearly] doubling",
    "[barely] rose", "is [rarely] waived"), any other modifier inside a noun phrase ("on [a roughly] decennial
    cycle", "a [near] unanimous decision"; R4-02: R3-02 let any two non-function words go here), a preposition ("are
    [about] doubling"), a clause boundary - means the source sentence is quoted instead, which only costs fluency
    (D7). This does not depend on recognising the quantity word. states_quantity() on the skipped text is kept as an
    extra check only. R5-02/D14: the same holds at both ends of the claim (lead_ok, tail_ok): only gaps between matched
    words were checked, so a claim could be any trailing run of the sentence and drop a leading qualifier ("[Less
    than] a plurality of voters backed the measure"). Under D14 the claim runs from the sentence start (determiners
    aside) to its end; a clause edge is not enough ("Analysts said that, at most, [a quintet ...]")."""
    c = [w.lower() for w in _TOKEN.findall(claim or "")]
    toks = [(m.group(0).lower(), m.start(), m.end()) for m in _TOKEN.finditer(source or "")]
    if not any(w not in _FUNCTION_WORDS for w in c):
        return False

    def gap_ok(a: int, b: int) -> bool:
        """The source tokens strictly between matched tokens a and b may be left out."""
        skipped = [w for w, _s, _e in toks[a + 1:b]]
        text = source[toks[a][2]:toks[b][1]]
        if any(w in _CLAUSE_WORDS for w in skipped) or _CLAUSE_MARK.search(text) or states_quantity(text):
            return False
        if toks[b][0] in _DETERMINER_SENSITIVE and any(w in _DETERMINERS for w in skipped):
            return False                             # R7-02: '[a] little progress' read as 'little progress'
        if all(w in _DETERMINERS for w in skipped):
            return True
        # R4-02: modifiers only from the closed allow-list; any other word (a qualifier, an unknown word) fails closed.
        return (skipped[0] in _DETERMINERS and len(skipped) - 1 <= MAX_GAP_WORDS
                and all(w in _PLAIN_MODIFIERS for w in skipped[1:]))

    def lead_ok(j: int) -> bool:
        """D14 (owner, 2026-10-11, after R6-02: a comma edge still let 'that, at most,' go): a claim in the Brain's
        words starts at the sentence start. Only determiners may be left out before its first matched word; any
        other leading word or clause, punctuation or not, means the source sentence is quoted (D7)."""
        if j and toks[j][0] in _DETERMINER_SENSITIVE:
            return False                             # R7-02: '[A] little progress was made' read as 'Little ...'
        return all(w in _DETERMINERS for w, _s, _e in toks[:j])

    def tail_ok(j: int) -> bool:
        """D14: the claim's last matched word is the sentence's last word (trailing punctuation aside)."""
        return j == len(toks) - 1

    seen = set()                                     # (ci, prev) already shown not to match: no exponential retry

    def match(ci: int, prev: int) -> bool:
        if ci == len(c):
            return prev >= 0 and tail_ok(prev)
        if (ci, prev) in seen:
            return False
        seen.add((ci, prev))
        if (c[ci] in _DETERMINERS and not (ci + 1 < len(c) and c[ci + 1] in _DETERMINER_SENSITIVE)
                and match(ci + 1, prev)):
            return True                              # a determiner the source does not have
        for j in range(prev + 1, len(toks)):
            if prev >= 0 and not gap_ok(prev, j):
                return False                         # a longer gap cannot become allowed again
            if toks[j][0] == c[ci] and (prev >= 0 or lead_ok(j)) and match(ci + 1, j):
                return True
        return False
    return match(0, -1)


def _supported_by(body: str, cw: set, claim_nums: set, sentence) -> bool:
    """One source sentence states the claim in the claim's own words: enough shared content words, every number,
    the same polarity, no new word, and the claim is a contiguous run of the sentence's words."""
    s, w, nums = sentence
    return (bool(cw) and len(cw & w) / len(cw) >= MIN_SUPPORT and claim_nums <= nums
            and bool(_NEG.search(body)) == bool(_NEG.search(s)) and not _antonym_flip(body, s)
            and not _novel_words(body, s) and _excerpt(body, s))


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
        if _novel_words(body, best[0]) or not _excerpt(body, best[0]):
            quote_instead()                          # R9-02 / R2-02: not a contiguous run of the source's words
            continue
        # R1-06: only the cited sources that themselves state the claim stay cited.
        kept = [c for c in cited if any(_supported_by(body, cw, claim_nums, x) for x in sents_of[c - 1])]
        if len(v.claims) < MAX_ANSWER_SENTENCES:
            v.claims.append(Claim(body, kept))
    _drop_joined_links(v)
    return v


def _drop_joined_links(v: Verified) -> None:
    """R7-01: claims are shown one after the other, so two neighbours that together hold a link ('... at
    refunds-portal .' then 'Com/claim ...') are both dropped, whichever path produced them."""
    i = 0
    while i + 1 < len(v.claims):
        a, b = v.claims[i], v.claims[i + 1]
        if U.joins_link(a.text, b.text):
            v.dropped += [{"text": a.text, "reason": "LINK_OR_CONTACT"}, {"text": b.text, "reason": "LINK_OR_CONTACT"}]
            del v.claims[i:i + 2]
            i = max(i - 1, 0)
        else:
            i += 1


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
    _drop_joined_links(v)
    picked = v.claims
    if not picked:
        v.no_answer = True
    return v


HIDDEN_TITLE = "(title hidden: instruction-like text)"


def brain_messages(query: str, sources: list) -> list:
    """`sources`: list of (title, text). Query goes in the user turn; sources only inside data blocks."""
    # R41-04: an instruction-like title is sent as a neutral placeholder (its sentences never reach the Brain).
    blocks = "\n\n".join(U.data_block(i + 1, HIDDEN_TITLE if U.flags(t or "") else t, x[:6000])
                         for i, (t, x) in enumerate(sources))
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
    if v.claims:
        return Synthesis("brain", v, brain_status=status)
    fb = extractive(query, texts)
    if v.no_answer:
        # R41-04: the Brain's NO_ANSWER can come from a source telling it to say so; it never hides sentences the
        # extractive path finds in the sources (those are shown instead, as when the Brain is off).
        if not fb.claims:
            return Synthesis("brain", v, brain_status=status)
        return Synthesis("extractive_fallback", fb, brain_status="NO_ANSWER")
    fb.dropped = v.dropped
    return Synthesis("extractive_fallback", fb, brain_status="ALL_CLAIMS_DROPPED")
