"""SYNTHETIC stand-in for Claude Code used by scheduler tests and the FIXTURE leg of the live test.

It is not a model. It speaks Claude's `--output-format stream-json` dialect (system/init, assistant, user tool results,
result) so the accepted CLAUDE_RULES interpret it, reads the task package URI wrote, and writes research.md,
concept.md and scene.json from deterministic templates. Every run is labelled FIXTURE by the scheduler.

Scenario: URI_FAKE_SCENARIO (forwarded by the supervisor's URI_FAKE_ prefix): honest | quota | hang | invalid |
false_claim | crash.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SCENE = HERE.parent / "fixtures" / "diwali_scene.json"


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def scene_for(task, previous):
    fest = task.get("festival") or {}
    name = fest.get("name") or "the festival"
    short = name.split("(")[0].strip()
    req = task.get("request") or {"kind": "generate"}
    if previous is not None and req.get("kind") == "refine":
        scene = previous
        for ly in scene["layers"]:
            if ly["type"] == "particles" and ly["kind"] in ("marigold", "petals"):
                ly["count"] = min(120, int(ly.get("count", 20) * 2))
                ly["speed"] = [s * 1.25 for s in ly.get("speed", [0.2, 0.4])]
        scene["layers"].insert(1, {"type": "particles", "kind": "petals", "count": 30, "colors": ["#ff6fa1", "#ffd1e3"],
                                   "size": [3, 6], "speed": [0.25, 0.5], "direction": "swirl", "seed": 21})
        scene["title"] = scene.get("title", "") + " (more floral energy)"
        return scene, "Changes: doubled the marigold fall and added a swirling petal ring for more floral energy."
    scene = json.loads(BASE_SCENE.read_text(encoding="utf-8"))
    scene["canvas"] = {"width": 320, "height": 320, "fps": 10, "duration_s": 3}
    scene["festival_key"] = fest.get("key") or "festival"
    for ly in scene["layers"]:
        if ly["type"] == "text" and ly["text"].startswith("Happy"):
            ly["text"] = f"Happy {short}"[:40]
    if req.get("kind") == "regenerate":
        scene["background"] = {"type": "gradient", "stops": [["#0b1d3a", 0], ["#3b1c5a", 0.6], ["#f6a35c", 1]]}
        scene["layers"] = [l for l in scene["layers"] if l["type"] in ("text", "particles", "bokeh")]
        scene["layers"].insert(1, {"type": "lotus", "x": 0.5, "y": 0.78, "scale": 0.22, "bloom": 0.1})
        scene["title"] = "Lotus at dusk"
        return scene, "Alternative concept: a blooming lotus at dusk with drifting petals."
    return scene, "Rows of diyas glow over a slowly turning rangoli while marigold petals fall and embers rise."


def main():
    if "--version" in sys.argv:
        print("0.0.0 (fake claude, synthetic)")
        return 0
    sys.stdin.read()
    sc = os.environ.get("URI_FAKE_SCENARIO", "honest")
    emit({"type": "system", "subtype": "init", "session_id": "fixture-" + os.environ.get("URI_ATTEMPT_FENCE", "0"),
          "model": "synthetic-fixture"})
    if sc == "quota":
        emit({"type": "result", "subtype": "success", "is_error": True, "session_id": "fixture",
              "result": "Claude AI usage limit reached|1790000000"})
        return 1
    if sc == "hang":
        time.sleep(3600)
        return 0
    if sc == "crash":
        os._exit(3)
    if sc == "false_claim":
        emit({"type": "result", "subtype": "success", "is_error": False, "session_id": "fixture", "result": "Done."})
        return 0
    task = json.loads(Path("task.json").read_text(encoding="utf-8"))
    prev = json.loads(Path("previous_scene.json").read_text(encoding="utf-8")) if Path("previous_scene.json").is_file() else None
    scene, concept = scene_for(task, prev)
    if sc == "invalid":
        Path("scene.json").write_text("{not json", encoding="utf-8")
    else:
        Path("scene.json").write_text(json.dumps(scene, indent=1), encoding="utf-8")
    fest = (task.get("festival") or {}).get("name") or "the festival"
    Path("research.md").write_text(f"# {fest}\n\nSYNTHETIC FIXTURE TEXT - not research. Placeholder written by the "
                                   "test stand-in so the pipeline can be exercised without a model.\n", encoding="utf-8")
    Path("concept.md").write_text(f"# {scene.get('title', 'Concept')}\n\n{concept}\n", encoding="utf-8")
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": "Wrote research.md, concept.md, scene.json"}]}})
    emit({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "session_id": "fixture", "result": "Done."})
    return 0


if __name__ == "__main__":
    sys.exit(main())
