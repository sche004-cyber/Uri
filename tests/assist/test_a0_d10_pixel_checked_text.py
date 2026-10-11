"""Owner decision D10 (2026-10-11): page text is sent to the Brain only where the screen shows it drawn.

The in-page visibility rules (snapshot.js) were bypassed in four review rounds (R10-R13) by CSS hiding techniques no
list anticipated. URI now keeps a page text piece (page text, selection, heading) only if an in-memory screenshot of
the tab, taken at observation time under the same OBSERVE grant, shows ink inside the piece's own viewport rectangles
(uri_assist/onscreen.py). Anything that cannot be checked - below the fold, no screenshot, a screenshot of another
size - is dropped (fail closed). The screenshot is never sent to the Brain on this path.

Covers: real Chromium with the R11, R12 and R13 hidden payloads and extra variants (negative z-index under the
ancestor's background, SVG fill transparent/none/fill-opacity 0, -webkit-mask-box-image, blur, tiny + blur,
rotateX(90deg), white on white, opacity 0, below the fold), with and without a Ctrl+A selection; unit tests of the
pixel check on synthetic screenshots; fail closed without a screenshot.
Self-contained: the page and the Playwright runner are embedded here and written to tmp_path at run time.
"""
import base64
import io
import json
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from uri_assist import access as AC
from uri_assist import perception as PE

from .test_a0_access_perception import FakeAdapter, FakeClient, ask_and_wait, dom_snapshot, grant, mk, stamp

ROOT = Path(__file__).resolve().parents[2]


class _LazyOnscreen:
    """uri_assist.onscreen, imported when first used (so the Chromium tests run, and fail, on a tree without it)."""

    def __getattr__(self, name):
        from uri_assist import onscreen
        return getattr(onscreen, name)


OS = _LazyOnscreen()
VW, VH = 1000, 1500

PAGE = """<!doctype html><html><head><title>Inbox</title></head><body style="background:#fff;margin:8px">
<h1 style="background:#fff">Welcome back<span style="filter:opacity(0)">HEADFILTER-PAYLOAD</span><span
 style="position:relative;z-index:-1">HEADZNEG-PAYLOAD</span></h1>
<h2>Agenda <span style="color:#fff">HEADWHITE-PAYLOAD</span></h2>
<p>Visible VIS-OK-1</p>
<!-- R13 -->
<div style="background:#fff"><span style="position:relative;z-index:-1">ZNEG-PAYLOAD</span></div>
<div style="background:#fff"><div style="position:relative;z-index:-1">ZNEGBLOCK-PAYLOAD</div></div>
<svg width="300" height="24"><text x="0" y="18" fill="transparent">SVGFILL-PAYLOAD</text></svg>
<svg width="300" height="24"><text x="0" y="18" fill-opacity="0">SVGFO-PAYLOAD</text></svg>
<svg width="300" height="24"><text x="0" y="18" fill="none">SVGNONE-PAYLOAD</text></svg>
<div><svg width="400" height="24"><text x="0" y="18" fill="#000">Drawn SVGOK-OK-9</text></svg></div>
<div style="-webkit-mask-box-image:linear-gradient(transparent,transparent)">MASKBOX-PAYLOAD</div>
<!-- extra variants -->
<div style="filter:blur(20px)">BLUR-PAYLOAD</div>
<div style="font-size:3px;filter:blur(20px)">BLURTINY-PAYLOAD</div>
<div style="transform:rotateX(90deg)">ROTX-PAYLOAD</div>
<div style="color:#fff">WHITE-PAYLOAD</div>
<div style="color:#fefefe;background:#fff">NEARWHITE-PAYLOAD</div>
<div style="opacity:0">OPACITY0-PAYLOAD</div>
<div style="position:relative"><div style="position:absolute;top:0;left:0;width:400px;height:24px;background:#fff;pointer-events:none"></div>PEN-PAYLOAD</div>
<!-- R11 -->
<div style="position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0">SRONLY-PAYLOAD</div>
<div style="height:0;overflow:hidden"><p>CLIPPED-PAYLOAD</p></div>
<div style="color:transparent">COLORTRANSPARENT-PAYLOAD</div>
<div style="text-indent:-9999px">INDENT-PAYLOAD</div>
<div style="max-height:0;overflow:hidden"><span style="display:block">MAXH-PAYLOAD</span></div>
<div style="position:relative;height:24px"><div style="position:absolute;inset:0;background:#fff;z-index:2"></div><div>COVERED-PAYLOAD</div></div>
<div style="position:relative;height:24px"><a href="#x" style="position:absolute;inset:0;z-index:2"></a><div>Card keeps STRETCHED-OK-1</div></div>
<div style="position:relative"><div style="overflow:hidden;height:10px"><div style="position:absolute;top:12px">Escaping ESCAPE-OK-2</div></div></div>
<div style="height:24px"></div>
<!-- R12 -->
<div style="filter:opacity(0)">FILTEROPACITY-PAYLOAD</div>
<div style="-webkit-text-fill-color:transparent">TEXTFILL-PAYLOAD</div>
<div style="clip-path:inset(0 0 100% 0)">CPBOTTOM-PAYLOAD</div>
<div style="clip-path:circle(0)">CIRCLE-PAYLOAD</div>
<div style="opacity:0.01">NEARZERO-PAYLOAD</div>
<div style="opacity:0.2"><div style="opacity:0.2"><span>PRODUCT-PAYLOAD</span></div></div>
<div style="mask-image:linear-gradient(transparent,transparent);-webkit-mask-image:linear-gradient(transparent,transparent)">MASK-PAYLOAD</div>
<div style="clip-path:polygon(0 0,0 0,0 0)">POLY-PAYLOAD</div>
<div style="color:rgba(0,0,0,0.02)">FAINT-PAYLOAD</div>
<details><summary>Summary SUMMARY-OK-6</summary>DETAILS-PAYLOAD<p>DETAILSP-PAYLOAD</p></details>
<div style="opacity:0.5">Half HALF-OK-1</div>
<div style="clip-path:inset(10%);height:40px">Inset INSET-OK-2</div>
<details open><summary>Open summary</summary>Open OPEN-OK-3</details>
<div style="mask-image:linear-gradient(black,black);-webkit-mask-image:linear-gradient(black,black)">Masked MASKOK-OK-4</div>
<div style="color:transparent;-webkit-text-fill-color:#000">Filled FILL-OK-5</div>
<div style="filter:opacity(0.6)">Dim DIM-OK-8</div>
<div style="color:#777">Grey GREY-OK-10</div>
<p style="font-size:11px">Small print SMALL-OK-11</p>
<p>You have 3 new messages.</p>
<div style="height:2200px"></div>
<p>Footer BELOWFOLD-PAYLOAD</p>
</body></html>"""

