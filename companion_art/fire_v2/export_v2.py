"""Render every Ember V2 clip and pack the app's sprite atlases + manifest.

    python -B companion_art/fire_v2/export_v2.py [--quality 88] [clip ...]

Atlas format is V1's (uri_ui/assets/companions/ember/<clip>.webp, square
cells, row-major, straight alpha), so the player reads it unchanged. V2 adds
per clip:
  "eye_offsets": per-frame [dx, dy] of the eyes in cell pixels relative to
                 frame 0 (the head breathes; the blink patch follows it);
  "blink":       the lid patch: where it sits in the cell at frame 0 ("rect")
                 and where each lid level is in blink.webp ("src").
Blinks are scheduled at runtime (irregular), so they are not baked into the
loops.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from animate import Panel, ell  # noqa: E402
from render_clips import EXPR, face_at  # noqa: E402

REPO = HERE.parents[1]
OUT = REPO / "uri_ui" / "assets" / "companions" / "ember"
LIMIT = 4096


class Framing:
    """Panel pixels -> cell pixels: a square of `side` panel pixels around the
    body axis with the feet at `feet_at` of the height, scaled to the cell."""

    def __init__(self, panel: Panel, cell: int):
        self.panel = panel
        self._aura: dict[float, np.ndarray | None] = {}
        side = EXPR["frame"]["side"]
        feet = max(f[1] for f in panel.r["feet"])
        self.x0 = panel.r["neck"][0] - side / 2
        self.y0 = feet - EXPR["frame"]["feet_at"] * side
        self.side = side
        self.s = cell / side
        self.cell = cell

    def place(self, img: np.ndarray) -> np.ndarray:
        """Panel-pixel image -> the square frame (zeros outside the panel)."""
        h, w = img.shape[:2]
        big = np.zeros((self.side, self.side) + img.shape[2:], np.float32)
        ox, oy = int(round(-self.x0)), int(round(-self.y0))
        ya, yb = max(oy, 0), min(oy + h, self.side)
        xa, xb = max(ox, 0), min(ox + w, self.side)
        big[ya:yb, xa:xb] = img[ya - oy:yb - oy, xa - ox:xb - ox]
        return big

    def aura(self, strength: float) -> np.ndarray | None:
        """The painting's own background as a soft pool of light behind the
        character, fading to nothing well inside the cell. Inside it the
        companion looks exactly as on the sheet (translucent flame strokes and
        dark parts keep the contrast they were painted with); outside it the
        app canvas shows. Premultiplied, square frame."""
        if strength <= 0:
            return None
        pn = self.panel
        h, w = pn.h, pn.w
        ox, oy = int(round(-self.x0)), int(round(-self.y0))
        # background plate, extended past the panel by its edge colours
        pad = ((max(oy, 0), max(self.side - oy - h, 0)), (max(ox, 0), max(self.side - ox - w, 0)), (0, 0))
        bg = np.pad(pn.bg, pad, mode="edge")
        y0, x0 = max(-oy, 0), max(-ox, 0)
        bg = bg[y0:y0 + self.side, x0:x0 + self.side]
        bg = ndi.gaussian_filter(bg, (8, 8, 0))
        hx, hy, hrx, hry = pn.r["head"]
        fy = max(f[1] for f in pn.r["feet"])
        top = hy - hry * 1.6
        cx = (pn.r["neck"][0] + hx) / 2 - self.x0
        cy = (top + fy) / 2 - self.y0
        yy, xx = np.mgrid[0:self.side, 0:self.side].astype(np.float32)
        d = np.sqrt(((xx - cx) / (0.56 * self.side)) ** 2 + ((yy - cy) / (0.58 * self.side)) ** 2)
        u = np.clip((d - 0.55) / 0.45, 0, 1)
        a = strength * (1 - u * u * (3 - 2 * u))
        # always zero at the cell border: never a hard edge in the app
        edge = np.minimum.reduce([xx, self.side - 1 - xx, yy, self.side - 1 - yy])
        e = np.clip(edge / (0.12 * self.side), 0, 1)
        a = a * e * e * (3 - 2 * e)
        return np.dstack([bg * a[..., None], a]).astype(np.float32)

    def big_frame(self, pm: np.ndarray, aura: float = 0.0) -> np.ndarray:
        big = self.place(pm)
        au = self._aura.get(aura)
        if au is None and aura > 0:
            au = self._aura[aura] = self.aura(aura)
        if au is not None:
            big = big + au * (1 - big[..., 3:4])
        return big

    def cell_image(self, pm: np.ndarray, aura: float = 0.0) -> np.ndarray:
        """Premultiplied panel frame -> premultiplied cell (area-averaged)."""
        big = self.big_frame(pm, aura)
        # downsample premultiplied (no dark fringes), Lanczos per channel
        out = [np.asarray(Image.fromarray(big[..., c]).resize((self.cell, self.cell), Image.LANCZOS))
               for c in range(4)]
        return np.clip(np.dstack(out), 0, 1)

    def pt(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.x0) * self.s, (y - self.y0) * self.s


def straight(pm: np.ndarray) -> np.ndarray:
    a = pm[..., 3:4]
    rgb = np.where(a > 1e-4, pm[..., :3] / np.maximum(a, 1e-4), 0)
    return (np.dstack([rgb.clip(0, 1), a]) * 255 + 0.5).astype(np.uint8)


def pack(cells: list[np.ndarray], path: Path, cell: int, quality: int) -> dict:
    n = len(cells)
    limit = LIMIT // cell
    cols = min(limit, math.ceil(math.sqrt(n * 1.5)))
    rows = math.ceil(n / cols)
    if rows > limit:
        raise SystemExit(f"{path.name}: {n} frames do not fit")
    sheet = np.zeros((rows * cell, cols * cell, 4), np.uint8)
    for i, c in enumerate(cells):
        r, k = divmod(i, cols)
        sheet[r * cell:(r + 1) * cell, k * cell:(k + 1) * cell] = straight(c)
    Image.fromarray(sheet, "RGBA").save(path, "WEBP", quality=quality, method=6, exact=True)
    return {"file": path.name, "frames": n, "cell": cell, "cols": cols, "rows": rows,
            "bytes": path.stat().st_size}


def blink_patches(name: str, spec: dict, pn: Panel, fr: Framing):
    """Lid patches at frame-0 geometry for each blink level (cell pixels)."""
    levels = spec.get("blink")
    if not levels:
        return None
    # box around both eyes (+ margin) in panel pixels at frame 0
    pn.frame(0.0, spec["motion"], face_at(spec.get("face", {}), 0.0))
    dx, dy = pn.last_field
    xs, ys = [], []
    m = 10 + max(abs(v) for v in spec.get("face", {}).get("gaze", (0, 0)))
    for (cx, cy, rx, ry) in pn.r["eyes"]:
        ox, oy = dx[int(cy), int(cx)], dy[int(cy), int(cx)]
        xs += [cx + ox - rx - m, cx + ox + rx + m]
        ys += [cy + oy - ry - m, cy + oy + ry + m]
    x0, y0 = fr.pt(min(xs), min(ys))
    x1, y1 = fr.pt(max(xs), max(ys))
    x0, y0 = int(math.floor(x0)), int(math.floor(y0))
    x1, y1 = int(math.ceil(x1)), int(math.ceil(y1))
    # the patch only replaces the eye sockets (soft mask), never the
    # surrounding head, so flicker around it cannot jump when it shows
    mask = np.zeros((pn.h, pn.w), np.float32)
    gx, gy = spec.get("face", {}).get("gaze", (0, 0))
    es = spec.get("face", {}).get("eye_scale", 1.0)
    for (cx, cy, rx, ry) in pn.r["eyes"]:
        g = ell(pn.xx - dx, pn.yy - dy, cx + gx / 2, cy + gy / 2,
                rx * es + 4 + abs(gx) / 2, ry * es + 4 + abs(gy) / 2) <= 1
        mask = np.maximum(mask, g.astype(np.float32))
    mask = ndi.gaussian_filter(mask, 1.2)
    mpm = np.dstack([mask, mask, mask, mask])
    mcell = fr.cell_image(mpm)[..., 3]
    out = []
    base_lid = spec.get("face", {}).get("lid", 0.0)
    for lv in levels:
        f = dict(face_at(spec.get("face", {}), 0.0))
        f["lid"] = max(lv, base_lid)
        pm = pn.frame(0.0, spec["motion"], f)
        c = fr.cell_image(pm, spec["motion"].get("aura", 0.0))
        c = c * mcell[..., None]
        out.append(c[y0:y1, x0:x1])
    return {"rect": [x0, y0, x1 - x0, y1 - y0], "levels": levels}, out


def main() -> None:
    args = sys.argv[1:]
    quality = int(args[args.index("--quality") + 1]) if "--quality" in args else 88
    only = [a for a in args if not a.startswith("--") and not a.isdigit()]
    cell = EXPR["cell"]
    OUT.mkdir(parents=True, exist_ok=True)
    old = OUT / "manifest.json"
    manifest = {"fps": EXPR["fps"], "cell": cell, "source": "companion_art/fire_v2 (painting-derived 2.5D)",
                "clips": {}}
    if only and old.exists():
        prev = json.loads(old.read_text(encoding="utf-8"))
        if prev.get("source", "").startswith("companion_art/fire_v2"):
            manifest["clips"] = prev["clips"]
            # keep the blink atlas of the clips not re-rendered (review R1-02)
            if "blink_atlas" in prev:
                manifest["blink_atlas"] = prev["blink_atlas"]
    panels: dict[str, Panel] = {}
    blink_cells: list[tuple[str, list[np.ndarray]]] = []
    for name, spec in EXPR["clips"].items():
        if only and name not in only:
            continue
        stale = OUT / f"{name}.webp"
        if spec.get("ship", True) is False:
            if stale.exists():
                stale.unlink()
            manifest["clips"].pop(name, None)
            continue
        pn = panels.get(spec["panel"]) or panels.setdefault(spec["panel"], Panel(spec["panel"]))
        fr = Framing(pn, cell)
        n = spec["loop"]
        cells, offs = [], []
        e0 = None
        for i in range(n):
            t = i / n
            pm = pn.frame(t, spec["motion"], face_at(spec.get("face", {}), t))
            dx, dy = pn.last_field
            cx, cy = pn.r["eyes"][0][:2]
            e = (float(dx[int(cy), int(cx)]) * fr.s, float(dy[int(cy), int(cx)]) * fr.s)
            e0 = e0 or e
            offs.append([round(e[0] - e0[0], 2), round(e[1] - e0[1], 2)])
            cells.append(fr.cell_image(pm, spec["motion"].get("aura", 0.0)))
        info = pack(cells, OUT / f"{name}.webp", cell, quality)
        info["sha256"] = hashlib.sha256((OUT / f"{name}.webp").read_bytes()).hexdigest()
        info["eye_offsets"] = offs
        b = blink_patches(name, spec, pn, fr)
        if b:
            info["blink"] = b[0]
            blink_cells.append((name, b[1]))
        else:
            info.pop("blink", None)
        manifest["clips"][name] = info
        print(f"{name}: {n} frames, {info['bytes'] / 1048576:.2f} MiB", flush=True)
        if name == "idle":
            still = straight(cells[0])
            Image.fromarray(still, "RGBA").resize((192, 192), Image.LANCZOS).save(
                OUT / "thumbnail.webp", "WEBP", quality=90, method=6, exact=True)
            manifest["thumbnail"] = "thumbnail.webp"
    if blink_cells:
        write_blinks(manifest, blink_cells, quality)
    if "thumbnail" not in manifest and (OUT / "thumbnail.webp").exists():
        manifest["thumbnail"] = "thumbnail.webp"
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    total = sum(c["bytes"] for c in manifest["clips"].values())
    print(f"EXPORT {len(manifest['clips'])} clips, {total / 1048576:.2f} MiB on disk")


def write_blinks(manifest: dict, blink_cells, quality: int) -> None:
    """One small atlas with every clip's lid patches, one row per clip."""
    path = OUT / "blink.webp"
    # keep rows of clips not re-rendered in this run
    rows: dict[str, list[np.ndarray]] = {}
    if path.exists() and "blink_atlas" in manifest:
        sheet = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255
        for name, info in manifest["clips"].items():
            b = info.get("blink")
            if not b or name in dict(blink_cells):
                continue
            w, h = b["rect"][2], b["rect"][3]
            got = []
            for sx, sy in b["src"]:
                p = sheet[sy:sy + h, sx:sx + w].copy()
                p[..., :3] *= p[..., 3:]
                got.append(p)
            rows[name] = got
    rows.update(dict(blink_cells))
    width = max(sum(p.shape[1] for p in ps) for ps in rows.values())
    height = sum(ps[0].shape[0] for ps in rows.values())
    sheet = np.zeros((height, width, 4), np.uint8)
    y = 0
    for name, ps in rows.items():
        x = 0
        src = []
        for p in ps:
            h, w = p.shape[:2]
            sheet[y:y + h, x:x + w] = straight(p)
            src.append([x, y])
            x += w
        manifest["clips"][name]["blink"]["src"] = src
        y += ps[0].shape[0]
    Image.fromarray(sheet, "RGBA").save(path, "WEBP", quality=quality, method=6, exact=True)
    manifest["blink_atlas"] = {"file": "blink.webp", "bytes": path.stat().st_size,
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    main()
