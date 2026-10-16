"""Shared validation pipeline (plan §8, A1 §A3 validation rows, spike S9).

`Validator.check_output_pdf(...)` runs the O2 checks on a PDF the pipeline produced and returns a `Findings` list.
It reads PDFs only through the two workers (text: pypdf; raster: Windows.Data.Pdf), never in this process, and it
looks at page images it rendered itself. No finding carries document text.

| check                | kind        | severity | O2 rule |
|----------------------|-------------|----------|---------|
| pdf_opens            | structural  | error    | opens in pypdf, not encrypted, at least one page |
| pdf_risky_content    | structural  | error    | output contains JavaScript, launch, remote go-to, non-web links or attachments |
| placeholders         | structural  | error    | «…», {{…}}, [NAME] tokens left in an output |
| page_count           | render      | error    | PPTX: pages == slides; DOCX: pages == preview pages (same engine: consistency, not fidelity) |
| blank_page           | visual      | warning  | fewer than 20 ink pixels outside the header and footer bands (440 px image) |
| text_outside_page    | visual      | warning  | pypdf span origins left of, below or above the page box |
| edge_ink_right       | visual      | warning  | ink within 2 mm of the right edge (weak: cannot tell text from graphics) |
| font_substitution    | visual      | warning  | a font named in the source is not in the PDF |
| font_not_embedded    | visual      | warning  | a PDF font is not embedded |
| min_font_size        | visual      | warning  | text under 8 pt (documents), 10 pt (slides), 6 pt (sheets) |
| source_unchanged     | integrity   | error    | every source file's SHA-256 equals the value recorded at the start |

Repair: `repair(findings)` applies registered deterministic rules (none in O2: conversion must not change content)
and returns (changes, remaining). O3 and O5 register rules without changing the pipeline.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

from lxml import etree

from .contracts import Findings

# A page is blank when it has almost no ink at all. The first rule (coverage under 0.2 %) called a page with two short
# lines blank (live run 2026-10-15: 335 ink pixels, 0.13 % at 440 px), so the rule is an absolute count.
BLANK_MAX_INK_PIXELS = 20
EDGE_MM = 2.0
MIN_SIZE = {"docx": 8.0, "pptx": 10.0, "xlsx": 6.0, "pdf": 0.0}
THUMB_W = 160
EDGE_W = 440
INK_THRESHOLD = 240          # a channel below this counts as ink

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, load_dtd=False)
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

REPAIR_RULES: dict = {}       # check id -> callable(finding, context) -> change | None   (empty in O2)


def repair(findings: Findings, context=None, max_passes: int = 2):
    """Apply registered deterministic rules, at most `max_passes` times. Returns (changes, remaining findings)."""
    changes, remaining = [], list(findings.items)
    for _ in range(max_passes):
        still = []
        for f in remaining:
            rule = REPAIR_RULES.get(f.check)
            ch = rule(f, context) if rule else None
            (changes.append(ch) if ch else still.append(f))
        if len(still) == len(remaining):
            break
        remaining = still
    return changes, remaining


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _theme_fonts(z) -> dict:
    """Theme fonts for theme references: {"major": latin, "minor": latin, "major_cs": .., "minor_cs": ..,
    "major_ea": .., "minor_ea": .., "major_scripts": {script: name}, "minor_scripts": {...}} from the first theme
    part. Empty typefaces are left out (Word then uses the per-script font for the text's language)."""
    for n in z.namelist():
        if n.lower().endswith(".xml") and "/theme/" in n.lower():
            try:
                root = etree.fromstring(z.read(n), _PARSER)
            except etree.XMLSyntaxError:
                continue
            out = {}
            for which in ("major", "minor"):
                for tag, key in (("latin", which), ("cs", f"{which}_cs"), ("ea", f"{which}_ea")):
                    el = root.find(f".//{{{A_NS}}}{which}Font/{{{A_NS}}}{tag}")
                    if el is not None and el.get("typeface"):
                        out[key] = el.get("typeface")
                out[f"{which}_scripts"] = {el.get("script"): el.get("typeface")
                                           for el in root.findall(f".//{{{A_NS}}}{which}Font/{{{A_NS}}}font")
                                           if el.get("script") and el.get("typeface")}
            return out
    return {}


_SCRIPT_RANGES = ((0x0590, 0x05FF, "Hebr"), (0x0600, 0x06FF, "Arab"), (0x0900, 0x097F, "Deva"),
                  (0x0980, 0x09FF, "Beng"), (0x0A00, 0x0A7F, "Guru"), (0x0A80, 0x0AFF, "Gujr"), (0x0B00, 0x0B7F, "Orya"),
                  (0x0B80, 0x0BFF, "Taml"), (0x0C00, 0x0C7F, "Telu"), (0x0C80, 0x0CFF, "Knda"), (0x0D00, 0x0D7F, "Mlym"),
                  (0x0E00, 0x0E7F, "Thai"), (0x3040, 0x30FF, "Jpan"), (0x3400, 0x4DBF, "CJK"), (0x4E00, 0x9FFF, "CJK"),
                  (0xA8E0, 0xA8FF, "Deva"), (0xAC00, 0xD7AF, "Hang"), (0xF900, 0xFAFF, "CJK"), (0xFB1D, 0xFB4F, "Hebr"),
                  (0xFB50, 0xFDFF, "Arab"), (0xFE70, 0xFEFF, "Arab"), (0x20000, 0x2FA1F, "CJK"))
_EA_SCRIPTS = {"Jpan", "CJK", "Hang", "Hans"}


def _script_of(ch: str):
    o = ord(ch)
    if o < 0x0590:
        return None
    for lo, hi, sc in _SCRIPT_RANGES:
        if lo <= o <= hi:
            return sc
    return None


# Language (w:lang w:bidi / w:eastAsia, primary subtag) -> theme script code, for theme fonts whose cs or ea typeface
# is empty (review round 4 m6: Hindi text in a theme font was checked against the Latin theme font).
_LANG_SCRIPT = {"hi": "Deva", "mr": "Deva", "ne": "Deva", "sa": "Deva", "kok": "Deva", "bn": "Beng", "as": "Beng",
                "ta": "Taml", "te": "Telu", "gu": "Gujr", "pa": "Guru", "kn": "Knda", "ml": "Mlym", "or": "Orya",
                "ar": "Arab", "ur": "Arab", "fa": "Arab", "he": "Hebr", "th": "Thai", "ja": "Jpan", "zh": "Hans",
                "ko": "Hang"}


def _word_used_fonts(z) -> set:
    """Fonts a Word document actually uses: direct run fonts in the body, headers and footers, plus the fonts of the
    styles those parts use (with their basedOn chain), the default paragraph style and the document defaults. Fonts
    that only appear in unused styles or the theme are not counted (live run 2026-10-15: the letter got "Calibri was
    not available" and "Courier was not available" for fonts it never used)."""
    w = f"{{{W_NS}}}"
    theme = _theme_fonts(z)
    # Scripts the document's text actually contains (O2 real-app run r2: the language tags alone, such as python-docx's
    # default w:bidi="ar-SA", pulled in theme fonts for scripts the document never uses and gave false warnings).
    present = set()
    langs = {"cs": set(), "ea": set()}
    for n in z.namelist():
        low = n.lower()
        if not (low.startswith("word/") and low.endswith(".xml")):
            continue
        try:
            root = etree.fromstring(z.read(n), _PARSER)
        except etree.XMLSyntaxError:
            continue
        for el in root.iter(f"{w}lang"):
            for attr, key in (("bidi", "cs"), ("eastAsia", "ea")):
                v = el.get(f"{w}{attr}")
                if v:
                    langs[key].add(v.split("-")[0].lower())
        if any(k in low for k in ("document", "header", "footer", "footnotes", "endnotes")):
            for t in root.iter(f"{w}t"):
                for ch in t.text or "":
                    sc = _script_of(ch)
                    if sc:
                        present.add(sc)

    def theme_font(which: str, kind: str) -> set:
        if kind == "latin":
            return {theme[which]} if theme.get(which) else set()
        wanted = {sc for sc in present if (sc in _EA_SCRIPTS) == (kind == "ea")}
        if not wanted:
            return set()                                     # no text of that kind: its theme font is never used
        named = theme.get(f"{which}_{kind}")
        if named:
            return {named}
        scripts = theme.get(f"{which}_scripts", {})
        if "CJK" in wanted:                                   # Han characters: the language tag picks the variant
            wanted = (wanted - {"CJK"}) | {_LANG_SCRIPT[lg] for lg in langs["ea"] if lg in ("ja", "zh", "ko")}
        return {scripts[sc] for sc in wanted if sc in scripts}

    def fonts_of(rfonts) -> set:
        out = set()
        if rfonts is None:
            return out
        for a in ("ascii", "hAnsi", "cs", "eastAsia"):
            v = rfonts.get(f"{w}{a}")
            if v:
                out.add(v)
        for a, kind in (("asciiTheme", "latin"), ("hAnsiTheme", "latin"), ("eastAsiaTheme", "ea"), ("cstheme", "cs")):
            v = rfonts.get(f"{w}{a}") or ""
            if v.startswith(("major", "minor")):
                out |= theme_font(v[:5], kind)
        return out

    used_styles, names = set(), set()
    num_ids = set()                              # list fonts count only for the lists used (run r2; Codex O2-R6-03)
    for n in z.namelist():
        low = n.lower()
        if not (low.startswith("word/") and low.endswith(".xml") and
                any(k in low for k in ("document", "header", "footer", "footnotes", "endnotes"))):
            continue
        try:
            root = etree.fromstring(z.read(n), _PARSER)
        except etree.XMLSyntaxError:
            continue
        for el in root.iter(f"{w}numId"):
            if el.get(f"{w}val") not in (None, "0"):
                num_ids.add(el.get(f"{w}val"))
        for el in root.iter(f"{w}rFonts"):
            names |= fonts_of(el)
        for tag in ("pStyle", "rStyle", "tblStyle"):
            for el in root.iter(f"{w}{tag}"):
                if el.get(f"{w}val"):
                    used_styles.add(el.get(f"{w}val"))
    try:
        st = etree.fromstring(z.read("word/styles.xml"), _PARSER)
    except (KeyError, etree.XMLSyntaxError):
        return names
    by_id = {}
    for el in st.iter(f"{w}style"):
        sid = el.get(f"{w}styleId")
        if sid:
            by_id[sid] = el
            if el.get(f"{w}default") in ("1", "true") and el.get(f"{w}type") in ("paragraph", "character", "table"):
                used_styles.add(sid)
    dd = st.find(f".//{w}docDefaults//{w}rFonts")
    names |= fonts_of(dd)
    seen = set()
    todo = list(used_styles)
    while todo:
        sid = todo.pop()
        if sid in seen or sid not in by_id:
            continue
        seen.add(sid)
        el = by_id[sid]
        names |= fonts_of(el.find(f".//{w}rFonts"))
        based = el.find(f"{w}basedOn")
        if based is not None and based.get(f"{w}val"):
            todo.append(based.get(f"{w}val"))
        link = el.find(f"{w}link")
        if link is not None and link.get(f"{w}val"):
            todo.append(link.get(f"{w}val"))
        for nid in el.iter(f"{w}numId"):
            if nid.get(f"{w}val") not in (None, "0"):
                num_ids.add(nid.get(f"{w}val"))
    if num_ids:
        try:
            numbering = etree.fromstring(z.read("word/numbering.xml"), _PARSER)
        except (KeyError, etree.XMLSyntaxError):
            numbering = None
        if numbering is not None:
            abstract = {n.get(f"{w}numId"): (n.find(f"{w}abstractNumId").get(f"{w}val")
                                              if n.find(f"{w}abstractNumId") is not None else None)
                        for n in numbering.iter(f"{w}num")}
            used_abs = {abstract.get(n) for n in num_ids} - {None}
            for an in numbering.iter(f"{w}abstractNum"):
                if an.get(f"{w}abstractNumId") in used_abs:
                    for el in an.iter(f"{w}rFonts"):
                        names |= fonts_of(el)
    return names


def source_fonts(path: Path, kind: str) -> set:
    """Font family names the (sanitized) source uses. Theme references (`+mn-lt`) resolve to the theme's fonts."""
    names: set = set()
    if kind not in ("docx", "pptx"):
        return names
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return names
    with z:
        if kind == "docx":
            return {n for n in _word_used_fonts(z) if n and not n.startswith("+")}
        theme = _theme_fonts(z)
        for n in z.namelist():
            low = n.lower()
            if not low.endswith(".xml") or not low.startswith(("ppt/slides/", "ppt/slidelayouts/",
                                                                 "ppt/slidemasters/", "ppt/theme/")):
                continue
            try:
                root = etree.fromstring(z.read(n), _PARSER)
            except etree.XMLSyntaxError:
                continue
            for el in root.iter(f"{{{A_NS}}}latin", f"{{{A_NS}}}cs"):
                v = el.get("typeface")
                if v == "+mj-lt" and theme.get("major"):
                    names.add(theme["major"])
                elif v == "+mn-lt" and theme.get("minor"):
                    names.add(theme["minor"])
                elif v:
                    names.add(v)
    return {n for n in names if n and not n.startswith("+")}


def _norm_font(n: str) -> str:
    n = n.split("+", 1)[1] if len(n) > 7 and n[6] == "+" else n
    n = re.sub(r"[,-](Bold|Italic|BoldItalic|Regular|Oblique|BoldOblique)$", "", n, flags=re.I)
    return re.sub(r"[\s_-]", "", n).lower()


def ink_stats(png: Path, edge_px: int) -> tuple:
    """(coverage fraction, ink pixels in the right `edge_px` columns, body ink pixels) of a page image."""
    from PIL import Image
    with Image.open(png) as im:
        g = im.convert("L")
        w, h = g.size
        mask = g.point(lambda v: 255 if v < INK_THRESHOLD else 0)
        ink = mask.histogram()[255]
        edge_hist = mask.crop((max(0, w - edge_px), 0, w, h)).histogram()
        # Body ink leaves out the top 5 % and bottom 8 % of the page, where headers, footers and page numbers sit
        # (review round 3, m5: a page holding only a page number is still a blank page).
        body = mask.crop((0, int(h * 0.05), w, int(h * 0.92))).histogram()[255]
        return ink / float(w * h or 1), edge_hist[255], body


class Validator:
    def __init__(self, text_worker, raster_worker):
        self.text = text_worker
        self.raster = raster_worker

    def check_output_pdf(self, pdf: Path, *, kind: str, work_dir: Path, source: Path | None = None,
                         expected_pages: int | None = None, sources: dict | None = None,
                         check_placeholders: bool = True) -> tuple:
        """Returns (Findings, facts) where facts = {pages, fonts, page_sizes}. `sources` maps a source path to the
        SHA-256 recorded when the workflow started."""
        fs = Findings()
        facts: dict = {}
        info = self.text.request("info", pdf=str(pdf))
        if not info.get("ok") or info.get("encrypted") or not info.get("pages"):
            fs.add("pdf_opens", "structural", "error", "The PDF could not be read.")
            return fs, facts
        pages = info["pages"]
        facts.update(pages=pages, fonts=info.get("fonts", []), page_boxes=info.get("page_boxes", []))
        risk = self.text.request("risk", pdf=str(pdf))
        if risk.get("ok"):
            bad = sum(risk.get(k, 0) for k in ("javascript", "launch", "remote_goto", "unsafe_uri", "embedded_files"))
            if bad:
                fs.add("pdf_risky_content", "structural", "error",
                       f"The PDF contains {bad} active item(s) (scripts, launch actions or attachments).")
        if check_placeholders:
            ph = self.text.request("placeholders", pdf=str(pdf))
            for p in (ph.get("pages") or [])[:20]:
                fs.add("placeholders", "structural", "error",
                       f"{p['count']} unfilled placeholder(s) on page {p['page']}.", page=p["page"])
        if expected_pages is not None and expected_pages != pages:
            what = "slides" if kind == "pptx" else "pages"
            fs.add("page_count", "render", "error",
                   f"The PDF has {pages} pages; the source has {expected_pages} {what}.")
        # fonts
        pdf_fonts = {_norm_font(f["name"]) for f in facts["fonts"]}
        for f in facts["fonts"]:
            if not f.get("embedded"):
                fs.add("font_not_embedded", "visual", "warning", f"Font {f['name'][:60]} is not embedded.")
        if source is not None:
            for name in sorted(source_fonts(source, kind))[:50]:
                if _norm_font(name) not in pdf_fonts and not any(_norm_font(name) in p for p in pdf_fonts):
                    fs.add("font_substitution", "visual", "warning",
                           f"Font {name[:60]} was not available and another font was used.")
        # spans: outside the page box and minimum size (pypdf; S9)
        min_size = MIN_SIZE.get(kind, 0.0)
        small_pages, outside_pages = [], []
        for n in range(1, min(pages, 200) + 1):
            sp = self.text.request("spans", pdf=str(pdf), page=n)
            if not sp.get("ok"):
                continue
            x0, y0, x1, y1 = sp["box"]
            for s in sp["spans"]:
                if s["x"] < x0 - 1 or s["y"] < y0 - 1 or s["y"] > y1 + 1:
                    outside_pages.append(n)
                    break
            if min_size and any(0 < s["size"] < min_size for s in sp["spans"]):
                small_pages.append(n)
        for n in outside_pages[:20]:
            fs.add("text_outside_page", "visual", "warning", f"Text runs off page {n}.", page=n)
        if small_pages:
            fs.add("min_font_size", "visual", "warning",
                   f"Text smaller than {min_size:g} pt on {len(small_pages)} page(s), first on page {small_pages[0]}.",
                   page=small_pages[0])
        # raster checks: blank pages (thumbnails) and right-edge ink (weak)
        work_dir.mkdir(parents=True, exist_ok=True)
        rendered, failed = [], 0
        for start in range(1, pages + 1, 20):
            batch = list(range(start, min(pages, start + 19) + 1))
            try:
                r = self.raster.request("render", pdf=str(pdf), out_dir=str(work_dir), pages=batch, width=EDGE_W,
                                        timeout=60 + 3 * len(batch))
            except Exception:  # noqa: BLE001 - a worker timeout or crash becomes a finding below
                r = {"ok": False}
            if r.get("ok"):
                rendered += r["rendered"]
            else:
                failed += len(batch)
        if failed:
            fs.add("pdf_opens", "render", "error", f"{failed} page(s) of the PDF could not be drawn.")
        if rendered:
            for item in rendered:
                n = item["page"]
                box = facts["page_boxes"][n - 1] if n - 1 < len(facts["page_boxes"]) else [612, 792]
                edge_px = max(1, round(EDGE_W * (EDGE_MM / 25.4 * 72) / box[0]))
                cov, edge, ink = ink_stats(work_dir / item["file"], edge_px)
                if ink < BLANK_MAX_INK_PIXELS:
                    fs.add("blank_page", "visual", "warning", f"Page {n} is blank.", page=n)
                elif edge > 0 and kind != "pptx":
                    fs.add("edge_ink_right", "visual", "warning",
                           f"Something reaches the right edge of page {n}; check that text is not cut off.",
                           page=n, weak=True)
        # integrity of the sources
        for p, recorded in (sources or {}).items():
            try:
                same = sha256(Path(p)) == recorded
            except OSError:
                same = False
            if not same:
                fs.add("source_unchanged", "integrity", "error", "A source file changed during the task.",
                       file="source")
        return fs, facts
