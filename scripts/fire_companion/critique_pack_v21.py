"""Blind critique pack for Ember V2.1 (protocol FP-21, docs/companions/fire/v21/03_FIDELITY_PROTOCOL_V21.md).

Every candidate except the three anchors is shown AS THE APP SHOWS IT: the
frame is reduced to the 320 px atlas cell (WebP q88 round trip, as exported),
drawn at the companion host's presence scale (0.5 / bodyRadius 0.42) into a
490 px box, faded to the host's SoftDisc (opaque to 0.72 of the radius, zero
at the box edge) and laid on the Solar Ember surface #130F0B.

Static candidates per reference state (letters shuffled per reviewer):
  ref_reframed  - the panel itself, sharp, 94 % and shifted (top anchor)
  ref_copy      - the panel blurred 2 px, shifted 3 px, JPEG q60 (anchor)
  v1            - Ember V1 render (bottom anchor)
  painting_app  - CONTROL: the unanimated, unmodified painting in the V2.1
                  app presentation (what the presentation alone costs)
  v2_app        - Ember V2 (b73bd26c settings) as the app shows it
  v21_worst     - Ember V2.1, the frame the automated scorer ranks furthest
  v21_mid       - Ember V2.1, half a loop later
  v21_frame_only - ABLATION: V2.1 framing with V2's smooth backdrop

Animation pack per reference state: six frames evenly spaced over the loop
for V2 and for V2.1, each as the app shows it, under the labels X / Y
(shuffled per reviewer).

    python -B scripts/fire_companion/critique_pack_v21.py --tag p1 --reviewers 3
"""
from __future__ import annotations

import argparse
import hashlib
import io
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
from export_v2 import Framing, straight  # noqa: E402

STATES = ["idle", "joyful", "fierce", "depleted"]
CANVAS = np.array([0x13, 0x0F, 0x0B], np.float32) / 255
V1_SHEET = REPO / "docs/companions/fire/evidence/fidelity/fidelity_sheet.jpg"
BOX = 490
PRESENCE_SCALE = min(max(0.50 / 0.42, 1.0), 1.4)  # companion_presence.dart presenceScale(ember)
# V2 as committed at b73bd26c (expressions.json had no "stage"; this "frame")
V2_FRAME = {"side": 490, "feet_at": 0.955}
V2_STAGE: dict = {}
EVID = REPO / "docs/companions/fire/v21/evidence/fidelity"
WORST = REPO / "docs/companions/fire/v2/evidence/fidelity/auto_cp8/scores_v2.json"


def webp_roundtrip(cell_pm: np.ndarray, quality: int = 88) -> np.ndarray:
    """Premultiplied cell -> the exporter's straight-alpha WebP -> premultiplied."""
    buf = io.BytesIO()
    Image.fromarray(straight(cell_pm), "RGBA").save(buf, "WEBP", quality=quality, method=6, exact=True)
    buf.seek(0)
    s = np.asarray(Image.open(buf).convert("RGBA")).astype(np.float32) / 255
    s[..., :3] *= s[..., 3:]
    return s


def host_mask(mask: str = "disc") -> np.ndarray:
    """Box-sized opacity mask. "disc" is the host's SoftDisc (opaque to 0.72
    of the radius, zero at the box edge). The others are host ALTERNATIVES
    probed in round P2, not implemented: "wide" (opaque to 0.86) and "card"
    (a square with soft rounded edges, fading over the outer 10 % of the box)."""
    yy, xx = np.mgrid[0:BOX, 0:BOX].astype(np.float32)
    if mask == "card":
        f = 0.10 * BOX

        def ss(v):
            v = np.clip(v / f, 0, 1)
            return v * v * (3 - 2 * v)
        return ss(xx) * ss(BOX - 1 - xx) * ss(yy) * ss(BOX - 1 - yy)
    inner = {"disc": 0.72, "wide": 0.86}[mask]
    rad = np.hypot(xx - (BOX - 1) / 2, yy - (BOX - 1) / 2) / (BOX / 2)
    return np.clip((1 - rad) / (1 - inner), 0, 1)


def app_view(cell_pm: np.ndarray, mask: str = "disc") -> Image.Image:
    """Atlas cell as LivingCompanion draws it: presence scale, SoftDisc, canvas."""
    r = int(round(BOX * PRESENCE_SCALE))
    big = np.dstack([np.asarray(Image.fromarray(cell_pm[..., c]).resize((r, r), Image.BILINEAR))
                     for c in range(4)])
    o = (r - BOX) // 2
    big = big[o:o + BOX, o:o + BOX]
    big = big * host_mask(mask)[..., None]
    rgb = big[..., :3] + CANVAS * (1 - big[..., 3:])
    return Image.fromarray((rgb.clip(0, 1) * 255 + 0.5).astype(np.uint8))