R13 = ("ZNEG-PAYLOAD", "ZNEGBLOCK-PAYLOAD", "SVGFILL-PAYLOAD", "SVGFO-PAYLOAD", "SVGNONE-PAYLOAD", "MASKBOX-PAYLOAD",
       "HEADZNEG-PAYLOAD")
EXTRA = ("BLUR-PAYLOAD", "BLURTINY-PAYLOAD", "ROTX-PAYLOAD", "WHITE-PAYLOAD", "NEARWHITE-PAYLOAD", "OPACITY0-PAYLOAD",
         "PEN-PAYLOAD", "HEADWHITE-PAYLOAD", "BELOWFOLD-PAYLOAD")
R11 = ("SRONLY-PAYLOAD", "CLIPPED-PAYLOAD", "COLORTRANSPARENT-PAYLOAD", "INDENT-PAYLOAD", "MAXH-PAYLOAD",
       "COVERED-PAYLOAD")
R12 = ("HEADFILTER-PAYLOAD", "FILTEROPACITY-PAYLOAD", "TEXTFILL-PAYLOAD", "CPBOTTOM-PAYLOAD", "CIRCLE-PAYLOAD",
       "NEARZERO-PAYLOAD", "PRODUCT-PAYLOAD", "MASK-PAYLOAD", "POLY-PAYLOAD", "FAINT-PAYLOAD", "DETAILS-PAYLOAD",
       "DETAILSP-PAYLOAD")
PAYLOADS = R13 + EXTRA + R11 + R12
# Payloads the in-page rules do not remove (the reason for D10): only the pixel check stands between them and the Brain.
PIXEL_ONLY = ("ZNEG-PAYLOAD", "ZNEGBLOCK-PAYLOAD", "SVGFILL-PAYLOAD", "SVGFO-PAYLOAD", "SVGNONE-PAYLOAD",
              "MASKBOX-PAYLOAD", "BLUR-PAYLOAD", "PEN-PAYLOAD", "BELOWFOLD-PAYLOAD")
