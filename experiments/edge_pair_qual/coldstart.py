"""Cold-start, warm-run and resource measurements (report A/B). No battery cases are used.

Needle: a fresh worker process each trial; time to ready, first decode (includes agent build),
then 20 warm decodes on the same tool set. RSS of the worker process tree.
Granite and Brain: unload (keep_alive 0), then time the first request (Ollama load_duration),
then 20 warm requests. VRAM from /api/ps.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness  # noqa: E402
from catalogue import ACTIONS, public  # noqa: E402

TOOLS = [public(ACTIONS[n]) for n in ("read_attached_file", "drive_search", "system_performance", "web_search")]
SYSTEM = harness.BASE_RULES + harness.P0_RULES
TEXTS = ["User request: Read the attached file travel_claim_0712.pdf.",
         "User request: How much disk space is left on this computer?"]


def needle_trials(n=5, warm=20):
    out = []
    for _ in range(n):
        ad = harness.NeedleAdapter()
        t = time.perf_counter()
        ad.start()
        ready = (time.perf_counter() - t) * 1000
        sp = {"system": SYSTEM, "tools": TOOLS, "user": TEXTS[0]}
        r1 = ad.call(sp, {"kind": "select"}, "P0", None)
        ws = []
        for i in range(warm):
            sp["user"] = TEXTS[i % 2]
            ws.append(ad.call(sp, {"kind": "select"}, "P0", None)["wall_ms"])
        out.append({"process_ready_ms": ready, "first_decode_wall_ms": r1["wall_ms"],
                    "first_agent_build_ms": r1["agent_build_ms"], "warm_wall_ms": ws, "peak_rss_bytes": ad.peak_rss,
                    "needle_peak_ram_mb": r1["raw"].get("peak_ram_mb")})
        ad.close()
    return out


def ollama_trials(model, n=5, warm=20, num_ctx=4096, think=None):
    c = httpx.Client(timeout=300, trust_env=False)
    out = []
    for _ in range(n):
        c.post(f"{harness.OLLAMA}/api/generate", json={"model": model, "keep_alive": 0})
        time.sleep(2)
        body = {"model": model, "stream": False, "keep_alive": "30m",
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TEXTS[0]}],
                "tools": [{"type": "function", "function": t} for t in TOOLS],
                "options": {"temperature": 0, "seed": 42, "num_predict": 128}}
        if num_ctx:
            body["options"]["num_ctx"] = num_ctx
        if think is not None:
            body["think"] = think
        t = time.perf_counter()
        r = c.post(f"{harness.OLLAMA}/api/chat", json=body).json()
        first = (time.perf_counter() - t) * 1000
        ps = c.get(f"{harness.OLLAMA}/api/ps").json()
        ws = []
        for i in range(warm):
            body["messages"][1]["content"] = TEXTS[i % 2]
            t = time.perf_counter()
            c.post(f"{harness.OLLAMA}/api/chat", json=body)
            ws.append((time.perf_counter() - t) * 1000)
        out.append({"first_wall_ms": first, "load_duration_ms": (r.get("load_duration") or 0) / 1e6,
                    "warm_wall_ms": ws, "ps": ps})
    return out


if __name__ == "__main__":
    which = sys.argv[1]
    res = {"load_before": harness.load_snapshot()}
    if which == "needle":
        res["needle"] = needle_trials()
    elif which == "granite":
        res["granite"] = ollama_trials(harness.GRANITE)
    elif which == "brain":
        res["brain"] = ollama_trials(harness.BRAIN, n=2, warm=5, num_ctx=None, think=False)
    res["load_after"] = harness.load_snapshot()
    Path(HERE / "runs").mkdir(exist_ok=True)
    p = HERE / "runs" / f"coldstart_{which}_{int(time.time())}.json"
    p.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(p)
