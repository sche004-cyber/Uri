"""URI-owned deterministic scene renderer: `uri.scene.v1` JSON -> RGBA frames -> optimized animated GIF.

Why a declarative scene instead of letting the harness run code: the accepted Claude executor profile
(`uri_supervisor.executors.CLAUDE_CODE`) grants only Read/Edit/Write/Glob/Grep. Giving it a shell or Python to render
would widen unattended permissions (an owner decision, RED). The harness therefore authors the creative content as
data (palette, motifs, particles, motion, greeting) and URI renders it here with fixed, reviewed code.

Seamless looping is structural: every periodic motion uses the scene duration as its base period and every particle
travels an integer number of wraps per loop, so the last frame flows into the first.

Coordinates are normalized (0..1 of width/height); sizes are fractions of the shorter side.
"""
from __future__ import annotations

import io
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

SCHEMA = "uri.scene.v1"
LAYER_TYPES = ("glow", "rays", "mandala", "diya", "particles", "lantern", "crescent", "star", "lotus", "text", "polygon",
               "bokeh")
PARTICLE_KINDS = ("petals", "embers", "sparkles", "snow", "confetti", "marigold")
LIMITS = {"max_side": 720, "min_side": 160, "max_frames": 120, "min_frames": 8, "max_fps": 30, "max_layers": 40,
          "max_particles": 400, "max_text": 80}
FONT_DIR = Path("C:/Windows/Fonts")
FONTS = {"serif": ("georgiab.ttf", "georgia.ttf", "cambriab.ttf"), "display": ("Gabriola.ttf", "georgiab.ttf"),
         "sans": ("segoeuib.ttf", "bahnschrift.ttf", "Candarab.ttf"), "elegant": ("constanb.ttf", "georgiab.ttf")}
SS = 2   # supersampling factor


class SceneError(ValueError):
    pass


# ---- validation -------------------------------------------------------------------------------------------------

def _color(c, field="color"):
    if isinstance(c, str) and c.startswith("#") and len(c) in (7, 9):
        try:
            v = tuple(int(c[i:i + 2], 16) for i in range(1, len(c), 2))
            return v if len(v) == 4 else v + (255,)
        except ValueError:
            pass
    raise SceneError(f"BAD_COLOR:{field}:{c}")


def _num(v, lo, hi, field):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise SceneError(f"BAD_NUMBER:{field}") from None
    if not (lo <= f <= hi) or math.isnan(f):
        raise SceneError(f"OUT_OF_RANGE:{field}:{f}")
    return f


def latin_only(text: str) -> bool:
    """Pillow here has no complex-text shaping (libraqm absent), so only Latin text renders correctly."""
    return all(ord(ch) < 0x0250 or ch in "\u2019\u2018\u201c\u201d\u2013\u2014\u2026\u2022\u2728" for ch in text)


