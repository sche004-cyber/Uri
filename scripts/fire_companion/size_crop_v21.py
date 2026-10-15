"""How much of Ember survives the host's disc at each companion size (UI V2 readiness).

The host (LivingCompanion, unchanged in UI V2 candidate 316e6475) draws the
cell at presenceScale(ember) * look.size * presentationScale and fades it to
a SoftDisc: opaque to 0.72 of the box radius, zero at the box edge. UI V2
sets presentationScale 1.85 only for Solar in companion mode, so Ember gets 1.
look.size is clamped to [0.8, 1.25] (CompanionLook.sizeMin/sizeMax).

For each state and size this reports, as shares of Ember's alpha mass at
frame 0:
  visible - weighted by the disc's opacity (diag_v21's "visible share")
  full    - inside the opaque core (r <= 0.72)
  cut     - outside the box edge (r > 1): not drawn at all

    python -B scripts/fire_companion/size_crop_v21.py [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "fire_companion"))
import critique_pack_v21 as cp  # noqa: E402
from export_v2 import Framing  # noqa: E402
from render_clips import EXPR, face_at, Panel  # noqa: E402

SIZES = [0.8, 1.0, 1.25]


def shares(state: str) -> dict:
    spec = EXPR["clips"][state]
    pn = Panel(spec["panel"])
    pm = pn.frame(0, spec["motion"], face_at(spec.get("face", {}), 0))
    fr = Framing(pn, EXPR["cell"], {}, EXPR["frame"])
    a = fr.place(pm)[..., 3]
    total = pm[..., 3].sum()
    s = a.shape[0]
    yy, xx = np.mgrid[0:s, 0:s]
    d = np.hypot(xx - (s - 1) / 2, yy - (s - 1) / 2)
    out = {}
    for size in SIZES:
        r = d / (s / 2 / (cp.PRESENCE_SCALE * size))
        m = np.clip((1 - r) / 0.28, 0, 1)
        out[str(size)] = {"scale": round(cp.PRESENCE_SCALE * size, 3),
                          "visible": round(float((a * m).sum() / total), 3),
                          "full": round(float((a * (r <= 0.72)).sum() / total), 3),
                          "cut": round(float((a * (r > 1)).sum() / total), 3)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "docs/companions/fire/v21/evidence/final/size_crop.json")
    a = ap.parse_args()
    res = {st: shares(st) for st in ["idle", "joyful", "depleted", "listening", "thinking", "speaking", "focused",
                                      "concerned", "kindling"]}
    for st, v in res.items():
        print(st, v)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    # what the user sees: idle and depleted (worst frame 0) at each size, over a light surround
    from PIL import Image
    rd = cp.Renderer()
    old_scale, old_canvas = cp.PRESENCE_SCALE, cp.CANVAS
    cp.CANVAS = np.array([0xE8, 0xE8, 0xE8], np.float32) / 255
    rows = []
    for st in ["idle", "depleted"]:
        stage = EXPR["clips"][st].get("stage", EXPR.get("stage", {}))
        cell = rd.cell(st, 0, EXPR["frame"], stage)
        row = []
        for size in SIZES:
            sc = old_scale * size
            if sc >= 1:
                cp.PRESENCE_SCALE = sc
                row.append(np.asarray(cp.app_view(cell)))
                continue
            # below 1 the scaled cell is smaller than the box: centre it on a transparent box first
            r = int(round(cp.BOX * sc))
            small = np.dstack([np.asarray(Image.fromarray(cell[..., c]).resize((r, r), Image.BILINEAR))
                               for c in range(4)])
            box = np.zeros((cp.BOX, cp.BOX, 4), np.float32)
            o = (cp.BOX - r) // 2
            box[o:o + r, o:o + r] = small
            cp.PRESENCE_SCALE = 1.0
            box_cell = np.dstack([np.asarray(Image.fromarray(box[..., c]).resize((cell.shape[0],) * 2, Image.BILINEAR))
                                  for c in range(4)])
            row.append(np.asarray(cp.app_view(box_cell)))
        rows.append(np.concatenate(row, 1))
    cp.PRESENCE_SCALE, cp.CANVAS = old_scale, old_canvas
    Image.fromarray(np.concatenate(rows, 0)).save(a.out.with_name("size_crop.jpg"), quality=90)


if __name__ == "__main__":
    main()