# INSET-OK-2 (clip-path inset(10%) on a 984 px wide box cuts away the first 98 px, where most of it is) is only partly
# drawn; under D10 a piece is all or nothing, so it is dropped.
KEPT = ("Welcome back", "VIS-OK-1", "SVGOK-OK-9", "STRETCHED-OK-1", "ESCAPE-OK-2", "SUMMARY-OK-6", "HALF-OK-1",
        "OPEN-OK-3", "MASKOK-OK-4", "FILL-OK-5", "DIM-OK-8", "GREY-OK-10", "SMALL-OK-11",
        "You have 3 new messages.")

RUNNER = r"""
const { chromium } = require("playwright");
const { readFileSync } = require("node:fs");
(async () => {
  const [, , scriptPath, pagePath, w, h] = process.argv;
  const script = readFileSync(scriptPath, "utf8"), html = readFileSync(pagePath, "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: +w, height: +h } });
  const out = {};
  const run = async (name, act) => {
    await page.setContent(html);
    await act();
    const snap = await page.evaluate(script);                     // the DOM snapshot, then the screenshot (as URI)
    out[name] = { snap, shot: (await page.screenshot()).toString("base64"), html: await page.content() };
  };
  await run("no_selection", async () => {});
  await run("ctrl_a", async () => { await page.mouse.click(990, 1490); await page.keyboard.press("Control+A"); });
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e)); process.exit(2); });
"""


def _runs(tmp_path):
    node = shutil.which("node")
    assert node is not None, "BLOCKED: node not installed"
    page, runner = tmp_path / "d10_page.html", tmp_path / "run_d10.cjs"
    page.write_text(PAGE)
    runner.write_text(RUNNER)
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    p = subprocess.run([node, str(runner), str(ROOT / "uri_assist/browser_extension/snapshot.js"), str(page),
                        str(VW), str(VH)], capture_output=True, text=True, env=env, timeout=180)
    assert p.returncode == 0, p.stderr[-500:]
    return json.loads(p.stdout)


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    return _runs(tmp_path_factory.mktemp("d10"))


def _ask(snap, png_bytes):
    client = FakeClient(text="You have three new messages.")
    br, ad = mk(snap=snap, png_bytes=png_bytes, client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "What does this page say?")
    assert out["status"] == "COMPLETE"
    return json.dumps(client.bodies), client.bodies[0]["messages"][1]["content"], out["observation"]


@pytest.mark.parametrize("name", ["no_selection", "ctrl_a"])
def test_d10_real_chromium_hidden_payloads_never_reach_the_brain(runs, name):
    run = runs[name]
    snap = run["snap"]
    body, user, observation = _ask(snap, base64.b64decode(run["shot"]))
    for v in PAYLOADS:
        assert v not in body, (name, v)
    for v in KEPT:                                     # visible text still reaches the Brain
        assert v in body, (name, v)
    assert "On-screen text (pixel-checked):" in user and "Visible text:" not in user
    assert "Headings (pixel-checked): Welcome back | Agenda" in user
    if name == "ctrl_a":
        sel = user.split("Selected text (pixel-checked): ", 1)[1].split("\n", 1)[0]
        assert sel.startswith("Welcome back") and "You have 3 new messages." in sel
        for v in KEPT:
            assert v in sel, v
        for v in PAYLOADS:
            assert v not in sel, v
    # The in-page rules still let these through; the pixel check removed them (they are in the snapshot's pieces).
    sent = json.dumps(snap["pieces"])
    for v in PIXEL_ONLY:
        assert v in sent, (name, v)
    red = observation["redactions"]
    assert red.get("no_ink", 0) >= 9 and red.get("offscreen_or_unverified", 0) >= 1, red
    assert run["html"] == runs["no_selection"]["html"]  # the snapshot changed nothing on the page
    # The verification screenshot itself is never part of a structured request.
    assert "image_url" not in body and run["shot"][:200] not in body


def test_d10_real_chromium_without_screenshot_sends_no_page_text(runs):
    snap = runs["ctrl_a"]["snap"]
    body, user, observation = _ask(snap, None)
    for v in PAYLOADS + KEPT:
        assert v not in body, v
    assert "Selected text" not in user and "Headings" not in user
    assert "none could be pixel-checked" in user
    assert observation["redactions"].get("pixel_check_unavailable") == 1


# ---- fail closed in the bridge ----------------------------------------------------------------------------------------

def _drawn(text, y=10, w=600):
    return {"t": text, "r": [[10, y, w, 18]], "c": 1, "g": 0}


