import json, sys, time
sys.path.insert(0, "/home/user/uri-wt/a0")
from uri_web.safe_fetch import SafeFetcher, system_resolver
from uri_web import pipeline as P
from uri_web.surface import build_surface
out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "egress": "direct (pinned); TLS verified against the container CA because the container network re-terminates TLS", "resolver": system_resolver("pypi.org", 443)}
import ssl, httpx
ctx = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
mkf = lambda: SafeFetcher(transport=httpx.HTTPTransport(verify=ctx, retries=0, trust_env=False))
f = mkf()
for u in ["https://pypi.org/project/httpx/", "https://pypi.org/rss/project/httpx/releases.xml", "https://pypi.org/nonexistent-xyz/"]:
    t = time.monotonic(); r = f.fetch(u)
    out.setdefault("fetch", []).append({"url": u, "status": r.record.fetch_status, "http": r.record.http_status, "type": r.record.content_type,
        "bytes": r.record.bytes, "sha256": (r.record.sha256 or "")[:16], "pinned": r.record.connected_address, "robots": r.record.robots_decision,
        "chain": r.record.redirect_chain, "s": round(time.monotonic() - t, 3)})
out["pins"] = f.connections
r = P.ResearchJob(P.ResearchRequest("httpx HTTP client python", urls=["https://pypi.org/project/httpx/"], use_search=False), fetcher=mkf(), providers=[]).run().to_dict()
out["research"] = {"status": r["status"], "elapsed_s": r["elapsed_s"], "method": r["synthesis_method"],
    "sources": [(s["number"], s["url"], s["analysed_scope"], s["record"]["title"], s["record"]["bytes"], s["injection_flags"]) for s in r["sources"]],
    "answer": r["answer"][:4]}
fe = P.ResearchJob(P.ResearchRequest("", feeds=["https://pypi.org/rss/project/httpx/releases.xml"], use_search=False), fetcher=mkf(), providers=[]).run().to_dict()
out["feed"] = {"status": fe["status"], "items": len(fe["feed_items"]), "first": fe["feed_items"][:2]}
s = build_surface(r); out["a2ui"] = {"digest": s.digest, "components": len(s.components)}
print(json.dumps(out, indent=1, default=str))
