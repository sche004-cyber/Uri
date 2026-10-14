"""Render URI fire companion clips from ember.blend.

    blender -b companion_art/fire/ember.blend -P companion_art/fire/render_ember.py -- \
        --clips idle,joyful --out build/fire/raw [--size 448x480] [--frames 1,12] [--samples 32]

Writes <out>/<clip>/f_0001.png ... (RGBA, straight alpha, before bloom). The
post-process (bloom, alpha from glow, packing) is done by postprocess.py with
numpy so it is deterministic and independent of the Blender compositor.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
STATES = json.loads((HERE / "states.json").read_text(encoding="utf-8"))


def parse() -> dict:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    o = {"clips": ",".join(STATES["clips"]), "out": "build/fire/raw", "size": "448x480", "frames": "", "samples": "32",
         "ortho": "", "lift": ""}
    for i, a in enumerate(argv):
        if a.startswith("--") and i + 1 < len(argv):
            o[a[2:]] = argv[i + 1]
    return o


def values_for(clip: str) -> dict:
    d = dict(STATES["defaults"])
    spec = STATES["clips"][clip]
    if "base" in spec:
        d.update({k: v for k, v in STATES["clips"][spec["base"]].items() if k in d})
    d.update({k: v for k, v in spec.items() if k in d})
    return d


def main() -> None:
    o = parse()
    sc = bpy.context.scene
    w, h = (int(v) for v in o["size"].split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    if hasattr(sc.eevee, "taa_render_samples"):
        sc.eevee.taa_render_samples = int(o["samples"])
    if o["ortho"]:
        # Sprite framing: wider and square, so flames and sparks are not cut.
        sc.camera.data.ortho_scale = float(o["ortho"])
    if o["lift"]:
        sc.camera.location.z += float(o["lift"])
    ctrl = bpy.data.objects["EMBER_CTRL"]
    if ctrl.animation_data:
        ctrl.animation_data.action = None
    out = Path(o["out"])
    for clip in [c for c in o["clips"].split(",") if c]:
        vals = values_for(clip)
        for k, v in vals.items():
            ctrl[k] = float(v)
        loop = int(vals["loop"])
        frames = [int(f) for f in o["frames"].split(",") if f] or list(range(1, loop + 1))
        d = out / clip
        d.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        for f in frames:
            sc.frame_set(f)
            sc.render.filepath = str(d / f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
        dt = time.perf_counter() - t0
        (d / "render_meta.json").write_text(json.dumps({
            "clip": clip, "frames": frames, "loop": loop, "size": [w, h],
            "samples": int(o["samples"]), "seconds": round(dt, 2),
            "ortho": sc.camera.data.ortho_scale,
            "blender": bpy.app.version_string, "engine": sc.render.engine, "values": vals,
        }, indent=1), encoding="utf-8")
        print(f"EMBER_RENDER {clip} {len(frames)} frames {dt:.1f}s")


if __name__ == "__main__":
    main()
