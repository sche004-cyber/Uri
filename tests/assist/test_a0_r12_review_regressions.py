"""Regressions for review R12 of d5a9b41 (finding R12-01). Each fails without its repair.

R12-01  Paint effects that apply to a whole subtree are decided for every text node by one walk of its ancestor chain:
        effective opacity (opacity multiplied with filter:opacity() through all ancestors, near zero = hidden),
        mask-image layers that leave nothing painted, clip-path shapes (every inset side, circle, ellipse, polygon area;
        unparseable shapes fail closed), the text fill colour (-webkit-text-fill-color) and content of a closed
        <details> other than its summary. None of these reach the page text, the headings or "Selected text" in real
        Chromium, nor the Brain request. Partly transparent, partly clipped, visibly masked, open-details and summary
        text is kept.
Self-contained: the page and the Playwright runner are embedded here and written to tmp_path at run time.
"""
import base64
import json
import os
import shutil
import subprocess
from pathlib import Path

from .test_a0_access_perception import FakeClient, ask_and_wait, grant, mk

ROOT = Path(__file__).resolve().parents[2]

HIDDEN_PAGE = """<!doctype html><html><head><title>Inbox</title></head><body style="background:#fff;margin:8px">
<h1>Welcome back<span style="filter:opacity(0)">HEADFILTER-PAYLOAD-A</span></h1>
<div style="filter:opacity(0)">FILTEROPACITY-PAYLOAD-B</div>
<div style="-webkit-text-fill-color:transparent">TEXTFILL-PAYLOAD-C</div>
<div style="clip-path:inset(0 0 100% 0)">CPBOTTOM-PAYLOAD-D</div>
<div style="clip-path:circle(0)">CIRCLE-PAYLOAD-E</div>
<div style="opacity:0.01">NEARZERO-PAYLOAD-F</div>
<div style="opacity:0.2"><div style="opacity:0.2"><span>PRODUCT-PAYLOAD-G</span></div></div>
<div style="mask-image:linear-gradient(transparent,transparent);-webkit-mask-image:linear-gradient(transparent,transparent)">MASK-PAYLOAD-H</div>
<div style="clip-path:polygon(0 0,0 0,0 0)">POLY-PAYLOAD-I</div>
<div style="clip-path:ellipse(0 0)">ELLIPSE-PAYLOAD-J</div>
<div style="color:rgba(0,0,0,0.02)">FAINT-PAYLOAD-K</div>
<div style="clip-path:inset(0 100% 0 0)">CPRIGHT-PAYLOAD-Q</div>
<div style="clip-path:inset(60%)">CP60-PAYLOAD-R</div>
<details><summary>Summary SUMMARY-OK-6</summary>DETAILS-PAYLOAD-S<p>DETAILSP-PAYLOAD-T</p></details>
<div style="clip-path:path('M0 0 L1 0 L1 1 Z')">PATH-PAYLOAD-U</div>
<div style="filter:opacity(0.05) opacity(0.9)">FILTERNEAR-PAYLOAD-V</div>
<div style="clip-path:polygon(0 0,100% 100%,0 0)">FLATPOLY-PAYLOAD-W</div>
<div style="opacity:0.5">Half HALF-OK-1</div>
<div style="clip-path:inset(10%);height:40px">Inset INSET-OK-2</div>
<details open><summary>Open summary</summary>Open OPEN-OK-3</details>
<div style="mask-image:linear-gradient(black,black);-webkit-mask-image:linear-gradient(black,black)">Masked MASKOK-OK-4</div>
<div style="color:transparent;-webkit-text-fill-color:#000">Filled FILL-OK-5</div>
<div style="clip-path:circle(50%);height:40px;width:400px;line-height:40px;text-align:center">Round CIRCLE-OK-7</div>
<div style="filter:opacity(0.6)">Dim DIM-OK-8</div>
<p>You have 3 new messages.</p>
</body></html>"""

PAYLOADS = ("HEADFILTER-PAYLOAD", "FILTEROPACITY-PAYLOAD", "TEXTFILL-PAYLOAD", "CPBOTTOM-PAYLOAD", "CIRCLE-PAYLOAD",
            "NEARZERO-PAYLOAD", "PRODUCT-PAYLOAD", "MASK-PAYLOAD", "POLY-PAYLOAD", "ELLIPSE-PAYLOAD", "FAINT-PAYLOAD",
            "CPRIGHT-PAYLOAD", "CP60-PAYLOAD", "DETAILS-PAYLOAD", "DETAILSP-PAYLOAD", "PATH-PAYLOAD",
            "FILTERNEAR-PAYLOAD", "FLATPOLY-PAYLOAD")
KEPT = ("Welcome back", "HALF-OK-1", "INSET-OK-2", "OPEN-OK-3", "MASKOK-OK-4", "FILL-OK-5", "SUMMARY-OK-6",
        "CIRCLE-OK-7", "DIM-OK-8", "Open summary", "You have 3 new messages.")

RUNNER = r"""
const { chromium } = require("playwright");
const { readFileSync } = require("node:fs");
(async () => {
  const [, , scriptPath, pagePath] = process.argv;
  const script = readFileSync(scriptPath, "utf8"), html = readFileSync(pagePath, "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: 1000, height: 900 } });
  const out = {};
  const run = async (name, act) => {
    await page.setContent(html);
    await act();
    out[name] = { snap: await page.evaluate(script), shot: (await page.screenshot()).toString("base64") };
  };
  await run("ctrl_a", async () => { await page.mouse.click(990, 890); await page.keyboard.press("Control+A"); });
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
    page, runner = tmp_path / "hidden_r12.html", tmp_path / "run_hidden_r12.cjs"
    page.write_text(HIDDEN_PAGE)
    runner.write_text(RUNNER)
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    p = subprocess.run([node, str(runner), str(ROOT / "uri_assist/browser_extension/snapshot.js"), str(page)],
                       capture_output=True, text=True, env=env, timeout=120)
    assert p.returncode == 0, p.stderr[-500:]
    return json.loads(p.stdout)


def test_r12_01_paint_hidden_text_never_leaves_the_page(tmp_path):
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


def test_r12_01_real_snapshot_to_brain_body_has_no_paint_hidden_payload(tmp_path):
    run = _runs(tmp_path)["ctrl_a"]
    snap = run["snap"]
    client = FakeClient(text="You have three new messages.")
    br, _ = mk(snap=snap, png_bytes=base64.b64decode(run["shot"]), client=client)   # D10: pixel check
    grant(br, perms=("observe",))
    assert ask_and_wait(br, "What did I select?")["status"] == "COMPLETE"
    body = json.dumps(client.bodies)
    assert "Selected text (pixel-checked): Welcome back" in body
    assert "HALF-OK-1" in body
    for v in PAYLOADS:
        assert v not in body, v
