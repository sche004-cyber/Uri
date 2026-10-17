"""CRASH-1 reproduction attempt (RUNTIME-PROFILES-INTEG live run p1b-main): llama-server b11425 exited with
0xC0000409 (fail-fast, no log message) on profile 64K + vision GPU, MTP off, right after a streamed task was cancelled
after 4 tokens and the next request was selected. P2 (64K main only) and a P1 repeat did not crash.

This drives the same pattern on a lab server (lab port, GPU lease, vlab isolation rules), N cycles of:
  1. a URI-like request (long fixed system prompt + short user turn) streamed, connection closed after K tokens
     (llama-server cancels the task: "srv stop: cancel task");
  2. immediately a full request with a different suffix (new task, prefix reuse from the cache).
Ordinary requests only, at normal URI turn sizes; no stress beyond the observed pattern.

    python -I crash_repro.py <name> --ctx 65536 --vision gpu [--no-mtp] [--cycles 150]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlab  # noqa: E402
import run_probe as RP  # noqa: E402


def stream_and_cancel(url, msgs, k):
    body = {"model": "local", "messages": msgs, "max_tokens": 300, "temperature": 0.0, "stream": True,
            "chat_template_kwargs": {"enable_thinking": False}}
    n = 0
    with httpx.Client(timeout=60) as c, c.stream("POST", url + "/v1/chat/completions", json=body) as r:
        for line in r.iter_lines():
            if line.startswith("data: ") and '"content"' in line:
                n += 1
                if n >= k:
                    break                       # closing the stream cancels the task server-side
    return n


def full(url, msgs):
    r = httpx.post(url + "/v1/chat/completions", json={"model": "local", "messages": msgs, "max_tokens": 60,
                                                       "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}},
                   timeout=120)
    return r.status_code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--ctx", type=int, default=65536)
    ap.add_argument("--vision", default="gpu")
    ap.add_argument("--no-mtp", action="store_true")
    ap.add_argument("--cycles", type=int, default=150)
    a = ap.parse_args()
    prof = vlab.Profile(a.name, ctx=a.ctx, mtp=not a.no_mtp, vision=a.vision)
    run_dir = vlab.EVIDENCE / "crash_repro" / f"{time.strftime('%Y%m%d-%H%M%S')}_{a.name}"
    srv = vlab.Server(prof, run_dir, max_hold_s=1800)
    rec = srv.record
    rows = []
    try:
        srv.start()
        for i in range(a.cycles):
            task = RP.URI_TASKS[i % len(RP.URI_TASKS)]
            msgs = [{"role": "system", "content": RP.URI_SYSTEM}, {"role": "user", "content": task + RP.URI_FORMAT}]
            k = 2 + (i % 5)
            got = stream_and_cancel(srv.url, msgs, k)
            msgs2 = [{"role": "system", "content": RP.URI_SYSTEM}, {"role": "user", "content": f"Turn {i}: say OK."}]
            st = full(srv.url, msgs2)
            alive = srv.proc.poll() is None
            rows.append({"i": i, "k": k, "got": got, "status": st, "alive": alive})
            if not alive:
                rec["crashed_at_cycle"] = i
                rec["exit_code"] = srv.proc.returncode
                break
        rec["cycles_done"] = len(rows)
        rec["after"] = srv.memory() if srv.proc.poll() is None else None
        rec["classification"] = "COMPLETED_WITH_RESULT"
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["classification"] = "FAILED" if srv.proc is None or srv.proc.poll() is None else "COMPLETED_WITH_RESULT"
        if srv.proc is not None and srv.proc.poll() is not None:
            rec["crashed_at_cycle"] = len(rows)
            rec["exit_code"] = srv.proc.returncode
    finally:
        rec["rows"] = rows
        srv.stop()
        vlab.save(run_dir, "crash_repro", rec)
    print(json.dumps({k: rec.get(k) for k in ("classification", "cycles_done", "crashed_at_cycle", "exit_code", "error")}))
    print("EVIDENCE", run_dir)


if __name__ == "__main__":
    main()
