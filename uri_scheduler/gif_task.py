"""Festival GIF task template (`festival_gif.v1`).

Stages (each recorded in the attempt receipt):
  Research -> Concept -> Assets -> Animation   harness (Claude) writes research.md, concept.md, scene.json
  Render -> GIF conversion                     URI renders scene.json with `renderer` (fixed, reviewed code)
  Validation                                   URI checks the file is a real animated GIF and the scene is legible
  Review                                       engine files a pending-review item bound to the GIF's sha256

The harness only ever writes inside its per-attempt workspace. Research comes from the model's own knowledge plus
the calendar record URI supplies; the executor profile grants no web tools (adding WebSearch would widen unattended
permissions and is an owner decision).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from . import renderer

TEMPLATE_ID = "festival_gif.v1"
OBJECTIVE = ("Research the upcoming Indian festival, identify its cultural and historical significance, and create a "
             "beautiful, informative, animated GIF suitable for sharing as a festival greeting.")
REQUIRED_FILES = ("research.md", "concept.md", "scene.json")
SCENE_REFERENCE = """\
scene.json schema "uri.scene.v1" (coordinates x,y are fractions 0..1 of the canvas; sizes are fractions of the
shorter side; colors are "#rrggbb" or "#rrggbbaa"; all motion loops seamlessly by construction):
{
 "schema": "uri.scene.v1", "festival_key": "<key>", "title": "<concept title>",
 "canvas": {"width": 400, "height": 400, "fps": 12, "duration_s": 4},          # 160..720 px, 8..120 frames
 "background": {"type": "gradient" | "radial", "cx": 0.5, "cy": 0.7, "stops": [["#hex", 0.0], ["#hex", 1.0]]},
 "layers": [ drawn in order, back to front; at most 40 ]
}
Layer types and their fields (all optional except type):
 glow      x y radius color opacity pulse:{amp, period_s}
 rays      x y count length width_deg color opacity turns_per_loop(int)
 bokeh     count colors[] seed
 mandala   x y radius petals rings(1..6) colors[] turns_per_loop(int) breathe     (rangoli / kolam / floral medallion)
 lotus     x y scale colors[] bloom
 diya      x y scale body_color flame_color flicker phase                         (oil lamp with live flame)
 lantern   x y scale color sway_deg phase                                         (hanging lamp, y is the hook)
 crescent  x y radius color star(bool)
 star      x y radius points color twinkle cycles phase
 polygon   points[[x,y],...] fill opacity pulse                                   (any custom silhouette, 3..64 points)
 particles kind: petals|marigold|embers|sparkles|snow|confetti, count, colors[], size[min,max], speed[min,max]
           (loops per animation), direction: down|up|swirl, seed                  (total particles <= 400)
 text      text(<=80 chars, Latin script only) x y size(0.03..0.2) font: serif|display|sans|elegant color stroke
           stroke_width glow shimmer fade_in_s                                    (at least one text layer required)
