"""Score Ember fidelity renders for the four reference states and build the
side-by-side comparison sheet.

    python -B scripts/fire_companion/score_all.py <post_dir> <out_dir>

<post_dir>/<state>/f_NNNN.png are post-processed renders at the comparison
framing (448x480, the default camera of ember.blend). Every rendered frame of a
state is scored; the report gives the median (the headline), min and max, and
the AI video redraw of the same character as an informational point.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fidelity_score as fs  # noqa: E402

STATES = ("idle", "joyful", "fierce", "depleted")


def main() -> None:
    post, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    video = fs.REF_DIR / "video_frames"
    report: dict = {"method": "scripts/fire_companion/fidelity_score.py", "states": {}}
    sheet = Image.new("RGB", (448 * 4, 480 * 2), (58, 48, 38))
    for i, s in enumerate(STATES):
        frames = sorted((post / s).glob("f_*.png"))
        rows = []
        for f in frames:
            r = fs.score(s, f)
            c = r["candidate"]
            rows.append({"frame": f.name, "calibrated": round(c["calibrated"], 2),
                         "unclamped": round(c["calibrated_unclamped"], 2),
                         "components": {k: round(v, 3) for k, v in c["components"].items()}})
        cal = [x["calibrated"] for x in rows]
        unc = [x["unclamped"] for x in rows]
        vid = fs.score(s, video / f"vcrop_{s}.jpg")["candidate"]
        report["states"][s] = {
            "frames": rows,
            "median_calibrated": statistics.median(cal),
            "min_calibrated": min(cal),
            "max_calibrated": max(cal),
            "median_unclamped": statistics.median(unc),
            "anchors_raw": fs.score(s)["anchor_raw"],
            "video_redraw_same_character": {"calibrated": round(vid["calibrated"], 2),
                                            "unclamped": round(vid["calibrated_unclamped"], 2)},
            "target": 90,
            "met": statistics.median(cal) >= 90,
        }
        ref = fs.load_panel(s)
        sheet.paste(ref, (448 * i, 0))
        mid = frames[len(frames) // 2]
        sheet.paste(fs.prepare_candidate(mid, ref), (448 * i, 480))
    sheet.save(out / "fidelity_sheet.jpg", quality=88)
    (out / "fidelity_scores.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for s, v in report["states"].items():
        print(s, "median", v["median_calibrated"], "range", v["min_calibrated"], v["max_calibrated"],
              "unclamped", v["median_unclamped"], "video", v["video_redraw_same_character"], "met", v["met"])


if __name__ == "__main__":
    main()
