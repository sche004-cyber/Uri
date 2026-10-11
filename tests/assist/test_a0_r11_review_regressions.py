"""Regressions for review R11 of 2de591e (finding R11-01). Each fails without its repair.

R11-01  Visibility is decided per text node: screen-reader-only (clip:rect(0,0,0,0) in a 1x1 overflow box), text inside
        a height:0 / max-height:0 overflow:hidden ancestor, text-indent:-9999px, transparent-coloured text and text
        under an opaque overlay never reach the page text, the headings or "Selected text" in real Chromium, nor the
        Brain request. Ordinary visible text (including a long page scrolled below the fold, a stretched transparent
        link overlay and an absolutely positioned child escaping a static overflow:hidden parent) is kept.
Self-contained: the page and the Playwright runner are embedded here and written to tmp_path at run time.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from .test_a0_access_perception import FakeClient, ask_and_wait, grant, mk
from .test_a0_r13_differential_render import PROBE_DRIVER_JS, decode_probe

ROOT = Path(__file__).resolve().parents[2]

HIDDEN_PAGE = """<!doctype html><html><head><title>Inbox</title></head><body style="background:#fff;margin:8px">
<h1 id="top">Welcome back<span style="position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0)">HEADSRONLY-PAYLOAD-0</span></h1>
<div style="position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0">SRONLY-PAYLOAD-1</div>
<div style="height:0;overflow:hidden"><p>CLIPPED-PAYLOAD-2</p></div>
<div style="color:transparent">COLORTRANSPARENT-PAYLOAD-3</div>
<div style="text-indent:-9999px">INDENT-PAYLOAD-5</div>
<div style="max-height:0;overflow:hidden"><span style="display:block">MAXH-PAYLOAD-7</span></div>
<div style="position:relative;height:30px"><div style="position:absolute;inset:0;background:#fff;z-index:2"></div><div>COVERED-PAYLOAD-8</div></div>
<div style="position:relative;height:30px"><a href="#x" style="position:absolute;inset:0;z-index:2"></a><div>Card keeps STRETCHED-OK-1</div></div>
<div style="position:relative"><div style="overflow:hidden;height:10px"><div style="position:absolute;top:12px">Escaping ESCAPE-OK-2</div></div></div>
<div style="height:40px"></div>
<p id="end">You have 3 new messages.</p>
<div style="height:1400px"></div>
<p id="below">Footer BELOWFOLD-OK-3</p>
</body></html>"""

PAYLOADS = ("HEADSRONLY-PAYLOAD", "SRONLY-PAYLOAD", "CLIPPED-PAYLOAD", "COLORTRANSPARENT-PAYLOAD", "INDENT-PAYLOAD",
            "MAXH-PAYLOAD", "COVERED-PAYLOAD")
KEPT = ("Welcome back", "STRETCHED-OK-1", "ESCAPE-OK-2", "You have 3 new messages.", "BELOWFOLD-OK-3")

RUNNER = PROBE_DRIVER_JS + r"""
const { chromium } = require("playwright");
const { readFileSync } = require("node:fs");
(async () => {
  const [, , scriptPath, pagePath, probePath] = process.argv;
  const script = readFileSync(scriptPath, "utf8"), html = readFileSync(pagePath, "utf8"), probeSrc = readFileSync(probePath, "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: 1000, height: 900 } });
  const out = {};
  const run = async (name, act) => {
    await page.setContent(html);
    await act();
    const snap = await page.evaluate(script);
    out[name] = { snap, shot: (await page.screenshot()).toString("base64") };
    out[name].probe = await probeTab(page, snap, probeSrc);
  };
  await run("ctrl_a", async () => { await page.mouse.click(900, 850); await page.keyboard.press("Control+A"); });
  await run("range_all", () => page.evaluate(() => {
    const r = document.createRange(); r.selectNodeContents(document.body);
    getSelection().removeAllRanges(); getSelection().addRange(r);
  }));
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e)); process.exit(2); });
"""


def _runs(tmp_path):
    node = shutil.which("node")
    assert node is not None, "BLOCKED: node not installed"
    page, runner = tmp_path / "hidden_r11.html", tmp_path / "run_hidden_r11.cjs"
    page.write_text(HIDDEN_PAGE)
    runner.write_text(RUNNER)
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    p = subprocess.run([node, str(runner), str(ROOT / "uri_assist/browser_extension/snapshot.js"), str(page),
                        str(ROOT / "uri_assist/browser_extension/probe.js")],
                       capture_output=True, text=True, env=env, timeout=120)
    assert p.returncode == 0, p.stderr[-500:]
    return json.loads(p.stdout)


def test_r11_01_clipped_indented_and_covered_text_never_leaves_the_page(tmp_path):
    runs = _runs(tmp_path)
    for name in ("ctrl_a", "range_all"):
        snap = runs[name]["snap"]
        sel, text, heads = snap["selection"], snap["text"], " ".join(snap["headings"])
        for v in PAYLOADS:
            assert v not in sel, (name, v, sel)
            assert v not in text, (name, v, text)
            assert v not in heads, (name, v, heads)
        for v in KEPT:                       # visible text is not over-filtered
            assert v in sel, (name, v, sel)
            assert v in text, (name, v, text)
        assert snap["headings"] == ["Welcome back"], snap["headings"]
        assert snap["redactions"].get("hidden_text", 0) >= len(PAYLOADS), (name, snap["redactions"])


def test_r11_01_real_snapshot_to_brain_body_has_no_clipped_payload(tmp_path):
    run = _runs(tmp_path)["ctrl_a"]
    snap = run["snap"]
    client = FakeClient(text="You have three new messages.")
    br, _ = mk(snap=snap, probe=decode_probe(run["probe"]), client=client)   # D10 / R13-01: render check
    grant(br, perms=("observe",))
    assert ask_and_wait(br, "What did I select?")["status"] == "COMPLETE"
    body = json.dumps(client.bodies)
    assert "Selected text (pixel-checked): Welcome back" in body
    for v in PAYLOADS:
        assert v not in body, v
