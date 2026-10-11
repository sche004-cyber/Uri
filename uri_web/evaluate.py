"""Evaluate retrieved sources deterministically: duplicates, near-duplicates, candidate conflicts, relevance.

Nothing here calls a model. Conflicts are CANDIDATES: two sources that make the same statement (high word overlap)
with different numbers or dates. They are shown with both citations; URI does not decide which source is right.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = re.compile(r"^(utm_[a-z]+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|ref|ref_src|igshid|spm)$", re.I)
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
# Only a preceding digit stops a match: "Rs.500", "approx.900" and "No.5" carry numbers too (R1-01).
_NUMBER = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(\s?%|\s?(?:percent|million|billion|thousand))?", re.I)
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


def numbers(s: str) -> set:
    out = set()
    for m in _NUMBER.finditer(s):
        n = m.group(1).replace(",", "")
        unit = (m.group(2) or "").strip().lower().replace("percent", "%")
        out.add(n + unit)
    return out


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
                    if not nb or na == nb or na <= nb or nb <= na:
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
