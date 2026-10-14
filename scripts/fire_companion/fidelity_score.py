"""Reproducible visual-fidelity scorer for the URI fire companion.

Compares a candidate image (a Blender render with a transparent background, or
any RGB image) against one reference panel of the "URI: EMOTIONS" sheet.

Why not plain pixel similarity: the candidate is a 3D recreation of a painted
illustration, so brush texture and exact flame strands can never match pixel
for pixel. The scorer therefore measures what a viewer recognises - silhouette,
where the light and dark masses sit, colour distribution, directional flow of
the strokes, the eyes - and calibrates the raw value between two anchors:

* 100 = the reference against a mildly degraded copy of itself (blur, 3 px
  shift, JPEG q60): "the same picture, rendered slightly differently".
* 0   = the reference against a synthetic generic fire spirit drawn in the
  reference's own colours and bounding box: an orange teardrop flame, two
  black eyes and a stick body. That is what "a generic fire spirit" means.

The calibrated value is (raw - raw0) / (raw100 - raw0) * 100, clamped to
[0, 100]. Both anchors are recomputed for every panel, so the number is
specific to that panel. A third, informational point is printed when a video
key frame is supplied: the same character redrawn by another hand.

Only numpy and Pillow are used, so the score is reproducible on any machine
with the repository's Python. Run:

    python -B scripts/fire_companion/fidelity_score.py --state idle \
        --candidate path/to/render.png [--json out.json]
"""

from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[2]
REF_DIR = REPO / "docs" / "companions" / "fire" / "reference"
SHEET = REF_DIR / "uri_emotions_sheet.png"

# Comparison crops of the 896x1200 sheet. They exclude the state labels and
# the title; the Gemini sparkle in the depleted panel is masked separately.
PANELS: dict[str, tuple[int, int, int, int]] = {
    "idle": (0, 90, 448, 570),
    "joyful": (448, 90, 896, 570),
    "fierce": (0, 650, 448, 1130),
    "depleted": (448, 650, 896, 1130),
}
# Sheet coordinates of the generator watermark (sparkle) - neutralised in both
# images so it can neither help nor hurt.
SPARKLE = (748, 1050, 805, 1110)

WORK = (192, 204)  # analysis size (w, h); 448x480 crops scale to this exactly

WEIGHTS = {
    "silhouette": 0.25,
    "structure": 0.25,
    "flow": 0.20,
    "colour": 0.15,
    "eyes": 0.15,
}


# ----------------------------------------------------------------- images


def load_panel(state: str) -> Image.Image:
    sheet = Image.open(SHEET).convert("RGB")
    box = PANELS[state]
    panel = sheet.crop(box)
    sx0, sy0, sx1, sy1 = SPARKLE
    bx0, by0, bx1, by1 = box
    if sx0 < bx1 and sx1 > bx0 and sy0 < by1 and sy1 > by0:
        fill = tuple(int(v) for v in background_colour(np.asarray(panel)))
        ImageDraw.Draw(panel).rectangle(
            (sx0 - bx0, sy0 - by0, sx1 - bx0, sy1 - by0), fill=fill
        )
    return panel


def background_colour(rgb: np.ndarray) -> np.ndarray:
    """Median of a 12 px border: the painted backdrop's typical colour."""
    b = 12
    border = np.concatenate(
        [
            rgb[:b].reshape(-1, 3),
            rgb[-b:].reshape(-1, 3),
            rgb[:, :b].reshape(-1, 3),
            rgb[:, -b:].reshape(-1, 3),
        ]
    )
    return np.median(border, axis=0)


def prepare_candidate(path: Path, reference: Image.Image) -> Image.Image:
    """Composite a transparent render over the reference's backdrop colour and
    fit it to the reference panel's size (letterboxed, never stretched)."""
    img = Image.open(path)
    ref = np.asarray(reference)
    bg = tuple(int(v) for v in background_colour(ref))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        base = Image.new("RGBA", img.size, bg + (255,))
        img = Image.alpha_composite(base, img).convert("RGB")
    else:
        img = img.convert("RGB")
    return register(img, reference)