class Renderer:
    def __init__(self) -> None:
        self.panels: dict[str, Panel] = {}

    def panel(self, name: str) -> Panel:
        return self.panels.get(name) or self.panels.setdefault(name, Panel(name))

    def cell(self, state: str, i: int | None, frame: dict, stage: dict) -> np.ndarray:
        """Frame i of the state's clip (None = the unanimated painting)."""
        spec = EXPR["clips"][state]
        pn = self.panel(spec["panel"])
        fr = Framing(pn, EXPR["cell"], stage, frame)
        if i is None:
            src = pn._z["src"].astype(np.float32)  # the painting (after the rig's erase only)
            pm = np.dstack([src, np.ones(src.shape[:2], np.float32)])
        else:
            n = spec["loop"]
            pm = pn.frame(i / n, spec["motion"], face_at(spec.get("face", {}), i / n))
        return webp_roundtrip(fr.cell_image(pm, spec["motion"].get("aura", 0.0)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewers", type=int, default=3)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--seed", type=int, default=2100)
    ap.add_argument("--hostprobe", action="store_true",
                    help="round P2: host presentation alternatives replace V2 and the V2.1 frame variants")
    a = ap.parse_args()
    base = EVID / a.tag
    keydir = EVID / f"{a.tag}_key"
    keydir.mkdir(parents=True, exist_ok=True)
    worst = json.loads(WORST.read_text())
    v21_frame, v21_stage = EXPR["frame"], EXPR.get("stage", {})
    if v21_frame.get("center") != "panel" or not v21_stage.get("texture"):
        raise SystemExit("expressions.json is not the V2.1 configuration")
    rd = Renderer()
    v1sheet = Image.open(V1_SHEET).convert("RGB")
    # render once, shuffle per reviewer
    static: dict[str, dict[str, Image.Image]] = {}
    anim: dict[str, dict[str, list[Image.Image]]] = {}
    for k, state in enumerate(STATES):
        ref = fs.load_panel(state)
        w, h = ref.size
        reframed = ref.resize((int(w * 0.94), int(h * 0.94)), Image.LANCZOS)
        sharp = Image.new("RGB", ref.size, tuple(int(v) for v in fs.background_colour(np.asarray(ref))))
        sharp.paste(reframed, ((w - reframed.width) // 2 + 5, (h - reframed.height) // 2))
        n = EXPR["clips"][state]["loop"]
        wf = worst[state]["worst_frame"] % n
        mid = (wf + n // 2) % n
        static[state] = {
            "target": ref,
            "ref_reframed": sharp,
            "ref_copy": fs.degraded_copy(ref),
            "v1": v1sheet.crop((k * 448, 480, (k + 1) * 448, 960)),
            "painting_app": app_view(rd.cell(state, None, v21_frame, v21_stage)),
            "v2_app": app_view(rd.cell(state, wf, V2_FRAME, V2_STAGE)),
            "v21_worst": app_view(rd.cell(state, wf, v21_frame, v21_stage)),
            "v21_mid": app_view(rd.cell(state, mid, v21_frame, v21_stage)),
            "v21_frame_only": app_view(rd.cell(state, wf, v21_frame, V2_STAGE)),
        }
        if a.hostprobe:
            c21 = rd.cell(state, wf, v21_frame, v21_stage)
            cp_ = rd.cell(state, None, v21_frame, v21_stage)
            for nm in ("v2_app", "v21_worst", "v21_mid", "v21_frame_only"):
                del static[state][nm]
            static[state].update({
                "v21_disc": app_view(c21, "disc"),
                "v21_wide": app_view(c21, "wide"),
                "v21_card": app_view(c21, "card"),
                "painting_card": app_view(cp_, "card"),
            })
        picks = [round(j * n / 6) % n for j in range(6)]
        if a.hostprobe:
            anim[state] = {}
            print(state, "rendered", flush=True)
            continue
        anim[state] = {
            "v2": [app_view(rd.cell(state, i, V2_FRAME, V2_STAGE)) for i in picks],
            "v21": [app_view(rd.cell(state, i, v21_frame, v21_stage)) for i in picks],
            "frames": picks,
        }
        print(state, "rendered", flush=True)
    key: dict = {"protocol": "FP-21", "tag": a.tag, "seed": a.seed, "files": {}}
    for r in range(1, a.reviewers + 1):
        rng = random.Random(a.seed + r)
        out = base / f"reviewer{r}"
        out.mkdir(parents=True, exist_ok=True)
        rk = key[f"reviewer{r}"] = {}
        for state in STATES:
            cands = static[state]
            cands["target"].save(out / f"{state}_target.png")
            names = [nm for nm in cands if nm != "target"]
            rng.shuffle(names)
            rk[state] = {}
            for L, nm in zip("ABCDEFGH", names):
                p = out / f"{state}_candidate_{L}.png"
                cands[nm].save(p)
                rk[state][L] = nm
            if a.hostprobe:
                continue
            pair = ["v2", "v21"]
            rng.shuffle(pair)
            rk[state]["anim"] = {"X": pair[0], "Y": pair[1], "frames": anim[state]["frames"]}
            for lab, nm in zip("XY", pair):
                for j, im in enumerate(anim[state][nm]):
                    im.save(out / f"{state}_motion_{lab}_{j + 1}.png")
        for p in sorted(out.iterdir()):
            key["files"][f"reviewer{r}/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
    (keydir / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print("pack written:", base)


if __name__ == "__main__":
    main()
