// Runs the extension's snapshot.js in real Chromium (Playwright) against a fixture page and prints the snapshot.
// Usage: [SNAPSHOT_URL=https://...] node run_snapshot.cjs <snapshot.js> <page.html> [css selector to select]
const { chromium } = require("playwright");
const { readFileSync } = require("node:fs");
(async () => {
  const [, , scriptPath, pagePath, select] = process.argv;
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: 1000, height: 900 } });
  const html = readFileSync(pagePath, "utf8");
  if (process.env.SNAPSHOT_URL) {
    // Serve the fixture at a given URL (no network) so the snapshot's `url` can be checked too.
    await page.route("**/*", (r) => r.fulfill({ status: 200, contentType: "text/html", body: html }));
    await page.goto(process.env.SNAPSHOT_URL);
  } else {
    await page.setContent(html);
  }
  if (select) {
    await page.evaluate((sel) => {
      const r = document.createRange(); r.selectNodeContents(document.querySelector(sel));
      getSelection().removeAllRanges(); getSelection().addRange(r);
    }, select);
  }
  const values = () => page.evaluate(() => [...document.querySelectorAll("input,textarea,select")].map((e) => e.value));
  const before = [await page.content(), await values()];
  const snap = await page.evaluate(readFileSync(scriptPath, "utf8"));
  const after = [await page.content(), await values()];
  const shot = await page.screenshot({ type: "png" });
  await browser.close();
  process.stdout.write(JSON.stringify({ snapshot: snap, page_unchanged: JSON.stringify(before) === JSON.stringify(after),
                                        screenshot_b64: shot.toString("base64") }));
})().catch((e) => { process.stderr.write(String(e)); process.exit(2); });