def character_box(img: Image.Image, bg_rgb: np.ndarray) -> tuple[float, float, float, float] | None:
    """Robust character bounds (2nd-98th percentile of foreground pixels)."""
    rgb = np.asarray(img.convert("RGB"))
    lab = to_lab(rgb)
    fg = foreground_mask(lab, to_lab(bg_rgb[None, None, :])[0, 0])
    ys, xs = np.nonzero(fg)
    if len(ys) < 50:
        return None
    return (
        float(np.percentile(xs, 2)),
        float(np.percentile(ys, 2)),
        float(np.percentile(xs, 98)),
        float(np.percentile(ys, 98)),
    )


def register(img: Image.Image, reference: Image.Image) -> Image.Image:
    """Scale and place the candidate so its character occupies the same box
    as the reference character (uniform scale by height, centres aligned).

    Without this the score mostly measures camera framing. Registration is a
    similarity transform only - the candidate is never stretched - so any
    difference in proportions still counts against it."""
    ref = np.asarray(reference)
    bg = background_colour(ref)
    fill = tuple(int(v) for v in bg)
    tw, th = reference.size
    rb = character_box(reference, bg)
    # An opaque candidate (e.g. a video frame) has its own backdrop; find its
    # character against that, not against the reference's.
    cb = character_box(img, background_colour(np.asarray(img.convert("RGB"))))
    if rb is None or cb is None:
        scale = min(tw / img.width, th / img.height)
        dx = (tw - img.width * scale) / 2
        dy = (th - img.height * scale) / 2
    else:
        scale = (rb[3] - rb[1]) / max(cb[3] - cb[1], 1)
        dx = (rb[0] + rb[2]) / 2 - (cb[0] + cb[2]) / 2 * scale
        dy = (rb[1] + rb[3]) / 2 - (cb[1] + cb[3]) / 2 * scale
    return img.transform(
        (tw, th),
        Image.AFFINE,
        (1 / scale, 0, -dx / scale, 0, 1 / scale, -dy / scale),
        resample=Image.BICUBIC,
        fillcolor=fill,
    )


# --------------------------------------------------------------- features


def to_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = c @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def box_blur(x: np.ndarray, r: int) -> np.ndarray:
    if r <= 0:
        return x
    k = 2 * r + 1
    pad = np.pad(x, ((r, r), (r, r)), mode="edge")
    c = pad.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def foreground_mask(lab: np.ndarray, bg_lab: np.ndarray) -> np.ndarray:
    """Character pixels: clearly brighter, darker or more saturated than the
    backdrop. Lightly smoothed so brush noise does not fragment it."""
    dL = lab[..., 0] - bg_lab[0]
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    bg_chroma = math.hypot(bg_lab[1], bg_lab[2])
    m = (dL > 14) | (dL < -9) | (chroma - bg_chroma > 16)
    m = box_blur(m.astype(np.float64), 2) > 0.5
    return m


def ssim(a: np.ndarray, b: np.ndarray, r: int = 4) -> float:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    c1, c2 = (0.01 * 100) ** 2, (0.03 * 100) ** 2
    mu_a, mu_b = box_blur(a, r), box_blur(b, r)
    va = box_blur(a * a, r) - mu_a**2
    vb = box_blur(b * b, r) - mu_b**2
    cov = box_blur(a * b, r) - mu_a * mu_b
    s = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / (
        (mu_a**2 + mu_b**2 + c1) * (va + vb + c2)
    )
    return float(np.clip(s.mean(), 0, 1))


def orientation_histograms(L: np.ndarray, cell: int = 12, bins: int = 9) -> np.ndarray:
    """HOG-style cell histograms of gradient orientation weighted by
    magnitude: captures the direction flames and strokes flow in."""
    g = box_blur(L, 1)
    gy, gx = np.gradient(g)
    mag = np.hypot(gx, gy)
    ang = (np.arctan2(gy, gx) % math.pi) / math.pi * bins
    h, w = L.shape
    ch, cw = h // cell, w // cell
    out = np.zeros((ch, cw, bins))
    idx = np.minimum(ang.astype(int), bins - 1)
    for i in range(ch):
        for j in range(cw):
            sl = (slice(i * cell, (i + 1) * cell), slice(j * cell, (j + 1) * cell))
            out[i, j] = np.bincount(idx[sl].ravel(), weights=mag[sl].ravel(), minlength=bins)
    return out


