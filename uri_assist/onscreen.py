"""Render check for page text (owner decision D10; R13-01 differential render, 2026-10-11).

A piece of page text (a page text segment, a selected segment or part of a heading) is sent to the Brain only if
every text unit it was built from drew its OWN glyphs, visibly, inside its own viewport rectangles. A unit is one
range of one text node (snapshot.js). Right after the DOM snapshot, under the same OBSERVE grant, the adapter runs
probe.js and takes in-memory screenshots of the tab: `base` (the page as it is, the user's selection removed for the
probe), for each probe group k `clear` (only group k's ranges repainted transparent with a CSS Custom Highlight),
`tint` and `tint2` (only group k's ranges repainted in the probe colours of two independent random palettes), and
`base2` (the page as it is again). For a pixel inside a unit's rectangles:
  * unstable: base and base2 differ by OWN_DELTA or more (the page changed during the probe); not counted, and a unit
             with more than MAX_UNSTABLE of such pixels is not verified.
  * tinted:  tint - clear = alpha x (probe colour - clear) with alpha >= MIN_ALPHA and a small residual, for the
             unit's own probe colour and no other colour of its group, and the same for tint2 with an alpha within
             MAX_ALPHA_GAP. Only the unit's own glyphs, where they are actually composited onto the screen, take the
             probe colours: glyphs that are clipped, covered, painted below an ancestor's background, masked, filtered
             away, transparent through opacity, or not repainted by the highlight (SVG text) do not, and nothing else
             on the page (decoy text, borders, patterns, images, animations) changes in that way between those shots
             for two colours the page does not know.
  * inked:   tinted, plain differs from clear by at least OWN_DELTA (the unit's own colour is visible against what
             is behind it: white on white, near-background colours and transparent fills are not) and base equals
             plain within OWN_DELTA (no decoration paints over it; R2-03 below).
R2-03: a CSS highlight cannot take away the element's own text-decoration (Chromium repaints it in the highlight
colour), so a line-through bar drawn over white text took both tints exactly where the glyphs are. The probe shots
are taken with every decoration off, and one more shot, `plain` (the page as it is with only the decorations off),
is required. A tinted pixel is inked only where `plain` differs from `clear` by OWN_DELTA (the glyph shows without
decorations) and `base` equals `plain` within OWN_DELTA (no decoration paints over it). A unit whose decorations
cover more than MAX_DECORATED of its box, or whose decoration the probe could not switch off (`d`: the page's own
!important rule, or one of the page's own highlights over it), is dropped (`decorated`).
A unit is kept only when
  * its inked pixels reach MIN_INK_PER_CHAR x (non-space characters) x (mean line height) (CSS px, x dpr^2),
  * at least MIN_OWN_FRACTION of its tinted pixels are inked, and
  * every cell of each rectangle (cells about one line height wide) holds at least MIN_CELL_INK x height^2 inked
    pixels, so a visible part of a text node cannot carry a part that is clipped, masked or covered.
Thresholds were set from headless Chromium at device pixel ratio 1 (tests/assist/test_a0_r13_differential_render.py
page): drawn text 1.13-4.4 inked px per character per px of line height (0.5 opacity, 11 px, grey, bold headings),
ink/tint 1.0; every hidden payload 0 inked pixels (negative z-index under a background or a pattern, SVG fill
none/transparent/fill-opacity 0, mask and mask-box-image, blur, overlays with or without pointer-events, clip, white
and near-white text), also when placed over visible text.

Anything that cannot be checked is dropped (fail closed): no probe, a probe with another schema, an image that does
not decode or is not the viewport, a palette that is not saturated and well separated, a group plan that puts touching
units in one group or near units in one colour, a unit whose rectangles, rectangle count or text node length differ from
the snapshot's (the page changed), rectangles (partly) outside the viewport, or a unit no group probed. The screenshots are
used only here and are never sent anywhere.

R14-02: a unit the snapshot or the probe reports as drawn with -webkit-text-security (discs or squares in place of the
glyphs; `s`) is dropped (`masked_glyphs`): its glyphs take the tints although the user sees only dots.

Limits (docs/assist/03_PERMISSION_AND_DATA_FLOW.md): the page's own scripts run during the probe and can change the
page between the shots; glyphs a font draws more than three line heights outside their own box can be credited to a
same-colour unit of the same group; text the highlight does not repaint (SVG text) is never kept; a web font that
draws other glyphs than the characters (glyph substitution) passes the check (owner decision).

Windows ClearType uses separate RGB subpixel coverage. When scalar coverage fails, a coloured edge can instead be
bound channel by channel to both independent paints, with the same contrast/residual/coverage bounds. Each credited
channel must be measurable in BOTH paints; a weak channel has zero weight. No competing group colour may explain the
credited subset. Verified channels contribute one third of a tinted pixel each; they contribute ink only when those
same subpixels are visibly drawn and undecorated. The complete verified tint mask stays in the visibility denominator.
Original stability, decoration, density and per-cell requirements still apply.
"""
from __future__ import annotations

