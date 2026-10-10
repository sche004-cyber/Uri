"""CPU-side latency benchmark for W1/A0 (cloud container; no GPU, no Brain). Prints JSON.
Run: python docs/assist/evidence/a0_w1_cpu_bench.py  (from the repository root)"""
import json, statistics, subprocess, sys, time, os, platform
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import httpx
from uri_web.extract import extract_html
from uri_web import pipeline as P, search as S
from uri_web.safe_fetch import SafeFetcher
from uri_web.surface import build_surface
from uri_web.synthesize import verify, extractive
from uri_assist.access import Stamp
from uri_assist import perception as PE, checks as CK, vision as VI

def bench(fn, n=30):
    xs = []
    for _ in range(n):
        t = time.perf_counter(); fn(); xs.append((time.perf_counter() - t) * 1000)
    xs.sort()
    return {"n": n, "p50_ms": round(statistics.median(xs), 3), "p95_ms": round(xs[int(n * 0.95) - 1], 3), "max_ms": round(xs[-1], 3)}

para = "<p>The district board approved a fee increase of 4.5% for the 2027 academic year after a long debate. </p>"
html_small = "<html><body><article>" + para * 20 + "</article></body></html>"
html_large = "<html><body><nav>menu</nav><article>" + para * 3000 + "</article><div style='display:none'>x</div></body></html>"
out = {"host": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(),
       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
out["extract_html_20_paragraphs"] = bench(lambda: extract_html(html_small, "https://x.example/"))
out["extract_html_3000_paragraphs_%dKB" % (len(html_large) // 1024)] = bench(lambda: extract_html(html_large, "https://x.example/"), 10)
srcs = [("t", (para.replace("<p>", "").replace("</p>", "")) * 30) for _ in range(6)]
answer = " ".join(f"The district board approved a fee increase of 4.5% for 2027 [{i}]." for i in range(1, 7))
out["verify_6_claims_6_sources"] = bench(lambda: verify(answer, [t for _, t in srcs]))
out["extractive_6_sources"] = bench(lambda: extractive("fee increase 2027", [t for _, t in srcs]))
def h(req):
    if req.url.path == "/robots.txt": return httpx.Response(404)
    return httpx.Response(200, headers={"content-type": "text/html"}, text=html_small)
class Prov:
    name = "fake"
    def available(self): return True
    def search(self, q, max_results=5):
        return S.SearchResult("fake", q, S.OK, hits=[S.SearchHit("t", f"https://s{i}.example/", "", i + 1, "fake") for i in range(6)])
def run_pipeline():
    f = SafeFetcher(resolver=lambda h_, p: ["93.184.216.34"], transport=httpx.MockTransport(h))
    return P.ResearchJob(P.ResearchRequest("fee increase 2027"), fetcher=f, providers=[Prov()]).run()
out["pipeline_6_pages_mock_network_no_brain"] = bench(run_pipeline, 15)
r = run_pipeline().to_dict()
out["a2ui_surface_build_and_validate"] = bench(lambda: build_surface(r).messages())
fix = ROOT / "tests/assist/fixtures"
env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
times, snap = [], None
for _ in range(5):
    t = time.perf_counter()
    p = subprocess.run(["node", str(fix / "run_snapshot.cjs"), str(ROOT / "uri_assist/browser_extension/snapshot.js"), str(fix / "form_page.html")],
                       capture_output=True, text=True, env=env, timeout=120)
    times.append((time.perf_counter() - t) * 1000)
    snap = json.loads(p.stdout)
out["chromium_launch_load_snapshot_screenshot_total_ms_p50"] = round(statistics.median(times), 1)
# in-page snapshot alone, measured inside Chromium
probe = r"""
const { chromium } = require("playwright"); const fs = require("fs");
(async () => { const b = await chromium.launch(); const pg = await b.newPage();
  await pg.setContent(fs.readFileSync(process.argv[1], "utf8")); const src = fs.readFileSync(process.argv[2], "utf8");
  const xs = []; for (let i = 0; i < 30; i++) { const t = Date.now(); await pg.evaluate(src); xs.push(Date.now() - t); }
  xs.sort((a, b) => a - b); console.log(JSON.stringify({ p50_ms: xs[15], max_ms: xs[29] })); await b.close(); })();
"""
pp = subprocess.run(["node", "-e", probe, str(fix / "form_page.html"), str(ROOT / "uri_assist/browser_extension/snapshot.js")],
                    capture_output=True, text=True, env=env, timeout=120)
out["dom_snapshot_in_page_eval_roundtrip"] = json.loads(pp.stdout) if pp.returncode == 0 else {"error": pp.stderr[-200:]}
st = Stamp("g", 1, "t", "dom", 0.0)
out["normalise_redact_real_snapshot"] = bench(lambda: PE.normalise(snap["snapshot"], st))
obs = PE.normalise(snap["snapshot"], st)
out["live_assist_findings"] = bench(lambda: CK.findings(obs))
import base64
png = base64.b64decode(snap["screenshot_b64"])
out["screenshot_mask_downscale_1000x900"] = bench(lambda: VI.prepare_image(png, obs.sensitive_rects, unlocated_sensitive=False), 15)
out["NOT_MEASURED_HERE"] = ["Brain VRAM / GPU contention / vision inference latency (no GPU, no Runtime v1)",
                            "Flutter UI GPU overhead (no display)", "Windows UI Automation responsiveness (not Windows)",
                            "live search-provider latency (no API keys; egress policy)"]
print(json.dumps(out, indent=1))
