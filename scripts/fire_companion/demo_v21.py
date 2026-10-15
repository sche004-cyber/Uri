"""Ember V2.1 demonstrations, as the app shows them (see critique_pack_v21.app_view).

    python -B scripts/fire_companion/demo_v21.py

Writes to docs/companions/fire/v21/evidence/demos/:
  <clip>.gif           V2.1 clip loops (idle, joyful, depleted, kindling), 12 fps
  before_after.jpg     per reference state: painting | V2 in the app | V2.1 in the app
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "fire_companion"))
import critique_pack_v21 as cp  # noqa: E402
import fidelity_score as fs  # noqa: E402
from render_clips import EXPR  # noqa: E402

OUT = REPO / "docs/companions/fire/v21/evidence/demos"


def gif(rd: cp.Renderer, clip: str, size: int = 300) -> None:
    n = EXPR["clips"][clip]["loop"]
    frames = [cp.app_view(rd.cell(clip, i, EXPR["frame"], EXPR["clips"][clip].get("stage", EXPR.get("stage", {})))).resize((size, size), Image.LANCZOS)
              for i in range(0, n, 2)]
    frames[0].save(OUT / f"{clip}.gif", save_all=True, append_images=frames[1:], duration=1000 // 12, loop=0)
    print(clip, "gif", flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rd = cp.Renderer()
    rows = []
    for state in cp.STATES:
        ref = fs.load_panel(state).resize((448, 480))
        tile = Image.new("RGB", (448 * 3 + 32, 490), (0x13, 0x0F, 0x0B))
        tile.paste(ref, (0, 5))
        tile.paste(cp.app_view(rd.cell(state, 0, cp.V2_FRAME, cp.V2_STAGE)).resize((448, 448)), (464, 21))
        tile.paste(cp.app_view(rd.cell(state, 0, EXPR["frame"], EXPR["clips"][state].get("stage", EXPR.get("stage", {})))).resize((448, 448)),
                   (928, 21))
        rows.append(np.asarray(tile))
    Image.fromarray(np.concatenate(rows, 0)).save(OUT / "before_after.jpg", quality=90)
    print("before_after", flush=True)
    for clip in ("idle", "joyful", "depleted", "kindling"):
        gif(rd, clip)


if __name__ == "__main__":
    main()
