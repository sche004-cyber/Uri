"""Re-runnable measurements behind 01_DIAGNOSIS_V21.md (review R1-07).

    python -B scripts/fire_companion/diag_v21.py [--out DIR]

1. Share of the character's alpha mass the app shows (frame 0 of each
   reference clip): the frame placed in the cell framing, weighted by the host's
   presence scale and SoftDisc (opaque to 0.72 of the box radius, zero at the
   box edge), for V2's framing and V2.1's.
2. V2 reproduction: frame 0 of idle rendered with V2's frame and no stage,
   through the WebP round trip, against cell 0 of the shipped V2 atlas
   (read from git history at b73bd26c).
3. Live check of the pack's app view (review R1-01): the live screenshot
   evidence/live/run1_first/first-05-idle-brain-ready.jpg (V2.1 painted build,
   idle) against app_view of idle frame 0 rendered at box sizes 240-340 px
   on the surround colour measured next to the disc; best box size, centre and
   mean absolute difference over the disc are reported, plus the same with the
   pack's flat #130F0B surround.
Writes docs/companions/fire/v21/evidence/diagnosis/diag_v21.json.
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "fire_companion"))
import critique_pack_v21 as cp  # noqa: E402
from export_v2 import Framing  # noqa: E402
from render_clips import EXPR, face_at, Panel  # noqa: E402

V21_FRAME = {"side": 643, "center": "panel"}


def visible_share(state: str, frame: dict) -> float:
    spec = EXPR["clips"][state]
    pn = Panel(spec["panel"])
    pm = pn.frame(0, spec["motion"], face_at(spec.get("face", {}), 0))
    fr = Framing(pn, 320, {}, frame)
    a = fr.place(pm)[..., 3]
    s = a.shape[0]
    yy, xx = np.mgrid[0:s, 0:s]
    # radius in units of the visible box half-side (the box is side / presence scale)
    r = np.hypot(xx - (s - 1) / 2, yy - (s - 1) / 2) / (s / 2 / cp.PRESENCE_SCALE)
    m = np.clip((1 - r) / 0.28, 0, 1)
    return float((a * m).sum() / pm[..., 3].sum())


def live_check() -> dict:
    shot = np.asarray(Image.open(REPO / "docs/companions/fire/v21/evidence/live/run1_first/"
                                 "first-05-idle-brain-ready.jpg").convert("RGB")).astype(np.float32) / 255
    cell = cp.Renderer().cell("idle", 0, V21_FRAME, cp.PAINTED)
    surround = shot[245:255, 455:465].reshape(-1, 3).mean(0)  # just left of the disc
    best = None
    for box in range(240, 342, 4):
        r = int(round(box * cp.PRESENCE_SCALE))
        big = np.dstack([np.asarray(Image.fromarray(cell[..., c]).resize((r, r), Image.BILINEAR)) for c in range(4)])
        o = (r - box) // 2
        big = big[o:o + box, o:o + box] * cp_mask(box)[..., None]
        for cx in range(622, 644, 2):
            for cy in range(236, 262, 2):
                y0, x0 = cy - box // 2, cx - box // 2
                crop = shot[y0:y0 + box, x0:x0 + box]
                if crop.shape[:2] != (box, box):
                    continue
                inner = cp_mask(box) > 0.5
                for name, bg in (("measured", surround), ("pack_130F0B", cp.CANVAS)):
                    rgb = big[..., :3] + bg * (1 - big[..., 3:])
                    d = float(np.abs(rgb - crop)[inner].mean())
                    if name == "measured" and (best is None or d < best["mad_measured"]):
                        best = {"box_px": box, "centre": [cx, cy], "mad_measured": round(d, 4)}
                    if name == "pack_130F0B" and best and best["box_px"] == box and best["centre"] == [cx, cy]:
                        best["mad_pack_canvas"] = round(d, 4)
    best["surround_rgb_255"] = [round(float(v) * 255, 1) for v in surround]
    best["note"] = "live frame index unknown (animation), so residual includes motion; inner disc only"
    return best


def cp_mask(box: int) -> np.ndarray:
    yy, xx = np.mgrid[0:box, 0:box].astype(np.float32)
    rad = np.hypot(xx - (box - 1) / 2, yy - (box - 1) / 2) / (box / 2)
    return np.clip((1 - rad) / 0.28, 0, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "docs/companions/fire/v21/evidence/diagnosis")
    a = ap.parse_args()
    out = {"visible_share": {}, "v2_reproduction": {}}
    for st in cp.STATES:
        out["visible_share"][st] = {"v2": round(visible_share(st, cp.V2_FRAME), 3),
                                    "v21": round(visible_share(st, V21_FRAME), 3)}
        print(st, out["visible_share"][st], flush=True)
    cell = cp.Renderer().cell("idle", 0, cp.V2_FRAME, cp.V2_STAGE)
    # the V2 atlas straight from git history (review R2-09), not from another worktree
    blob = subprocess.run(["git", "show", "b73bd26c:uri_ui/assets/companions/ember/idle.webp"], cwd=REPO,
                          capture_output=True, check=True).stdout
    sheet = np.asarray(Image.open(io.BytesIO(blob)).convert("RGBA")).astype(np.float32) / 255
    s = sheet[:320, :320].copy()
    s[..., :3] *= s[..., 3:]
    d = np.abs(s - cell)
    out["v2_reproduction"] = {"v2_atlas": "git b73bd26c:uri_ui/assets/companions/ember/idle.webp", "mean_abs_diff": round(float(d.mean()), 4),
                              "max_abs_diff": round(float(d.max()), 4)}
    print(out["v2_reproduction"])
    out["live_check"] = live_check()
    print(out["live_check"])
    dst = a.out
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "diag_v21.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
