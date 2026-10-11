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
    # R7-01: a split never cuts a link in two ('at refunds-portal . Com/claim'): pieces a link runs across are joined
    # again, so the link checks downstream see the whole link, not two link-free halves.
    from .untrusted import merge_split_links   # local import: untrusted imports this module
    out = []
    for block in (text or "").split("\n"):
        for s in merge_split_links([p.strip() for p in _SENT.split(block.strip())]):
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


def _values(m, signed: bool = True, suf: str = None) -> list:
    """The values of one _NUMBER match. `signed=False` when its "-" is a separator ("5%-10%"); `suf` lends the unit or
    scale of a range's upper end to its bare lower end ("$5-10 million", "10-20%")."""
    out = []
    vals = _read(m.group("num"))
    neg = signed and bool(m.group("sign") or m.group("minus"))
    raw = ((m.group("suf") if suf is None else suf) or "").strip().lower()
    unit = raw[:-1] if len(raw) > 3 and raw.endswith("s") and raw[:-1] in _SCALE.keys() | _UNIT.keys() else raw
    for i, n in enumerate(vals):
        last = i == len(vals) - 1          # a sign belongs to the first value, a unit to the last
        sign = "-" if neg and i == 0 else ""
        if n.startswith(UNREADABLE):
            out.append(UNREADABLE + sign + n[1:])
        elif not last or unit in ("", *_ORDINAL):
            out.append(sign + n)
        elif unit in _SCALE and n.count(".") <= 1:
            out.append(sign + _fmt(Decimal(n).scaleb(_SCALE[unit])))
        else:
            out.append(sign + n + _UNIT.get(unit, unit))
    return out


# Compound numerals (R6-01). A value written as several digit groups is ONE ordered value, never a set of fragments:
# "2026-11-10" and "2026-10-11", "11/10/2026" and "10/11/2026", "3:1" and "1:3", "10-20" and "20-10", "from 100 to
# 200" and "from 200 to 100" are different values. Groups joined by "-", "/", ":" or a dash with no space, or by
# " - ", an en/em dash or " to " (a range), form one token in written order; the separator is normalised, never sorted.
_TIGHT = re.compile(r"[-‐‑–—/:]")
_RANGE_GAP = re.compile(r"(?:\s*[–—]\s*|\s+-\s+|\s+to\s+|-)[$€£₹¥]?", re.I)   # also "$5 to $10", "$5-$10"
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
_MON = (r"(?P<mon>January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\b\.?")
_DMY_WORDS = re.compile(r"(?<![\w.,])(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MON +
                        r"(?:,?\s+(?P<y>\d{4})(?![\d,.]\d))?")
_MDY_WORDS = re.compile(r"(?<!\w)" + _MON + r"\s+(?:(?P<d>\d{1,2})(?:st|nd|rd|th)?(?![\d,.]?\d)"
                        r"(?:,?\s+(?P<y>\d{4})(?![\d,.]\d))?|(?P<y2>\d{4})(?![\d,.]\d))")


def _month(name: str) -> int:
    return next(i for i, full in enumerate(_MONTHS, 1) if full.startswith(name[:3]))


def _date_tokens(y, mo, d) -> list:
    """A calendar date as canonical tokens: the full date, its month-day and its year (so "in 2026" and "on 10
    November" are supported by "10 November 2026"), never the bare day or month number."""
    if d is not None and not 1 <= int(d) <= 31 or not 1 <= mo <= 12:
        return []
    if d is None:
        return [f"{y}-{mo:02d}", y]
    md = f"--{mo:02d}-{int(d):02d}"
    return [f"{y}-{md[2:]}", md, y] if y else [md]


def _named_dates(s: str):
    out = []

    def sub(m):
        d, y = m.group("d"), m.group("y") or (m.groupdict().get("y2"))
        toks = _date_tokens(y, _month(m.group("mon")), d)
        if not toks:
            return m.group(0)
        out.extend(toks)
        return " " * len(m.group(0))
    s = _DMY_WORDS.sub(sub, s)
    return out, _MDY_WORDS.sub(sub, s)


def _compound(parts: list, seps: list) -> list:
    """One token for a chain of whole values in written order (plus a calendar date's year and month-day, and a
    two-value range's endpoints, which the chain does state)."""
    if any(p.startswith(UNREADABLE) for p in parts):
        return [UNREADABLE + "".join(p.lstrip(UNREADABLE) + s for p, s in zip(parts, seps + [""]))]
    if len(parts) == 3 and seps[0] == seps[1] and seps[0] in "-/" and all(p.isdigit() for p in parts):
        a, b, c = parts
        if len(a) == 4 and len(b) <= 2 and len(c) <= 2:                      # ISO / Y-M-D
            toks = _date_tokens(a, int(b), c)
            if toks:
                return toks
        if len(a) <= 2 and len(b) <= 2 and len(c) in (2, 4):                  # D/M/Y or M/D/Y: written order kept
            return [f"{int(a):02d}/{int(b):02d}/{c}"] + ([c] if len(c) == 4 else [])
    token = "".join(p + s for p, s in zip(parts, seps + [""]))
    return [token] + (parts if len(parts) == 2 and seps[0] == "-" else [])


def numbers(s: str) -> set:
    out, s = _named_dates(s)
    out = set(out)
    ms = list(_NUMBER.finditer(s))
    i = 0
    while i < len(ms):
        chain, seps, signed, j = [ms[i]], [], [True], i
        while j + 1 < len(ms):
            gap, nxt = s[ms[j].end():ms[j + 1].start()], ms[j + 1]
            sep_sign = gap == "" and bool(nxt.group("sign"))   # "5%-10%": the "-" was read as a sign
            if sep_sign:
                seps.append("-")
            elif _TIGHT.fullmatch(gap):
                seps.append({"/": "/", ":": ":"}.get(gap, "-"))
            elif _RANGE_GAP.fullmatch(gap):
                seps.append("-")
            else:
                break
            signed.append(not sep_sign)
            chain.append(nxt)
            j += 1
        if len(chain) == 1:
            out.update(_values(ms[i]))
        else:
            vals = [_values(m, signed=sg) for m, sg in zip(chain, signed)]
            if all(len(v) == 1 for v in vals):
                if len(chain) == 2 and seps[0] == "-" and not chain[0].group("suf") and chain[1].group("suf"):
                    vals[0] = _values(chain[0], suf=chain[1].group("suf"))
                out.update(_compound([v[0] for v in vals], seps))
            else:                                         # "2020 100-200": read each numeral on its own
                out.update(v for vs in vals for v in vs)
        i = j + 1
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
    # A conflict statement is shown verbatim on the research surface, so it obeys the answer's rules (R6-03): an
    # instruction-like sentence or one carrying a link / e-mail / IP is never a statement.
    from .untrusted import flags, has_link_or_contact   # local import: untrusted imports this module
    sents = {i: [(s, content_words(s), numbers(s)) for s in sentences(sources[i].get("text") or "")
                 if not flags(s) and not has_link_or_contact(s)] for i in indices}
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
