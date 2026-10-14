"""Pack post-processed Ember clips into the app's sprite atlases + manifest.

    python -B companion_art/fire/export_sprites.py <post_dir> [--cell 320] [--quality 88]

Writes uri_ui/assets/companions/ember/<clip>.webp and manifest.json. Column
count keeps every atlas at or under 4096 px wide and tall (the safe texture
size on any desktop GPU).
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

from postprocess import pack

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "uri_ui" / "assets" / "companions" / "ember"
STATES = json.loads((HERE / "states.json").read_text(encoding="utf-8"))


def main() -> None:
    post = Path(sys.argv[1])
    args = sys.argv[2:]
    cell = int(args[args.index("--cell") + 1]) if "--cell" in args else 320
    quality = int(args[args.index("--quality") + 1]) if "--quality" in args else 88
    limit = 4096 // cell
    manifest = {"fps": STATES["fps"], "cell": cell, "source": "companion_art/fire (Blender)", "clips": {}}
    for clip, spec in STATES["clips"].items():
        if spec.get("ship", True) is False:
            stale = OUT / f"{clip}.webp"
            if stale.exists():
                stale.unlink()
            continue
        frames = len(list((post / clip).glob("f_*.png")))
        if frames == 0:
            raise SystemExit(f"no frames for {clip}")
        cols = min(limit, math.ceil(math.sqrt(frames * 1.5)))
        rows = math.ceil(frames / cols)
        if rows > limit:
            raise SystemExit(f"{clip}: {frames} frames do not fit {limit}x{limit} cells of {cell}")
        info = pack(post / clip, OUT / f"{clip}.webp", cell, cols, quality)
        info["sha256"] = hashlib.sha256((OUT / f"{clip}.webp").read_bytes()).hexdigest()
        manifest["clips"][clip] = info
    # Picker tile: one still idle frame, small, so the settings page never
    # decodes an animation atlas just to show a thumbnail.
    from PIL import Image
    still = Image.open(sorted((post / "idle").glob("f_*.png"))[0]).convert("RGBA")
    still.resize((192, 192), Image.LANCZOS).save(OUT / "thumbnail.webp", "WEBP", quality=90, method=6, exact=True)
    manifest["thumbnail"] = "thumbnail.webp"
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    total = sum(c["bytes"] for c in manifest["clips"].values())
    print(f"EXPORT {len(manifest['clips'])} clips, {total / 1048576:.2f} MiB on disk")


if __name__ == "__main__":
    main()
