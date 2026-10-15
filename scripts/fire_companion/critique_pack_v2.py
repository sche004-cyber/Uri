"""Blind critique pack for Ember V2 (AC-2a/b).

Per reference state: target.png (the reference panel) and four candidates
under shuffled letters, a different shuffle per reviewer:
  ref_reframed - the panel itself, sharp, scaled to 94 % and shifted: the top
              of the scale (added at checkpoint 3);
  ref_copy  - the panel itself, mildly degraded (blur, 3 px shift, JPEG q60):
              calibration anchor, expected near 100 %;
  v1        - Ember V1 render (V1 evidence/fidelity/fidelity_sheet.jpg):
              prior 41-51 %;
  video     - the owner's AI video redraw key frame: prior 63-67 %;
  v2        - Ember V2 as the app shows it (Solar Ember surface #130F0B),
              four frames across the loop including the frame the automated
              scorer found furthest from the painting.
The letter key goes to a separate folder the reviewers are not given.

    python -B scripts/fire_companion/critique_pack_v2.py --reviewers 2 --tag cp2
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "fire_companion"))
sys.path.insert(0, str(REPO / "companion_art" / "fire_v2"))
import fidelity_score as fs  # noqa: E402
from render_clips import EXPR, face_at, Panel  # noqa: E402
from export_v2 import Framing  # noqa: E402

STATES = ["idle", "joyful", "fierce", "depleted"]
CANVAS = np.array([0x13, 0x0F, 0x0B], np.float32) / 255
V1_SHEET = REPO / "docs/companions/fire/evidence/fidelity/fidelity_sheet.jpg"
VIDEO = REPO / "docs/companions/fire/reference/video_frames"
# video key frames: character box in the 1280x720 frame (read from the frames)
VIDEO_BOX = (340, 0, 940, 720)


def v2_strip(state: str, worst: int) -> Image.Image:
    spec = EXPR["clips"][state]
    pn = Panel(spec["panel"])
    n = spec["loop"]
    # off the motion cycles (quarter-loop frames hit the same phase of a
    # 2-per-loop hop or breath; checkpoint 3)
    picks = sorted({0, round(n * 0.3), round(n * 0.55), worst % n})
    while len(picks) < 4:
        picks = sorted(set(picks) | {(picks[-1] + n // 8) % n})
    tiles = []
    fr = Framing(pn, EXPR["cell"])
    for i in picks[:4]:
        pm = pn.frame(i / n, spec["motion"], face_at(spec.get("face", {}), i / n))
        # the app's own framing and backdrop glow, at full panel resolution
        big = fr.big_frame(pm, spec["motion"].get("aura", 0.0))
        rgb = big[..., :3] + CANVAS * (1 - big[..., 3:])
        tiles.append((rgb.clip(0, 1) * 255).astype(np.uint8))
    return Image.fromarray(np.concatenate(tiles, 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewers", type=int, default=2)
    ap.add_argument("--tag", default="cp2")
    a = ap.parse_args()
    base = REPO / "docs/companions/fire/v2/evidence/fidelity" / a.tag
    keydir = REPO / "docs/companions/fire/v2/evidence/fidelity" / f"{a.tag}_key"
    keydir.mkdir(parents=True, exist_ok=True)
    auto = json.loads((REPO / "docs/companions/fire/v2/evidence/fidelity/auto/scores_v2.json").read_text())
    v1sheet = Image.open(V1_SHEET).convert("RGB")
    key = {}
    for r in range(1, a.reviewers + 1):
        rng = random.Random(1000 + r)
        out = base / f"reviewer{r}"
        out.mkdir(parents=True, exist_ok=True)
        key[f"reviewer{r}"] = {}
        for k, state in enumerate(STATES):
            ref = fs.load_panel(state)
            ref.save(out / f"{state}_target.png")
            w, h = ref.size
            reframed = ref.resize((int(w * 0.94), int(h * 0.94)), Image.LANCZOS)
            sharp = Image.new("RGB", ref.size, tuple(int(v) for v in fs.background_colour(np.asarray(ref))))
            sharp.paste(reframed, ((w - reframed.width) // 2 + 5, (h - reframed.height) // 2))
            cands = {
                "ref_reframed": sharp,
                "ref_copy": fs.degraded_copy(ref),
                "v1": v1sheet.crop((k * 448, 480, (k + 1) * 448, 960)),
                "video": Image.open(VIDEO / f"key_{state}.jpg").convert("RGB").crop(VIDEO_BOX),
                "v2": v2_strip(state, auto[state]["worst_frame"]),
            }
            letters = ["A", "B", "C", "D", "E"]
            names = list(cands)
            rng.shuffle(names)
            key[f"reviewer{r}"][state] = {}
            for L, nm in zip(letters, names):
                cands[nm].save(out / f"{state}_candidate_{L}.png")
                key[f"reviewer{r}"][state][L] = nm
    (keydir / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print("pack written:", base)


if __name__ == "__main__":
    main()