def validate_scene(scene: dict) -> dict:
    if not isinstance(scene, dict) or scene.get("schema") != SCHEMA:
        raise SceneError("BAD_SCHEMA")
    cv = scene.get("canvas") or {}
    w = int(_num(cv.get("width", 480), LIMITS["min_side"], LIMITS["max_side"], "canvas.width"))
    h = int(_num(cv.get("height", 480), LIMITS["min_side"], LIMITS["max_side"], "canvas.height"))
    fps = _num(cv.get("fps", 15), 4, LIMITS["max_fps"], "canvas.fps")
    dur = _num(cv.get("duration_s", 4), 1, 12, "canvas.duration_s")
    frames = int(round(fps * dur))
    if not (LIMITS["min_frames"] <= frames <= LIMITS["max_frames"]):
        raise SceneError(f"FRAME_COUNT:{frames}")
    bg = scene.get("background") or {}
    stops = bg.get("stops") or [["#101020", 0], ["#302050", 1]]
    for s in stops:
        _color(s[0], "background.stops")
        _num(s[1], 0, 1, "background.stops.pos")
    if bg.get("type", "gradient") not in ("gradient", "radial"):
        raise SceneError("BAD_BACKGROUND")
    layers = scene.get("layers") or []
    if not isinstance(layers, list) or len(layers) > LIMITS["max_layers"]:
        raise SceneError("BAD_LAYERS")
    particles = 0
    has_text = False
    for i, ly in enumerate(layers):
        t = ly.get("type")
        if t not in LAYER_TYPES:
            raise SceneError(f"UNKNOWN_LAYER:{i}:{t}")
        for k in ("x", "y"):
            if k in ly:
                _num(ly[k], -0.5, 1.5, f"layers[{i}].{k}")
        for k, v in ly.items():
            if k in ("color", "flame_color", "body_color", "stroke", "glow", "fill") and v is not None:
                _color(v, f"layers[{i}].{k}")
            if k == "colors":
                if not isinstance(v, list) or not v:
                    raise SceneError(f"BAD_COLORS:{i}")
                for c in v:
                    _color(c, f"layers[{i}].colors")
        if t == "particles":
            if ly.get("kind") not in PARTICLE_KINDS:
                raise SceneError(f"BAD_PARTICLE_KIND:{i}")
            particles += int(_num(ly.get("count", 30), 1, LIMITS["max_particles"], f"layers[{i}].count"))
        if t == "text":
            txt = ly.get("text")
            if not isinstance(txt, str) or not txt.strip() or len(txt) > LIMITS["max_text"]:
                raise SceneError(f"BAD_TEXT:{i}")
            if not latin_only(txt):
                raise SceneError(f"TEXT_SCRIPT_UNSUPPORTED:{i}")
            if ly.get("font", "serif") not in FONTS:
                raise SceneError(f"BAD_FONT:{i}")
            _num(ly.get("size", 0.08), 0.03, 0.2, f"layers[{i}].size")
            has_text = True
        if t == "polygon":
            pts = ly.get("points")
            if not isinstance(pts, list) or not (3 <= len(pts) <= 64):
                raise SceneError(f"BAD_POLYGON:{i}")
    if particles > LIMITS["max_particles"]:
        raise SceneError("TOO_MANY_PARTICLES")
    if not has_text:
        raise SceneError("GREETING_TEXT_REQUIRED")
    return {"width": w, "height": h, "fps": fps, "duration_s": dur, "frames": frames}


# ---- drawing helpers ------------------------------------------------------------------------------------------------

def _font(name, px):
    for fn in FONTS.get(name, FONTS["serif"]):
        p = FONT_DIR / fn
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), px)
            except OSError:
                continue
    return ImageFont.load_default(size=px)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))


def _with_alpha(c, a):
    return (c[0], c[1], c[2], max(0, min(255, int(c[3] * a))))


