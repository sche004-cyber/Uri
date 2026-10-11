"""Evaluate retrieved sources deterministically: duplicates, near-duplicates, candidate conflicts, relevance.

Nothing here calls a model. Conflicts are CANDIDATES: two sources that make the same statement (high word overlap)
with different numbers or dates. They are shown with both citations; URI does not decide which source is right.
"""
from __future__ import annotations

import re
from decimal import Decimal
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = re.compile(r"^(utm_[a-z]+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|ref|ref_src|igshid|spm)$", re.I)
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
# Only a preceding digit stops a match: "Rs.500", "approx.900" and "No.5" carry numbers too (R1-01).
# A magnitude or unit is part of the number (R4-02): letters written against it ("$5m", "$5bn", "5k", "5km") and a
# scale or unit word after one space ("5 million", "2 lakh", "500 crore", "5 miles"). Scales are multiplied out, so
# "$5m", "$5 million" and "$5,000,000" are one number and "$5m" vs "$5bn" are two.
# Every numeral is read WHOLE or not at all (R5-01): the match takes the full run of digits joined by "," or "." (and
# by a space / NBSP / thin space before a 3-digit group), with its sign ("-", U+2212 or "minus"). _read() accepts
# western (1,234,567), Indian (5,00,00,000) and space (1 000 000) grouping; any other comma run is UNREADABLE and is
# never split into fragments that could pass a subset test.
_NUMBER = re.compile(r"(?:(?<![\w.,\-\u2212])(?P<sign>[-\u2212])|(?<![\w-])(?P<minus>minus)\s+)?"
                     r"(?<!\d)(?P<num>\d+(?:(?:[,.]|[ \u00a0\u2009\u202f](?=\d{3}(?!\d)))\d+)*)"
                     r"(?P<suf>\s?%|[A-Za-z]+\b|\s(?:percent|thousands?|millions?|billions?|trillions?|lakhs?|lacs?|crores?|"
                     r"mn|bn|tn|cr|km|kms|kilomet(?:re|er)s?|miles?|mi|kgs?|kilograms?|grams?|tonnes?|tons?|lbs?|"
                     r"pounds?|feet|ft|metres?|meters?|cm|mm|acres?|hectares?|litres?|liters?|gallons?|mph)\b)?", re.I)
_GROUPED = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?")   # western | Indian
_SPACED = re.compile(r"\d{1,3}(?:[ \u00a0\u2009\u202f]\d{3})+(?:\.\d+)?")
_PLAIN = re.compile(r"\d+(?:\.\d+)?")
UNREADABLE = "?"   # prefix of a numeral that could not be read whole; such a value never supports a claim
_SCALE = {"k": 3, "thousand": 3, "m": 6, "mn": 6, "mio": 6, "million": 6, "b": 9, "bn": 9, "billion": 9,
          "t": 12, "tn": 12, "trillion": 12, "lakh": 5, "lac": 5, "crore": 7, "cr": 7}
_UNIT = {"percent": "%", "kms": "km", "kgs": "kg", "lbs": "lb", "kilometre": "km", "kilometer": "km", "mile": "mi", "kg": "kg",
         "kilogram": "kg", "gram": "g", "tonne": "t-mass", "ton": "t-mass", "lb": "lb", "pound": "lb", "foot": "ft",
         "feet": "ft", "metre": "metre", "meter": "metre", "liter": "litre"}
_ORDINAL = {"st", "nd", "rd", "th"}
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
STOP = frozenset("""the and for are was were has have had that this with from which their there been being into than
then them they its also but not can may will would could should about after before over under more most such
other some any each per via into onto upon while where when what who whom whose how why our your his her she him
""".split())
CONFLICT_OVERLAP = 0.5
NEAR_DUP = 0.8


def normalise_url(url: str) -> str:
    try:
        p = urlsplit(url)
    except ValueError:
        return url
    host = (p.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    port = p.port
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    q = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not _TRACKING.match(k))
    path = re.sub(r"/+$", "", p.path) or "/"
    return urlunsplit(((p.scheme or "https").lower(), netloc, path, urlencode(q), ""))


def sentences(text: str, limit: int = 400) -> list:
    out = []
    for block in (text or "").split("\n"):
        for s in _SENT.split(block.strip()):
            s = s.strip()
            if 20 <= len(s) <= 600:
                out.append(s)
                if len(out) >= limit:
                    return out
    return out


def content_words(s: str) -> set:
    return {w.lower() for w in _WORD.findall(s) if w.lower() not in STOP}


