// AC15 page-layer probe in a real Chromium engine (headless Microsoft Edge, same engine family as WebView2).
//
//   node test/edge_probe.mjs <built page dir> <edge exe> <out.json>
//
// Serves the built page from 127.0.0.1 (its own origin, like the WebView2 virtual host) and runs a "canary" server on a
// second port that records every request reaching it. Each attempt targets the canary. Two page variants:
//   full      the real built page: no-network.js + CSP
//   csp_only  a page with only the same CSP meta (no scripts), to show what the CSP alone blocks
// Nothing here uses the internet. Edge runs headless with --disable-gpu and a throwaway profile folder.
// The WebView2 host layer (request filter, navigation and new-window refusal) is NOT exercised here.
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { extname, join, normalize } from 'node:path';

const [pageDir, edgeExe, outFile] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' };

const html = readFileSync(join(pageDir, 'index.html'), 'utf8');
const csp = /http-equiv="Content-Security-Policy"\s+content="([^"]+)"/.exec(html)[1];
const cspOnly = `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="${csp}"></head><body></body></html>`;

function listen(server) {
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r(server.address().port)));
}

const pageServer = createServer((req, res) => {
  const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (path === '/csp-only.html') { res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end(cspOnly); }
  const file = normalize(join(pageDir, path === '/' ? 'index.html' : path));
  if (!file.startsWith(normalize(pageDir)) || !existsSync(file)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' });
  res.end(readFileSync(file));
});
const hits = [];
const canary = createServer((req, res) => { hits.push(req.url); res.writeHead(200, { 'Access-Control-Allow-Origin': '*' }); res.end('x'); });
canary.on('upgrade', (req, socket) => { hits.push('UPGRADE ' + req.url); socket.destroy(); });
const pagePort = await listen(pageServer);
const canaryPort = await listen(canary);
const C = `http://127.0.0.1:${canaryPort}`;

const profile = mkdtempSync(join(tmpdir(), 'uri-office-edge-'));
const edge = spawn(edgeExe, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-extensions', '--disable-background-networking', '--disable-sync', '--disable-component-update',
  `--user-data-dir=${profile}`, '--remote-debugging-port=0', 'about:blank'], { stdio: 'ignore' });