def _background(bg, W, H):
    stops = sorted(((_color(c), float(p)) for c, p in (bg.get("stops") or [["#101020", 0], ["#302050", 1]])),
                   key=lambda s: s[1])
    radial = bg.get("type") == "radial"
    grad = Image.new("RGBA", (1, 256) if not radial else (256, 1))
    px = grad.load()
    for i in range(256):
        t = i / 255
        lo = max((s for s in stops if s[1] <= t), key=lambda s: s[1], default=stops[0])
        hi = min((s for s in stops if s[1] >= t), key=lambda s: s[1], default=stops[-1])
        span = hi[1] - lo[1]
        c = lo[0] if span <= 0 else _lerp(lo[0], hi[0], (t - lo[1]) / span)
        if radial:
            px[i, 0] = c
        else:
            px[0, i] = c
    if not radial:
        return grad.resize((W, H), Image.BICUBIC)
    # radial: distance from center mapped through the strip
    cx, cy = W * float(bg.get("cx", 0.5)), H * float(bg.get("cy", 0.5))
    maxd = math.hypot(max(cx, W - cx), max(cy, H - cy))
    small = Image.new("RGBA", (W // 4 + 1, H // 4 + 1))
    sp = small.load()
    for y in range(small.height):
        for x in range(small.width):
            d = min(1.0, math.hypot(x * 4 - cx, y * 4 - cy) / maxd)
            sp[x, y] = px[int(d * 255), 0]
    return small.resize((W, H), Image.BICUBIC)


def _phase(t, dur, period=None, cycles=1):
    """Angle in radians of a loop-safe oscillation: an integer number of cycles per scene loop."""
    k = max(1, int(round(dur / period))) if period else max(1, int(cycles))
    return 2 * math.pi * k * (t / dur)


def _glow(layer, W, H, S, t, dur):
    col = _color(layer.get("color", "#ffcc66"))
    r = float(layer.get("radius", 0.3)) * S
    pulse = layer.get("pulse") or {}
    amp = float(pulse.get("amp", 0.0))
    r *= 1 + amp * math.sin(_phase(t, dur, pulse.get("period_s")))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = float(layer.get("x", 0.5)) * W, float(layer.get("y", 0.5)) * H
    op = float(layer.get("opacity", 0.8))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_with_alpha(col, op))
    return _soft(im, r * 0.45)


def _rays(layer, W, H, S, t, dur):
    col = _color(layer.get("color", "#ffd27a"))
    cx, cy = float(layer.get("x", 0.5)) * W, float(layer.get("y", 0.5)) * H
    n = int(layer.get("count", 12))
    L = float(layer.get("length", 0.7)) * S
    wdeg = float(layer.get("width_deg", 5))
    turns = int(layer.get("turns_per_loop", 0))
    rot = (360.0 / n) * turns * (t / dur) if turns else 0.0      # loop-safe: advances whole ray spacings
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    op = float(layer.get("opacity", 0.25))
    for i in range(n):
        a0 = math.radians(i * 360 / n + rot - wdeg / 2)
        a1 = math.radians(i * 360 / n + rot + wdeg / 2)
        d.polygon([(cx, cy), (cx + L * math.cos(a0), cy + L * math.sin(a0)), (cx + L * math.cos(a1), cy + L * math.sin(a1))],
                  fill=_with_alpha(col, op))
    return im.filter(ImageFilter.GaussianBlur(S * 0.01))


def _mandala(layer, W, H, S, t, dur):
    cx, cy = float(layer.get("x", 0.5)) * W, float(layer.get("y", 0.5)) * H
    R = float(layer.get("radius", 0.2)) * S
    petals = int(layer.get("petals", 12))
    rings = max(1, min(6, int(layer.get("rings", 3))))
    cols = [_color(c) for c in (layer.get("colors") or ["#e74c3c", "#f39c12", "#f1c40f", "#ffffff"])]
    steps = int(layer.get("turns_per_loop", 0))      # whole petal spacings advanced per loop -> seamless
    rot = 360.0 / petals * steps * (t / dur)
    breathe = 1 + float(layer.get("breathe", 0.0)) * math.sin(_phase(t, dur))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for ring in range(rings, 0, -1):
        rr = R * ring / rings * breathe
        col = cols[(rings - ring) % len(cols)]
        pr = rr * 0.38
        for i in range(petals):
            a = math.radians(i * 360 / petals + rot * (1 if ring % 2 else -1) + (180 / petals) * (ring % 2))
            px, py = cx + (rr - pr) * math.cos(a), cy + (rr - pr) * math.sin(a)
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=col)
        d.ellipse([cx - rr * 0.55, cy - rr * 0.55, cx + rr * 0.55, cy + rr * 0.55], fill=cols[(rings - ring + 1) % len(cols)])
    d.ellipse([cx - R * 0.12, cy - R * 0.12, cx + R * 0.12, cy + R * 0.12], fill=cols[-1])
    return im


def _flame(d, fx, fy, fh, col, wob):
    """Teardrop flame: tip at the top, bulb at the bottom; `wob` bends the tip sideways."""
    fw = fh * 0.42
    pts = []
    for k in range(32):
        a = 2 * math.pi * k / 32
        top = 0.5 + 0.5 * math.cos(a)                     # 1 at the tip, 0 at the base
        x = fx + fw * math.sin(a) * abs(math.sin(a / 2)) ** 1.3 + wob * fh * 0.18 * top
        y = fy - fh * 0.5 * math.cos(a)
        pts.append((x, y))
    d.polygon(pts, fill=col)