def flow_similarity(La: np.ndarray, Lb: np.ndarray) -> float:
    ha, hb = orientation_histograms(La), orientation_histograms(Lb)
    na = np.linalg.norm(ha, axis=-1)
    nb = np.linalg.norm(hb, axis=-1)
    dot = (ha * hb).sum(-1)
    cos = np.where((na > 1e-6) & (nb > 1e-6), dot / (na * nb + 1e-9), 0.0)
    w = np.maximum(na, nb)
    if w.sum() < 1e-9:
        return 0.0
    # Cosine of orientation pattern, weighted by how much edge there is, times
    # agreement in edge energy (a blank region against a busy one scores 0).
    energy = 1 - np.abs(na - nb) / (na + nb + 1e-9)
    return float(((cos * energy) * w).sum() / w.sum())


def colour_similarity(lab_a, mask_a, lab_b, mask_b) -> float:
    """1 - normalised 1D Wasserstein distance per Lab channel over the
    character pixels (quantile matching)."""
    if mask_a.sum() < 20 or mask_b.sum() < 20:
        return 0.0
    q = np.linspace(0.02, 0.98, 49)
    scale = np.array([100.0, 80.0, 80.0])
    d = 0.0
    for ch in range(3):
        qa = np.quantile(lab_a[..., ch][mask_a], q)
        qb = np.quantile(lab_b[..., ch][mask_b], q)
        d += np.abs(qa - qb).mean() / scale[ch]
    d /= 3
    return float(max(0.0, 1 - d * 2.5))


