"""Render a ResearchResult through the existing A2UI catalog (`uri:a2ui/catalog/v1`), read-only.

No catalog change, no new action: the surface uses Column / Card / Text / Badge / Divider / Button and the existing
presentation action `surface.dismiss`. The catalog refuses URLs anywhere, so a citation shows the source as
`host/path` text with its retrieval and publication dates; nothing in the surface is a link. All text is cleaned of
URL and script schemes before it enters the surface; in web-derived text, links, e-mail and IP addresses are masked
whole and an instruction-like title or conflict statement is not shown (R6-03).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from uri_a2ui.surface import Surface

from . import pipeline as P
from . import untrusted as U

KIND = "web.research_result"
_SCHEME = re.compile(r"(?i)\b(?:https?|ftp|file)://")
_SCRIPTISH = re.compile(r"(?i)\b(javascript|vbscript|data):")
# Links, e-mail addresses and IP addresses in web-derived text are masked whole (R6-03): the surface carries no
# address a user could follow or contact, whichever field the text arrived in.
_LINK = re.compile(r"(?i)\b(?:https?|ftp|file)://\S*|\bwww\.\S+|[\w.+-]+@[\w-]+\.[\w.-]+|\b\d{1,3}(?:\.\d{1,3}){3}\b|"
                   r"\b(?:javascript|vbscript):\S*|\bdata:[a-z]+/\S*")
LINK_MASK = "[link removed]"
HIDDEN_TITLE = "(title hidden: instruction-like text)"
MAX_TEXT = 1200
STATUS_TONE = {P.COMPLETED_WITH_RESULT: "success", P.NO_RESULT: "warning", P.PROVIDER_UNAVAILABLE: "warning",
               P.CANCELLED: "neutral", P.TIMED_OUT: "warning", P.FAILED: "danger"}
STATUS_LABEL = {P.COMPLETED_WITH_RESULT: "Answer with sources", P.NO_RESULT: "No answer found",
                P.PROVIDER_UNAVAILABLE: "Search unavailable", P.CANCELLED: "Cancelled", P.TIMED_OUT: "Timed out",
                P.FAILED: "Failed"}


def _mask_link(m) -> str:
    tail = re.search(r"[.,;:!?)\]'\"]+$", m.group(0))
    return LINK_MASK + (tail.group(0) if tail else "")


def clean(s, limit=MAX_TEXT, links=True) -> str:
    s = _LINK.sub(_mask_link, str(s or "")) if links else str(s or "")
    s = _SCHEME.sub("", s)
    s = _SCRIPTISH.sub(lambda m: m.group(1) + " :", s)
    s = "".join(ch for ch in s if ch in "\n\t" or (ord(ch) >= 32 and not 0xD800 <= ord(ch) <= 0xDFFF))
    return s[:limit]


def cite_label(url: str) -> str:
    try:
        p = urlsplit(url)
        return clean((p.hostname or "") + (p.path if p.path not in ("", "/") else ""), 120, links=False)
    except ValueError:
        return "source"


def build_surface(result: dict) -> Surface:
    comps, order = [], []

    def add(c):
        comps.append(c)
        return c["id"]

    def text(cid, value, variant="body", links=True):
        return add({"id": cid, "component": "Text", "text": clean(value, links=links), "variant": variant})

    status = result.get("status", P.FAILED)
    head = [text("h_title", "Research: " + (result.get("query") or "(no query)"), "title"),
            add({"id": "h_status", "component": "Badge", "text": STATUS_LABEL.get(status, status),
                 "tone": STATUS_TONE.get(status, "neutral")}),
            text("h_meta", f"{len(result.get('sources') or [])} sources · synthesis: {result.get('synthesis_method')}"
                           f" · {result.get('elapsed_s', 0)} s · sentences with numbers, dates or amounts are quoted word for word from"
                           f" their source; other sentences are checked against one cited sentence (wording, negation);"
                           f" web content is untrusted evidence", "caption")]
    add({"id": "h_col", "component": "Column", "children": head, "gap": "small"})
    order.append(add({"id": "h_card", "component": "Card", "child": "h_col", "tone": "neutral"}))

    answer = result.get("answer") or []
    if answer:
        ids = [text(f"a{i}", (f"\u201c{c['text']}\u201d " if c.get("quoted") else f"{c['text']} ")
                    + "".join(f"[{n}]" for n in c["citations"])) for i, c in
               enumerate(answer[:8])]
        add({"id": "a_col", "component": "Column", "children": [text("a_t", "Answer", "label"), *ids], "gap": "small"})
        order.append(add({"id": "a_card", "component": "Card", "child": "a_col", "tone": "accent"}))

    # Defence in depth: a pair whose statement is instruction-like is not shown (evaluate already skips them).
    conflicts = [c for c in result.get("conflicts") or []
                 if not U.flags(c.get("statement_a")) and not U.flags(c.get("statement_b"))]
    if conflicts:
        ids = []
        for i, c in enumerate(conflicts[:3]):
            ids.append(text(f"c{i}a", f"[{c['a']}] {c['statement_a']}"))
            ids.append(text(f"c{i}b", f"[{c['b']}] {c['statement_b']}"))
        add({"id": "c_col", "component": "Column",
             "children": [text("c_t", "Sources disagree (both shown; URI does not pick one)", "label"), *ids],
             "gap": "small"})
        order.append(add({"id": "c_card", "component": "Card", "child": "c_col", "tone": "warning"}))

    sources = result.get("sources") or []
    if sources:
        ids = []
        for s in sources[:10]:
            rec = s.get("record") or {}
            title = s.get("title") or ""
            # Each web-derived part is masked here; the line is joined with the host/path label, which is kept.
            bits = [f"[{s['number']}] " + clean(HIDDEN_TITLE if U.flags(title) else title, 300),
                    cite_label(s.get("url") or ""), "retrieved " + clean(rec.get("retrieved_at") or "?", 80)]
            if rec.get("published_at"):
                bits.append("published " + clean(rec["published_at"], 80))
            if s.get("analysed_scope") != "full_text":
                bits.append(s.get("analysed_scope"))
            if s.get("near_duplicate_of"):
                bits.append(f"near-duplicate of [{s['near_duplicate_of']}]")
            if s.get("injection_flags"):
                bits.append("contains instruction-like text (ignored)")
            ids.append(text(f"s{s['number']}", " · ".join(clean(b, links=False) for b in bits if b), "caption",
                            links=False))
        add({"id": "s_col", "component": "Column", "children": [text("s_t", "Sources", "label"), *ids], "gap": "small"})
        order.append(add({"id": "s_card", "component": "Card", "child": "s_col", "tone": "neutral"}))

    unavailable = [p for p in result.get("providers") or [] if p.get("status") not in ("OK", "NO_RESULTS")]
    if unavailable or result.get("dropped_claims"):
        notes = [f"{p['provider']}: {p['status']} ({p.get('error_code') or '-'})" for p in unavailable]
        if result.get("dropped_claims"):
            notes.append(f"{len(result['dropped_claims'])} unsupported sentence(s) removed by citation check")
        ids = [text(f"n{i}", n, "caption") for i, n in enumerate(notes[:6])]
        add({"id": "n_col", "component": "Column", "children": ids, "gap": "none"})
        order.append(add({"id": "n_card", "component": "Card", "child": "n_col", "tone": "neutral"}))

    order.append(add({"id": "dismiss", "component": "Button", "label": "Close",
                      "action": {"event": {"name": "surface.dismiss", "context": {}}}, "variant": "secondary"}))
    add({"id": "root", "component": "Column", "children": order, "gap": "medium"})
    # The root must be first for renderers that take components[0] as the root.
    comps.insert(0, comps.pop())
    return Surface(surface_id="web.research." + result.get("job_id", "x")[:36], kind=KIND, components=comps,
                   data={}, bound={"research": {"job_id": result.get("job_id"), "status": status}},
                   actions=("surface.dismiss",), placement="workspace", title="Research")
