"""Determinism probe 2: is the decision_contract output a function of the prompt-processing layout? (research only)

determinism_probe.py showed: production flags -> 188-token text (5/5 calls), --ctx-checkpoints 0 -> a different
198-token text (5/5 calls). The server trace explains the difference in processing: with checkpoints the prompt is
split into ubatches at the message boundaries where checkpoints are created; without them it runs in plain
-ub-sized ubatches. The bench_spec rep1 (192 tokens) resumed from a restored checkpoint (n_past = 54), a third layout.

Part 1 (layout): no prompt cache, no checkpoints; -ub 1024 / 512 / 256; one fresh server each; "hi" then the
decision_contract prompt 3x non-streaming with top-3 logprobs. If the text follows -ub and is stable within -ub, the
anomaly is batch-layout numerics (different accumulation order per ubatch split), not randomness.
Part 2 (replay): production flags, the exact bench_spec task order (8 tasks x 2 reps, streaming, same client), but
the decision_contract occurrences are made non-streaming with logprobs so the first divergent token's top-2 margin
is readable. Server trace lines (-lv 4) around each decision_contract task are kept.
Part 3 (run-to-run, same layout): the Part 1 -ub 1024 server is asked the same prompt 3 more times after a 16k
filler prompt (the ctx_control observation: 6/30 same-layout repeats differed at 16k-30k).

  python model_lab/uri_engine/determinism_probe2.py
Evidence: model_lab/evidence/uri_engine/determinism_probe2.json (+ determinism_logs/server_det2_*.log)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(HERE), str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import httpx  # noqa: E402

from bench_spec import tasks as spec_tasks  # noqa: E402
from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine"
FAST = {"enable_thinking": False}
PAT = re.compile(r"checkpoint|prompt cache|forcing full|cached n_tokens|erasing|superseding|restored|n_past|f_sim", re.I)
OUT = EVID / "determinism_probe2.json"


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def nonstream(url, t):
    body = {"messages": t["messages"], "max_tokens": t["max_tokens"], "temperature": 0, "seed": 7, "chat_template_kwargs": FAST,
            "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": t["json_schema"], "strict": True}},
            "logprobs": True, "top_logprobs": 3}
    j = httpx.post(url + "/v1/chat/completions", json=body, timeout=600).json()
    ch = j["choices"][0]
    toks = [{"token": it.get("token"), "logprob": it.get("logprob"), "top": [(x.get("token"), x.get("logprob")) for x in it.get("top_logprobs") or []]}
            for it in (ch.get("logprobs") or {}).get("content") or []]
    tm = j.get("timings") or {}
    text = ch["message"]["content"]
    return {"text": text, "sha": sha(text), "finish": ch.get("finish_reason"), "predicted_n": tm.get("predicted_n"),
            "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"), "tokens": toks}


def divergence(a, b):
    ta, tb = a.get("tokens") or [], b.get("tokens") or []
    for i, (x, y) in enumerate(zip(ta, tb)):
        if x["token"] != y["token"]:
            def margin(tok):
                top = sorted(tok["top"], key=lambda z: -z[1]) if tok["top"] else []
                return round(top[0][1] - top[1][1], 4) if len(top) > 1 else None
            return {"token_index": i, "a": x["token"], "b": y["token"], "a_margin_top2": margin(x), "b_margin_top2": margin(y),
                    "a_top": x["top"], "b_top": y["top"]}
    return {"token_index": None, "len_a": len(ta), "len_b": len(tb), "note": "no token-level difference within the shorter output"}


def margins(r):
    """Smallest top-2 margins along the output: how close to a tie the greedy path runs."""
    ms = []
    for i, tok in enumerate(r.get("tokens") or []):
        top = sorted(tok["top"], key=lambda z: -z[1]) if tok["top"] else []
        if len(top) > 1:
            ms.append((round(top[0][1] - top[1][1], 4), i, top[0][0], top[1][0]))
    ms.sort()
    return [{"margin": m, "index": i, "top1": a, "top2": b} for m, i, a, b in ms[:5]]


def strip(r):
    return {k: v for k, v in r.items() if k != "tokens"} | {"n_logprob_tokens": len(r.get("tokens") or []), "smallest_margins": margins(r)}


def trace_lines(log_path, limit=400):
    log = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    return [l[:240] for l in log if PAT.search(l) and "print_timing" not in l][-limit:]


def save(out):
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


def main():
    out = {"parts": {}}
    all_tasks = spec_tasks()
    dc = next(t for t in all_tasks if t["id"] == "decision_contract")
    log_dir = EVID / "determinism_logs"
    # ---- Part 1 + 3: layout and same-layout repeats --------------------------------------------------------------
    part1 = {}
    for ub in (1024, 512, 256):
        extra = f"-b 2048 -ub {ub} --cache-ram 0 --ctx-checkpoints 0"
        cfg = ServerConfig(name=f"det2_ub{ub}", model=CFG["model"]["path"], ctx=32768, ngl=999, port=18496, load_mode="none",
                           mmproj=CFG["model"]["mmproj"], extra=tuple(extra.split() + ["-lv", "4"]))
        srv = Server(cfg, log_dir).start()
        url = srv.url
        calls = []
        try:
            chat(url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs=FAST)
            for i in range(3):
                calls.append((f"ub{ub}_call{i}", nonstream(url, dc)))
            if ub == 1024:
                long_t = next(t for t in all_tasks if t["id"] == "dossier_answer")
                chat(url, long_t["messages"], max_tokens=long_t["max_tokens"], template_kwargs=FAST)
                for i in range(3, 6):
                    calls.append((f"ub{ub}_after_dossier_call{i}", nonstream(url, dc)))
            res = srv.resource_snapshot()
        finally:
            srv.stop()
        base = calls[0][1]
        part1[f"ub{ub}"] = {"extra": extra, "rows": [dict(label=l, **strip(r)) for l, r in calls],
                            "distinct": sorted({r["sha"] for _, r in calls}),
                            "divergence_vs_first": {l: divergence(base, r) for l, r in calls[1:]},
                            "resources": res, "trace": trace_lines(log_dir / f"server_det2_ub{ub}.log", 120)}
        print(f"== ub{ub}: " + ", ".join(f"{l}={r['sha']}/{r['predicted_n']}t" for l, r in calls), flush=True)
        out["parts"]["layout"] = part1
        save(out)
    # cross-layout divergence (first call of each)
    firsts = {k: v["rows"][0] for k, v in part1.items()}
    full = {}
    for ub in (1024, 512, 256):
        full[f"ub{ub}"] = None
    out["parts"]["layout_summary"] = {k: {"sha": v["sha"], "predicted_n": v["predicted_n"]} for k, v in firsts.items()}
    save(out)
    # ---- Part 2: exact bench_spec replay under production flags ---------------------------------------------------
    extra = "-b 2048 -ub 1024 --cache-ram 1024"
    cfg = ServerConfig(name="det2_replay", model=CFG["model"]["path"], ctx=32768, ngl=999, port=18496, load_mode="none",
                       mmproj=CFG["model"]["mmproj"], extra=tuple(extra.split() + ["-lv", "4"]))
    srv = Server(cfg, log_dir).start()
    url = srv.url
    seq = []
    try:
        chat(url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs=FAST)
        for rep in range(2):
            for t in all_tasks:
                if t["id"] == "decision_contract":
                    seq.append((f"decision_contract_rep{rep}", nonstream(url, t)))
                else:
                    r = chat(url, t["messages"], max_tokens=t["max_tokens"], template_kwargs=FAST, json_schema=t.get("json_schema"))
                    tm = r.get("timings") or {}
                    seq.append((f"{t['id']}_rep{rep}", {"text": r.text, "sha": sha(r.text), "finish": r.get("finish_reason"),
                                                        "predicted_n": tm.get("predicted_n"), "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"), "tokens": []}))
        res = srv.resource_snapshot()
    finally:
        srv.stop()
    dcs = [(l, r) for l, r in seq if l.startswith("decision_contract")]
    out["parts"]["replay"] = {"extra": extra, "order": [l for l, _ in seq],
                              "rows": [dict(label=l, **strip(r)) for l, r in seq],
                              "decision_contract": {l: {"sha": r["sha"], "predicted_n": r["predicted_n"], "cache_n": r["cache_n"], "prompt_n": r["prompt_n"]} for l, r in dcs},
                              "divergence_rep0_vs_rep1": divergence(dcs[0][1], dcs[1][1]) if len(dcs) == 2 else None,
                              "resources": res, "trace": trace_lines(log_dir / "server_det2_replay.log", 400)}
    # compare with the stored texts
    try:
        spec_off = json.loads((EVID / "spec" / "spec_off.json").read_text(encoding="utf-8"))
        stored = {f"rep{r['rep']}": sha(r["text"]) for r in spec_off["rows"] if r["id"] == "decision_contract"}
        out["parts"]["replay"]["stored_spec_off_shas"] = stored
        out["parts"]["replay"]["reproduces_stored"] = {l: r["sha"] == stored.get(l.replace("decision_contract_", "")) for l, r in dcs}
    except Exception as exc:
        out["parts"]["replay"]["stored_spec_off_shas"] = f"unavailable: {exc}"
    save(out)
    print("== replay: " + ", ".join(f"{l}={r['sha']}/{r['predicted_n']}t cache_n={r['cache_n']}" for l, r in dcs), flush=True)
    print(json.dumps({"layout": out["parts"]["layout_summary"],
                      "layout_distinct": {k: v["distinct"] for k, v in part1.items()},
                      "replay_dc": out["parts"]["replay"]["decision_contract"],
                      "replay_divergence": out["parts"]["replay"]["divergence_rep0_vs_rep1"],
                      "reproduces_stored": out["parts"]["replay"].get("reproduces_stored")}, indent=1, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    main()
