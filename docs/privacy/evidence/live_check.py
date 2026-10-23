"""M95 live Windows verification (AC-17), process level, on the owner's PC.

    python docs/privacy/evidence/live_check.py <out.json>

What is real here: Windows DPAPI for the current user, the filesystem, TCP sockets on 127.0.0.1, httpx, the production
`uri_web.search` providers built the way the integrated worker builds them (`providers_from_keys`), the production
`BrainClient`, the integrated server's own `persistent_secret` function run in two separate processes (a restart).
What is NOT exercised: the full working system (materialized runtime, paired Core, Runtime v1 Brain on the GPU, the
Flutter app). Each check records COMPLETED_WITH_RESULT only when its assertion held; anything else is FAILED.
All data is synthetic.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EMAIL, AADHAAR, PASSWORD = "asha.rao7@example.in", "2345 6789 0124", "Tr0ub4dor&3"


def serve(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def capture_server():
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            body = json.dumps({"results": [{"title": "t", "url": "https://example.com/a", "content": "c"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    return serve(H), seen


def check(name, fn, results):
    t = time.time()
    try:
        detail = fn()
        results.append({"check": name, "result_class": "COMPLETED_WITH_RESULT", "detail": detail,
                        "seconds": round(time.time() - t, 3)})
    except Exception as exc:                                         # noqa: BLE001
        results.append({"check": name, "result_class": "FAILED", "detail": f"{type(exc).__name__}: {exc}"})


def web_search_on_the_wire(tmp):
    os.environ["URI_PRIVACY_HOME"] = str(tmp / "privacy")
    sys.path.insert(0, str(ROOT))
    from uri_web import search as S
    srv, seen = capture_server()
    providers = S.providers_from_keys({"searxng_url": f"http://127.0.0.1:{srv.server_address[1]}"})
    sx = [p for p in providers if p.name == "searxng"][0]
    r1 = sx.search("diwali 2026 date karnataka")
    r2 = sx.search(f"why is mail to {EMAIL} bouncing, aadhaar {AADHAAR}")
    r3 = sx.search(f"bank login fails, password: {PASSWORD}")
    srv.shutdown()
    wire = "\n".join(seen)
    from urllib.parse import unquote_plus
    plain = unquote_plus(wire)
    assert r1.status == S.OK and "diwali 2026 date karnataka" in plain
    assert r2.status == S.OK and EMAIL not in plain and AADHAAR.replace(" ", "") not in plain.replace(" ", "")
    assert "bouncing" in plain
    assert r3.status == S.REFUSED and r3.error_code == "PRIVACY_REFUSED" and len(seen) == 2
    audit = (tmp / "privacy" / "audit.jsonl").read_text(encoding="utf-8")
    for v in (EMAIL, AADHAAR, PASSWORD, "Tr0ub"):
        assert v not in audit
    lines = [json.loads(x) for x in audit.splitlines()]
    return {"requests_on_wire": len(seen), "refused_before_send": r3.error_code, "audit_records": len(lines),
            "audit_outcomes": [x["outcome"] for x in lines]}


SERVER_FN = r'''
import ast, os, secrets, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from uri_core.core.runtime_identity import RuntimeIdentityError, dpapi
src = Path(sys.argv[1], "scripts", "run_uri_integrated_server.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "persistent_secret")
ns = {"Path": Path, "os": os, "secrets": secrets, "dpapi": dpapi, "RuntimeIdentityError": RuntimeIdentityError}
exec(compile(ast.Module([fn], []), "persistent_secret", "exec"), ns)
try:
    s = ns["persistent_secret"](Path(sys.argv[2]))
    import hashlib; print("OK", hashlib.sha256(s.encode()).hexdigest())
except RuntimeIdentityError as e:
    print("REFUSED", e)
'''


def d10_restart(tmp):
    secret = tmp / "state" / "secure" / "provider-key-secret.dpapi"
    run = lambda: subprocess.run([sys.executable, "-I", "-c", SERVER_FN, str(ROOT), str(secret)],
                                 capture_output=True, text=True, timeout=120).stdout.strip()
    a, b = run(), run()
    assert a.startswith("OK ") and a == b, (a, b)                    # same secret across two processes ("restart")
    blob = secret.read_bytes()
    assert len(blob) > 100                                           # a DPAPI blob, not 32 raw bytes or 64 hex chars
    secret.write_bytes(b"corrupt")
    c = run()
    assert c.startswith("REFUSED") and secret.read_bytes() == b"corrupt", c
    return {"first_start": "created", "second_start": "same secret (sha256 of secret compared, not printed)",
            "dpapi_blob_bytes": len(blob), "corrupt_file": "startup refused, file kept"}


def brain_client_ignores_a_real_proxy(tmp):
    sys.path.insert(0, str(ROOT))
    hits_proxy, hits_brain = [], []

    class Proxy(BaseHTTPRequestHandler):
        def do_POST(self):
            hits_proxy.append(self.path)
            self.send_response(502)
            self.end_headers()
        do_GET = do_POST

        def log_message(self, *a):
            pass

    class Brain(BaseHTTPRequestHandler):
        def do_GET(self):
            hits_brain.append(self.path)
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    p, b = serve(Proxy), serve(Brain)
    os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{p.server_address[1]}"
    os.environ.pop("NO_PROXY", None)
    from uri_operational_intelligence import brain_client as BC
    c = BC.BrainClient(f"http://127.0.0.1:{b.server_address[1]}")
    r = c._get().get("/health")
    refused = None
    try:
        BC.BrainClient("http://192.0.2.10:18470")
    except BC.NotLoopback as exc:
        refused = str(exc)
    p.shutdown()
    b.shutdown()
    os.environ.pop("HTTP_PROXY", None)
    assert r.status_code == 200 and hits_brain == ["/health"] and hits_proxy == [] and refused
    return {"brain_hits": len(hits_brain), "proxy_hits": len(hits_proxy), "non_loopback": refused}


def vault_dpapi_restart(tmp):
    code = r'''
import sys; sys.path.insert(0, sys.argv[1])
from uri_privacy import PrivacyGateway
from uri_privacy.vault import PersistentVaultStore
g = PrivacyGateway(vault=PersistentVaultStore(sys.argv[2]))
if sys.argv[3] == "write":
    print(g.prepare("mail asha.rao7@example.in", requester="live", destination="EXTERNAL_MODEL", purpose="live",
                    scope="live-1").text)
else:
    print(g.restore(sys.argv[4], "live-1", requester="live"))
'''
    home = tmp / "vault"
    w = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT), str(home), "write"], capture_output=True,
                       text=True, timeout=120)
    tok = w.stdout.strip()
    assert EMAIL not in tok and "[[CONTACT_" in tok, w.stderr[-400:]
    r = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT), str(home), "read", tok], capture_output=True,
                       text=True, timeout=120).stdout.strip()
    assert r == "mail " + EMAIL
    for f in home.rglob("*"):
        if f.is_file():
            assert EMAIL.encode() not in f.read_bytes()
    return {"restored_in_new_process": True, "files": sorted(str(f.relative_to(home)) for f in home.rglob("*") if f.is_file())}


def main(out):
    results = []
    with tempfile.TemporaryDirectory(prefix="m95-live-") as d:
        tmp = Path(d)
        check("web_search_wire_capture", lambda: web_search_on_the_wire(tmp), results)
        check("d10_restart_persistence", lambda: d10_restart(tmp), results)
        check("brain_client_real_proxy", lambda: brain_client_ignores_a_real_proxy(tmp), results)
        check("vault_dpapi_cross_process", lambda: vault_dpapi_restart(tmp), results)
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "uri_privacy", "uri_web",
                            "uri_operational_intelligence", "scripts"], capture_output=True, text=True).stdout.strip()
    rec = {"schema": "m95-live/1", "code_commit": head, "code_paths_clean": dirty == "", "host_os": os.name,
           "python": sys.version.split()[0], "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "scope": "process-level on the Windows host; full working-system run NOT exercised",
           "checks": results,
           "status": "PASS" if all(r["result_class"] == "COMPLETED_WITH_RESULT" for r in results) else "FAIL"}
    Path(out).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec, indent=1))
    return 0 if rec["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
