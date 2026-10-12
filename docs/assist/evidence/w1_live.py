import json, os, ssl, sys, time
sys.path.insert(0, "/home/user/Uri")
import httpx
from uri_web.safe_fetch import SafeFetcher
from uri_web import pipeline as P, search as S, social as SO
from uri_web.surface import build_surface
ctx = ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
proxy = os.environ["HTTPS_PROXY"]
def fetcher():
    return SafeFetcher(egress="proxy", proxy=proxy, transport=httpx.HTTPTransport(proxy=proxy, verify=ctx, retries=0, trust_env=False))
out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "egress": "proxy (cloud container; direct pinned mode not exercised live)"}
f = fetcher()
for u in ["https://www.rfc-editor.org/rfc/rfc9110.html", "http://127.0.0.1:18470/v1/models", "http://169.254.169.254/latest/meta-data/"]:
    t = time.monotonic(); r = f.fetch(u)
    out.setdefault("fetch", []).append({"url": u, "status": r.record.fetch_status, "code": r.record.refusal_code,
        "http": r.record.http_status, "bytes": r.record.bytes, "robots": r.record.robots_decision, "s": round(time.monotonic()-t, 3)})
out["providers"] = [{"p": p.name, "available": p.available()} for p in S.default_providers()]
t = time.monotonic()
job = P.ResearchJob(P.ResearchRequest("HTTP semantics idempotent methods", urls=["https://www.rfc-editor.org/rfc/rfc9110.html", "https://developer.mozilla.org/en-US/docs/Glossary/Idempotent"]), fetcher=fetcher(), providers=S.default_providers())
r = job.run().to_dict()
out["research"] = {"status": r["status"], "elapsed_s": r["elapsed_s"], "sources": [(s["number"], s["url"], s["analysed_scope"], s["record"]["bytes"]) for s in r["sources"]],
    "answer": r["answer"][:4], "providers": r["providers"], "attempts": [(a["requested_url"], a["fetch_status"]) for a in r["attempts"]], "method": r["synthesis_method"]}
s = build_surface(r); out["a2ui_digest"] = s.digest
fe = P.ResearchJob(P.ResearchRequest("", feeds=["https://www.python.org/blogs/feeds/blog.atom" ], use_search=False), fetcher=fetcher(), providers=[]).run().to_dict()
out["feed"] = {"status": fe["status"], "items": len(fe["feed_items"]), "first": fe["feed_items"][:1], "attempts": [(a["requested_url"], a["fetch_status"], a.get("http_status")) for a in fe["attempts"]]}
b = SO.bluesky_author(fetcher(), "bsky.app", limit=3)
out["bluesky"] = {"status": b.status, "posts": len(b.posts), "code": b.error_code, "http": b.record.http_status if b.record else None}
m = SO.mastodon_tag(fetcher(), "mastodon.social", "python", limit=3)
out["mastodon"] = {"status": m.status, "posts": len(m.posts), "code": m.error_code, "http": m.record.http_status if m.record else None}
print(json.dumps(out, indent=1, default=str))
