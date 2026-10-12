"""OI benchmarks against a READY Runtime v1 (attaches; never starts or stops the runtime).

    .venv\\Scripts\\python.exe -m uri_operational_intelligence.bench.reasoning --label mtp [--url http://127.0.0.1:18470]
        [--parts tasks,routing,latency] [--tiers FAST,NORMAL]

Measured separately (the mandate: never conflate them): prompt processing (prompt_n, prompt tok/s), time to first token,
decode throughput (predicted tok/s), MTP draft acceptance, wall time, VRAM / server RSS samples, and task success
(deterministic code-checked scores). Writes work/oi/evidence/bench_<label>_<ts>.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from .. import answer as A
from .. import brain_client as BC
from .. import reasoning_policy as RP
from .. import triage as T
from . import tasks as TK

SYSTEM = "You are URI's reasoning engine. Think carefully, then answer with the requested JSON only."


def server_rss():
    import psutil
    for p in psutil.process_iter(["name", "memory_info"]):
        if (p.info["name"] or "").lower() == "llama-server.exe":
            return round(p.info["memory_info"].rss / 2**20, 1)
    return None


def residency():
    """Per-process GPU dedicated/shared MiB of the server (OI-PERF-1 check: a timing run is valid only when residency
    did not drop during it)."""
    import psutil
    from ..perf_monitor import gpu_process_memory
    pid = next((p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "llama-server.exe"), None)
    d, s = gpu_process_memory(pid)
    return {"pid": pid, "dedicated_mib": d, "shared_mib": s}


def vram():
    try:
        sys.path.insert(0, str(ROOT / "model_lab"))
        from lab.runtime import gpu_dedicated_mib
        return gpu_dedicated_mib()
    except Exception:
        return None


def run_tasks(client, tiers):
    rows = []
    for tier in tiers:
        for t in TK.TASKS:
            body = {"model": "local", "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": t["prompt"]}],
                    "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": t["schema"], "strict": True}},
                    **RP.tier_params(tier, use="answer")}
            res = client.stream_chat(body, deadlines=BC.Deadlines(first_token_s=60, idle_s=60, total_s=240))
            score, err = 0.0, None
            if res.status == BC.COMPLETE:
                try:
                    score = float(t["check"](json.loads(res.text)))
                except Exception as exc:
                    err = "SCORE_ERROR:" + type(exc).__name__
            rows.append({"tier": tier, "id": t["id"], "cat": t["cat"], "status": res.status, "score": score, "error": err,
                         "answer": res.text[:300], "ttft_s": res.ttft_s, "first_answer_s": res.first_answer_s,
                         "total_s": res.total_s, "reasoning_chars": len(res.reasoning),
                         "prompt_n": res.timings.get("prompt_n"), "prompt_tps": res.timings.get("prompt_per_second"),
                         "predicted_n": res.timings.get("predicted_n"), "decode_tps": res.timings.get("predicted_per_second"),
                         "draft_n": res.timings.get("draft_n"), "draft_accepted": res.timings.get("draft_n_accepted"),
                         "cache_n": res.timings.get("cache_n")})
            print(tier, t["id"], res.status, score, res.total_s, flush=True)
    return rows


def summarize_tasks(rows):
    out = {}
    for tier in sorted({r["tier"] for r in rows}):
        rs = [r for r in rows if r["tier"] == tier]
        cats = {}
        for r in rs:
            cats.setdefault(r["cat"], []).append(r["score"])
        dec = [r["decode_tps"] for r in rs if r["decode_tps"]]
        drafts = sum(r["draft_n"] or 0 for r in rs)
        out[tier] = {"score": round(sum(r["score"] for r in rs) / len(rs), 3),
                     "by_category": {c: round(sum(v) / len(v), 3) for c, v in sorted(cats.items())},
                     "non_complete": [(r["id"], r["status"]) for r in rs if r["status"] != BC.COMPLETE],
                     "total_s_p50": round(statistics.median(r["total_s"] for r in rs), 2),
                     "total_s_p90": round(sorted(r["total_s"] for r in rs)[int(0.9 * (len(rs) - 1))], 2),
                     "ttft_s_p50": round(statistics.median(r["ttft_s"] for r in rs if r["ttft_s"]), 3),
                     "first_answer_s_p50": round(statistics.median(r["first_answer_s"] for r in rs if r["first_answer_s"]), 3),
                     "decode_tps_p50": round(statistics.median(dec), 1) if dec else None,
                     "prompt_tps_p50": round(statistics.median(r["prompt_tps"] for r in rs if r["prompt_tps"]), 1),
                     "predicted_n_p50": statistics.median(r["predicted_n"] or 0 for r in rs),
                     "draft_acceptance": round(sum(r["draft_accepted"] or 0 for r in rs) / drafts, 3) if drafts else None}
    return out


def run_routing(client):
    rows = []
    for text, needs_core in TK.ROUTING:
        tri = T.triage(text)
        to_core = tri.kind in (T.ACTION, T.HARNESS, T.MULTI_STEP)
        marker = None
        if not to_core:
            r = A.answer(client, text, tier=RP.FAST, max_tokens=60)
            marker = r.status == "ACTION_REQUESTED"
        rows.append({"text": text, "needs_core": needs_core, "triage": tri.kind, "triage_to_core": to_core,
                     "marker": marker, "final_to_core": bool(to_core or marker)})
    pos = [r for r in rows if r["needs_core"]]
    neg = [r for r in rows if not r["needs_core"]]
    return {"rows": rows,
            "triage_recall": round(sum(r["triage_to_core"] for r in pos) / len(pos), 3),
            "triage_false_positive": round(sum(r["triage_to_core"] for r in neg) / len(neg), 3),
            "combined_recall": round(sum(r["final_to_core"] for r in pos) / len(pos), 3),
            "combined_false_positive": round(sum(r["final_to_core"] for r in neg) / len(neg), 3),
            "missed": [r["text"] for r in pos if not r["final_to_core"]],
            "over_routed": [r["text"] for r in neg if r["final_to_core"]]}


def run_latency(client):
    """Simple turns through the answer channel as the orchestrator runs them (warm server, persistent client)."""
    turns = [("hi", T.TRIVIAL), ("thanks!", T.TRIVIAL), ("What is an office order?", T.QUESTION),
             ("How many days are there in a leap year?", T.QUESTION), ("Translate 'good morning' into Hindi.", T.QUESTION),
             ("Give me 3 ideas for annual day themes.", T.QUESTION)] * 2
    rows = []
    for text, kind in turns:
        t0 = time.monotonic()
        tri = T.triage(text)
        tier = RP.decide(tri.kind)
        r = A.answer(client, text, tier=tier.tier, use="trivial" if tri.kind == T.TRIVIAL else "answer")
        rows.append({"text": text, "triage": tri.kind, "tier": tier.tier, "status": r.status,
                     "first_answer_s": r.metrics["first_answer_s"], "total_s": round(time.monotonic() - t0, 3),
                     "predicted_n": r.metrics["predicted_n"], "decode_tps": r.metrics["predicted_per_second"]})
    fa = [r["first_answer_s"] for r in rows if r["first_answer_s"]]
    return {"rows": rows, "first_answer_s_p50": round(statistics.median(fa), 3), "first_answer_s_max": max(fa),
            "total_s_p50": round(statistics.median(r["total_s"] for r in rows), 3),
            "total_s_max": max(r["total_s"] for r in rows),
            "under_2s": sum(1 for r in rows if r["total_s"] < 2.0), "n": len(rows)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:18470")
    ap.add_argument("--parts", default="tasks,routing,latency")
    ap.add_argument("--tiers", default="FAST,NORMAL")
    a = ap.parse_args(argv)
    client = BC.BrainClient(a.url)
    parts = a.parts.split(",")
    report = {"label": a.label, "url": a.url, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "memory_before": {"vram_mib": vram(), "server_rss_mib": server_rss(), "server_gpu": residency()}}
    with BC.httpx.Client() as h:
        report["props"] = {k: v for k, v in h.get(a.url + "/props").json().items() if k in ("model_path", "build_info", "total_slots")}
    if "latency" in parts:
        report["latency"] = run_latency(client)
    if "tasks" in parts:
        rows = run_tasks(client, a.tiers.split(","))
        report["tasks"] = {"rows": rows, "summary": summarize_tasks(rows)}
    if "routing" in parts:
        report["routing"] = run_routing(client)
    report["memory_after"] = {"vram_mib": vram(), "server_rss_mib": server_rss(), "server_gpu": residency()}
    out = ROOT / "work/oi/evidence" / ("bench_%s_%s.json" % (a.label, time.strftime("%Y%m%d-%H%M%S")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    brief = {k: v for k, v in report.items() if k in ("label", "memory_before", "memory_after")}
    if "tasks" in report:
        brief["tasks"] = report["tasks"]["summary"]
    if "routing" in report:
        brief["routing"] = {k: v for k, v in report["routing"].items() if k != "rows"}
    if "latency" in report:
        brief["latency"] = {k: v for k, v in report["latency"].items() if k != "rows"}
    print(json.dumps(brief, indent=1))
    print("EVIDENCE", out)


if __name__ == "__main__":
    main()