def eye_blobs(lab: np.ndarray, fg: np.ndarray) -> list[tuple[float, float, float]]:
    """The two largest very dark compact blobs in the upper 70% of the
    character's box: (cx, cy, area) normalised to the image."""
    h, w = fg.shape
    ys, xs = np.nonzero(fg)
    if len(ys) == 0:
        return []
    y0, y1 = ys.min(), ys.max()
    limit = y0 + 0.7 * (y1 - y0)
    dark = (lab[..., 0] < 22) & (np.arange(h)[:, None] < limit)
    # Connected components (4-neighbour flood fill; images are small).
    seen = np.zeros_like(dark)
    blobs = []
    for sy, sx in zip(*np.nonzero(dark)):
        if seen[sy, sx]:
            continue
        stack = [(sy, sx)]
        seen[sy, sx] = True
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and dark[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(pts) < 6:
            continue
        p = np.array(pts, dtype=np.float64)
        bh = np.ptp(p[:, 0]) + 1
        bw = np.ptp(p[:, 1]) + 1
        fill = len(pts) / (bh * bw)
        aspect = min(bh, bw) / max(bh, bw)
        if fill < 0.45 or aspect < 0.35:
            continue  # strokes and limbs, not eyes
        blobs.append((p[:, 1].mean() / w, p[:, 0].mean() / h, len(pts) / (w * h)))
    blobs.sort(key=lambda b: -b[2])
    return blobs[:2]


def eye_similarity(lab_a, fg_a, lab_b, fg_b) -> float:
    ea, eb = eye_blobs(lab_a, fg_a), eye_blobs(lab_b, fg_b)
    if len(ea) < 2 and len(eb) < 2:
        return 1.0  # neither shows open dark eyes (e.g. joyful smiles)
    if len(ea) < 2 or len(eb) < 2:
        return 0.0
    ea.sort()
    eb.sort()
    score = 0.0
    for (xa, ya, aa), (xb, yb, ab) in zip(ea, eb):
        pos = math.hypot(xa - xb, ya - yb) / 0.12  # 12% of the frame = 0
        size = abs(math.sqrt(aa) - math.sqrt(ab)) / max(math.sqrt(aa), 1e-6)
        score += max(0.0, 1 - pos) * 0.6 + max(0.0, 1 - size) * 0.4
    return score / 2


def raw_components(ref: Image.Image, cand: Image.Image) -> dict[str, float]:
    ra = np.asarray(ref.resize(WORK, Image.LANCZOS))
    rb = np.asarray(cand.resize(WORK, Image.LANCZOS))
    la, lb = to_lab(ra), to_lab(rb)
    # Each image is segmented against its own backdrop. For a transparent
    # render composited over the reference colour the two are identical.
    bga = to_lab(background_colour(ra)[None, None, :])[0, 0]
    bgb = to_lab(background_colour(rb)[None, None, :])[0, 0]
    ma, mb = foreground_mask(la, bga), foreground_mask(lb, bgb)
    inter = (ma & mb).sum()
    union = (ma | mb).sum()
    silhouette = float(inter / union) if union else 0.0
    # Structure on low-pass luminance: placement of light and dark masses.
    sa = box_blur(la[..., 0], 2)
    sb = box_blur(lb[..., 0], 2)
    return {
        "silhouette": silhouette,
        "structure": ssim(sa, sb),
        "flow": flow_similarity(la[..., 0], lb[..., 0]),
        "colour": colour_similarity(la, ma, lb, mb),
        "eyes": eye_similarity(la, ma, lb, mb),
    }


def combine(c: dict[str, float]) -> float:
    return sum(WEIGHTS[k] * c[k] for k in WEIGHTS)


# ---------------------------------------------------------------- anchors


def degraded_copy(ref: Image.Image) -> Image.Image:
    img = ref.filter(ImageFilter.GaussianBlur(2))
    img = img.transform(img.size, Image.AFFINE, (1, 0, -3, 0, 1, -3), fillcolor=tuple(
        int(v) for v in background_colour(np.asarray(ref))))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=60)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def generic_fire_spirit(ref: Image.Image) -> Image.Image:
    """A competent but generic fire spirit in the reference's own bounding box
    and colours: teardrop flame head, two black eyes, stick body."""
    rgb = np.asarray(ref)
    lab = to_lab(rgb)
    bg = background_colour(rgb)
    fg = foreground_mask(lab, to_lab(bg[None, None, :])[0, 0])
    ys, xs = np.nonzero(fg)
    img = Image.new("RGB", ref.size, tuple(int(v) for v in bg))
    if len(ys) == 0:
        return img
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cx = (x0 + x1) / 2
    hw = (x1 - x0) * 0.35
    head_cy = y0 + (y1 - y0) * 0.42
    bright = rgb[fg]
    lum = bright.mean(axis=1)
    flame = tuple(int(v) for v in bright[lum > np.quantile(lum, 0.7)].mean(axis=0))
    d = ImageDraw.Draw(img)
    d.polygon(
        [(cx, y0), (cx + hw, head_cy), (cx, head_cy + hw), (cx - hw, head_cy)],
        fill=flame,
    )
    d.ellipse((cx - hw, head_cy - hw * 0.6, cx + hw, head_cy + hw), fill=flame)
    er = hw * 0.2
    for ex in (cx - hw * 0.4, cx + hw * 0.4):
        d.ellipse((ex - er, head_cy - er, ex + er, head_cy + er), fill=(10, 8, 8))
    d.line((cx, head_cy + hw, cx, y1 - (y1 - y0) * 0.1), fill=(25, 18, 14), width=6)
    for sx in (-1, 1):
        d.line((cx, y1 - (y1 - y0) * 0.1, cx + sx * hw * 0.3, y1), fill=(25, 18, 14), width=4)
        d.line((cx, head_cy + hw * 1.3, cx + sx * hw * 0.6, head_cy + hw * 1.8), fill=(25, 18, 14), width=4)
    return img.filter(ImageFilter.GaussianBlur(1.5))


def score(state: str, candidate: Path | None = None, extra: dict[str, Path] | None = None) -> dict:
    ref = load_panel(state)
    hi = combine(raw_components(ref, degraded_copy(ref)))
    lo = combine(raw_components(ref, generic_fire_spirit(ref)))

    def calibrate(raw: float) -> float:
        if hi - lo < 1e-6:
            return 0.0
        return float(np.clip((raw - lo) / (hi - lo) * 100, 0, 100))

    out: dict = {
        "state": state,
        "panel_box": PANELS[state],
        "weights": WEIGHTS,
        "anchor_raw": {"degraded_reference_100": hi, "generic_fire_spirit_0": lo},
    }
    items = dict(extra or {})
    if candidate is not None:
        items = {"candidate": candidate, **items}
    for name, path in items.items():
        cand = prepare_candidate(Path(path), ref)
        comps = raw_components(ref, cand)
        raw = combine(comps)
        out[name] = {
            "path": str(path),
            "components": comps,
            "raw": raw,
            "calibrated": calibrate(raw),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", choices=sorted(PANELS), required=True)
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--extra", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    extra = dict(e.split("=", 1) for e in a.extra)
    res = score(a.state, a.candidate, {k: Path(v) for k, v in extra.items()})
    text = json.dumps(res, indent=2)
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