"""


class TaskError(ValueError):
    pass


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_package(workspace: Path, *, occurrence: dict, params: dict, request: dict | None, previous: dict | None) -> bytes:
    """Write the task package (task.json + reference copies) into the empty workspace; return the instructions."""
    workspace.mkdir(parents=True, exist_ok=True)
    fest = occurrence.get("meta") or {}
    package = {"template": TEMPLATE_ID, "objective": OBJECTIVE, "festival": {
        "key": fest.get("festival_key"), "name": fest.get("festival"), "date": fest.get("festival_date"),
        "calendar_record": fest.get("calendar_record"), "calendar_version": fest.get("calendar_version")},
        "style": params.get("style", "high-quality illustrated / manga-inspired, elegant motion, rich festival colours, "
                                     "floral particles, embers and atmospheric light where suitable"),
        "audience": params.get("audience", "friends and family"), "greeting_language": "English (Latin script)",
        "request": request or {"kind": "generate"}}
    if fest.get("festival_key") is None and params.get("festival"):
        package["festival"].update({"key": params["festival"].get("key"), "name": params["festival"].get("name"),
                                    "date": params["festival"].get("date")})
    (workspace / "task.json").write_text(json.dumps(package, indent=1, ensure_ascii=False), encoding="utf-8")
    if previous:
        (workspace / "previous_scene.json").write_text(json.dumps(previous["scene"], indent=1), encoding="utf-8")
        (workspace / "previous_concept.md").write_text(previous.get("concept", ""), encoding="utf-8")
    kind = (request or {}).get("kind", "generate")
    lines = [
        "You are URI's creative harness for one scheduled task. Work ONLY inside the current directory.",
        f"Objective: {OBJECTIVE}",
        "Read task.json first. Then produce exactly these files in the current directory:",
        "  research.md  - 150-300 words: the festival's cultural and historical significance, how it is celebrated, "
        "its traditional symbols and colours, and any representation sensitivities (religious imagery, deities, "
        "sacred symbols) that a respectful greeting must observe. State that it is from your own knowledge.",
        "  concept.md   - a title line, then 3-6 sentences explaining the visual concept, palette, motion and greeting.",
        "  scene.json   - the animation, following the reference below exactly. It must be valid JSON.",
        "Visual direction: high-quality illustrated or manga-inspired styling, elegant composition, rich colours suited "
        "to the festival, floral particles / embers / light / atmospheric motion where suitable, respectful symbols "
        "(no caricature of deities or sacred figures), and clear, legible greeting text (light text with a dark stroke "
        "or the reverse). Avoid generic clip-art: layer depth (background glow, mid motifs, foreground particles).",
        "Use a 400x400 canvas at 12 fps for 4 seconds unless task.json says otherwise.",
    ]
    if kind == "refine":
        lines += ["This is a REFINEMENT. previous_scene.json and previous_concept.md are the current candidate.",
                  f"Owner's instruction: {request.get('instruction', '')!s}",
                  "Apply the instruction faithfully, keep everything else that works, and explain the change at the "
                  "end of concept.md under 'Changes:'."]
    elif kind == "regenerate":
        lines += ["This is a REGENERATION: create a clearly different alternative concept from previous_concept.md "
                  "(different composition and motifs), same festival and quality bar."
                  + (f" Owner's note: {request.get('instruction')}" if request.get("instruction") else "")]
    lines += ["Do not create any other files. Do not attempt to render images yourself; URI renders scene.json.",
              "", SCENE_REFERENCE]
    return "\n".join(lines).encode("utf-8")


def collect(workspace: Path) -> dict:
    """Read and validate the harness outputs. Raises TaskError with a stable code."""
    missing = [f for f in REQUIRED_FILES if not (workspace / f).is_file()]
    if missing:
        raise TaskError("MISSING_OUTPUT:" + ",".join(missing))
    for f in REQUIRED_FILES:
        p = workspace / f
        if p.is_symlink() or p.stat().st_size == 0 or p.stat().st_size > 512 * 1024:
            raise TaskError(f"BAD_OUTPUT_FILE:{f}")
    try:
        scene = json.loads((workspace / "scene.json").read_text(encoding="utf-8"))
    except ValueError as exc:
        raise TaskError("SCENE_NOT_JSON") from exc
    try:
        info = renderer.validate_scene(scene)
    except renderer.SceneError as exc:
        raise TaskError("SCENE_INVALID:" + str(exc)) from exc
    return {"scene": scene, "scene_info": info, "concept": (workspace / "concept.md").read_text(encoding="utf-8")[:4000],
            "research": (workspace / "research.md").read_text(encoding="utf-8")[:8000],
            "scene_sha256": sha256_file(workspace / "scene.json")}


def verify_gif(path) -> dict:
    """Independent check that `path` is a genuine animated GIF (not a renamed still image)."""
    p = Path(path)
    head = p.read_bytes()[:6]
    checks = {"signature": head.decode("latin-1"), "signature_ok": head in (b"GIF89a", b"GIF87a")}
    with Image.open(p) as im:
        checks["format"] = im.format
        checks["is_animated"] = bool(getattr(im, "is_animated", False))
        checks["n_frames"] = int(getattr(im, "n_frames", 1))
        checks["size"] = list(im.size)
        checks["loop"] = im.info.get("loop")
        durations, hashes = [], set()
        for i in range(checks["n_frames"]):
            im.seek(i)
            durations.append(int(im.info.get("duration", 0)))
            if i % max(1, checks["n_frames"] // 6) == 0:
                hashes.add(hashlib.sha256(im.convert("RGB").tobytes()).hexdigest())
    checks["total_duration_ms"] = sum(durations)
    checks["distinct_sampled_frames"] = len(hashes)
    checks["ok"] = bool(checks["signature_ok"] and checks["format"] == "GIF" and checks["is_animated"]
                        and checks["n_frames"] >= renderer.LIMITS["min_frames"] and checks["distinct_sampled_frames"] >= 2
                        and checks["total_duration_ms"] > 0 and checks["loop"] == 0)
    return checks


def render_and_validate(collected: dict, out_dir: Path, name: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    gif = out_dir / f"{name}.gif"
    render = renderer.render_gif(collected["scene"], gif)
    checks = verify_gif(gif)
    legible = all(x["legible"] for x in render["legibility"]) and bool(render["legibility"])
    quality = {"animated_gif": checks["ok"], "text_legible": legible, "within_size_budget": render["within_size_budget"],
               "loop_seam_mean_abs_diff": render["loop_seam_mean_abs_diff"], "loop_seamless": render["loop_seam_mean_abs_diff"] <= 12}
    return {"path": str(gif), "sha256": sha256_file(gif), "bytes": gif.stat().st_size, "render": render, "gif_checks": checks,
            "quality": quality, "ok": checks["ok"] and legible}
