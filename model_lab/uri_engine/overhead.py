"""Per-request fixed overhead decomposition for llama-server on URI prompts.

For a trivial prompt and a decision prompt: time /apply-template (jinja render), /tokenize (full prompt),
a non-streaming completion with max_tokens=1 (wall) against the server's own timings (prompt_ms +
predicted_ms), and the same with the grammar (json_schema) on/off. The difference wall - (prompt_ms +
predicted_ms) is the HTTP/template/tokenize/sampler-setup/cache-management cost per request.

  python model_lab/uri_engine/overhead.py --extra "-b 2048 -ub 1024 --cache-ram 1024"
"""
import argparse
import json
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

from lab import decision  # noqa: E402
from lab import prompts as P  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402
from scripts.m30_4_decision_quality_analysis import real_directory, turn_state_for  # noqa: E402
from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT, build_decision_request, preselect_candidate_ids  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine"


def timed(fn, n=5):
    xs = []
    out = None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        xs.append(time.perf_counter() - t0)
    return round(statistics.median(xs) * 1000, 1), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", default="-b 2048 -ub 1024 --cache-ram 1024")
    ap.add_argument("--port", type=int, default=18498)
    a = ap.parse_args()
    cfg = ServerConfig(name="overhead", model=CFG["model"]["path"], ctx=32768, ngl=999, port=a.port, load_mode="none",
                       mmproj=CFG["model"]["mmproj"], extra=tuple(a.extra.split()))
    srv = Server(cfg, EVID / "overhead_logs").start()
    url = srv.url
    directory = real_directory()
    st = turn_state_for("Draft an office order appointing Dr. Rao as warden from 1 November.", directory)
    pre = preselect_candidate_ids(st, directory) or [s["capability_id"] for s in directory.summaries()]
    req = build_decision_request(st, preselected_ids=pre, capability_directory=directory)
    schema = decision.decision_schema([s["capability_id"] for s in req["capability_summaries"]])
    prompts = {
        "trivial": [{"role": "system", "content": P.FAST_SYSTEM}, {"role": "user", "content": "What is 2+2?"}],
        "decision": [{"role": "system", "content": DECISION_CONTRACT_SYSTEM_PROMPT},
                     {"role": "user", "content": json.dumps(req, sort_keys=True, separators=(",", ":"), ensure_ascii=True)}],
    }
    res = {"extra": a.extra, "load_seconds": srv.load_seconds}
    try:
        with httpx.Client(timeout=120) as c:
            c.post(url + "/v1/chat/completions", json={"messages": prompts["trivial"], "max_tokens": 1,
                                                       "chat_template_kwargs": {"enable_thinking": False}})
            for name, msgs in prompts.items():
                r = {}
                body = {"messages": msgs, "chat_template_kwargs": {"enable_thinking": False}}
                r["apply_template_ms"], tpl = timed(lambda: c.post(url + "/apply-template", json=body).json())
                text = tpl.get("prompt", "")
                r["prompt_chars"] = len(text)
                r["tokenize_ms"], tok = timed(lambda: c.post(url + "/tokenize", json={"content": text}).json())
                r["prompt_tokens"] = len(tok.get("tokens", []))
                for label, extra in (("plain", {}), ("grammar", {"response_format": {"type": "json_schema", "json_schema": {"name": "o", "schema": schema, "strict": True}}})):
                    def call():
                        return c.post(url + "/v1/chat/completions", json={**body, "max_tokens": 1, "temperature": 0, **extra}).json()
                    wall, out = timed(call, 5)
                    tm = out.get("timings", {})
                    r[label] = {"wall_ms": wall, "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"),
                                "prompt_ms": tm.get("prompt_ms"), "predicted_ms": tm.get("predicted_ms"),
                                "unaccounted_ms": round(wall - (tm.get("prompt_ms") or 0) - (tm.get("predicted_ms") or 0), 1)}
                # 20-token generation: per-token cost with/without grammar
                for label, extra in (("plain20", {}), ("grammar20", {"response_format": {"type": "json_schema", "json_schema": {"name": "o", "schema": schema, "strict": True}}})):
                    def call20():
                        return c.post(url + "/v1/chat/completions", json={**body, "max_tokens": 40, "temperature": 0, **extra}).json()
                    wall, out = timed(call20, 3)
                    tm = out.get("timings", {})
                    r[label] = {"wall_ms": wall, "predicted_n": tm.get("predicted_n"), "predicted_ms": tm.get("predicted_ms"),
                                "ms_per_token": round(tm["predicted_ms"] / tm["predicted_n"], 2) if tm.get("predicted_n") else None}
                res[name] = r
    finally:
        srv.stop()
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "overhead.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