import io
import math
import re
from collections import Counter
from typing import Optional

PROBE = "uri.assist.probe.v1"
MIN_ALPHA, MAX_ALPHA = 0.3, 1.2   # glyph coverage x opacity a tinted pixel must show
MAX_ALPHA_GAP = 0.2               # the two tints must agree on it
MAX_UNSTABLE = 0.1                # share of a unit's pixels that may change between base and base2
MAX_DECORATED = 0.25              # R2-03: share of a unit's pixels its decorations (base vs plain) may cover
MAX_RESIDUAL = 28                 # per channel, how far a tinted pixel may be from alpha x (probe - clear)
MIN_PROBE_CONTRAST = 64           # |probe - clear| a pixel needs for its tint to be measurable
OWN_DELTA = 24                    # base vs clear, some channel: the unit's own colour shows
MIN_INK_PER_CHAR = 0.6            # inked px per non-space character per CSS px of line height (x dpr^2)
MIN_OWN_FRACTION = 0.6            # inked / tinted
MIN_CELL_INK = 0.03               # inked px per cell, x (rect height in device px)^2
GROW, NEAR = 0.25, 3.0            # line heights: touching units -> other group; near units -> other colour
MIN_PALETTE_SPREAD, MIN_PALETTE_GAP, MAX_PALETTE = 120, 96, 6
EDGE_TOLERANCE = 2                # CSS px a rectangle may overhang the viewport (glyph overhang, rounding)
SIZE_TOLERANCE = 2                # device px a screenshot may differ from viewport x device pixel ratio
MAX_RECTS = 8                     # the page sends at most this many rectangles per unit
MAX_GROUPS = 8
MAX_UNITS = 6000
MAX_PIXELS = 40_000_000           # decompression bomb guard (same as vision.py)

UNVERIFIED, NO_INK, MASKED_GLYPHS = "offscreen_or_unverified", "no_ink", "masked_glyphs"
DECORATED = "decorated"


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _int(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _rects(raw) -> Optional[list]:
    if not isinstance(raw, list) or len(raw) > MAX_RECTS:
        return None
    out = []
    for r in raw:
        if not (isinstance(r, (list, tuple)) and len(r) == 4 and all(_num(v) for v in r)):
            return None
        out.append([float(v) for v in r])
    return out


def _unit(u) -> Optional[dict]:
    """A snapshot or probe unit {r, c, l, k?}; None when malformed."""
    if not isinstance(u, dict):
        return None
    r = _rects(u.get("r"))
    if r is None or not _int(u.get("c"), 0, 10_000) or not _int(u.get("l"), 0, 10_000_000):
        return None
    return {"r": r, "c": u["c"], "l": u["l"], "k": u["k"] if _int(u.get("k"), 0, 100_000) else None,
            "s": u.get("s") not in (None, 0, False), "d": u.get("d") not in (None, 0, False)}


def _image(png, w, h, dpr):
    from PIL import Image
    if not isinstance(png, (bytes, bytearray)) or not png:
        return None
    try:
        img = Image.open(io.BytesIO(png))           # header only
        if img.width * img.height > MAX_PIXELS:
            return None
        img.load()
    except Exception:
        return None
    if abs(img.width - w * dpr) > SIZE_TOLERANCE or abs(img.height - h * dpr) > SIZE_TOLERANCE:
        return None                                   # not this viewport (or scaled): cannot be trusted
    return img.convert("RGB")


def _box(r, m=0.0):
    return (r[0] - m, r[1] - m, r[0] + r[2] + m, r[1] + r[3] + m)


def _meets(p, q):
    return p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]