def _read(span: str) -> list:
    """Whole values in one numeral span: a canonical digit string (separators removed), a dotted literal such as a
    date or version ("11.10.2026", kept exactly), or UNREADABLE + span. Never a fragment of a grouped numeral."""
    if _PLAIN.fullmatch(span) or _GROUPED.fullmatch(span) or _SPACED.fullmatch(span):
        return [re.sub(r"[, \u00a0\u2009\u202f]", "", span)]
    if re.fullmatch(r"\d+(?:\.\d+)+", span):
        return [span]
    if re.search(r"[ \u00a0\u2009\u202f]", span):   # "2020 100": a space joined two separate numbers
        return [v for part in re.split(r"[ \u00a0\u2009\u202f]", span) for v in _read(part)]
    return [UNREADABLE + span]


def unreadable(nums) -> bool:
    return any(n.startswith(UNREADABLE) for n in nums)


def numbers(s: str) -> set:
    out = set()
    for m in _NUMBER.finditer(s):
        vals = _read(m.group("num"))
        neg = bool(m.group("sign") or m.group("minus"))
        raw = (m.group("suf") or "").strip().lower()
        unit = raw[:-1] if len(raw) > 3 and raw.endswith("s") and raw[:-1] in _SCALE.keys() | _UNIT.keys() else raw
        for i, n in enumerate(vals):
            last = i == len(vals) - 1          # a sign belongs to the first value, a unit to the last
            sign = "-" if neg and i == 0 else ""
            if n.startswith(UNREADABLE):
                out.add(UNREADABLE + sign + n[1:])
            elif not last or unit in ("", *_ORDINAL):
                out.add(sign + n)
            elif unit in _SCALE and n.count(".") <= 1:
                out.add(sign + _fmt(Decimal(n).scaleb(_SCALE[unit])))
            else:
                out.add(sign + n + _UNIT.get(unit, unit))
    return out


def _fmt(n: Decimal) -> str:
    t = format(n.normalize(), "f")
    return t.rstrip("0").rstrip(".") if "." in t else t


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'.,%-]*")


def shingles(text: str, k: int = 5) -> set:
    # Numbers are part of the shingles: two pages that differ only in a figure are NOT near-duplicates.
    w = [x.lower().rstrip(".,") for x in _TOKEN.findall(text or "")]
    return {" ".join(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


@dataclass
class Conflict:
    source_a: int
    source_b: int
    statement_a: str
    statement_b: str
    values_a: list
    values_b: list
    overlap: float


@dataclass
class Evaluation:
    kept: list = field(default_factory=list)            # source indices kept, in order
    duplicates: dict = field(default_factory=dict)      # index -> index of the source it duplicates
    near_duplicates: dict = field(default_factory=dict)
    conflicts: list = field(default_factory=list)
    relevance: dict = field(default_factory=dict)       # index -> score in [0, 1]


def evaluate(sources: list, query: str) -> Evaluation:
    """`sources`: list of dicts with keys `url`, `text`, `sha256` (optional). Indices are positions in the list."""
    ev = Evaluation()
    by_url, by_hash, sh = {}, {}, {}
    for i, s in enumerate(sources):
        nu = normalise_url(s.get("url") or "")
        h = s.get("sha256")
        if nu in by_url:
            ev.duplicates[i] = by_url[nu]
            continue
        if h and h in by_hash:
            ev.duplicates[i] = by_hash[h]
            continue
        by_url[nu] = i
        if h:
            by_hash[h] = i
        sh[i] = shingles(s.get("text") or "")
        for j in ev.kept:
            if sh[i] and sh[j] and jaccard(sh[i], sh[j]) >= NEAR_DUP:
                ev.near_duplicates[i] = j
                break
        ev.kept.append(i)
    q = content_words(query)
    for i in ev.kept:
        words = content_words(sources[i].get("text") or "")
        ev.relevance[i] = round(len(q & words) / len(q), 3) if q else 0.0
    # Near-duplicates are still compared: a copy that changed one figure is exactly the disagreement to show.
    ev.conflicts = find_conflicts(sources, list(ev.kept))
    return ev


def find_conflicts(sources: list, indices: list, max_conflicts: int = 20) -> list:
    sents = {i: [(s, content_words(s), numbers(s)) for s in sentences(sources[i].get("text") or "")] for i in indices}
    found, seen = [], set()
    for x, a in enumerate(indices):
        for b in indices[x + 1:]:
            for sa, wa, na in sents[a]:
                if not na:
                    continue
                for sb, wb, nb in sents[b]:
                    # Subset suppression only between numbers read whole: an UNREADABLE numeral rules nothing out.
                    if not nb or na == nb or (not unreadable(na | nb) and (na <= nb or nb <= na)):
                        continue
                    ov = jaccard(wa, wb)
                    if ov >= CONFLICT_OVERLAP:
                        key = (a, b, frozenset(na), frozenset(nb))
                        if key in seen:
                            continue
                        seen.add(key)
                        found.append(Conflict(a, b, sa, sb, sorted(na), sorted(nb), round(ov, 3)))
                        if len(found) >= max_conflicts:
                            return found
    return found
