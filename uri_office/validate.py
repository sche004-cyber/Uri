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
| blank_page           | visual      | warning  | ink coverage under 0.2 % on a page |
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

BLANK_COVERAGE = 0.002
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


def source_fonts(path: Path, kind: str) -> set:
    """Font family names the (sanitized) source asks for. Theme references (`+mn-lt`) resolve to the theme's fonts."""
    names: set = set()
    if kind not in ("docx", "pptx"):
        return names
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return names
    with z:
        for n in z.namelist():
            low = n.lower()
            if not low.endswith(".xml"):
                continue
            if kind == "docx" and not (low.startswith("word/") and ("document" in low or "styles" in low
                                                                     or "theme" in low or "header" in low
                                                                     or "footer" in low)):
                continue
            if kind == "pptx" and not low.startswith(("ppt/slides/", "ppt/slidelayouts/", "ppt/slidemasters/",
                                                      "ppt/theme/")):
                continue
            try:
                root = etree.fromstring(z.read(n), _PARSER)
            except etree.XMLSyntaxError:
                continue
            for el in root.iter(f"{{{W_NS}}}rFonts"):
                for a in ("ascii", "hAnsi", "cs"):
                    v = el.get(f"{{{W_NS}}}{a}")
                    if v:
                        names.add(v)
            for el in root.iter(f"{{{A_NS}}}latin", f"{{{A_NS}}}cs"):
                v = el.get("typeface")
                if v:
                    names.add(v)
    return {n for n in names if n and not n.startswith("+")}


def _norm_font(n: str) -> str:
    n = n.split("+", 1)[1] if len(n) > 7 and n[6] == "+" else n
    n = re.sub(r"[,-](Bold|Italic|BoldItalic|Regular|Oblique|BoldOblique)$", "", n, flags=re.I)
    return re.sub(r"[\s_-]", "", n).lower()


def ink_stats(png: Path, edge_px: int) -> tuple:
    """(coverage fraction, ink pixels in the right `edge_px` columns) of a page image."""
    from PIL import Image
    with Image.open(png) as im:
        g = im.convert("L")
        w, h = g.size
        mask = g.point(lambda v: 255 if v < INK_THRESHOLD else 0)
        ink = mask.histogram()[255]
        edge_hist = mask.crop((max(0, w - edge_px), 0, w, h)).histogram()
        return ink / float(w * h or 1), edge_hist[255]


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
        r = self.raster.request("render", pdf=str(pdf), out_dir=str(work_dir), pages=list(range(1, pages + 1)),
                                width=EDGE_W, timeout=120)
        if r.get("ok"):
            for item in r["rendered"]:
                n = item["page"]
                box = facts["page_boxes"][n - 1] if n - 1 < len(facts["page_boxes"]) else [612, 792]
                edge_px = max(1, round(EDGE_W * (EDGE_MM / 25.4 * 72) / box[0]))
                cov, edge = ink_stats(work_dir / item["file"], edge_px)
                if cov < BLANK_COVERAGE:
                    fs.add("blank_page", "visual", "warning", f"Page {n} is blank.", page=n)
                elif edge > 0 and kind != "pptx":
                    fs.add("edge_ink_right", "visual", "warning",
                           f"Something reaches the right edge of page {n}; check that text is not cut off.",
                           page=n, weak=True)
        else:
            fs.add("pdf_opens", "render", "error", "The PDF pages could not be drawn.")
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
