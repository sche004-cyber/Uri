"""Automated fidelity of Ember V2 animation frames (regression check, AC-2c).

For each reference state, every `--every`-th frame of its clip is rendered at
the panel's pixel frame, composited over the panel's own background plate
(estimated by companion_art/fire_v2/layers.py) and scored in place against the
reference panel with fidelity_score.py --aligned. Reports median and minimum
over the loop (the minimum is the frame furthest from the painting).

    python -B scripts/fire_companion/score_v2.py [--every 6] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "fire_companion"))
sys.path.insert(0, str(REPO / "companion_art" / "fire_v2"))
import fidelity_score as fs  # noqa: E402
from render_clips import EXPR, face_at, Panel  # noqa: E402
from animate import RIG  # noqa: E402

STATES = ["idle", "joyful", "fierce", "depleted"]


def window_image(state: str, pm: np.ndarray, bg: np.ndarray) -> Image.Image:
    """Frame (premultiplied, panel crop) over its background plate, placed
    into the scorer's comparison window of the sheet."""
    sx0, sy0, sx1, sy1 = fs.PANELS[state]
    cx0, cy0, cx1, cy1 = RIG[state]["crop"]
    base = np.asarray(fs.load_panel(state)).astype(np.float32) / 255
    comp = pm[..., :3] + bg * (1 - pm[..., 3:4])
    # overlap of crop and window in sheet coordinates
    ox0, oy0 = max(sx0, cx0), max(sy0, cy0)
    ox1, oy1 = min(sx1, cx1), min(sy1, cy1)
    base[oy0 - sy0:oy1 - sy0, ox0 - sx0:ox1 - sx0] = comp[oy0 - cy0:oy1 - cy0, ox0 - cx0:ox1 - cx0]
    return Image.fromarray((base.clip(0, 1) * 255 + 0.5).astype(np.uint8))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=6)
    ap.add_argument("--out", type=Path, default=REPO / "docs/companions/fire/v2/evidence/fidelity/auto")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for state in STATES:
        spec = EXPR["clips"][state]
        pn = Panel(spec["panel"])
        bg = np.load(REPO / f"companion_art/fire_v2/work/{spec['panel']}_layers.npz")["bg"].astype(np.float32)
        n = spec["loop"]
        rows = []
        worst = None
        for i in range(0, n, a.every):
            pm = pn.frame(i / n, spec["motion"], face_at(spec.get("face", {}), i / n))
            img = window_image(state, pm, bg)
            p = a.out / f"{state}_{i:03d}.png"
            img.save(p)
            r = fs.score(state, p, aligned=True)["candidate"]
            rows.append({"frame": i, "calibrated_unclamped": round(r["calibrated_unclamped"], 2),
                         "components": {k: round(v, 4) for k, v in r["components"].items()}})
            if worst is None or r["calibrated_unclamped"] < worst[1]:
                worst = (i, r["calibrated_unclamped"])
            if i:
                p.unlink()  # keep frame 0 and the worst only
        vals = [r["calibrated_unclamped"] for r in rows]
        if worst[0] != 0:
            pm = pn.frame(worst[0] / n, spec["motion"], face_at(spec.get("face", {}), worst[0] / n))
            window_image(state, pm, bg).save(a.out / f"{state}_{worst[0]:03d}_worst.png")
        summary[state] = {"frames_scored": len(vals), "median": float(np.median(vals)), "min": min(vals),
                          "max": max(vals), "worst_frame": worst[0], "per_frame": rows}
        print(f"{state}: median {np.median(vals):.1f} min {min(vals):.1f} (frame {worst[0]}) max {max(vals):.1f}",
              flush=True)
    (a.out / "scores_v2.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
