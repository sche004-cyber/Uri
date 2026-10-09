"""Decode-speed probe for a running Runtime v1 (live voice phase, AC-13).

Sends the Brain host's own calibration prompt (scripts/ws_brain_host.py:
CALIBRATION_PROMPT, 160 tokens, temperature 0) to the running server and
records llama.cpp's reported prompt and decode rates. It starts nothing and
stops nothing; it only reads from a server whose GPU lease is held by its
Brain host. Usage:

  python -I brain_decode_probe.py <label> <out.jsonl> [--repeat N] [--url http://127.0.0.1:18470]
"""
import argparse
import json
import time
import urllib.request

PROMPT = "Here is a numbered list of forty everyday household objects, one per line:\n1."


def once(url: str) -> dict:
    body = json.dumps({"prompt": PROMPT, "n_predict": 160, "temperature": 0, "cache_prompt": False}).encode()
    req = urllib.request.Request(url + "/completion", data=body, headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    tm = d.get("timings", {})
    return {"wall_ms": round((time.perf_counter() - t) * 1000), "predicted_n": tm.get("predicted_n"),
            "decode_tps": round(tm.get("predicted_per_second") or 0, 1),
            "prompt_tps": round(tm.get("prompt_per_second") or 0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("out")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--url", default="http://127.0.0.1:18470")
    a = ap.parse_args()
    with open(a.out, "a", encoding="utf-8") as f:
        for i in range(a.repeat):
            r = {"t": time.strftime("%H:%M:%S"), "label": a.label, "i": i, **once(a.url)}
            f.write(json.dumps(r) + "\n")
            print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
