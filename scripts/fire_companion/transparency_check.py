"""Ember transparency gates on the SHIPPED atlases (owner directive: URI UI V2 compatibility).

    python -B scripts/fire_companion/transparency_check.py [--out DIR]

Reads uri_ui/assets/companions/ember/manifest.json and every atlas it names,
decodes each cell exactly as stored (straight-alpha WebP) and checks every
frame of every clip, plus every blink patch, with no host mask:

  T1 border   - the outer 2 % band of the cell is transparent (alpha <= 2/255):
                no rectangle, no visible window boundary;
  T2 ring     - outside the central circle (radius 0.45 of the side) alpha
                stays <= 128/255: no opaque backdrop, atmosphere translucent;
  T3 opaque   - at most 25 % of the cell is opaque (alpha >= 250/255): the
                character, not a background;
  T4 matte    - no dark-matte fringe: among semi-transparent pixels
                (8 <= alpha < 128) next to opaque ones, the share whose
                straight colour is near black (max channel < 12/255) and not
                part of a dark painted area is reported (premultiplication
                errors show up as black rims on light desktops);
  T5 blink    - each blink patch is inside its cell and transparent outside
                the eye sockets' soft mask (checked like T1 on the patch edge).

It also writes contact sheets of each clip's frames 0, 1/3 and 2/3 composited
over synthetic backgrounds (black, white, saturated blue, mid grey, a warm
gradient, a checkerboard and a high-frequency noise texture) for visual review.
Thresholds are the same as uri_ui/test/living/ember_transparency_test.dart.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "uri_ui/assets/companions/ember"


def backgrounds(s: int) -> dict[str, np.ndarray]:
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32) / s
    rng = np.random.default_rng(7)
    noise = ndi.gaussian_filter(rng.random((s, s, 3)).astype(np.float32), (1.5, 1.5, 0))
    noise = (noise - noise.min()) / (noise.max() - noise.min())
    cb = ((np.floor(xx * 16) + np.floor(yy * 16)) % 2)[..., None] * 0.5 + 0.25
    return {
        "black": np.zeros((s, s, 3), np.float32),
        "white": np.full((s, s, 3), 0.96, np.float32),
        "blue": np.broadcast_to(np.array([0.12, 0.35, 0.78], np.float32), (s, s, 3)).copy(),
        "grey": np.full((s, s, 3), 0.5, np.float32),
        "gradient": np.dstack([0.2 + 0.7 * xx, 0.3 + 0.4 * yy, 0.9 - 0.6 * xx]),
        "checker": np.repeat(cb, 3, 2),
        "noise": noise,
    }


def cells(info: dict) -> list[np.ndarray]:
    sheet = np.asarray(Image.open(ASSETS / info["file"]).convert("RGBA")).astype(np.float32) / 255
    c = info["cell"]
    out = []
    for i in range(info["frames"]):
        r, k = divmod(i, info["cols"])
        out.append(sheet[r * c:(r + 1) * c, k * c:(k + 1) * c])
    return out


def gates(cell: np.ndarray) -> dict:
    s = cell.shape[0]
    a = cell[..., 3]
    band = max(2, round(s * 0.02))
    edge = np.zeros_like(a, bool)
    edge[:band] = edge[-band:] = True
    edge[:, :band] = edge[:, -band:] = True
    yy, xx = np.mgrid[0:s, 0:s]
    ring = np.hypot(xx - (s - 1) / 2, yy - (s - 1) / 2) / s > 0.45
    a8 = np.round(a * 255)
    semi = (a8 >= 8) & (a8 < 128) & ndi.binary_dilation(a8 >= 250, iterations=2)
    dark = cell[..., :3].max(2) < 12 / 255
    # dark painted areas (body, eyes, smoke) are legitimately dark at their rim
    painted_dark = ndi.binary_dilation((a8 >= 250) & dark, iterations=3)
    fringe = semi & dark & ~painted_dark
    return {
        "border_max": int(a8[edge].max()),
        "ring_max": int(a8[ring].max()),
        "opaque_frac": float((a8 >= 250).mean()),
        "matte_fringe_px": int(fringe.sum()),
        "semi_rim_px": int(semi.sum()),
    }


def main() -> None:
    global ASSETS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "docs/companions/fire/v21/evidence/transparency")
    ap.add_argument("--assets", type=Path, default=ASSETS, help="atlas folder to check (default: this tree's)")
    a = ap.parse_args()
    ASSETS = a.assets
    a.out.mkdir(parents=True, exist_ok=True)
    man = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    report: dict = {"manifest_source": man.get("source"), "stage": man.get("stage"), "clips": {}}
    ok = True
    for name, info in man["clips"].items():
        cs = cells(info)
        g = [gates(c) for c in cs]
        worst = {
            "border_max": max(x["border_max"] for x in g),
            "ring_max": max(x["ring_max"] for x in g),
            "opaque_frac_max": max(x["opaque_frac"] for x in g),
            "matte_fringe_px_max": max(x["matte_fringe_px"] for x in g),
            "semi_rim_px_median": float(np.median([x["semi_rim_px"] for x in g])),
        }
        passed = {
            "T1_border": worst["border_max"] <= 2,
            "T2_ring": worst["ring_max"] <= 128,
            "T3_opaque": worst["opaque_frac_max"] <= 0.25,
            "T4_matte": worst["matte_fringe_px_max"] <= max(5, 0.02 * worst["semi_rim_px_median"]),
        }
        ok &= all(passed.values())
        report["clips"][name] = {"frames": len(cs), "worst": worst, "pass": passed}
        # contact sheet: frames 0, n/3, 2n/3 over every background
        n = len(cs)
        bgs = backgrounds(cs[0].shape[0])
        rows = []
        for i in (0, n // 3, 2 * n // 3):
            c = cs[i]
            rows.append(np.concatenate([c[..., :3] * c[..., 3:] + b * (1 - c[..., 3:]) for b in bgs.values()], 1))
        Image.fromarray((np.concatenate(rows, 0).clip(0, 1) * 255 + 0.5).astype(np.uint8)).save(
            a.out / f"contrast_{name}.jpg", quality=85)
        print(name, worst, passed, flush=True)
    # T5 blink patches
    b = man.get("blink_atlas")
    if b:
        sheet = np.asarray(Image.open(ASSETS / b["file"]).convert("RGBA")).astype(np.float32) / 255
        res = {}
        for name, info in man["clips"].items():
            bl = info.get("blink")
            if not bl:
                continue
            x0, y0, w, h = bl["rect"]
            inside = x0 >= 0 and y0 >= 0 and x0 + w <= info["cell"] and y0 + h <= info["cell"]
            edges = []
            for sx, sy in bl["src"]:
                p = np.round(sheet[sy:sy + h, sx:sx + w, 3] * 255)
                edges.append(int(max(p[0].max(), p[-1].max(), p[:, 0].max(), p[:, -1].max())))
            res[name] = {"inside_cell": inside, "patch_edge_alpha_max": max(edges),
                         "pass": inside and max(edges) <= 2}
            ok &= res[name]["pass"]
        report["blink"] = res
        print("blink", res, flush=True)
    report["all_pass"] = bool(ok)
    (a.out / "transparency_gates.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("ALL PASS" if ok else "SOME GATES FAIL")


if __name__ == "__main__":
    main()
