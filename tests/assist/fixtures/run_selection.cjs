// R9-01: selects text in real Chromium the ways a user does (double-click in a field, select() then blur, a drag
// across page text and fields) and prints the extension snapshot after each.
// Usage: node run_selection.cjs <snapshot.js> <page.html>
const { chromium } = require("playwright");
const { readFileSync } = require("node:fs");
(async () => {
  const [, , scriptPath, pagePath] = process.argv;
  const script = readFileSync(scriptPath, "utf8"), html = readFileSync(pagePath, "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: 1000, height: 900 } });
  const out = {};
  const select = (sel) => page.evaluate((s) => {
    const r = document.createRange(); r.selectNodeContents(document.querySelector(s));
    getSelection().removeAllRanges(); getSelection().addRange(r);
  }, sel);
  const run = async (name, act) => {
    await page.setContent(html);
    await act();
    out[name] = await page.evaluate(script);
  };
  await run("dblclick_otp", () => page.dblclick("#otp"));
  await run("dblclick_cvv", () => page.dblclick("#cvv"));
  await run("dblclick_email", () => page.dblclick("#email"));
  await run("select_cvv_then_blur", async () => {
    await page.evaluate(() => { const e = document.querySelector("#cvv"); e.focus(); e.select(); e.blur(); });
    await page.evaluate(() => { document.querySelector("#intro").tabIndex = -1; document.querySelector("#intro").focus(); });
  });
  await run("textarea_select", () => page.evaluate(() => { const e = document.querySelector("#addr"); e.focus(); e.select(); }));
  await run("contenteditable_select", () => select("#gate"));
  await run("contenteditable_word", () => page.dblclick("#gate"));
  await run("drag_across_form", () => page.evaluate(() => {
    const r = document.createRange(); r.setStartBefore(document.querySelector("#intro"));
    r.setEndAfter(document.querySelector("#outro"));
    getSelection().removeAllRanges(); getSelection().addRange(r);
  }));
  await run("page_text", () => select("#intro"));
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e)); process.exit(2); });
