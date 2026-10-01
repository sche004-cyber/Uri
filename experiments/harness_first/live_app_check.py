"""Exercise a running URI backend the way the desktop app does (POST /ask/stream, SSE) and record which
path handled each turn: harness_route (harness-first seam), serving model, wall latency.

Run against a scratch backend started from this branch (never the live app). A throwaway test user is
created through the app's own /auth/signup; its password is generated here and never printed.
Usage: python live_app_check.py --base http://127.0.0.1:8766 --out runs/live_app_r1.jsonl --repeats 3
"""
from __future__ import annotations

import argparse
import json
import secrets
import time
import uuid

import httpx

SOCIAL = ["hello", "hey there", "Thank you so much!", "good night", "ok cool", "what can you do?",
          "hi URI, how are you?", "thanks, bye", "see you tomorrow", "what's your name?", "namaste", "great, thanks"]
WORK = ["How much memory is this computer using right now?", "Search the web for NAAC criterion 3 guidelines.",
        "hi, how much RAM is this PC using?", "Don't search anything, just tell me what NAAC is."]


def stream(c, h, text):
    sid = str(uuid.uuid4())
    t0 = time.perf_counter()
    first = None
    msg = None
    with c.stream("POST", "/ask/stream", json={"session_id": sid, "text": text}, headers=h) as r:
        ev = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                if first is None:
                    first = (time.perf_counter() - t0) * 1000
                data = json.loads(line[5:])
                if ev in ("message", "done") and isinstance(data, dict) and ("status" in data or "envelope" in data):
                    msg = data.get("envelope", data) if ev == "done" and "envelope" in data else (data if ev == "message" else msg)
    return (time.perf_counter() - t0) * 1000, first, msg or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    c = httpx.Client(base_url=a.base, timeout=300, trust_env=False)
    r = c.post("/auth/signup", json={"username": "hflive" + secrets.token_hex(4), "password": secrets.token_urlsafe(18)})
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}
    with open(a.out, "a", encoding="utf-8") as fh:
        for rep in range(a.repeats):
            for kind, turns in (("social", SOCIAL), ("work", WORK)):
                for t in turns:
                    ms, first, m = stream(c, h, t)
                    rec = {"rep": rep, "kind": kind, "text": t, "ms": round(ms), "first_event_ms": round(first or 0),
                           "status": m.get("status"), "harness_route": m.get("harness_route"),
                           "serving_provider": m.get("serving_provider"), "serving_model": m.get("serving_model"),
                           "reasoning_s": m.get("serving_reasoning_duration_seconds"),
                           "drafting_s": m.get("serving_drafting_duration_seconds"),
                           "reply": (m.get("narrative") or (m.get("response") or {}).get("message") or "")[:200]}
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
                    print(rep, kind, t[:30], rec["ms"], rec["serving_model"], (rec["harness_route"] or {}).get("class"))


if __name__ == "__main__":
    main()