def _soft(im, radius):
    """Gaussian blur at quarter resolution (identical look for soft glows, ~10x cheaper)."""
    if radius <= 2:
        return im.filter(ImageFilter.GaussianBlur(radius))
    W, H = im.size
    small = im.resize((max(1, W // 4), max(1, H // 4)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius / 4))
    return small.resize((W, H), Image.BILINEAR)


def _diya(layer, W, H, S, t, dur):
    cx, cy = float(layer.get("x", 0.5)) * W, float(layer.get("y", 0.7)) * H
    s = float(layer.get("scale", 0.12)) * S
    body = _color(layer.get("body_color", "#b5482a"))
    flame = _color(layer.get("flame_color", "#ffc93c"))
    flick = float(layer.get("flicker", 0.2))
    ph = _phase(t, dur, cycles=int(layer.get("flicker_cycles", 6))) + float(layer.get("phase", 0))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # halo
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hr = s * (0.9 + 0.1 * math.sin(ph))
    hd.ellipse([cx - hr, cy - s * 0.55 - hr, cx + hr, cy - s * 0.55 + hr], fill=_with_alpha(flame, 0.55))
    im = Image.alpha_composite(im, _soft(halo, hr * 0.5))
    d = ImageDraw.Draw(im)
    # bowl
    d.chord([cx - s * 0.6, cy - s * 0.35, cx + s * 0.6, cy + s * 0.35], 0, 180, fill=body)
    d.polygon([(cx + s * 0.45, cy - s * 0.02), (cx + s * 0.78, cy - s * 0.16), (cx + s * 0.5, cy + s * 0.1)], fill=body)
    rim = _lerp(body, (255, 214, 120, 255), 0.45)
    d.line([(cx - s * 0.6, cy), (cx + s * 0.6, cy)], fill=rim, width=max(1, int(s * 0.06)))
    # flame
    fh = s * (0.62 + flick * 0.25 * math.sin(ph * 1.0) + flick * 0.1 * math.sin(ph * 2.0))
    wob = flick * math.sin(ph * 1.5)
    _flame(d, cx + s * 0.6, cy - s * 0.12 - fh * 0.5, fh, flame, wob)
    _flame(d, cx + s * 0.6, cy - s * 0.12 - fh * 0.3, fh * 0.5, (255, 250, 220, 255), wob * 0.5)
    return im


def _petal(d, x, y, size, ang, col):
    pts = []
    for k in range(12):
        a = 2 * math.pi * k / 12
        px, py = size * math.cos(a), size * 0.45 * math.sin(a)
        pts.append((x + px * math.cos(ang) - py * math.sin(ang), y + px * math.sin(ang) + py * math.cos(ang)))
    d.polygon(pts, fill=col)


def _particles(layer, W, H, S, t, dur):
    kind = layer["kind"]
    rnd = random.Random(int(layer.get("seed", 7)))
    n = int(layer.get("count", 30))
    cols = [_color(c) for c in (layer.get("colors") or ["#ffcc66"])]
    smin, smax = (layer.get("size") or [3, 8])[:2]
    vmin, vmax = (layer.get("speed") or [0.05, 0.2])[:2]
    direction = layer.get("direction", "up" if kind in ("embers", "sparkles") else "down")
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = t / dur
    for i in range(n):
        x0, y0 = rnd.random(), rnd.random()
        wraps = max(1, int(round(rnd.uniform(vmin, vmax) * dur)))      # integer wraps per loop -> seamless
        size = rnd.uniform(smin, smax) * SS * (S / (480 * SS))
        col = cols[i % len(cols)]
        sway_k = rnd.randint(1, 3)
        sway = rnd.uniform(0.01, 0.04) * math.sin(2 * math.pi * sway_k * u + rnd.random() * 6.28)
        prog = (u * wraps) % 1.0
        if direction == "down":
            x, y = (x0 + sway) % 1.0, (y0 + prog) % 1.0
        elif direction == "up":
            x, y = (x0 + sway) % 1.0, (y0 - prog) % 1.0
        else:  # swirl around center
            ang = 2 * math.pi * (x0 + prog * (1 if i % 2 else -1))
            rad = 0.15 + 0.35 * y0
            x, y = 0.5 + rad * math.cos(ang), 0.5 + rad * math.sin(ang) * 0.85
        X, Y = x * W, y * H
        tw = 0.6 + 0.4 * math.sin(2 * math.pi * sway_k * u + i)
        if kind in ("petals", "marigold"):
            spin = 2 * math.pi * rnd.randint(1, 2) * u + rnd.random() * 6.28
            _petal(d, X, Y, size * 1.6, spin, _with_alpha(col, 0.9))
            if kind == "marigold":
                d.ellipse([X - size * 0.5, Y - size * 0.5, X + size * 0.5, Y + size * 0.5], fill=_lerp(col, (255, 140, 0, 255), 0.5))
        elif kind == "embers":
            r = size * 0.6
            d.ellipse([X - r * 2, Y - r * 2, X + r * 2, Y + r * 2], fill=_with_alpha(col, 0.18 * tw))
            d.ellipse([X - r, Y - r, X + r, Y + r], fill=_with_alpha(col, tw))
        elif kind == "sparkles":
            r = size * tw
            d.line([(X - r * 1.8, Y), (X + r * 1.8, Y)], fill=_with_alpha(col, tw), width=max(1, int(size * 0.3)))
            d.line([(X, Y - r * 1.8), (X, Y + r * 1.8)], fill=_with_alpha(col, tw), width=max(1, int(size * 0.3)))
            d.ellipse([X - r * 0.5, Y - r * 0.5, X + r * 0.5, Y + r * 0.5], fill=_with_alpha((255, 255, 255, 255), tw))
        elif kind == "snow":
            d.ellipse([X - size * 0.6, Y - size * 0.6, X + size * 0.6, Y + size * 0.6], fill=_with_alpha(col, 0.85))
        else:  # confetti
            ang = 2 * math.pi * rnd.randint(1, 3) * u
            w2, h2 = size, size * 0.45 * abs(math.cos(ang)) + 1
            d.rectangle([X - w2, Y - h2, X + w2, Y + h2], fill=col)
    if kind == "embers":
        im = Image.alpha_composite(im.filter(ImageFilter.GaussianBlur(SS * 1.5)), im)
    return im


def _lantern(layer, W, H, S, t, dur):
    cx, top = float(layer.get("x", 0.2)) * W, float(layer.get("y", 0.1)) * H
    s = float(layer.get("scale", 0.1)) * S
    col = _color(layer.get("color", "#e8452c"))
    sway = math.radians(float(layer.get("sway_deg", 6))) * math.sin(_phase(t, dur) + float(layer.get("phase", 0)))
    L = s * 1.4
    bx, by = cx + L * math.sin(sway), top + L * math.cos(sway)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([bx - s, by - s * 0.2, bx + s, by + s * 1.6], fill=_with_alpha(col, 0.5))
    im = Image.alpha_composite(im, _soft(glow, s * 0.5))
    d = ImageDraw.Draw(im)
    d.line([(cx, top), (bx, by)], fill=(60, 40, 30, 255), width=max(1, int(s * 0.04)))
    d.ellipse([bx - s * 0.5, by, bx + s * 0.5, by + s * 1.3], fill=col)
    inner = _lerp(col, (255, 230, 150, 255), 0.55)
    d.ellipse([bx - s * 0.25, by + s * 0.25, bx + s * 0.25, by + s * 1.05], fill=inner)
    gold = (220, 170, 60, 255)
    d.rectangle([bx - s * 0.3, by - s * 0.05, bx + s * 0.3, by + s * 0.08], fill=gold)
    d.rectangle([bx - s * 0.3, by + s * 1.25, bx + s * 0.3, by + s * 1.38], fill=gold)
    d.line([(bx, by + s * 1.38), (bx, by + s * 1.75)], fill=gold, width=max(1, int(s * 0.05)))
    return im


def _star_pts(cx, cy, r, points, inner=0.45, rot=-90):
    out = []
    for k in range(points * 2):
        rr = r if k % 2 == 0 else r * inner
        a = math.radians(rot + k * 180 / points)
        out.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return out


def _star(layer, W, H, S, t, dur):
    cx, cy = float(layer.get("x", 0.5)) * W, float(layer.get("y", 0.2)) * H
    r = float(layer.get("radius", 0.05)) * S
    col = _color(layer.get("color", "#fff2a8"))
    tw = 1 + float(layer.get("twinkle", 0.2)) * math.sin(_phase(t, dur, cycles=int(layer.get("cycles", 2))) + float(layer.get("phase", 0)))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([cx - r * 1.6 * tw, cy - r * 1.6 * tw, cx + r * 1.6 * tw, cy + r * 1.6 * tw], fill=_with_alpha(col, 0.35))
    im = Image.alpha_composite(im, _soft(g, r * 0.6))
    ImageDraw.Draw(im).polygon(_star_pts(cx, cy, r * tw, int(layer.get("points", 5))), fill=col)
    return im


def _crescent(layer, W, H, S, t, dur):
    cx, cy = float(layer.get("x", 0.75)) * W, float(layer.get("y", 0.2)) * H
    r = float(layer.get("radius", 0.08)) * S
    col = _color(layer.get("color", "#fbe7a1"))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([cx - r * 1.5, cy - r * 1.5, cx + r * 1.5, cy + r * 1.5], fill=_with_alpha(col, 0.3))
    im = Image.alpha_composite(im, _soft(g, r * 0.5))
    moon = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(moon)
    md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    md.ellipse([cx - r * 0.55, cy - r * 1.05, cx + r * 1.25, cy + r * 0.85], fill=0)
    solid = Image.new("RGBA", (W, H), col)
    im.paste(solid, (0, 0), moon)
    if layer.get("star", True):
        ImageDraw.Draw(im).polygon(_star_pts(cx + r * 0.75, cy - r * 0.05, r * 0.3, 5), fill=col)
    return im


def _lotus(layer, W, H, S, t, dur):
    cx, cy = float(layer.get("x", 0.5)) * W, float(layer.get("y", 0.75)) * H
    s = float(layer.get("scale", 0.15)) * S
    cols = [_color(c) for c in (layer.get("colors") or ["#f78fb3", "#f8a5c2", "#fdd7e4"])]
    bloom = 1 + float(layer.get("bloom", 0.08)) * math.sin(_phase(t, dur))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for ring, (n, spread, length) in enumerate(((7, 150, 1.0), (5, 110, 0.85), (3, 60, 0.7))):
        col = cols[ring % len(cols)]
        for i in range(n):
            a = math.radians(-90 - spread / 2 * bloom + spread * bloom * i / max(1, n - 1))
            tip = (cx + s * length * math.cos(a), cy + s * length * math.sin(a))
            base_l = (cx + s * 0.18 * math.cos(a - 1.2), cy + s * 0.12)
            base_r = (cx + s * 0.18 * math.cos(a + 1.2), cy + s * 0.12)
            mid_l = (cx + s * 0.55 * length * math.cos(a - 0.35), cy + s * 0.55 * length * math.sin(a - 0.35))
            mid_r = (cx + s * 0.55 * length * math.cos(a + 0.35), cy + s * 0.55 * length * math.sin(a + 0.35))
            d.polygon([base_l, mid_l, tip, mid_r, base_r], fill=col, outline=_lerp(col, (120, 40, 80, 255), 0.35))
    return im


def _polygon(layer, W, H, S, t, dur):
    pts = [(float(x) * W, float(y) * H) for x, y in layer["points"]]
    col = _color(layer.get("fill", layer.get("color", "#ffffff")))
    op = 1 + float(layer.get("pulse", 0.0)) * math.sin(_phase(t, dur))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon(pts, fill=_with_alpha(col, min(1.0, op * float(layer.get("opacity", 1.0)))))
    return im


def _bokeh(layer, W, H, S, t, dur):
    rnd = random.Random(int(layer.get("seed", 3)))
    cols = [_color(c) for c in (layer.get("colors") or ["#ffcc66", "#ff8a5c"])]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(int(layer.get("count", 12))):
        x, y = rnd.random() * W, rnd.random() * H
        r = rnd.uniform(0.02, 0.06) * S
        a = 0.15 + 0.12 * math.sin(_phase(t, dur, cycles=rnd.randint(1, 2)) + i)
        d.ellipse([x - r, y - r, x + r, y + r], fill=_with_alpha(cols[i % len(cols)], a))
    return _soft(im, S * 0.006)


def _text(layer, W, H, S, t, dur):
    txt = layer["text"]
    px = max(8, int(float(layer.get("size", 0.08)) * S))
    font = _font(layer.get("font", "serif"), px)
    col = _color(layer.get("color", "#fff6e0"))
    stroke = _color(layer.get("stroke", "#2a0f1e"))
    sw = max(1, int(px * float(layer.get("stroke_width", 0.08))))
    cx, cy = float(layer.get("x", 0.5)) * W, float(layer.get("y", 0.15)) * H
    fade = float(layer.get("fade_in_s", 0.0))
    alpha = 1.0 if fade <= 0 else min(1.0, 0.35 + 0.65 * (0.5 - 0.5 * math.cos(_phase(t, dur))))
    shimmer = float(layer.get("shimmer", 0.0))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if layer.get("glow"):
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((cx, cy), txt, font=font, anchor="mm", fill=_with_alpha(_color(layer["glow"]), 0.8),
                                 stroke_width=sw * 3, stroke_fill=_with_alpha(_color(layer["glow"]), 0.5))
        im = Image.alpha_composite(im, _soft(g, px * 0.25))
    c = col if shimmer <= 0 else _lerp(col, (255, 255, 255, 255), shimmer * (0.5 + 0.5 * math.sin(_phase(t, dur))))
    ImageDraw.Draw(im).text((cx, cy), txt, font=font, anchor="mm", fill=_with_alpha(c, alpha), stroke_width=sw,
                            stroke_fill=_with_alpha(stroke, alpha))
    return im


DRAW = {"glow": _glow, "rays": _rays, "mandala": _mandala, "diya": _diya, "particles": _particles, "lantern": _lantern,
        "crescent": _crescent, "star": _star, "lotus": _lotus, "text": _text, "polygon": _polygon, "bokeh": _bokeh}


def _relative_luminance(c):
    def ch(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast_ratio(a, b) -> float:
    la, lb = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def render_frames(scene: dict):
    info = validate_scene(scene)
    W, H = info["width"] * SS, info["height"] * SS
    S = min(W, H)
    dur, n = info["duration_s"], info["frames"]
    bg = _background(scene.get("background") or {}, W, H)
    out = []
    for f in range(n):
        t = dur * f / n
        frame = bg.copy()
        for ly in scene.get("layers") or []:
            frame = Image.alpha_composite(frame, DRAW[ly["type"]](ly, W, H, S, t, dur))
        out.append(frame.resize((info["width"], info["height"]), Image.LANCZOS).convert("RGB"))
    return out, info


def text_legibility(scene: dict, frame: Image.Image) -> list:
    """Per text layer: contrast of fill vs stroke and fill vs the rendered background under the text box."""
    res = []
    W, H = frame.size
    for ly in scene.get("layers") or []:
        if ly.get("type") != "text":
            continue
        fill = _color(ly.get("color", "#fff6e0"))
        stroke = _color(ly.get("stroke", "#2a0f1e"))
        cx, cy = float(ly.get("x", 0.5)) * W, float(ly.get("y", 0.15)) * H
        px = float(ly.get("size", 0.08)) * min(W, H)
        box = (max(0, int(cx - px * len(ly["text"]) * 0.28)), max(0, int(cy - px * 0.6)),
               min(W, int(cx + px * len(ly["text"]) * 0.28)), min(H, int(cy + px * 0.6)))
        region = frame.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0)) if box[2] > box[0] and box[3] > box[1] else (0, 0, 0)
        res.append({"text": ly["text"], "fill_vs_stroke": round(contrast_ratio(fill, stroke), 2),
                    "fill_vs_background": round(contrast_ratio(fill, region), 2),
                    "px": int(px), "legible": contrast_ratio(fill, stroke) >= 4.5 and px >= 14})
    return res


def encode_gif(frames, fps, *, colors=192, loop=0, dither=True) -> bytes:
    """Shared-palette GIF: one adaptive palette from a frame mosaic (stable colors, no per-frame flicker)."""
    dur_ms = int(round(1000 / fps / 10.0)) * 10 or 20            # GIF delays are centiseconds
    sample = Image.new("RGB", (frames[0].width, frames[0].height * min(4, len(frames))))
    step = max(1, len(frames) // 4)
    for i, fr in enumerate(frames[::step][:4]):
        sample.paste(fr, (0, i * frames[0].height))
    pal = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    q = [fr.quantize(palette=pal, dither=mode) for fr in frames]
    buf = io.BytesIO()
    q[0].save(buf, format="GIF", save_all=True, append_images=q[1:], duration=dur_ms, loop=loop, optimize=True,
              disposal=1)
    return buf.getvalue()


def render_gif(scene: dict, out_path, *, max_bytes=5 * 1024 * 1024) -> dict:
    """Render and encode; walk a quality ladder (dithered first, then flat palettes) until the size budget holds."""
    frames, info = render_frames(scene)
    data, used = None, None
    for dither, colors in ((True, 192), (False, 224), (False, 160), (False, 112), (False, 64)):
        data = encode_gif(frames, info["fps"], colors=colors, dither=dither)
        used = {"dither": dither, "palette_colors": colors}
        if len(data) <= max_bytes:
            break
    Path(out_path).write_bytes(data)
    poster = Path(out_path).with_suffix(".poster.png")
    frames[len(frames) // 3].save(poster)
    loop_seam = ImageChops.difference(frames[0], frames[-1]).convert("L").resize((1, 1), Image.BOX).getpixel((0, 0))
    return {**info, **used, "bytes": len(data), "within_size_budget": len(data) <= max_bytes, "size_budget": max_bytes,
            "poster": str(poster), "loop_seam_mean_abs_diff": loop_seam,
            "legibility": text_legibility(scene, frames[len(frames) // 2])}
