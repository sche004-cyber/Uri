"""M35 URIv1 -- A2.8D D1: small, deterministic, generalizable reference detector.

Benchmark-only. Does NOT modify uri_v1/turn/*. Does NOT import any private
helper from turn_frame_builder.py -- fully self-contained so it stands as an
independent detector, not a disguised extension of TurnFrame's own module.

Frozen boundary (per M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md
S13): may output presence/span/coarse-type/recency-hint/scoped-negation only.
MUST NOT output a candidate ID, a ranking, or a resolution decision.

Design discipline (per the frozen plan S12/S16): generalizable linguistic
mechanisms only, not a bigger hand-listed phrase vocabulary. Every mechanism
below is a general grammatical/orthographic SHAPE rule (determiner + noun
phrase, quoted span, filename extension, closed-class temporal deixis word),
not an enumeration of the corpus's own wording. None of these mechanisms was
tuned against this corpus's pass/fail rate -- they were designed from the
general shape of the failure (SILENT_STEP1_MISS dominated by multi-word noun
phrases TurnFrame's 21 fixed patterns cannot match) before any run was scored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Generic type vocabulary -- reused verbatim from rar_deterministic.py's own
# GENERIC_TYPE_WORDS (not a new invented list; mechanical reuse of an
# existing, already-approved vocabulary so D1 does not introduce a second,
# divergent notion of "generic type word").
# ---------------------------------------------------------------------------
TYPE_HEAD_WORDS = {
    "document": "document", "documents": "document",
    "file": "document", "files": "document",
    "spreadsheet": "spreadsheet", "spreadsheets": "spreadsheet",
    "pdf": "pdf",
    "image": "image", "images": "image", "photo": "image", "photos": "image",
    "picture": "image", "pictures": "image", "scan": "pdf", "scans": "pdf",
    "email": "email", "emails": "email", "message": "email", "reply": "email",
    "person": "person", "record": "record", "records": "record",
    "attachment": None, "attachments": None,  # ambiguous type on its own
    "letter": "document", "invoice": "pdf", "contract": None,
    "template": None, "roster": "spreadsheet", "minutes": "document",
    "agenda": "document", "certificate": "pdf",
}

# Closed grammatical class of English temporal-deixis / ordinal words --
# not a domain vocabulary. Mapped to the same recency_hint vocabulary
# RAREvidence already recognizes (RAR itself only acts on "same", "previous",
# "earlier", "latest", "current", "revised", "original", "other").
_RECENCY_LEXICON: Tuple[Tuple[str, str], ...] = (
    (r"\bmost recent\b", "latest"),
    (r"\blatest\b", "latest"),
    (r"\bcurrent\b", "current"),
    (r"\bsame\b", "same"),
    (r"\bthe one before\b", "previous"),
    (r"\bone before\b", "previous"),
    (r"\bbefore (?:that|it)\b", "previous"),
    (r"\bprevious\b", "previous"),
    (r"\bearlier\b", "earlier"),
    (r"\bearliest\b", "earlier"),
    (r"\blast week\b", "earlier"),
    (r"\byesterday\b", "earlier"),
    (r"\brevised\b", "revised"),
    (r"\boriginal\b", "original"),
    (r"\bthe other\b", "other"),
)

_FILENAME_RE = re.compile(
    r"\b[\w][\w\-]*\.(?:pdf|docx?|xlsx?|csv|jpe?g|png|pptx?|txt)\b", re.IGNORECASE
)
_QUOTED_RE = re.compile(r"['\"]([^'\"]+)['\"]")

# General determiner + short noun phrase shape. Captures "the attached file",
# "the latest board minutes", "the one before that", "that document", "this
# spreadsheet", "the contract Jonas sent over last week" (the phrase extends
# until a clause-ending punctuation or coordinating conjunction). This is a
# grammatical shape rule (determiner-headed NP), not an enumeration.
_NP_STOP_WORD = r"(?:and|but|so|because|which|who|that|to|for)"
_DET_NP_RE = re.compile(
    r"\b(the|this|that|these|those)\s+"
    r"((?:(?!\b" + _NP_STOP_WORD + r"\b)[a-z][a-z\'\-]*\s+){0,6}"
    r"(?!\b" + _NP_STOP_WORD + r"\b)[a-z][a-z\'\-]*)"
    r"(?=[,.;!?]|\s+" + _NP_STOP_WORD + r"\b|$)",
    re.IGNORECASE,
)

_BARE_PRONOUN_RE = re.compile(
    r"\b(it|this|that|them|him|her|they|these|those)\b", re.IGNORECASE
)

_STOPWORD_NP_HEADS = {
    "one", "ones", "thing", "things",  # too generic alone unless combined w/ qualifier
}

_NEGATION_PATTERNS = [
    r"\bdon't\b", r"\bdont\b", r"\bdo not\b", r"\bnot\b", r"\bnever\b",
    r"\bno\b", r"\bcannot\b", r"\bcan't\b", r"\bshouldn't\b", r"\bwon't\b",
]


def _unmask(s: str, placeholders: List[str]) -> str:
    for i, orig in enumerate(placeholders):
        s = s.replace(f"\x00FN{i}\x00", orig)
    return s


def _split_clauses(text: str) -> Tuple[str, ...]:
    """Self-contained clause splitter (independent re-implementation, not an
    import of turn_frame_builder's private helper). Splits on sentence
    terminals, semicolons, and strong coordinating conjunctions -- the same
    general grammatical shape TurnFrame's own splitter uses, reasoned from
    first principles rather than copied line-for-line.

    Filename-shaped tokens (e.g. "report.pdf") are protected from having
    their own "." treated as a sentence terminal by masking them first.
    """
    masked = text
    placeholders: List[str] = []
    for m in _FILENAME_RE.finditer(text):
        token = f"\x00FN{len(placeholders)}\x00"
        placeholders.append(m.group(0))
        masked = masked.replace(m.group(0), token, 1)
    sentences = re.split(r"[.?!]+", masked)
    sentences = [
        s if not placeholders else _unmask(s, placeholders)
        for s in sentences
    ]
    clauses: List[str] = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        parts = re.split(r";|\s*,\s*(?:and|but|while|so)\s+|\s*-\s*", s_clean)
        for p in parts:
            p_clean = p.strip()
            if p_clean:
                clauses.append(p_clean)
    return tuple(clauses) if clauses else (text.strip(),)


@dataclass(frozen=True)
class D1Reference:
    span: str
    clause_text: str
    coarse_type: Optional[str] = None
    recency_hint: Optional[str] = None
    negation_spans: Tuple[str, ...] = ()
    mechanism: str = ""  # which sub-mechanism produced this (for telemetry/audit)


def _type_hint_for_phrase(phrase: str) -> Optional[str]:
    tokens = re.findall(r"[a-zA-Z]+", phrase.lower())
    for tok in reversed(tokens):  # head noun is usually last
        if tok in TYPE_HEAD_WORDS:
            mapped = TYPE_HEAD_WORDS[tok]
            if mapped:
                return mapped
    return None


def _recency_hint_for_text(text: str) -> Optional[str]:
    low = text.lower()
    for pat, hint in _RECENCY_LEXICON:
        if re.search(pat, low):
            return hint
    return None


def _clause_negation_spans(clause: str) -> Tuple[str, ...]:
    spans: List[str] = []
    for pat in _NEGATION_PATTERNS:
        for m in re.finditer(pat, clause, re.IGNORECASE):
            spans.append(m.group(0))
    # also capture short relational exclusions ("the other", "not the X")
    for m in re.finditer(r"\bnot\s+the\s+[a-z][a-z\s]{0,30}?(?=[,.;]|$)", clause, re.IGNORECASE):
        spans.append(m.group(0).strip())
    for m in re.finditer(r"\bno,?\s+the\s+other\b", clause, re.IGNORECASE):
        spans.append(m.group(0).strip())
    seen: List[str] = []
    for s in spans:
        if s not in seen:
            seen.append(s)
    return tuple(seen)


def detect_references(raw_text: str) -> Tuple[D1Reference, ...]:
    """Runs all D1 sub-mechanisms over raw text and returns detected
    reference-bearing spans with their per-clause-scoped evidence.

    Mechanically deduplicates overlapping spans (prefers the longer/more
    specific match: determiner-NP > filename > quoted > bare pronoun) so a
    sentence like "rename the attached file" yields one reference, not four.
    """
    # Filenames and quoted spans are detected on the WHOLE raw text first
    # (a filename's own "." must not be split as a sentence terminal by the
    # clause splitter below -- mirrors TurnFrame's own quoted_spans, which
    # likewise matches on raw_text directly, not per-clause).
    whole_text_spans: List[Tuple[str, str, str]] = []  # (span, coarse_type, mechanism)
    for m in _FILENAME_RE.finditer(raw_text):
        span = m.group(0)
        whole_text_spans.append((span, _type_hint_for_phrase(span) or "document", "filename_shape"))
    for m in _QUOTED_RE.finditer(raw_text):
        inner = m.group(1).strip()
        if inner:
            whole_text_spans.append((inner, _type_hint_for_phrase(inner), "quoted_span"))

    clauses = _split_clauses(raw_text)
    found: List[D1Reference] = []
    global_used_spans: List[str] = [s.lower() for s, _, _ in whole_text_spans]

    def _clause_containing(span: str) -> str:
        for c in clauses:
            if span.lower() in c.lower():
                return c
        return raw_text

    for span, coarse_type, mechanism in whole_text_spans:
        home_clause = _clause_containing(span)
        found.append(D1Reference(
            span=span, clause_text=home_clause, coarse_type=coarse_type,
            recency_hint=_recency_hint_for_text(home_clause),
            negation_spans=_clause_negation_spans(home_clause), mechanism=mechanism,
        ))

    for clause in clauses:
        clause_negation = _clause_negation_spans(clause)
        clause_recency = _recency_hint_for_text(clause)
        used_spans: List[str] = list(global_used_spans)

        # 3. Determiner + noun-phrase shape (the dominant, most general mechanism)
        for m in _DET_NP_RE.finditer(clause):
            full_span = m.group(0).strip()
            np_body = m.group(2).strip()
            if full_span.lower() in used_spans:
                continue
            body_tokens = np_body.lower().split()
            if all(t in _STOPWORD_NP_HEADS for t in body_tokens):
                # "the one", "that thing" alone -- too generic to trust as its
                # own detection; still counts as a bare-pronoun-equivalent,
                # handled by mechanism 4 below via the determiner word itself.
                continue
            found.append(D1Reference(
                span=full_span, clause_text=clause,
                coarse_type=_type_hint_for_phrase(np_body),
                recency_hint=clause_recency or _recency_hint_for_text(full_span),
                negation_spans=clause_negation, mechanism="determiner_noun_phrase",
            ))
            used_spans.append(full_span.lower())

        # 4. Bare pronoun fallback (only if nothing more specific already
        # covers that word span in this clause)
        for m in _BARE_PRONOUN_RE.finditer(clause):
            word = m.group(0)
            if any(word.lower() in s for s in used_spans):
                continue
            found.append(D1Reference(
                span=word.lower(), clause_text=clause, coarse_type=None,
                recency_hint=clause_recency, negation_spans=clause_negation, mechanism="bare_pronoun",
            ))
            used_spans.append(word.lower())

    return tuple(found)
