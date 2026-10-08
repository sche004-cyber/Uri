"""Where do the ~220 ms of streaming overhead go? (research only; follows stream_overhead.py)

stream_overhead.py: the same 27-token / 2-token request costs 0.161 s non-streaming but 0.386 s to the first
streamed token through the lab client (httpx.stream + iter_lines). This probe measures the same request on the
production server through four paths, 6 calls each, after one warm-up:
  nonstream_httpx   httpx.post, wall time
  stream_lab        lab.client.chat (new httpx connection per call, iter_lines)
  stream_client     one persistent httpx.Client, iter_raw(), first byte of the first "data:" line with content
  stream_socket     raw TCP socket, time to the first byte of the response body after the headers, and to the
                    first "data:" line containing a content delta
If stream_socket's first-byte time is ~0.16 s and the lab client's is ~0.39 s, the cost is in the Python client;
if the socket also waits ~0.2 s for the first chunk, it is server-side (SSE flush / Nagle).

  python model_lab/uri_engine/stream_probe2.py
Evidence: model_lab/evidence/uri_engine/stream_probe2.json
"""
from __future__ import annotations

import json
import socket
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import httpx  # noqa: E402

from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine"
FAST = {"enable_thinking": False}
MSGS = [{"role": "user", "content": "Reply with exactly the two words: ok done"}]
N = 6


def body(stream):
    return {"model": "local", "messages": MSGS, "max_tokens": 2, "temperature": 0, "seed": 7, "stream": stream,
            "chat_template_kwargs": FAST, **({"stream_options": {"include_usage": True}} if stream else {})}


def nonstream_httpx(url):
    t0 = time.monotonic()
    j = httpx.post(url + "/v1/chat/completions", json=body(False), timeout=120).json()
    t = j.get("timings") or {}
    return {"wall_s": round(time.monotonic() - t0, 4), "prompt_ms": t.get("prompt_ms"), "predicted_ms": t.get("predicted_ms")}


def stream_lab(url):
    r = chat(url, MSGS, max_tokens=2, template_kwargs=FAST)
    t = r.get("timings") or {}
    return {"ttft_s": r.get("ttft_s"), "total_s": r.get("total_s"), "prompt_ms": t.get("prompt_ms")}


def stream_client(client, url):
    t0 = time.monotonic()
    first_byte = first_content = None
    buf = b""
    with client.stream("POST", url + "/v1/chat/completions", json=body(True), timeout=120) as r:
        for raw in r.iter_raw():
            now = time.monotonic()
            if first_byte is None:
                first_byte = now
            buf += raw
            if first_content is None and b'"content":"' in buf and b'"content":""' not in buf.split(b'"content":"')[0][-12:]:
                first_content = now
            if b"[DONE]" in buf:
                break
    return {"first_byte_s": round(first_byte - t0, 4) if first_byte else None,
            "first_content_s": round(first_content - t0, 4) if first_content else None, "total_s": round(time.monotonic() - t0, 4)}


def stream_socket(host, port):
    payload = json.dumps(body(True)).encode()
    req = (f"POST /v1/chat/completions HTTP/1.1\r\nHost: {host}:{port}\r\nContent-Type: application/json\r\n"
           f"Content-Length: {len(payload)}\r\nAccept: text/event-stream\r\nConnection: close\r\n\r\n").encode() + payload
    t0 = time.monotonic()
    s = socket.create_connection((host, port), timeout=120)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.sendall(req)
    buf = b""
    first_byte = headers_done = first_data = first_content = None
    while True:
        chunk = s.recv(65536)
        now = time.monotonic()
        if not chunk:
            break
        if first_byte is None:
            first_byte = now
        buf += chunk
        if headers_done is None and b"\r\n\r\n" in buf:
            headers_done = now
        if first_data is None and b"data:" in buf:
            first_data = now
        if first_content is None and b'"content":"' in buf and not buf.endswith(b'"content":""'):
            idx = buf.find(b'"content":"')
            if buf[idx + 11:idx + 12] != b'"':
                first_content = now
        if b"[DONE]" in buf:
            break
    s.close()
    return {"first_byte_s": round(first_byte - t0, 4) if first_byte else None, "headers_s": round(headers_done - t0, 4) if headers_done else None,
            "first_data_s": round(first_data - t0, 4) if first_data else None, "first_content_s": round(first_content - t0, 4) if first_content else None,
            "total_s": round(time.monotonic() - t0, 4), "bytes": len(buf)}


def main():
    cfg = ServerConfig(name="stream_probe2", model=CFG["model"]["path"], ctx=32768, ngl=999, port=18495, load_mode="none",
                       mmproj=CFG["model"]["mmproj"], extra=tuple("-b 2048 -ub 1024 --cache-ram 1024".split()))
    srv = Server(cfg, EVID / "overhead_logs").start()
    url = srv.url
    out = {"request": body(True), "paths": {}}
    try:
        for _ in range(2):
            chat(url, MSGS, max_tokens=2, template_kwargs=FAST)
        out["paths"]["nonstream_httpx"] = [nonstream_httpx(url) for _ in range(N)]
        out["paths"]["stream_lab"] = [stream_lab(url) for _ in range(N)]
        with httpx.Client() as client:
            out["paths"]["stream_client_persistent"] = [stream_client(client, url) for _ in range(N)]
        out["paths"]["stream_socket"] = [stream_socket("127.0.0.1", cfg.port) for _ in range(N)]
        out["resources"] = srv.resource_snapshot()
    finally:
        srv.stop()

    def med(rows, k):
        v = [r[k] for r in rows if r.get(k) is not None]
        return round(statistics.median(v), 4) if v else None
    out["summary"] = {
        "nonstream_wall_p50": med(out["paths"]["nonstream_httpx"], "wall_s"),
        "server_prompt_ms_p50": med(out["paths"]["nonstream_httpx"], "prompt_ms"),
        "stream_lab_ttft_p50": med(out["paths"]["stream_lab"], "ttft_s"),
        "stream_client_first_byte_p50": med(out["paths"]["stream_client_persistent"], "first_byte_s"),
        "stream_client_first_content_p50": med(out["paths"]["stream_client_persistent"], "first_content_s"),
        "stream_socket_first_byte_p50": med(out["paths"]["stream_socket"], "first_byte_s"),
        "stream_socket_headers_p50": med(out["paths"]["stream_socket"], "headers_s"),
        "stream_socket_first_data_p50": med(out["paths"]["stream_socket"], "first_data_s"),
        "stream_socket_first_content_p50": med(out["paths"]["stream_socket"], "first_content_s"),
    }
    (EVID / "stream_probe2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
