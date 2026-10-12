"""URI -> Brain client overhead on the production server (research only).

Compares, on the same resident llama-server and the same requests:
  new_client   : a new httpx client per request (the integration prototype before 2026-10-06)
  persistent   : model_lab.integration.local_brain.BrainClient (one keep-alive pool, reconnect once on failure)
  raw_socket   : a fresh TCP socket per request with a hand-written HTTP/1.1 POST (floor without any client library)
on three request classes: a trivial turn (fast tier, 2 tokens), a repeated cached-context decision turn (the real
Core decision prompt with grammar, prompt cache warm) and a restart/reconnect check (kill the server, start it
again, next call through the persistent client must succeed after exactly one transport error).

  python model_lab/uri_engine/client_overhead.py
Evidence: model_lab/evidence/uri_engine/client_overhead.json
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
for p in (str(HERE), str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import httpx  # noqa: E402

from bench_spec import tasks as spec_tasks  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402
from model_lab.integration.local_brain import BrainClient  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine"
FAST = {"enable_thinking": False}
N = 8


def body(messages, max_tokens, schema=None):
    b = {"model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": 0, "seed": 7, "stream": False,
         "chat_template_kwargs": FAST}
    if schema:
        b["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema, "strict": True}}
    return b


def call_new_client(url, b):
    t0 = time.monotonic()
    j = httpx.post(url + "/v1/chat/completions", json=b, timeout=300).json()
    return time.monotonic() - t0, j


def call_persistent(client, b):
    t0 = time.monotonic()
    j = client.post("/v1/chat/completions", b, timeout=300).json()
    return time.monotonic() - t0, j


def call_socket(host, port, b):
    payload = json.dumps(b).encode()
    req = (f"POST /v1/chat/completions HTTP/1.1\r\nHost: {host}:{port}\r\nContent-Type: application/json\r\n"
           f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n").encode() + payload
    t0 = time.monotonic()
    s = socket.create_connection((host, port), timeout=300)
    s.sendall(req)
    buf = b""
    while True:
        c = s.recv(65536)
        if not c:
            break
        buf += c
    s.close()
    head, _, rest = buf.partition(b"\r\n\r\n")
    j = json.loads(rest.decode(errors="replace")) if rest.strip().startswith(b"{") else {"raw": rest[:200].decode(errors="replace")}
    return time.monotonic() - t0, j


def server_ms(j):
    t = j.get("timings") or {}
    return round((t.get("prompt_ms") or 0) + (t.get("predicted_ms") or 0), 1)


def main():
    cfg = ServerConfig(name="client_overhead", model=CFG["model"]["path"], ctx=32768, ngl=999, port=18494, load_mode="none",
                       mmproj=CFG["model"]["mmproj"], extra=tuple(CFG["runtime"]["extra_args"] + ["--cache-ram", str(CFG["runtime"]["cache_ram_mib"])]))
    srv = Server(cfg, EVID / "overhead_logs").start()
    url = srv.url
    out = {"server_argv": cfg.argv(), "load_seconds": srv.load_seconds, "classes": {}}
    dc = next(t for t in spec_tasks() if t["id"] == "decision_contract")
    classes = {"trivial": body([{"role": "user", "content": "Reply with exactly the two words: ok done"}], 2),
               "decision_cached": body(dc["messages"], 500, dc["json_schema"])}
    client = BrainClient(url)
    try:
        for name, b in classes.items():
            call_persistent(client, b)  # warm the prompt cache / graph
            rows = {"new_client": [], "persistent": [], "raw_socket": []}
            for _ in range(N):
                w, j = call_new_client(url, b)
                rows["new_client"].append({"wall_s": round(w, 4), "server_ms": server_ms(j)})
                w, j = call_persistent(client, b)
                rows["persistent"].append({"wall_s": round(w, 4), "server_ms": server_ms(j)})
                w, j = call_socket("127.0.0.1", cfg.port, b)
                rows["raw_socket"].append({"wall_s": round(w, 4), "server_ms": server_ms(j)})
            summ = {k: {"wall_p50_s": round(statistics.median(r["wall_s"] for r in v), 4),
                        "server_p50_ms": round(statistics.median(r["server_ms"] for r in v), 1),
                        "client_overhead_p50_ms": round(statistics.median(r["wall_s"] * 1000 - r["server_ms"] for r in v), 1)} for k, v in rows.items()}
            out["classes"][name] = {"rows": rows, "summary": summ}
            print(name, json.dumps(summ), flush=True)
        # restart / reconnect: the persistent client must recover after the server process is replaced
        srv.stop()
        err = None
        try:
            client.post("/v1/chat/completions", classes["trivial"], timeout=10, retry_once=False)
        except Exception as exc:
            err = type(exc).__name__
        srv = Server(cfg, EVID / "overhead_logs").start()
        t0 = time.monotonic()
        j = client.post("/v1/chat/completions", classes["trivial"], timeout=300).json()
        out["restart_reconnect"] = {"error_while_down": err, "first_call_after_restart_s": round(time.monotonic() - t0, 3),
                                    "ok": bool(j.get("choices")), "reload_seconds": srv.load_seconds}
        print("restart_reconnect", json.dumps(out["restart_reconnect"]), flush=True)
        out["resources"] = srv.resource_snapshot()
    finally:
        srv.stop()
        client.reset()
    (EVID / "client_overhead.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
