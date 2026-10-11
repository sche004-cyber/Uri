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
from .test_a0_r13_differential_render import PROBE_DRIVER_JS, decode_probe, drawn_probe

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
# drawn; under D10 a piece is all or nothing, so it is dropped. SVGOK-OK-9 is drawn, but SVG text is not repainted by
# the render probe's highlight (R13-01), so it cannot be bound to its pixels and is dropped (fail closed).
NOT_VERIFIABLE = ("INSET-OK-2", "SVGOK-OK-9")
KEPT = ("Welcome back", "VIS-OK-1", "STRETCHED-OK-1", "ESCAPE-OK-2", "SUMMARY-OK-6", "HALF-OK-1",
        "OPEN-OK-3", "MASKOK-OK-4", "FILL-OK-5", "DIM-OK-8", "GREY-OK-10", "SMALL-OK-11",
        "You have 3 new messages.")

RUNNER = PROBE_DRIVER_JS + r"""
const { chromium } = require("playwright");
const { readFileSync } = require("node:fs");
(async () => {
  const [, , scriptPath, pagePath, w, h, probePath] = process.argv;
  const script = readFileSync(scriptPath, "utf8"), html = readFileSync(pagePath, "utf8"), probeSrc = readFileSync(probePath, "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: +w, height: +h } });
  const out = {};
  const run = async (name, act) => {
    await page.setContent(html);
    await act();
    const snap = await page.evaluate(script);                     // the DOM snapshot, then the probe (as URI)
    const shot = (await page.screenshot()).toString("base64"), probe = await probeTab(page, snap, probeSrc);
    out[name] = { snap, shot, probe, html: await page.content() };
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
                        str(VW), str(VH), str(ROOT / "uri_assist/browser_extension/probe.js")], capture_output=True, text=True, env=env, timeout=180)
    assert p.returncode == 0, p.stderr[-500:]
    return json.loads(p.stdout)


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    return _runs(tmp_path_factory.mktemp("d10"))


def _ask(snap, probe):
    client = FakeClient(text="You have three new messages.")
    br, ad = mk(snap=snap, probe=probe, client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "What does this page say?")
    assert out["status"] == "COMPLETE"
    return json.dumps(client.bodies), client.bodies[0]["messages"][1]["content"], out["observation"]


@pytest.mark.parametrize("name", ["no_selection", "ctrl_a"])
def test_d10_real_chromium_hidden_payloads_never_reach_the_brain(runs, name):
    run = runs[name]
    snap = run["snap"]
    body, user, observation = _ask(snap, decode_probe(run["probe"]))
    for v in PAYLOADS + NOT_VERIFIABLE:
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
    # The verification screenshots themselves are never part of a structured request.
    assert "image_url" not in body and run["probe"]["base"][100:300] not in body


def test_d10_real_chromium_without_screenshot_sends_no_page_text(runs):
    snap = runs["ctrl_a"]["snap"]
    body, user, observation = _ask(snap, None)
    for v in PAYLOADS + KEPT:
        assert v not in body, v
    assert "Selected text" not in user and "Headings" not in user
    assert "none could be pixel-checked" in user
    assert observation["redactions"].get("pixel_check_unavailable") == 1


# ---- fail closed in the bridge ----------------------------------------------------------------------------------------

def _unit(i, y, k=20, w=600):
    return {"n": i, "a": 0, "b": k, "r": [[10, y, w, 18]], "c": 1, "k": k, "l": k + 1}


def _pieced_snapshot(**over):
    units = [_unit(0, 10, 24), _unit(1, 40, 9), _unit(2, 70, 10)]
    snap = dom_snapshot(text="Pay now LEGACY-TEXT", selection="LEGACY-SEL", selection_source="page_text",
                        headings=["LEGACY-HEAD"], viewport={"w": VW, "h": 900}, device_pixel_ratio=1, units=units,
                        pieces={"text": [{"t": "Fee payment due DRAWN-TEXT", "u": [0], "g": 0}],
                                "selection": [{"t": "DRAWN-SEL", "u": [1], "g": 0}],
                                "headings": [[{"t": "DRAWN-HEAD", "u": [2], "g": 0}]]})
    snap.update(over)
    return snap


class _NoShot(FakeAdapter):
    def __init__(self, snap, probe=None, raises=False):
        super().__init__("browser_tab", snap, targets=[{"target_id": "t", "label": "Fee payment"}], probe=probe)
        self.raises, self.shots = raises, 0

    def screenshot(self, target_id):
        self.shots += 1
        return None

    def probe(self, target_id):
        self.shots += 1
        if self.raises:
            raise RuntimeError("capture failed")
        return self._probe


@pytest.mark.parametrize("probe,raises", [(None, False), (b"", False), ({"schema": "uri.assist.probe.v1"}, False),
                                          ("not a probe", False), (None, True)])
def test_d10_bridge_without_a_usable_screenshot_sends_no_page_text(probe, raises):
    from uri_assist import bridge as B
    client = FakeClient()
    ad = _NoShot(_pieced_snapshot(), probe=probe, raises=raises)
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
    snap = _pieced_snapshot()
    br, _ = mk(snap=snap, probe=drawn_probe(snap), client=client)
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
    snap = _pieced_snapshot()
    ad = _NoShot(snap, probe=drawn_probe(snap))
    br = B.AssistCommands(adapters={AC.ScopeKind.BROWSER_TAB: ad})
    grant(br)
    out = br.handle("assist_check", {"command": "assist_check"})
    assert ad.shots == 0 and out["observation"]["text_chars"] == 0


def test_d10_withheld_selection_vetting_still_sees_undrawn_pieces():
    # A selection piece that contains a withheld field value refuses the whole selection even if that piece is not drawn.
    fields = [{"id": "cvv", "type": "text", "name": "cvv", "autocomplete": "cc-csc", "label": "Security code (CVV)",
               "value": "417", "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}]
    snap = _pieced_snapshot(fields=fields, units=[_unit(0, 40, 9), _unit(1, 800, 7)],
                            pieces={"selection": [{"t": "DRAWN-SEL", "u": [0], "g": 0},
                                                  {"t": "code 417", "u": [1], "g": 0}]})
    obs = PE.normalise(snap, stamp(), probe=drawn_probe(snap, hidden={1}))
    assert obs.selection == "" and obs.selection_withheld is True


# ---- the render check on synthetic probes ------------------------------------------------------------------------------

def _snap(units, w=VW, h=900, dpr=1):
    return {"units": units, "viewport": {"w": w, "h": h}, "device_pixel_ratio": dpr}


def _pieces(units):
    return [{"t": "x" * u["k"], "u": [i], "g": i} for i, u in enumerate(units)]


def test_onscreen_inked_rect_kept_blank_rect_dropped():
    units = [_unit(0, 10), _unit(1, 100)]
    snap = _snap(units)
    c = Counter()
    kept = OS.keep(_pieces(units), OS.load(drawn_probe(snap, hidden={1}), snap), c, 10)
    assert [p["g"] for p in kept] == [0] and c == {"no_ink": 1}


def test_onscreen_off_viewport_and_partly_off_viewport_dropped():
    units = [_unit(0, 950), _unit(1, 890), {**_unit(2, 10), "r": [[-400, 10, 300, 18]]}, {**_unit(3, 200), "r": []},
             {**_unit(4, 300), "c": 9}, {**_unit(5, 400), "r": [[10, "x", 1, 1]]}, _unit(6, 500)]
    snap = _snap(units)
    pieces = _pieces(units) + [{"t": "no units", "u": [], "g": 7}, {"t": "bad unit", "u": [99], "g": 8}]
    c = Counter()
    assert [p["g"] for p in OS.keep(pieces, OS.load(drawn_probe(snap), snap), c, 20)] == [6]
    assert c == {"offscreen_or_unverified": 8}


def test_onscreen_missing_or_wrong_screenshot_keeps_nothing():
    units = [_unit(0, 10)]
    snap = _snap(units)
    good = drawn_probe(snap)
    small = drawn_probe(_snap(units, w=800))
    for probe in (None, {}, b"png", {**good, "schema": "other"}, {**good, "viewport": {"w": 800, "h": 900}},
                  {**good, "device_pixel_ratio": 2}, {**good, "base": small["base"]}, {**good, "base2": None},
                  {**good, "plain": None},
                  {**good, "groups": [{**good["groups"][0], "tint2": b"\x89PNG broken"}]},
                  {**good, "units": []}, {**good, "palette": good["palette"][:1]}):
        c = Counter()
        assert OS.keep(_pieces(units), OS.load(probe, snap), c, 10) == [] and c == {"offscreen_or_unverified": 1}
    assert OS.load(good, {**snap, "viewport": {"w": 0, "h": 900}}) is None
    obs = PE.normalise(_pieced_snapshot(), stamp(), probe=None)
    assert obs.text == "" and obs.selection == "" and obs.headings == []
    assert obs.redactions["pixel_check_unavailable"] == 1


def test_onscreen_few_glyphs_cannot_carry_a_long_piece():
    units = [_unit(0, 10, k=33, w=300), _unit(1, 60, k=3, w=40)]
    snap = _snap(units)
    probe = drawn_probe({**snap, "units": [{**units[0], "r": [[10, 10, 40, 18]]}, units[1]]})
    probe["units"] = [{"r": u["r"], "c": 1, "l": u["l"]} for u in units]   # only the first 40 px of unit 0 drew
    c = Counter()
    assert [p["g"] for p in OS.keep(_pieces(units), OS.load(probe, snap), c, 5)] == [1] and c == {"no_ink": 1}


def test_onscreen_flat_band_and_gradient_are_not_ink():
    # Ink that stays the same in every shot (a selection band, a gradient, decoy text) is not the unit's own glyphs.
    from PIL import Image, ImageDraw
    units = [_unit(0, 10), _unit(1, 100, w=900)]
    snap = _snap(units)
    probe = drawn_probe(snap, hidden={0, 1})

    def paint(png):
        img = Image.open(io.BytesIO(png)).convert("RGB")
        d = ImageDraw.Draw(img)
        d.rectangle([10, 12, 609, 25], fill=(51, 103, 214))
        for x in range(1000):
            d.line([(x, 100), (x, 118)], fill=(x // 4, x // 4, x // 4))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    probe = {**probe, "base": paint(probe["base"]), "base2": paint(probe["base2"]), "plain": paint(probe["plain"]),
             "groups": [{**g, **{k: paint(g[k]) for k in ("clear", "tint", "tint2")}} for g in probe["groups"]]}
    c = Counter()
    assert OS.keep(_pieces(units), OS.load(probe, snap), c, 5) == [] and c == {"no_ink": 2}


def test_onscreen_device_pixel_ratio_scales_rects():
    units = [_unit(0, 10), _unit(1, 300)]
    snap = _snap(units, dpr=2)
    c = Counter()
    kept = OS.keep(_pieces(units), OS.load(drawn_probe(snap, hidden={1}), snap), c, 5)
    assert [p["g"] for p in kept] == [0] and c == {"no_ink": 1}


def test_onscreen_join_groups():
    pieces = [{"t": "Hello ", "g": 0, "u": []}, {"t": "world", "g": 0, "u": []}, {"t": "Next", "g": 1, "u": []}]
    assert OS.join(pieces, "\n") == "Hello world\nNext" and OS.join(pieces, "") == "Hello worldNext"
    assert OS.join(pieces, " ") == "Hello world Next"
