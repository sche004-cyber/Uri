"""Measures the real app's /ask latency for trivial and bounded turns (current Main-Brain-heavy path).

Target: a backend started from a scratch export of the preserved app branch (never the live app),
on a loopback port, with its default local Brain (Ollama qwen3.5:9b). A throwaway test user is
created through the app's own /auth/signup; its password is generated here and never printed.
Records wall-clock latency per turn, the response status, and the Ollama models resident.

Usage: python app_latency.py --base http://127.0.0.1:8765 --out runs/app_latency.jsonl --repeats 3
"""
from __future__ import annotations

import argparse
import json
import secrets
import time
import uuid
from pathlib import Path

import httpx

TURNS = ["hello", "Hi URI", "thanks", "Thank you!", "good night", "What can you do?", "ok", "hey there",
         "hello, how are you?", "How much memory is this computer using right now?",
         "Search the web for NAAC criterion 3 guidelines."]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    c = httpx.Client(base_url=a.base, timeout=300, trust_env=False)
    user = "hflatency" + secrets.token_hex(4)
    r = c.post("/auth/signup", json={"username": user, "password": secrets.token_urlsafe(18)})
    r.raise_for_status()
    token = r.json().get("token") or r.json().get("access_token")
    h = {"Authorization": f"Bearer {token}"}
    out = Path(a.out)
    with out.open("a", encoding="utf-8") as fh:
        for rep in range(a.repeats):
            for t in TURNS:
                sid = str(uuid.uuid4())
                ps = httpx.get("http://127.0.0.1:11434/api/ps", trust_env=False).json()
                t0 = time.perf_counter()
                resp = c.post("/ask", json={"session_id": sid, "text": t}, headers=h)
                ms = (time.perf_counter() - t0) * 1000
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                rec = {"rep": rep, "text": t, "http": resp.status_code, "ms": ms, "status": body.get("status"),
                       "edge": (body.get("_edge_routing") or {}).get("disposition") if isinstance(body.get("_edge_routing"), dict) else None,
                       "narrative": (body.get("narrative") or "")[:200],
                       "serving": {k: body.get(k) for k in body if k.startswith("serving_")},
                       "resident_before": [m["name"] for m in ps.get("models", [])]}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                print(rep, t, resp.status_code, round(ms), rec["status"])


if __name__ == "__main__":
    main()
