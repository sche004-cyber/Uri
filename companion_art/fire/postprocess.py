"""Post-process raw Ember renders: painterly glow, glow-derived alpha, packing.

    python -B companion_art/fire/postprocess.py frames <raw_clip_dir> <out_dir>
    python -B companion_art/fire/postprocess.py pack <frames_dir> <atlas.webp> --cell 320 --cols 8

Why outside Blender: bloom on a transparent film has no alpha to live in -
the glow around the flames would vanish in the sprite. Here the glow is
computed from the premultiplied colour and its luminance becomes alpha, so a
sprite composited over any URI background keeps its halo. The same code runs
for the fidelity renders and the app sprites, so what is scored is what ships.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def load_premul(path: Path) -> np.ndarray:
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return a


def blur(x: np.ndarray, radius: float) -> np.ndarray:
    chans = []
    for c in range(x.shape[-1]):
        im = Image.fromarray(np.clip(x[..., c] * 255, 0, 255).astype(np.uint8), "L")
        chans.append(np.asarray(im.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32) / 255.0)
    return np.stack(chans, -1)


def glow(premul: np.ndarray) -> np.ndarray:
    """Three-octave bloom from the bright, warm parts. Returns premultiplied
    RGBA where the halo's alpha follows its luminance."""
    h = premul.shape[0]
    rgb = premul[..., :3]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bright = rgb * np.clip((lum[..., None] - 0.5) / 0.5, 0, 1)
    halo = (
        0.30 * blur(bright, h * 0.012)
        + 0.30 * blur(bright, h * 0.035)
        + 0.35 * blur(bright, h * 0.09)
    )
    out_rgb = rgb + halo
    halo_a = np.clip(halo @ np.array([0.40, 0.45, 0.15], dtype=np.float32) * 1.6, 0, 1)
    a = premul[..., 3]
    out_a = a + halo_a * (1 - a)
    out = np.concatenate([np.clip(out_rgb, 0, 1), out_a[..., None]], -1)
    return out


def to_straight(premul: np.ndarray) -> Image.Image:
    a = premul[..., 3:4]
    rgb = np.where(a > 1e-4, premul[..., :3] / np.maximum(a, 1e-4), 0)
    arr = np.concatenate([np.clip(rgb, 0, 1), a], -1)
    return Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBA")


def frames(raw: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(raw.glob("f_*.png")):
        to_straight(glow(load_premul(f))).save(out / f.name, optimize=True)
        n += 1
    meta = raw / "render_meta.json"
    if meta.exists():
        (out / "render_meta.json").write_text(meta.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"POST {raw.name} {n} frames")


def pack(src: Path, atlas: Path, cell: int, cols: int, quality: int) -> dict:
    """Square cells, row-major; the character is scaled to fit the cell
    (renders are 448x480 portrait: centred, never stretched)."""
    files = sorted(src.glob("f_*.png"))
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGBA", (cell * cols, cell * rows), (0, 0, 0, 0))
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        s = cell / max(im.width, im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        x = (i % cols) * cell + (cell - im.width) // 2
        y = (i // cols) * cell + (cell - im.height) // 2
        sheet.paste(im, (x, y))
    atlas.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(atlas, "WEBP", quality=quality, method=6, exact=True)
    info = {"file": atlas.name, "frames": len(files), "cell": cell, "cols": cols, "rows": rows,
            "bytes": atlas.stat().st_size}
    print("PACK", json.dumps(info))
    return info


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "frames":
        frames(Path(sys.argv[2]), Path(sys.argv[3]))
    elif cmd == "pack":
        args = sys.argv[2:]
        cell = int(args[args.index("--cell") + 1]) if "--cell" in args else 320
        cols = int(args[args.index("--cols") + 1]) if "--cols" in args else 8
        q = int(args[args.index("--quality") + 1]) if "--quality" in args else 88
        pack(Path(args[0]), Path(args[1]), cell, cols, q)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
