"""Pixel check for page text (owner decision D10, 2026-10-11).

A piece of page text (a page text segment, a selected segment or part of a heading) is sent to the Brain only if an
in-memory screenshot of the tab, taken at observation time under the same OBSERVE grant, shows something drawn inside
the piece's own viewport rectangles. Anything that cannot be checked is dropped (fail closed, as D8): no or invalid
screenshot, a screenshot whose size does not match the viewport, no rectangles, rectangles (partly) outside the
viewport, or more rectangles than the page reported. The screenshot is used only here and is never sent anywhere.

"Something drawn" is measured as glyph edges: horizontally adjacent pixel pairs inside the rectangle whose colours
differ by at least EDGE_DELTA in some channel. Text strokes produce many such edges per character; a flat area, a
smooth gradient, a blur, or a colour band that only partly covers the rectangle produce almost none. A piece is kept
only when
  * every rectangle at least MIN_RECT_W px wide has an edge density (edges per pixel, normalised for the device pixel
    ratio) of at least MIN_EDGE_DENSITY, and
  * the piece's edges reach EDGES_PER_CHAR x (non-space characters) x (mean line height in CSS px), so a few visible
    glyphs cannot carry a long piece whose other characters are not drawn.
The thresholds were set from headless Chromium renderings at device pixel ratio 1 (16 px and 11 px serif, grey #777,
half opacity, bold 32 px headings, SVG text, with and without a selection highlight): drawn text measured edge
densities of 0.16-0.31 and 1.5-3.0 edges per character per px of line height; hidden text (negative z-index, SVG
fill none/transparent/fill-opacity 0, mask, blur, overlays) measured densities of 0-0.006 and at most 0.06 edges per
character per px. MIN_EDGE_DENSITY leaves a margin of about five on both sides; EDGES_PER_CHAR about three below the
faintest drawn text, so one drawn glyph can vouch for at most a few undrawn characters.

What this does not prove (see docs/assist/03_PERMISSION_AND_DATA_FLOW.md): hidden text whose rectangle overlaps other
visible ink (text, borders, a busy image) passes; text the browser itself repaints because it is selected (the
selection highlight forces its own colours) is visible on screen and passes the pixel check - colour-hidden selected
text is removed only by the in-page colour rule; the page can change between the DOM snapshot and the screenshot.
"""
from __future__ import annotations

import io
import math
from collections import Counter
from typing import Optional

EDGE_DELTA = 40             # a pixel pair is an edge when some channel differs by at least this (0-255)
MIN_EDGE_DENSITY = 0.03     # minimum edges per pixel in each rectangle (x device pixel ratio)
EDGES_PER_CHAR = 0.5        # minimum edges per non-space character per CSS px of line height (x device pixel ratio)
MIN_RECT_W = 4              # rectangles narrower than this (CSS px; a space) carry no requirement of their own
EDGE_TOLERANCE = 2          # CSS px a rectangle may overhang the viewport (glyph overhang, rounding)
SIZE_TOLERANCE = 2          # device px the screenshot may differ from viewport x device pixel ratio
MAX_RECTS = 8               # the page sends at most this many rectangles per piece
MAX_PIXELS = 40_000_000     # decompression bomb guard (same as vision.py)

UNVERIFIED, NO_INK = "offscreen_or_unverified", "no_ink"


