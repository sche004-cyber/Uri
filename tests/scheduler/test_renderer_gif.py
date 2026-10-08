"""Scene validation, rendering and the 'is this really an animated GIF' check."""
import json
from pathlib import Path

import pytest
from PIL import Image

from uri_scheduler import gif_task, renderer

FIX = Path(__file__).parent / "fixtures" / "diwali_scene.json"


def small():
    s = json.loads(FIX.read_text(encoding="utf-8"))
    s["canvas"] = {"width": 200, "height": 200, "fps": 8, "duration_s": 1}
    for ly in s["layers"]:
        if ly["type"] == "text":
            ly["size"] = 0.09
    return s


def test_validate_rejects_bad_scenes():
    s = small()
    for mutate, code in ((lambda x: x.update(schema="nope"), "BAD_SCHEMA"),
                         (lambda x: x["layers"].append({"type": "shell"}), "UNKNOWN_LAYER"),
                         (lambda x: x["layers"].append({"type": "glow", "color": "red"}), "BAD_COLOR"),
                         (lambda x: x.update(layers=[l for l in x["layers"] if l["type"] != "text"]), "GREETING_TEXT_REQUIRED"),
                         (lambda x: x["canvas"].update(width=5000), "OUT_OF_RANGE"),
                         (lambda x: x["layers"].append({"type": "text", "text": "दीपावली की शुभकामनाएं"}), "TEXT_SCRIPT_UNSUPPORTED")):
        t = json.loads(json.dumps(s))
        mutate(t)
        with pytest.raises(renderer.SceneError) as e:
            renderer.validate_scene(t)
        assert str(e.value).startswith(code)


def test_render_is_real_animated_loop_safe_gif(tmp_path):
    out = tmp_path / "a.gif"
    info = renderer.render_gif(small(), out)
    chk = gif_task.verify_gif(out)
    assert chk["ok"] and chk["n_frames"] == 8 and chk["signature"] == "GIF89a" and chk["loop"] == 0
    assert chk["distinct_sampled_frames"] >= 2
    assert info["loop_seam_mean_abs_diff"] <= 12
    assert all(x["legible"] for x in info["legibility"])
    # determinism: same scene -> same bytes
    out2 = tmp_path / "b.gif"
    renderer.render_gif(small(), out2)
    assert out.read_bytes() == out2.read_bytes()


def test_renamed_static_image_is_not_accepted(tmp_path):
    p = tmp_path / "fake.gif"
    Image.new("RGB", (64, 64), "red").save(tmp_path / "x.png")
    p.write_bytes((tmp_path / "x.png").read_bytes())
    chk = gif_task.verify_gif(p)
    assert chk["ok"] is False and chk["signature_ok"] is False and chk["format"] == "PNG"
    Image.new("RGB", (64, 64), "red").save(p, format="GIF")          # genuine GIF but a single frame
    assert gif_task.verify_gif(p)["ok"] is False


def test_low_contrast_text_fails_legibility(tmp_path):
    s = small()
    for ly in s["layers"]:
        if ly["type"] == "text":
            ly["color"], ly["stroke"] = "#777777", "#888888"
    info = renderer.render_gif(s, tmp_path / "c.gif")
    assert not all(x["legible"] for x in info["legibility"])