let devtoolsPort = null;
for (let i = 0; i < 100 && !devtoolsPort; i++) {
  await sleep(100);
  try { devtoolsPort = readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0].trim(); } catch {}
}
if (!devtoolsPort) throw new Error('Edge did not start');
const version = await (await fetch(`http://127.0.0.1:${devtoolsPort}/json/version`)).json();
const target = (await (await fetch(`http://127.0.0.1:${devtoolsPort}/json/list`)).json()).find((t) => t.type === 'page');

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let id = 0;
const pending = new Map();
const consoleMsgs = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === 'Runtime.consoleAPICalled' || m.method === 'Log.entryAdded') consoleMsgs.push(JSON.stringify(m.params).slice(0, 300));
});
const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => {
  const r = await cdp('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  return r.result?.result?.value ?? r.result?.exceptionDetails?.exception?.description ?? r.result?.exceptionDetails?.text;
};
// A stand-in for the WebView2 host bridge (window.chrome.webview), installed before the page's scripts: it records
// what the page sends and answers the page's 'ready' with a small test workbook carrying one URI-proposed change.
const HOST_SHIM = `(() => {
  const listeners = [];
  window.__sent = [];
  window.__TEST_LOAD = { type: 'load', marks: [{ sheet: 'Sales', cell: 'B2', state: 'proposed', after: { v: 12 } }],
    workbook: { styles: {}, kept_not_shown: {}, sheets: [{ name: 'Sales', index: 0, max_row: 3, max_col: 2,
      merges: [], col_widths: {}, row_heights: {}, locked: [],
      cells: { A1: { v: 'Region' }, B1: { v: 'Amount' }, A2: { v: 'North' }, B2: { v: 10 }, B3: { f: '=SUM(B2:B2)', v: 10 } } }] } };
  window.chrome = { webview: {
    postMessage(m) { window.__sent.push(m); if (m && m.type === 'ready') setTimeout(() => listeners.forEach((l) => l({ data: window.__TEST_LOAD })), 0); },
    addEventListener(type, l) { if (type === 'message') listeners.push(l); },
  } };
})()`;
await cdp('Runtime.enable');
await cdp('Log.enable');
await cdp('Page.enable');

const ATTEMPTS = {
  fetch: `fetch('${C}/fetch').then(() => 'SENT').catch(e => 'refused: ' + e.name)`,
  xhr: `(() => { try { const x = new XMLHttpRequest(); x.open('GET', '${C}/xhr'); x.send(); return 'SENT'; } catch (e) { return 'refused: ' + e.name; } })()`,
  websocket: `(() => { try { new WebSocket('ws://127.0.0.1:${canaryPort}/ws'); return 'SENT'; } catch (e) { return 'refused: ' + e.name; } })()`,
  eventsource: `(() => { try { new EventSource('${C}/sse'); return 'SENT'; } catch (e) { return 'refused: ' + e.name; } })()`,
  sendbeacon: `String(navigator.sendBeacon('${C}/beacon', 'x'))`,
  image: `(() => { const i = new Image(); i.src = '${C}/img'; document.body.appendChild(i); return 'attempted'; })()`,
  css_url: `(() => { const s = document.createElement('style'); s.textContent = 'body{background-image:url(${C}/css)}'; document.head.appendChild(s); return 'attempted'; })()`,
  bundled_css_class: `(() => { const d = document.createElement('div'); d.className = 'univer-bg-[url(https://example.com/a-b.svg)]'; d.style.width='10px'; d.style.height='10px'; document.body.appendChild(d); return getComputedStyle(d).backgroundImage; })()`,
  prefetch: `(() => { const l = document.createElement('link'); l.rel = 'prefetch'; l.href = '${C}/prefetch'; document.head.appendChild(l); return 'attempted'; })()`,
  iframe: `(() => { const f = document.createElement('iframe'); f.src = '${C}/iframe'; document.body.appendChild(f); return 'attempted'; })()`,
  window_open: `String(window.open('${C}/open'))`,
  worker: `(() => { try { const w = new Worker(URL.createObjectURL(new Blob(["fetch('${C}/worker')"], {type:'text/javascript'}))); return 'SENT'; } catch (e) { return 'refused: ' + e.name; } })()`,
  font: `(() => { const s = document.createElement('style'); s.textContent = "@font-face{font-family:x;src:url(${C}/font)} body{font-family:x}"; document.head.appendChild(s); document.body.textContent += 'x'; return 'attempted'; })()`,
  form_post: `(() => { const f = document.createElement('form'); f.method='post'; f.action='${C}/form'; document.body.appendChild(f); try { f.submit(); } catch (e) { return 'refused: ' + e.name; } return 'attempted'; })()`,
};
const NAVIGATION = `(() => { location.href = '${C}/nav'; return 'attempted'; })()`;

async function run(variant, path) {
  hits.length = 0;
  const shim = variant === 'full' ? await cdp('Page.addScriptToEvaluateOnNewDocument', { source: HOST_SHIM }) : null;
  await cdp('Page.navigate', { url: `http://127.0.0.1:${pagePort}${path}` });
  await sleep(variant === 'full' ? 4000 : 800);
  const ready = variant === 'full' ? await evaluate(`(async () => JSON.stringify({
      univer_dom: !!document.querySelector('#app *'),
      host_messages: window.__sent.map((m) => m.type),
      only_ready_sent: window.__sent.length === 1 && window.__sent[0].type === 'ready',
      canvas: !!document.querySelector('canvas'),
      // after the test workbook loaded: network formula functions must not be registered (AC15, R1-01)
      blocked_functions_present: window.uriOfficeGuard ? window.uriOfficeGuard.blockedFunctionsPresent() : 'missing',
      patched: (await fetch('http://127.0.0.1:1/').then(() => 'SENT', (e) => e.name)) === 'NetworkDisabledError',
      data_url_fetch: await fetch('data:,ok').then((r) => r.text(), (e) => 'refused: ' + e.name) }))()`) : 'n/a';
  const results = {};
  for (const [name, expr] of Object.entries(ATTEMPTS)) {
    const before = hits.length;
    results[name] = { page_result: String(await evaluate(expr)).slice(0, 160) };
    await sleep(700);
    results[name].canary_hits = hits.slice(before);
    results[name].blocked = results[name].canary_hits.length === 0;
  }
  const before = hits.length;
  await evaluate(NAVIGATION);
  await sleep(1200);
  results.navigation = { canary_hits: hits.slice(before), blocked: hits.length === before,
    note: 'top-level navigation is not covered by CSP or the page patch; the WebView2 host must cancel it' };
  results.window_open.note = 'headless Edge blocks pop-ups without a user gesture, so a null here does not prove the ' +
    'CSP blocks window.open; in the full page the patch replaces window.open; the WebView2 host must refuse new windows';
  if (shim) await cdp('Page.removeScriptToEvaluateOnNewDocument', { identifier: shim.result.identifier });
  return { page_loaded_and_patched: ready, results };
}

const report = { tool: 'edge_probe.mjs', engine: version.Browser, user_agent: version['User-Agent'],
  headless: true, gpu: 'disabled', network: 'loopback only (page server + canary)', csp,
  full: await run('full', '/index.html'), csp_only: await run('csp_only', '/csp-only.html'),
  console_sample: consoleMsgs.slice(0, 20) };
writeFileSync(outFile, JSON.stringify(report, null, 2));
// Edge may relaunch the spawned process on Windows. Close the browser that owns
// this CDP session; killing only the original spawn can leave it and its HTTP
// keep-alive connections alive, keeping this probe running after it has finished.
await cdp('Browser.close');
ws.close();
edge.kill();
await sleep(500);
pageServer.close(); canary.close();
try { rmSync(profile, { recursive: true, force: true }); } catch {}
const summary = {};
for (const v of ['full', 'csp_only']) summary[v] = Object.fromEntries(Object.entries(report[v].results).map(([k, r]) => [k, r.blocked]));
console.log(JSON.stringify({ engine: report.engine, page_loaded_and_patched: report.full.page_loaded_and_patched, summary }));