def _near(a: list, b: list, f: float) -> bool:
    return any(_meets(_box(p, f * max(p[3], q[3])), _box(q)) for p in a for q in b)


def _plan_ok(groups, units) -> bool:
    """Touching units never share a group; near units never share a colour inside a group."""
    for g in groups:
        rows = sorted(((min(r[1] for r in units[i]["r"]), i, c) for i, c in zip(g["units"], g["colours"])))
        reach = NEAR * max((r[3] for _, i, _ in rows for r in units[i]["r"]), default=0) + 1
        for a, (top, i, ci) in enumerate(rows):
            bottom = max(r[1] + r[3] for r in units[i]["r"])
            for top2, j, cj in rows[a + 1:]:
                if top2 > bottom + reach:
                    break
                if _near(units[i]["r"], units[j]["r"], GROW) or (ci == cj and _near(units[i]["r"], units[j]["r"], NEAR)):
                    return False
    return True


class Probe:
    """A validated differential render of one snapshot. Built only by load()."""

    def __init__(self, base, base2, plain, groups, palettes, units, where, vw, vh, dpr):
        self.base, self.base2, self.plain, self.groups, self.palettes = base, base2, plain, groups, palettes
        self.units, self.where = units, where
        self.vw, self.vh, self.dpr = vw, vh, dpr
        self._cache = {}

    def _counts(self, gk, ci, rect):
        """(tinted, inked, unstable, inked per cell, decorated) inside one rectangle (CSS px), for group gk and colour
        ci."""
        g, d = self.groups[gk], self.dpr
        x, y, w, h = rect
        l, t = max(0.0, x), max(0.0, y)
        r, b = min(self.vw, x + w), min(self.vh, y + h)
        box = (max(0, math.floor(l * d)), max(0, math.floor(t * d)),
               min(self.base.width, math.ceil(r * d)), min(self.base.height, math.ceil(b * d)))
        bw, bh = box[2] - box[0], box[3] - box[1]
        if bw <= 0 or bh <= 0:
            return 0, 0, 0, [0], 0
        from PIL import ImageChops
        cells = max(1, int(bw // max(4 * d, bh)))
        per = [0] * cells
        tinted = inked = 0
        crops = [im.crop(box) for im in (self.base, self.base2, g["clear"], g["tint"], g["tint2"], self.plain)]
        n_px, _, c_px, a_px, b_px, p_px = (im.tobytes() for im in crops)

        def changed(p, q, at):                           # 255 where some channel differs by `at` or more
            r_, g_, b_ = ImageChops.difference(p, q).split()
            return ImageChops.lighter(ImageChops.lighter(r_, g_), b_).point(lambda v: 255 if v >= at else 0)
        moved = changed(crops[0], crops[1], OWN_DELTA)
        unstable = moved.histogram()[255]
        # R2-03: where the page differs from itself with decorations off, a decoration is drawn.
        decorated = ImageChops.subtract(changed(crops[0], crops[5], OWN_DELTA), moved).histogram()[255]
        # Only pixels the first tint changed and that stayed put between base and base2 can be tinted glyph pixels.
        cand = ImageChops.subtract(changed(crops[3], crops[2], math.ceil(MIN_PROBE_CONTRAST * MIN_ALPHA / 2)), moved)
        tints = [(a_px, pal[ci], [pal[c] for c in g["used"] if c != ci]) for a_px, pal in
                 ((a_px, self.palettes[0]), (b_px, self.palettes[1]))]

        def alpha(Q, c0, c1, c2, d0, d1, d2):
            p0, p1, p2 = Q[0] - c0, Q[1] - c1, Q[2] - c2
            s = p0 * p0 + p1 * p1 + p2 * p2
            if s < MIN_PROBE_CONTRAST * MIN_PROBE_CONTRAST:
                return None
            al = (d0 * p0 + d1 * p1 + d2 * p2) / s
            ok = MIN_ALPHA <= al <= MAX_ALPHA and max(abs(d0 - al * p0), abs(d1 - al * p1),
                                                      abs(d2 - al * p2)) <= MAX_RESIDUAL
            return al if ok else None

        # Fixed sRGB transfer (W3C CSS Color 4), never a per-pixel fitted gamma.
        linear = tuple(v / 255 / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4
                       for v in range(256))
        def encoded(v):
            return 255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)

        def channel_coverage(colour, ch, k, background):
            clear = background[ch]
            pa, pb = self.palettes[0][colour][ch], self.palettes[1][colour][ch]
            if pa == clear or pb == clear:
                return None
            ta, tb = a_px[k + ch], b_px[k + ch]
            bg = linear[clear]
            p1, p2 = linear[pa] - bg, linear[pb] - bg
            a1, a2 = (linear[ta] - bg) / p1, (linear[tb] - bg) / p2
            if not 0 <= a1 <= MAX_ALPHA or not 0 <= a2 <= MAX_ALPHA or abs(a1 - a2) > MAX_ALPHA_GAP:
                return None
            al = (a1 + a2) / 2
            if max(abs(ta - encoded(bg + al * p1)), abs(tb - encoded(bg + al * p2))) > MAX_RESIDUAL:
                return None
            return min(a1, a2)

        def subpixel_channels(colour, k, background):
            # Each credited channel supplies its OWN signal in both paints.
            # Weak channels receive zero credit, and cannot establish a match.
            measured, channels = [], []
            floor = math.ceil(MIN_PROBE_CONTRAST * MIN_ALPHA / 2)
            for ch in range(3):
                clear = background[ch]
                pa, pb = self.palettes[0][colour][ch], self.palettes[1][colour][ch]
                ta, tb = a_px[k + ch], b_px[k + ch]
                if pa == clear or pb == clear:
                    return ()                             # retain strict refusal of a flat probe paint
                bg = linear[clear]
                a1, a2 = (linear[ta] - bg) / (linear[pa] - bg), (linear[tb] - bg) / (linear[pb] - bg)
                if not 0 <= a1 <= MAX_ALPHA or not 0 <= a2 <= MAX_ALPHA:
                    return ()                             # even weak data cannot claim impossible coverage
                if min(abs(pa - clear), abs(pb - clear), abs(ta - clear), abs(tb - clear)) < floor:
                    continue                              # no credit from this weak channel
                al = channel_coverage(colour, ch, k, background)
                if al is None:
                    return ()                             # contradictory measurable data
                measured.append(al)
                if al >= MIN_ALPHA:
                    channels.append(ch)
            if len(channels) < 2 or max(measured) - min(measured) <= MAX_ALPHA_GAP:
                return ()                                 # keep scalar and ambiguous sparse evidence out
            return tuple(channels)

        for m in re.finditer(rb"[^\x00]", cand.tobytes()):
            k = 3 * m.start()
            c0, c1, c2 = c_px[k], c_px[k + 1], c_px[k + 2]
            alphas = []
            for px, P, others in tints:
                d0, d1, d2 = px[k] - c0, px[k + 1] - c1, px[k + 2] - c2
                if max(abs(d0), abs(d1), abs(d2)) < MIN_PROBE_CONTRAST * MIN_ALPHA / 2:
                    break                                # the tint changed nothing here
                al = alpha(P, c0, c1, c2, d0, d1, d2)
                if al is None or any(alpha(Q, c0, c1, c2, d0, d1, d2) is not None for Q in others):
                    break
                alphas.append(al)
            weight = ink_weight = 1.0
            if len(alphas) != 2 or abs(alphas[0] - alphas[1]) > MAX_ALPHA_GAP:
                channels = subpixel_channels(ci, k, (c0, c1, c2))
                # Compare competing colours on EXACTLY the credited channels:
                # an unmeasured component must not create false uniqueness.
                if not channels or any(all(channel_coverage(other, ch, k, (c0, c1, c2)) is not None
                                           for ch in channels) for other in g["used"] if other != ci):
                    continue
                weight = len(channels) / 3
                ink_weight = sum(abs(p_px[k + ch] - c_px[k + ch]) >= OWN_DELTA and
                                 abs(n_px[k + ch] - p_px[k + ch]) < OWN_DELTA for ch in channels) / 3
            tinted += weight
            # R2-03: the glyph shows with decorations off (plain vs clear) and nothing paints over it (base = plain).
            if max(abs(p_px[k] - c0), abs(p_px[k + 1] - c1), abs(p_px[k + 2] - c2)) >= OWN_DELTA and max(
                    abs(n_px[k] - p_px[k]), abs(n_px[k + 1] - p_px[k + 1]), abs(n_px[k + 2] - p_px[k + 2])) < OWN_DELTA:
                inked += ink_weight
                per[min(cells - 1, ((k // 3) % bw) * cells // bw)] += ink_weight
        return tinted, inked, unstable, [p / (bh * bh) for p in per], decorated

    def verify(self, i: int) -> Optional[str]:
        """None when unit i drew its own glyphs visibly in its own box, else the reason it is dropped."""
        if i in self._cache:
            return self._cache[i]
        self._cache[i] = why = self._verify(i)
        return why

    def _verify(self, i):
        if not _int(i, 0, len(self.units) - 1):
            return UNVERIFIED
        u = self.units[i]
        if u["k"] == 0:
            return None                                  # whitespace carries nothing to verify
        if u.get("s"):
            return MASKED_GLYPHS                         # R14-02: -webkit-text-security shows dots, not the text
        if u.get("d"):
            return DECORATED                             # R2-03: a decoration the probe could not switch off
        if u["k"] is None or not u["r"] or u["c"] > len(u["r"]) or i not in self.where:
            return UNVERIFIED
        tinted = inked = unstable = area = decorated = 0
        empty_cell = False
        for x, y, w, h in u["r"]:
            if w <= 0 or h <= 0:
                return UNVERIFIED
            if x < -EDGE_TOLERANCE or y < -EDGE_TOLERANCE or x + w > self.vw + EDGE_TOLERANCE \
                    or y + h > self.vh + EDGE_TOLERANCE:
                return UNVERIFIED                        # (partly) outside the viewport: cannot be checked
            t, k, n, cells, dk = self._counts(*self.where[i], [x, y, w, h])
            tinted, inked, unstable, area = tinted + t, inked + k, unstable + n, area + w * h * self.dpr ** 2
            decorated += dk
            empty_cell = empty_cell or (w >= 4 and min(cells) < MIN_CELL_INK)
        if unstable > MAX_UNSTABLE * area:
            return UNVERIFIED                            # the page changed under this unit during the probe
        if decorated > MAX_DECORATED * area:
            return DECORATED                             # R2-03: its decorations cover the glyphs
        if empty_cell:
            return NO_INK                                # part of a box shows none of the unit's own glyphs
        height = sum(r[3] for r in u["r"]) / len(u["r"])
        if inked < MIN_INK_PER_CHAR * u["k"] * height * self.dpr ** 2 or inked < MIN_OWN_FRACTION * tinted:
            return NO_INK
        return None


def load(probe, snapshot) -> Optional[Probe]:
    """Validate the adapter's probe against the snapshot; None when it cannot be used (then no page text is kept)."""
    if not isinstance(probe, dict) or probe.get("schema") != PROBE or not isinstance(snapshot, dict):
        return None
    vp, dpr = snapshot.get("viewport"), snapshot.get("device_pixel_ratio")
    if not isinstance(vp, dict) or probe.get("viewport") != vp or probe.get("device_pixel_ratio") != dpr:
        return None
    vw, vh = vp.get("w"), vp.get("h")
    if not all(_num(v) and 0 < v < 100_000 for v in (vw, vh)) or not _num(dpr) or not 0.25 <= dpr <= 8:
        return None
    palette, palette2 = probe.get("palette"), probe.get("palette2")
    gap = lambda p, q: max(abs(a - b) for a, b in zip(p, q))
    for pal in (palette, palette2):
        if not isinstance(pal, list) or not 1 <= len(pal) <= MAX_PALETTE or not all(
                isinstance(c, list) and len(c) == 3 and all(_int(v, 0, 255) for v in c) for c in pal):
            return None
        if any(max(c) - min(c) < MIN_PALETTE_SPREAD for c in pal) or any(
                gap(p, q) < MIN_PALETTE_GAP for n, p in enumerate(pal) for q in pal[n + 1:]):
            return None                                  # grey or near-duplicate probe colours cannot be told apart
    if len(palette) != len(palette2) or any(gap(p, q) < MIN_PALETTE_GAP for p, q in zip(palette, palette2)):
        return None                                      # the second tint must be an independent measurement
    s_units, p_units = snapshot.get("units"), probe.get("units")
    if not isinstance(s_units, list) or not isinstance(p_units, list) or len(s_units) != len(p_units) \
            or len(s_units) > MAX_UNITS:
        return None
    units = []
    for su, pu in zip(s_units, p_units):
        a, b = _unit(su), _unit(pu)
        if a is None or b is None or (a["k"] or 0) == 0:
            units.append({"r": [], "c": 0, "l": 0, "k": None if a is None else a["k"]})
        elif a["s"] or b["s"]:
            units.append({"r": [], "c": 0, "l": 0, "k": a["k"], "s": True})   # R14-02: drawn as discs/squares
        elif b["d"]:
            units.append({"r": [], "c": 0, "l": 0, "k": a["k"], "d": True})   # R2-03: decoration not switched off
        elif (a["r"], a["c"], a["l"]) != (b["r"], b["c"], b["l"]):
            units.append({"r": [], "c": 0, "l": 0, "k": None})     # the page changed between snapshot and probe
        else:
            units.append({**b, "k": a["k"]})
    base, base2 = _image(probe.get("base"), vw, vh, dpr), _image(probe.get("base2"), vw, vh, dpr)
    plain = _image(probe.get("plain"), vw, vh, dpr)     # R2-03: required; without it no page text is kept
    raw_groups = probe.get("groups")
    if base is None or base2 is None or plain is None or not isinstance(raw_groups, list) or len(raw_groups) > MAX_GROUPS:
        return None
    groups, where = [], {}
    for gk, g in enumerate(raw_groups):
        if not isinstance(g, dict):
            return None
        gu, gc = g.get("units"), g.get("colours")
        if not isinstance(gu, list) or not isinstance(gc, list) or len(gu) != len(gc) or not all(
                _int(i, 0, len(units) - 1) and i not in where for i in gu) or not all(
                _int(c, 0, len(palette) - 1) for c in gc) or len(set(gu)) != len(gu):
            return None
        clear, tint, tint2 = (_image(g.get(k), vw, vh, dpr) for k in ("clear", "tint", "tint2"))
        if clear is None or tint is None or tint2 is None:
            return None
        live = [(i, c) for i, c in zip(gu, gc) if units[i]["r"]]
        groups.append({"units": [i for i, _ in live], "colours": [c for _, c in live], "used": sorted(set(gc)),
                       "clear": clear, "tint": tint, "tint2": tint2})
        for i, c in zip(gu, gc):
            where[i] = (gk, c)
    if not _plan_ok(groups, units):
        return None
    return Probe(base, base2, plain, groups, ([tuple(c) for c in palette], [tuple(c) for c in palette2]), units, where,
                 float(vw), float(vh), float(dpr))


def _piece(p) -> Optional[dict]:
    if not isinstance(p, dict) or not isinstance(p.get("t"), str):
        return None
    u = p.get("u")
    ids = [i for i in u if _int(i, -1, MAX_UNITS)] if isinstance(u, list) else []
    g = p.get("g") if isinstance(p.get("g"), int) and not isinstance(p.get("g"), bool) else 0
    return {"t": p["t"][:4000], "u": ids if isinstance(u, list) and len(ids) == len(u) and u else [], "g": g}


def _chars(t: str) -> int:
    return sum(1 for ch in t.replace("[redacted]", "") if not ch.isspace())


def check(piece: dict, probe: Optional[Probe]) -> Optional[str]:
    """None when every unit of the piece passed the render check, else the reason it is dropped."""
    if _chars(piece["t"]) == 0 and "[redacted]" not in piece["t"]:
        return None                                      # whitespace carries nothing to verify
    if probe is None or not piece["u"]:
        return UNVERIFIED
    for i in piece["u"]:
        why = probe.verify(i)
        if why is not None:
            return why
    # The piece's text must be accounted for by its units' characters (masking only shortens).
    if sum(probe.units[i]["k"] or 0 for i in piece["u"]) < _chars(piece["t"]):
        return UNVERIFIED
    return None


def keep(pieces, probe: Optional[Probe], counts: Counter, limit: int) -> list:
    """The pieces drawn on screen, in order (at most `limit` are examined). Dropped ones are counted by reason."""
    out = []
    for p in (pieces if isinstance(pieces, list) else [])[:limit]:
        q = _piece(p)
        if q is None:
            continue
        why = check(q, probe)
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
