"""Run URI qualification suites against one model/runtime configuration.

Example:
  python model_lab/run_bench.py --name qwen36-35b-a3b --model D:/.../Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
      --family qwen --ctx 32768 --n-cpu-moe 12 --paths fast,deep --suites F,D,C,H,S,O,R,L

Evidence: model_lab/evidence/runs/<name>/<timestamp>/ (results.jsonl, summary.json, server log).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lab import cases as CS  # noqa: E402
from lab import decision, longctx  # noqa: E402
from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig, file_sha256  # noqa: E402

# Per-family reasoning controls. "fast" must be the cheapest mode the model supports.
FAMILIES = {
    "qwen": {"fast": {"enable_thinking": False}, "normal": {"enable_thinking": True, "_budget": 768}, "deep": {"enable_thinking": True}},
    "qwen38": {"fast": {"enable_thinking": False}, "normal": {"enable_thinking": True, "_budget": 768},
               "deep": {"enable_thinking": True}},
    "gptoss": {"fast": {"reasoning_effort": "low"}, "normal": {"reasoning_effort": "medium"}, "deep": {"reasoning_effort": "high"}},
    "gemma": {"fast": {"enable_thinking": False}, "normal": {"enable_thinking": True, "_budget": 768}, "deep": {"enable_thinking": True}},
    "nemotron": {"fast": {"enable_thinking": False}, "normal": {"enable_thinking": True, "_budget": 768}, "deep": {"enable_thinking": True}},
    "plain": {"fast": {}},
}
# Token ceilings: thinking modes need room to think before answering.
MAXTOK = {"fast": {"D": 500, "R": 1500}, "normal": {"D": 3000, "R": 6000}, "deep": {"D": 6000, "R": 12000}}


def pct(values, p):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    k = max(0, min(len(v) - 1, int(round(p / 100 * (len(v) - 1)))))
    return round(v[k], 3)


def summarize(rows):
    out = {}
    by = {}
    for r in rows:
        by.setdefault((r["path"], r["suite"]), []).append(r)
    for (path, suite), rs in sorted(by.items()):
        key = f"{path}/{suite}"
        s = {"n": len(rs), "score": round(statistics.mean(r["score"] for r in rs), 3),
             "ttft_p50": pct([r.get("ttft_s") for r in rs], 50), "ttfa_p50": pct([r.get("ttfa_s") for r in rs], 50),
             "total_p50": pct([r.get("total_s") or r.get("latency_s") for r in rs], 50),
             "total_p95": pct([r.get("total_s") or r.get("latency_s") for r in rs], 95),
             "gen_tps_p50": pct([r.get("gen_tps") for r in rs], 50), "prefill_tps_p50": pct([r.get("prefill_tps") for r in rs], 50),
             "gen_tokens_p50": pct([r.get("gen_tokens") for r in rs], 50),
             "errors": sum(1 for r in rs if r.get("error")),
             "truncated": sum(1 for r in rs if r.get("finish_reason") == "length")}
        if suite == "D":
            s["invalid"] = sum(1 for r in rs if r.get("status") != "ok")
            s["golden_acc"] = round(statistics.mean(r["score"] for r in rs if r["source"] == "m30_golden"), 3)
            s["extra_acc"] = round(statistics.mean(r["score"] for r in rs if r["source"] != "m30_golden"), 3)
            cats = {}
            for r in rs:
                cats[r["category"]] = cats.get(r["category"], 0) + 1
            s["categories"] = cats
        if suite == "C":
            s["hallucinations"] = sum(1 for r in rs if r.get("detail", {}).get("hallucination"))
        if suite == "H":
            s["over_escalation"] = sum(1 for r in rs if r.get("detail", {}).get("over_escalation"))
            s["under_escalation"] = sum(1 for r in rs if r.get("detail", {}).get("under_escalation"))
        if suite == "S":
            for mode in ("prompt", "grammar"):
                sub = [r for r in rs if r["id"].endswith(mode)]
                if sub:
                    s[mode + "_score"] = round(statistics.mean(r["score"] for r in sub), 3)
                    s[mode + "_valid"] = sum(1 for r in sub if r.get("detail", {}).get("valid_json"))
                    s[mode + "_hallucinated_fields"] = sum(len(r.get("detail", {}).get("hallucinated_fields") or []) for r in sub)
        if suite == "V":
            for mode in ("vlm", "ocr"):
                sub = [r for r in rs if r.get("mode") == mode]
                if sub:
                    s[mode + "_score"] = round(statistics.mean(r["score"] for r in sub), 3)
        if suite == "P":
            s["proposer_invalid"] = sum(r.get("proposer_invalid") or 0 for r in rs)
            s["failed_ids"] = [r["id"] for r in rs if r["score"] < 1]
        if suite == "L":
            s["by_size"] = {r["id"]: {"score": r["score"], "prompt_tokens": r.get("prompt_tokens"), "total_s": r.get("total_s"),
                                      "prefill_tps": r.get("prefill_tps"), "checks": r.get("detail", {}).get("checks")} for r in rs}
        out[key] = s
    return out


def _clip(s, n=900):
    return s if len(s) <= 2 * n else s[:n] + " ...[clipped]... " + s[-n:]


ALWAYS_REASONS = {"gptoss"}   # no reasoning-off switch: even "fast" emits a reasoning channel


def run_simple(url, case, path, kwargs, model, family=None):
    # Thinking paths need room to think before the answer; a short cap would only measure truncation.
    max_tokens = case["max_tokens"] if (path == "fast" and family not in ALWAYS_REASONS) else max(case["max_tokens"], 4000)
    r = chat(url, case["messages"], max_tokens=max_tokens, temperature=0.0, template_kwargs=kwargs,
             json_schema=case.get("json_schema"), model=model)
    try:
        det = case["score"](r)
    except Exception as exc:  # scorer must never crash the run
        det = {"score": 0.0, "scorer_error": repr(exc)}
    return {"id": case["id"], "suite": case["suite"], "path": path, "score": det.get("score", 0.0), "detail": det,
            **{k: r.get(k) for k in ("ttft_s", "ttfa_s", "total_s", "prompt_tokens", "gen_tokens", "gen_tps", "prefill_tps",
                                     "finish_reason", "error")},
            "reasoning_chars": len(r.get("reasoning") or ""), "content": _clip(r.get("content") or "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--model")
    ap.add_argument("--url", help="use an already running OpenAI-compatible server instead of launching one")
    ap.add_argument("--api-model", default="local")
    ap.add_argument("--family", default="qwen")
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--n-cpu-moe", type=int, default=0)
    ap.add_argument("--ngl", type=int, default=999)
    ap.add_argument("--cache", default="q8_0")
    ap.add_argument("--paths", default="fast")
    ap.add_argument("--suites", default="F,D,C,H,S,O,R")
    ap.add_argument("--l-sizes", default="4000,16000,32000")
    ap.add_argument("--repeat-f", type=int, default=3)
    ap.add_argument("--port", type=int, default=18480)
    ap.add_argument("--load-mode", default="none")
    ap.add_argument("--extra", default="")
    ap.add_argument("--mmproj", default=None)
    a = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "evidence" / "runs" / a.name / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {"name": a.name, "args": vars(a), "started": stamp}
    srv = None
    if a.url:
        url = a.url
    else:
        cfg = ServerConfig(name=a.name, model=a.model, ctx=a.ctx, n_cpu_moe=a.n_cpu_moe, ngl=a.ngl,
                           cache_k=a.cache, cache_v=a.cache, port=a.port,
                           load_mode=a.load_mode, extra=tuple(a.extra.split()), mmproj=a.mmproj)
        meta["model_sha256"] = file_sha256(a.model)
        meta["argv"] = cfg.argv()
        srv = Server(cfg, out_dir).start()
        url = srv.url
        meta["load"] = srv.resource_snapshot()
        meta["props"] = {k: v for k, v in srv.props().items() if k in ("model_path", "n_ctx", "build_info", "default_generation_settings")}
    fam = FAMILIES[a.family]
    suites = [s.strip() for s in a.suites.split(",") if s.strip()]
    rows = []
    res_f = open(out_dir / "results.jsonl", "w", encoding="utf-8")

    def emit(row):
        rows.append(row)
        res_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        res_f.flush()

    # warm-up (excluded): first request pays graph/allocation costs
    chat(url, [{"role": "user", "content": "Hello"}], max_tokens=8, template_kwargs=fam.get("fast"), model=a.api_model)
    for path in [p.strip() for p in a.paths.split(",") if p.strip()]:
        if path not in fam:
            continue
        kw = fam[path]
        t0 = time.monotonic()
        for suite in suites:
            if suite == "D":
                for row in decision.run_suite(url, max_tokens=MAXTOK[path]["D"], template_kwargs=kw, model=a.api_model):
                    row["path"] = path
                    emit(row)
                continue
            if suite == "DG":
                for row in decision.run_suite(url, max_tokens=MAXTOK[path]["D"], template_kwargs=kw, grammar=True, model=a.api_model):
                    row["path"], row["suite"] = path, "DG"
                    emit(row)
                continue
            if suite == "V":
                from lab import vision
                for row in vision.run(url, template_kwargs=kw, model=a.api_model):
                    row["path"] = path
                    emit(row)
                continue
            if suite == "P":
                from lab import paired
                for row in paired.run(url, label=a.name, template_kwargs=kw, model=a.api_model, max_tokens=MAXTOK[path]["D"]):
                    row["path"] = path
                    emit(row)
                continue
            if suite == "L":
                lc = longctx.build_cases(tuple(int(x) for x in a.l_sizes.split(",")))
                for c in lc:
                    emit(run_simple(url, c, path, kw, a.api_model, a.family))
                continue
            builders = {"C": [CS.build_c(c) for c in CS.C_CASES], "H": [CS.build_h(c) for c in CS.H_CASES],
                        "R": [CS.build_r(c, MAXTOK[path]["R"]) for c in CS.R_CASES],
                        "S": [CS.build_s(c, False) for c in CS.S_CASES] + [CS.build_s(c, True) for c in CS.S_CASES],
                        "O": [CS.build_o(c) for c in CS.O_CASES], "F": [CS.build_f(c) for c in CS.F_CASES],
                        "RH": __import__("lab.hard", fromlist=["build"]).build(max(MAXTOK[path]["R"], 4000) if path != "fast" else 3000)}
            reps = a.repeat_f if suite == "F" else 1
            for rep in range(reps):
                for c in builders[suite]:
                    row = run_simple(url, c, path, kw, a.api_model, a.family)
                    row["rep"] = rep
                    emit(row)
        meta.setdefault("path_wall_s", {})[path] = round(time.monotonic() - t0, 1)
    res_f.close()
    if srv:
        meta["resources_end"] = srv.resource_snapshot()
        srv.stop()
    summary = {"meta": meta, "summary": summarize(rows)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary["summary"], indent=1))
    print("EVIDENCE", out_dir)


if __name__ == "__main__":
    main()