def _ink_png(rects, size=(VW, 900), text_rects=True, scale=1):
    """A white screenshot with real glyphs (Pillow's default font) drawn in each rectangle."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (size[0] * scale, size[1] * scale), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for x, y, w, h in rects:
        if text_rects:
            for k in range(0, int(w * scale), 40):
                d.text((x * scale + k, y * scale + 2), "Wmh", fill=(0, 0, 0))
                if scale > 1:
                    d.text((x * scale + k, y * scale + 2 + 10), "Wmh", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pieced_snapshot(**over):
    snap = dom_snapshot(text="Pay now LEGACY-TEXT", selection="LEGACY-SEL", selection_source="page_text",
                        headings=["LEGACY-HEAD"], viewport={"w": VW, "h": 900}, device_pixel_ratio=1,
                        pieces={"text": [_drawn("Fee payment due DRAWN-TEXT", 10)],
                                "selection": [_drawn("DRAWN-SEL", 40)], "headings": [[_drawn("DRAWN-HEAD", 70)]]})
    snap.update(over)
    return snap


class _NoShot(FakeAdapter):
    def __init__(self, snap, png=None, raises=False):
        super().__init__("browser_tab", snap, targets=[{"target_id": "t", "label": "Fee payment"}], png=png)
        self.raises, self.shots = raises, 0

    def screenshot(self, target_id):
        self.shots += 1
        if self.raises:
            raise RuntimeError("capture failed")
        return self.png


@pytest.mark.parametrize("png_bytes,raises", [(None, False), (b"", False), (b"not a png", False), (None, True)])
def test_d10_bridge_without_a_usable_screenshot_sends_no_page_text(png_bytes, raises):
    from uri_assist import bridge as B
    client = FakeClient()
    ad = _NoShot(_pieced_snapshot(), png=png_bytes, raises=raises)
    br = B.AssistCommands(adapters={AC.ScopeKind.BROWSER_TAB: ad}, brain_client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "What does it say?")
    assert out["status"] == "COMPLETE" and ad.shots == 1
    body = json.dumps(client.bodies)
    for v in ("DRAWN-TEXT", "DRAWN-SEL", "DRAWN-HEAD", "LEGACY-TEXT", "LEGACY-SEL", "LEGACY-HEAD", "Fee payment due"):
        assert v not in body, v
    assert "none could be pixel-checked" in body
    assert "[private field, value hidden]" in body       # form-field handling (D8) unchanged


def test_d10_bridge_with_screenshot_sends_only_drawn_pieces_never_the_legacy_strings():
    client = FakeClient()
    png_bytes = _ink_png([[10, 10, 600, 18], [10, 40, 600, 18], [10, 70, 600, 18]])
    br, _ = mk(snap=_pieced_snapshot(), png_bytes=png_bytes, client=client)
    grant(br, perms=("observe",))
    ask_and_wait(br, "q")
    user = client.bodies[0]["messages"][1]["content"]
    assert "On-screen text (pixel-checked):\nFee payment due DRAWN-TEXT" in user
    assert "Selected text (pixel-checked): DRAWN-SEL" in user and "Headings (pixel-checked): DRAWN-HEAD" in user
    for v in ("LEGACY-TEXT", "LEGACY-SEL", "LEGACY-HEAD"):
        assert v not in user, v
    assert "image_url" not in json.dumps(client.bodies)


def test_d10_live_check_takes_no_screenshot():
    from uri_assist import bridge as B
    ad = _NoShot(_pieced_snapshot(), png=_ink_png([[10, 10, 600, 18]]))
    br = B.AssistCommands(adapters={AC.ScopeKind.BROWSER_TAB: ad})
    grant(br)
    out = br.handle("assist_check", {"command": "assist_check"})
    assert ad.shots == 0 and out["observation"]["text_chars"] == 0


def test_d10_withheld_selection_vetting_still_sees_undrawn_pieces():
    # A selection piece that contains a withheld field value refuses the whole selection even if that piece is not drawn.
    fields = [{"id": "cvv", "type": "text", "name": "cvv", "autocomplete": "cc-csc", "label": "Security code (CVV)",
               "value": "417", "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}]
    snap = _pieced_snapshot(fields=fields, pieces={"selection": [_drawn("DRAWN-SEL", 40), _drawn("code 417", 800)]})
    obs = PE.normalise(snap, stamp(), screenshot=_ink_png([[10, 40, 600, 18]]))
    assert obs.selection == "" and obs.selection_withheld is True


# ---- the pixel check on synthetic screenshots --------------------------------------------------------------------------

def _screen(png_bytes, w=VW, h=900, dpr=1):
    return OS.load(png_bytes, {"w": w, "h": h}, dpr)


def test_onscreen_inked_rect_kept_blank_rect_dropped():
    sc = _screen(_ink_png([[10, 10, 600, 18]]))
    c = Counter()
    kept = OS.keep([_drawn("drawn words here", 10), _drawn("blank words here", 100)], sc, c, 10)
    assert [p["t"] for p in kept] == ["drawn words here"] and c == {"no_ink": 1}


def test_onscreen_off_viewport_and_partly_off_viewport_dropped():
    sc = _screen(_ink_png([[10, 10, 600, 18], [10, 880, 600, 18]]))
    c = Counter()
    pieces = [{"t": "below", "r": [[10, 950, 300, 18]], "c": 1, "g": 0},
              {"t": "straddles", "r": [[10, 890, 300, 18]], "c": 1, "g": 1},
              {"t": "left of it", "r": [[-400, 10, 300, 18]], "c": 1, "g": 2},
              {"t": "no rects", "r": [], "c": 0, "g": 3},
              {"t": "truncated", "r": [[10, 10, 600, 18]], "c": 9, "g": 4},
              {"t": "bad rect", "r": [[10, "x", 1, 1]], "c": 1, "g": 5},
              {"t": "inside", "r": [[10, 10, 600, 18]], "c": 1, "g": 6}]
    assert [p["t"] for p in OS.keep(pieces, sc, c, 20)] == ["inside"]
    assert c == {"offscreen_or_unverified": 6}


def test_onscreen_missing_or_wrong_screenshot_keeps_nothing():
    pieces = [_drawn("drawn words here", 10)]
    good = _ink_png([[10, 10, 600, 18]])
    for sc in (None, _screen(None), _screen(b""), _screen(b"\x89PNG broken"), _screen(good, w=800),
               _screen(good, dpr=2), _screen(good, w=0), _screen(good, dpr=True)):
        c = Counter()
        assert OS.keep(pieces, sc, c, 10) == [] and c == {"offscreen_or_unverified": 1}
    obs = PE.normalise(_pieced_snapshot(), stamp(), screenshot=None)
    assert obs.text == "" and obs.selection == "" and obs.headings == []
    assert obs.redactions["pixel_check_unavailable"] == 1


def test_onscreen_few_glyphs_cannot_carry_a_long_piece():
    sc = _screen(_ink_png([[10, 10, 40, 18]]))         # one short word drawn at the start of a long rectangle
    c = Counter()
    assert OS.keep([{"t": "Hi " + "x" * 30, "r": [[10, 10, 40, 18]], "c": 1, "g": 0}], sc, c, 1) == [] \
        and c == {"no_ink": 1}
    assert OS.keep([{"t": "Wmh", "r": [[10, 10, 40, 18]], "c": 1, "g": 0}], sc, Counter(), 1)


def test_onscreen_flat_band_and_gradient_are_not_ink():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (VW, 900), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 12, 609, 25], fill=(51, 103, 214))          # a selection band that misses the rect's edges
    for x in range(1000):                                         # a smooth gradient
        d.line([(x, 100), (x, 118)], fill=(x // 4, x // 4, x // 4))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    sc = _screen(buf.getvalue())
    c = Counter()
    assert OS.keep([_drawn("band text here", 10), _drawn("gradient text here", 100, 900)], sc, c, 5) == []
    assert c == {"no_ink": 2}


def test_onscreen_device_pixel_ratio_scales_rects():
    png2 = _ink_png([[10, 10, 600, 18]], scale=2)
    sc = _screen(png2, dpr=2)
    assert OS.keep([_drawn("drawn words here", 10)], sc, Counter(), 1)
    assert not OS.keep([_drawn("blank words here", 300)], sc, Counter(), 1)


def test_onscreen_join_groups():
    pieces = [{"t": "Hello ", "g": 0, "r": [], "c": 0}, {"t": "world", "g": 0, "r": [], "c": 0},
              {"t": "Next", "g": 1, "r": [], "c": 0}]
    assert OS.join(pieces, "\n") == "Hello world\nNext" and OS.join(pieces, "") == "Hello worldNext"
    assert OS.join(pieces, " ") == "Hello world Next"
