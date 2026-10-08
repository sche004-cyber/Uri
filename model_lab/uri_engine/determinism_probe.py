"""Determinism probe for the "188 vs 192 tokens" decision_contract anomaly (research only).

Stored evidence (spec/*.json, 9 fresh server sessions): the first occurrence of the greedy decision_contract
prompt in a session always produced the same 188-token text; the second occurrence in the same session always
produced a different 192-token text (198 with accepted drafts). cache_n was 0 both times. So the difference is
systematic, not random. This probe isolates what state makes the second occurrence differ:

  config prod     : production flags (prompt cache --cache-ram 1024, context checkpoints on)
  config nocache  : --cache-ram 0            (no prompt-cache restore of a previous slot state)
  config nockpt   : --cache-ram 0 --ctx-checkpoints 0 (and no checkpoints)

Per config, one fresh server: hi -> 4 filler tasks -> DC (streaming, exactly as bench_spec rep0) -> DC x2
(non-streaming with logprobs) -> 4 filler tasks -> DC x2 (the bench_spec rep1 condition, with logprobs).
Records every output, the first divergent token between occurrences and the top-2 logprob margin there, plus
the server's own prompt-cache / checkpoint / "forcing full prompt re-processing" trace lines (server run with -lv 4).

  python model_lab/uri_engine/determinism_probe.py
Evidence: model_lab/evidence/uri_engine/determinism_probe.json (+ determinism_logs/server_det_*.log)
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
CONFIGS = [("prod", "-b 2048 -ub 1024 --cache-ram 1024"),
           ("nocache", "-b 2048 -ub 1024 --cache-ram 0"),
           ("nockpt", "-b 2048 -ub 1024 --cache-ram 0 --ctx-checkpoints 0")]
PAT = re.compile(r"checkpoint|prompt cache|forcing full|lcp|f_keep|n_past|cached n_tokens|erasing|superseding|restored|reuse", re.I)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def nonstream(url, t, logprobs=True):
    body = {"messages": t["messages"], "max_tokens": t["max_tokens"], "temperature": 0, "seed": 7, "chat_template_kwargs": FAST,
            "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": t["json_schema"], "strict": True}}}
    if logprobs:
        body.update({"logprobs": True, "top_logprobs": 3})
    j = httpx.post(url + "/v1/chat/completions", json=body, timeout=600).json()
    ch = j["choices"][0]
    toks = []
    for it in (ch.get("logprobs") or {}).get("content") or []:
        toks.append({"token": it.get("token"), "logprob": it.get("logprob"),
                     "top": [(x.get("token"), x.get("logprob")) for x in it.get("top_logprobs") or []]})
    tm = j.get("timings") or {}
    return {"text": ch["message"]["content"], "finish": ch.get("finish_reason"), "predicted_n": tm.get("predicted_n"),
            "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"), "tokens": toks}


def stream(url, t):
    r = chat(url, t["messages"], max_tokens=t["max_tokens"], template_kwargs=FAST, json_schema=t.get("json_schema"))
    tm = r.get("timings") or {}
    return {"text": r.text, "finish": r.get("finish_reason"), "predicted_n": tm.get("predicted_n"), "prompt_n": tm.get("prompt_n"),
            "cache_n": tm.get("cache_n"), "tokens": [], "error": r.get("error")}


def first_divergence(a, b):
    """Index of the first differing token (by token string list) and the margin there, when logprobs exist."""
    ta, tb = a.get("tokens") or [], b.get("tokens") or []
    if ta and tb:
        for i, (x, y) in enumerate(zip(ta, tb)):
            if x["token"] != y["token"]:
                def margin(tok):
                    top = sorted(tok["top"], key=lambda z: -z[1]) if tok["top"] else []
                    return round(top[0][1] - top[1][1], 4) if len(top) > 1 else None
                return {"token_index": i, "a": x["token"], "b": y["token"], "a_margin_top2": margin(x), "b_margin_top2": margin(y),
                        "a_top": x["top"], "b_top": y["top"]}
        return {"token_index": None, "note": "no token-level difference within the shorter output", "len_a": len(ta), "len_b": len(tb)}
    # fall back to character level
    sa, sb = a["text"], b["text"]
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            return {"char_index": i, "a_context": sa[max(0, i - 30):i + 30], "b_context": sb[max(0, i - 30):i + 30]}
    return {"char_index": None, "len_a": len(sa), "len_b": len(sb)}


def main():
    out = {"configs": {}}
    all_tasks = spec_tasks()
    dc = next(t for t in all_tasks if t["id"] == "decision_contract")
    fillers = [t for t in all_tasks if t["id"] in ("office_draft", "rewrite_circular", "code_patch", "extract_record")]
    log_dir = EVID / "determinism_logs"
    for name, extra in CONFIGS:
        cfg = ServerConfig(name=f"det_{name}", model=CFG["model"]["path"], ctx=32768, ngl=999, port=18497, load_mode="none",
                           mmproj=CFG["model"]["mmproj"], extra=tuple(extra.split() + ["-lv", "4"]))
        srv = Server(cfg, log_dir).start()
        url = srv.url
        seq = []
        try:
            chat(url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs=FAST)
            for t in fillers:
                chat(url, t["messages"], max_tokens=t["max_tokens"], template_kwargs=FAST)
            seq.append(("dc1_stream_rep0_condition", stream(url, dc)))
            seq.append(("dc2_nonstream", nonstream(url, dc)))
            seq.append(("dc3_nonstream", nonstream(url, dc)))
            for t in fillers:
                chat(url, t["messages"], max_tokens=t["max_tokens"], template_kwargs=FAST)
            seq.append(("dc4_nonstream_rep1_condition", nonstream(url, dc)))
            seq.append(("dc5_nonstream", nonstream(url, dc)))
            res = srv.resource_snapshot()
        finally:
            srv.stop()
        log = (log_dir / f"server_det_{name}.log").read_text(encoding="utf-8", errors="replace").splitlines()
        trace = [l[:260] for l in log if PAT.search(l) and "print_timing" not in l]
        rows = []
        for label, r in seq:
            rows.append({"label": label, "sha": sha(r["text"]), "predicted_n": r["predicted_n"], "prompt_n": r["prompt_n"],
                         "cache_n": r["cache_n"], "finish": r["finish"], "len": len(r["text"]), "text": r["text"],
                         "n_logprob_tokens": len(r["tokens"]), "error": r.get("error")})
        div = {}
        base = seq[0][1]
        for label, r in seq[1:]:
            div[f"{seq[0][0]} vs {label}"] = first_divergence(seq[1][1] if seq[1][1]["tokens"] else base, r) if r["tokens"] else first_divergence(base, r)
        out["configs"][name] = {"extra": extra, "rows": rows, "divergence": div, "resources": res,
                                "distinct_outputs": sorted({x["sha"] for x in rows}), "trace": trace[-200:]}
        print(f"== {name}: " + ", ".join(f"{x['label']}={x['sha']}/{x['predicted_n']}t cache_n={x['cache_n']}" for x in rows))
        (EVID / "determinism_probe.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: {"distinct": v["distinct_outputs"], "divergence": v["divergence"]} for k, v in out["configs"].items()}, indent=1)[:6000])


if __name__ == "__main__":
    main()
