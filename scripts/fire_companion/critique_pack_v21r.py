"""Blind critique pack for protocol FP-21R (reference-relative presentation,
docs/companions/fire/v21/08_FIDELITY_PROTOCOL_V21R.md).

Per reference state: the target and ten candidates (letters A-J, shuffled per
reviewer): the three FP-21 anchors, Ember V2 as the app showed it, and - over a
dark and a light surround - the reference under equivalent conditions
(`painting_t`) and the shipped Ember (worst frame and half a loop later).

`painting_t` is the unanimated painting cut out with Ember's layer alpha (its
own pixels where the alpha is >= 0.85, the layer colour in the soft edge) and
given each clip's shipped transparent stage, cell, WebP round trip and host
presentation - the same treatment as every shipped Ember frame.

    python -B scripts/fire_companion/critique_pack_v21r.py --tag r1 --out DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "fire_companion"))
import critique_pack_v21 as cp  # noqa: E402
from critique_pack_v21 import EXPR, Framing, fs  # noqa: E402

DARK = cp.CANVAS
LIGHT = np.array([0xE8, 0xE8, 0xE8], np.float32) / 255
LETTERS = "ABCDEFGHIJ"


def view(cell_pm: np.ndarray, canvas: np.ndarray) -> Image.Image:
    """cp.app_view with a chosen surround (the host arithmetic is the same)."""
    old = cp.CANVAS
    cp.CANVAS = canvas
    try:
        return cp.app_view(cell_pm)
    finally:
        cp.CANVAS = old


def painting_t(rd: cp.Renderer, state: str, frame: dict, stage: dict) -> np.ndarray:
    spec = EXPR["clips"][state]
    pn = rd.panel(spec["panel"])
    z = pn._z
    src = z["src"].astype(np.float32)
    rgba = z["rgba"].astype(np.float32)
    a = rgba[..., 3:4]
    w = np.clip((a - 0.60) / 0.25, 0, 1)
    col = src * w + rgba[..., :3] * (1 - w)
    pm = np.dstack([col * a, a])
    fr = Framing(pn, EXPR["cell"], stage, frame)
    return cp.webp_roundtrip(fr.cell_image(pm, spec["motion"].get("aura", 0.0)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--reviewers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=4100)
    ap.add_argument("--out", type=Path, required=True, help="pack folder (reviewer<N> subfolders)")
    ap.add_argument("--keydir", type=Path, default=cp.EVID)
    a = ap.parse_args()
    keydir = a.keydir / f"{a.tag}_key"
    keydir.mkdir(parents=True, exist_ok=True)
    worst = json.loads(cp.WORST.read_text())
    frame = EXPR["frame"]
    rd = cp.Renderer()
    v1sheet = Image.open(cp.V1_SHEET).convert("RGB")
    static: dict[str, dict[str, Image.Image]] = {}
    for k, state in enumerate(cp.STATES):
        stage = EXPR["clips"][state].get("stage", EXPR.get("stage", {}))
        if not stage.get("glow") or stage.get("strength", 1.0) > 0.6:
            raise SystemExit(f"{state}: expressions.json is not the shipped transparent configuration")
        ref = fs.load_panel(state)
        w, h = ref.size
        reframed = ref.resize((int(w * 0.94), int(h * 0.94)), Image.LANCZOS)
        sharp = Image.new("RGB", ref.size, tuple(int(v) for v in fs.background_colour(np.asarray(ref))))
        sharp.paste(reframed, ((w - reframed.width) // 2 + 5, (h - reframed.height) // 2))
        n = EXPR["clips"][state]["loop"]
        wf = worst[state]["worst_frame"] % n
        mid = (wf + n // 2) % n
        pt = painting_t(rd, state, frame, stage)
        cw = rd.cell(state, wf, frame, stage)
        cm = rd.cell(state, mid, frame, stage)
        static[state] = {
            "target": ref,
            "ref_reframed": sharp,
            "ref_copy": fs.degraded_copy(ref),
            "v1": v1sheet.crop((k * 448, 480, (k + 1) * 448, 960)),
            "v2_app": view(rd.cell(state, wf, cp.V2_FRAME, cp.V2_STAGE), DARK),
            "painting_t_dark": view(pt, DARK),
            "v21_worst_dark": view(cw, DARK),
            "v21_mid_dark": view(cm, DARK),
            "painting_t_light": view(pt, LIGHT),
            "v21_worst_light": view(cw, LIGHT),
            "v21_mid_light": view(cm, LIGHT),
        }
        print(state, "rendered", flush=True)
    key: dict = {"protocol": "FP-21R", "tag": a.tag, "seed": a.seed, "files": {}}
    for r in range(1, a.reviewers + 1):
        rng = random.Random(a.seed + r)
        out = a.out / f"reviewer{r}"
        out.mkdir(parents=True, exist_ok=True)
        rk = key[f"reviewer{r}"] = {}
        for state in cp.STATES:
            cands = static[state]
            cands["target"].save(out / f"{state}_target.png")
            names = [nm for nm in cands if nm != "target"]
            rng.shuffle(names)
            rk[state] = {}
            for L, nm in zip(LETTERS, names):
                cands[nm].save(out / f"{state}_candidate_{L}.png")
                rk[state][L] = nm
        for p in sorted(out.iterdir()):
            key["files"][f"reviewer{r}/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
    (keydir / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print("pack written:", a.out)


if __name__ == "__main__":
    main()