class Screen:
    """One decoded viewport screenshot with its geometry. Built only by load()."""

    def __init__(self, img, vw: float, vh: float, dpr: float):
        self.img, self.vw, self.vh, self.dpr = img, vw, vh, dpr

    def _edges(self, box) -> int:
        from PIL import ImageChops
        x0, y0, x1, y1 = box
        if x1 - x0 < 2 or y1 - y0 < 1:
            return 0
        a = self.img.crop((x0, y0, x1 - 1, y1))
        b = self.img.crop((x0 + 1, y0, x1, y1))
        r, g, bl = ImageChops.difference(a, b).split()
        m = ImageChops.lighter(ImageChops.lighter(r, g), bl)
        return sum(m.histogram()[EDGE_DELTA:])

    def check(self, piece: dict) -> Optional[str]:
        """None when the piece is drawn on screen, else the reason it is dropped."""
        text = piece.get("t") or ""
        chars = sum(1 for ch in text if not ch.isspace())
        if chars == 0:
            return None                                # whitespace carries nothing to verify
        rects = piece.get("r") or []
        if not rects or piece.get("c", len(rects)) > len(rects) or len(rects) > MAX_RECTS:
            return UNVERIFIED
        d, total, heights = self.dpr, 0, []
        for x, y, w, h in rects:
            if w <= 0 or h <= 0:
                continue
            if x < -EDGE_TOLERANCE or y < -EDGE_TOLERANCE or x + w > self.vw + EDGE_TOLERANCE \
                    or y + h > self.vh + EDGE_TOLERANCE:
                return UNVERIFIED                      # (partly) outside the viewport: cannot be checked
            l, t = max(0.0, x), max(0.0, y)
            r, b = min(self.vw, x + w), min(self.vh, y + h)
            box = (max(0, math.floor(l * d)), max(0, math.floor(t * d)),
                   min(self.img.width, math.ceil(r * d)), min(self.img.height, math.ceil(b * d)))
            area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
            e = self._edges(box)
            if w >= MIN_RECT_W and e * d / area < MIN_EDGE_DENSITY:
                return NO_INK
            total += e
            heights.append(h)
        if not heights:
            return UNVERIFIED
        if total / d < EDGES_PER_CHAR * chars * (sum(heights) / len(heights)):
            return NO_INK
        return None


def load(png, viewport, dpr) -> Optional[Screen]:
    """Decode the screenshot and check it is the viewport the rectangles refer to; None when it cannot be used."""
    if not isinstance(png, (bytes, bytearray)) or not png or not isinstance(viewport, dict):
        return None
    vw, vh = viewport.get("w"), viewport.get("h")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 100_000 for v in (vw, vh)):
        return None
    if not isinstance(dpr, (int, float)) or isinstance(dpr, bool) or not 0.25 <= dpr <= 8:
        return None
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(png))           # header only
        if img.width * img.height > MAX_PIXELS:
            return None
        img.load()
    except Exception:
        return None
    if abs(img.width - vw * dpr) > SIZE_TOLERANCE or abs(img.height - vh * dpr) > SIZE_TOLERANCE:
        return None                                   # not this viewport (or scaled): cannot be trusted
    return Screen(img.convert("RGB"), float(vw), float(vh), float(dpr))


def _piece(p) -> Optional[dict]:
    if not isinstance(p, dict) or not isinstance(p.get("t"), str):
        return None
    rects = []
    raw = p.get("r") if isinstance(p.get("r"), list) else []
    for r in raw[:MAX_RECTS + 1]:
        if isinstance(r, (list, tuple)) and len(r) == 4 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in r):
            rects.append([float(v) for v in r])
        else:
            return {"t": p["t"][:4000], "r": [], "c": 1, "g": 0}     # malformed rectangle: unverifiable
    c = p.get("c")
    c = int(c) if isinstance(c, int) and not isinstance(c, bool) and c >= 0 else len(raw)
    g = p.get("g") if isinstance(p.get("g"), int) and not isinstance(p.get("g"), bool) else 0
    return {"t": p["t"][:4000], "r": rects, "c": max(c, len(raw)), "g": g}


def keep(pieces, screen: Optional[Screen], counts: Counter, limit: int) -> list:
    """The pieces drawn on screen, in order (at most `limit` are examined). Dropped ones are counted by reason."""
    out = []
    for p in (pieces if isinstance(pieces, list) else [])[:limit]:
        q = _piece(p)
        if q is None:
            continue
        why = UNVERIFIED if screen is None else screen.check(q)
        if why is None:
            out.append(q)
        else:
            counts[why] += 1
    return out


def join(pieces: list, sep: str) -> str:
    """Join kept pieces: segments of one group directly, groups with `sep`; whitespace collapsed."""
    parts, prev = [], None
    for p in pieces:
        if prev is not None and p["g"] != prev:
            parts.append(sep)
        parts.append(p["t"])
        prev = p["g"]
    text = "".join(parts)
    if sep == "\n":
        return "\n".join(" ".join(line.split()) for line in text.split("\n") if line.strip())
    return " ".join(text.split())
