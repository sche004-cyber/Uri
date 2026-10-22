"""Depleted haze probe (Ember V2.1 final, owner requirement: the haze must not
read as a grey patch or a rectangular region on light desktops).

Renders depleted frames for each candidate stage, composites them over white,
mid grey, blue and the app's dark canvas, and measures on white:
  footprint_pct  - share of the cell where the background is darkened by
                   >= 6 % (about 15/255) away from the character
  outside_circle - darkening >= 6 % outside the central circle (radius 0.45 of
                   the side): any such pixel makes the haze read as a square
  corner_max     - strongest darkening in the four corner squares (side/6)
  fill_ratio     - footprint area / its bounding box (ellipse ~0.79, square 1.0)

Gates on the SHIPPED depleted stage (expressions.json), worst frame:
  H1 outside_circle_px == 0   (no darkening outside the circle: never square)
  H2 corner_max <= 0.02       (corners stay clear)
  H3 footprint_pct <= 15      (a halo near the figure, not a patch)

    python -B scripts/fire_companion/haze_probe_v21.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "fire_companion"))
import critique_pack_v21 as cp  # noqa: E402

GLOW = cp.GLOW
CANDIDATES = {
    "h0_current": {"glow": GLOW, "texture": True, "strength": 0.6, "pool": [0.35, 0.95], "edge": 0.08, "edge_margin": 0.03},
    "h1_pool_tight": {"glow": GLOW, "texture": True, "strength": 0.6, "pool": [0.15, 0.70], "edge": 0.08, "edge_margin": 0.03},
    "h2_pool_tighter": {"glow": GLOW, "texture": True, "strength": 0.6, "pool": [0.10, 0.60], "edge": 0.08, "edge_margin": 0.03},
    "h3_tight_45": {"glow": GLOW, "texture": True, "strength": 0.45, "pool": [0.15, 0.70], "edge": 0.08, "edge_margin": 0.03},
    "h4_none": {"glow": GLOW, "strength": 0.0},
    "shipped": cp.EXPR["clips"]["depleted"].get("stage", cp.EXPR.get("stage", {})),
}
BACKS = {"white": (0.96, 0.96, 0.96), "grey": (0.5, 0.5, 0.5), "blue": (0.12, 0.35, 0.8), "dark": tuple(cp.CANVAS)}


def over(pm: np.ndarray, rgb) -> np.ndarray:
    return pm[..., :3] + (1 - pm[..., 3:4]) * np.array(rgb, np.float32)


def metrics(pm: np.ndarray, char_a: np.ndarray) -> dict:
    n = pm.shape[0]
    comp = over(pm, (1, 1, 1))
    dark = 1 - comp.mean(2)
    away = ~ndi.binary_dilation(char_a > 0.05, iterations=6)
    fp = (dark >= 0.06) & away
    yy, xx = np.mgrid[0:n, 0:n]
    outside = np.hypot(xx - n / 2, yy - n / 2) > 0.45 * n
    k = n // 6
    corners = np.concatenate([dark[:k, :k].ravel(), dark[:k, -k:].ravel(), dark[-k:, :k].ravel(), dark[-k:, -k:].ravel()])
    ys, xs = np.nonzero(fp)
    fill = float(fp.sum() / ((np.ptp(ys) + 1) * (np.ptp(xs) + 1))) if len(ys) else 0.0
    return {"footprint_pct": round(100 * float(fp.mean()), 2),
            "outside_circle_px": int((fp & outside).sum()),
            "corner_max": round(float(corners.max()), 4),
            "fill_ratio": round(fill, 3),
            "max_alpha_away": round(float((pm[..., 3] * away).max()), 3)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "docs/companions/fire/v21/evidence/final/haze")
    ap.add_argument("--frames", type=int, nargs="*", default=[0, 24, 48])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rd = cp.Renderer()
    frame = cp.EXPR["frame"]
    char = {i: rd.cell("depleted", i, frame, {"strength": 0.0}) for i in a.frames}
    res, rows = {}, []
    for name, st in CANDIDATES.items():
        cells = [rd.cell("depleted", i, frame, st) for i in a.frames]
        ms = [metrics(c, char[i][..., 3]) for c, i in zip(cells, a.frames)]
        res[name] = {"stage": st, "worst": {k: max(m[k] for m in ms) for k in ms[0]}, "frames": ms}
        rows.append(np.concatenate([over(cells[0], b) for b in BACKS.values()], 1))
        print(name, res[name]["worst"])
    w = res["shipped"]["worst"]
    gates = {"H1_outside_circle": w["outside_circle_px"] == 0, "H2_corners": w["corner_max"] <= 0.02,
             "H3_footprint": w["footprint_pct"] <= 15}
    print("shipped gates:", gates)
    sheet = (np.concatenate(rows, 0).clip(0, 1) * 255).astype(np.uint8)
    Image.fromarray(sheet).save(a.out / "haze_candidates.jpg", quality=90)
    (a.out / "haze_probe.json").write_text(json.dumps({"gates_shipped": gates, "rows": list(CANDIDATES), "columns": list(BACKS), "results": res}, indent=1))


if __name__ == "__main__":
    main()
