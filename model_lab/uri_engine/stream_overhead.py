"""Streaming vs non-streaming request overhead on the production server configuration.

bench_uri.py's client measures time-to-first-token on the SSE stream; overhead.py showed the non-streaming
wall time is within 3-10 ms of the server's own prompt+decode timings. This isolates where the remaining
~0.2 s of a trivial streamed turn goes: server-side prompt eval of a small batch, first decode step, SSE
delivery, or the Python client.

  python model_lab/uri_engine/stream_overhead.py
"""
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
import httpx  # noqa: E402

from lab import prompts as P  # noqa: E402
from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine"
FAST = {"enable_thinking": False}


def main():
    cfg = ServerConfig(name="stream", model=CFG["model"]["path"], ctx=32768, ngl=999, port=18493, load_mode="none",
                       mmproj=CFG["model"]["mmproj"], extra=("-b", "2048", "-ub", "1024", "--cache-ram", "1024"))
    srv = Server(cfg, EVID / "stream_logs").start()
    out = {}
    try:
        msgs = [{"role": "system", "content": P.FAST_SYSTEM}, {"role": "user", "content": "Which is larger, 0.7 or 0.65? Answer in one sentence."}]
        chat(srv.url, msgs, max_tokens=8, template_kwargs=FAST)
        rows = []
        for i in range(6):
            q = [{"role": "system", "content": P.FAST_SYSTEM}, {"role": "user", "content": f"Give one word that rhymes with 'light' (variant {i})."}]
            r = chat(srv.url, q, max_tokens=12, template_kwargs=FAST)
            t = r["timings"]
            rows.append({"ttft_client_s": r["ttft_s"], "total_client_s": r["total_s"], "prompt_n": t["prompt_n"], "cache_n": t["cache_n"],
                         "prompt_ms": t["prompt_ms"], "predicted_n": t["predicted_n"], "predicted_ms": t["predicted_ms"]})
        out["stream"] = rows
        with httpx.Client(timeout=60) as c:
            ns = []
            for i in range(6):
                q = [{"role": "system", "content": P.FAST_SYSTEM}, {"role": "user", "content": f"Give one word that rhymes with 'night' (variant {i})."}]
                t0 = time.perf_counter()
                j = c.post(srv.url + "/v1/chat/completions", json={"messages": q, "max_tokens": 12, "temperature": 0,
                                                                   "chat_template_kwargs": FAST}).json()
                wall = time.perf_counter() - t0
                t = j["timings"]
                ns.append({"wall_s": round(wall, 3), "prompt_n": t["prompt_n"], "cache_n": t["cache_n"], "prompt_ms": t["prompt_ms"],
                           "predicted_n": t["predicted_n"], "predicted_ms": t["predicted_ms"],
                           "unaccounted_ms": round(wall * 1000 - t["prompt_ms"] - t["predicted_ms"], 1)})
            out["nonstream"] = ns
            # prompt-eval cost vs new-token count (small-batch prefill efficiency)
            pe = []
            for n_words in (1, 8, 32, 128, 512):
                q = [{"role": "system", "content": P.FAST_SYSTEM}, {"role": "user", "content": " ".join(f"w{k}" for k in range(n_words)) + " . Reply with OK."}]
                j = c.post(srv.url + "/v1/chat/completions", json={"messages": q, "max_tokens": 1, "temperature": 0, "chat_template_kwargs": FAST}).json()
                t = j["timings"]
                pe.append({"new_tokens": t["prompt_n"], "cache_n": t["cache_n"], "prompt_ms": t["prompt_ms"],
                           "ms_per_new_token": round(t["prompt_ms"] / max(1, t["prompt_n"]), 2)})
            out["prompt_eval_vs_size"] = pe
    finally:
        srv.stop()
    out["summary"] = {
        "stream_ttft_p50": statistics.median(r["ttft_client_s"] for r in out["stream"]),
        "stream_server_prompt_ms_p50": statistics.median(r["prompt_ms"] for r in out["stream"]),
        "nonstream_wall_p50": statistics.median(r["wall_s"] for r in out["nonstream"]),
        "nonstream_unaccounted_ms_p50": statistics.median(r["unaccounted_ms"] for r in out["nonstream"]),
    }
    (EVID / "stream_overhead.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
