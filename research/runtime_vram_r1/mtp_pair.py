"""MTP on vs off with identical context, prompts and runtime conditions (owner addition 2026-10-17).

For each profile in the pair: load under the lease, run the same workload set (prose, URI JSON decision, code,
structured office edit, list extraction, thinking-on reasoning, and one long-depth turn), stop. Alternating order
(A B B A) cancels drift. Timings are llama-server's own.

    python -I mtp_pair.py --ctx 65536 [--vision off] [--depth 24000]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "model_lab"))
import vlab  # noqa: E402
import speed  # noqa: E402
import run_probe as RP  # noqa: E402
import longctx_suite as LC  # noqa: E402

WORK = [
    ("prose", [{"role": "user", "content": speed.FIXED_PROMPT}], 400, False),
    ("uri_json", [{"role": "system", "content": RP.URI_SYSTEM},
                  {"role": "user", "content": RP.URI_TASKS[0] + RP.URI_FORMAT}], 400, False),
    ("code", [{"role": "user", "content": "Write a Python function `merge_timetables(a, b)` that merges two lists of "
                                          "(day, period, subject) tuples, reports clashes, and includes doctests. "
                                          "Code only."}], 500, False),
    ("office_edit", [{"role": "user", "content": "Return ONLY JSON describing edits to a spreadsheet: set B2:B11 to "
                                                 "the numbers 10..19, add a SUM in B12, bold row 1, and rename the sheet "
                                                 "to 'Marks'. Schema: {\"edits\":[{\"op\":...,\"range\":...,\"value\":...}]}"}],
     400, False),
    ("extract", [{"role": "user", "content": "List twenty Indian state capitals as a markdown table with columns "
                                             "State | Capital | Approximate population."}], 600, False),
    ("reason_think", [{"role": "user", "content": "Three teachers must cover five exam rooms over two sessions with no "
                                                  "teacher in two rooms at once and each teacher at most four duties. "
                                                  "Give one valid assignment and check it."}], 1600, True),
]


def run_set(srv, depth):
    rows = []
    for name, msgs, mx, think in WORK:
        extra = {"thinking_budget_tokens": 768} if think else None
        r = speed.stream_chat(srv.url, msgs, max_tokens=mx, thinking=think, extra=extra)
        rows.append({"work": name, **{k: r.get(k) for k in ("prompt_n", "predicted_n", "decode_tps", "prompt_tps",
                                                           "ttft_s", "total_s", "draft_n", "draft_accepted",
                                                           "finish_reason", "error")}})
    if depth:
        dossier = LC.build(depth, tokenize=srv.tokenize)
        r = speed.stream_chat(srv.url, LC.messages(dossier), max_tokens=500)
        row = {"work": f"depth{depth // 1000}k", **{k: r.get(k) for k in ("prompt_n", "predicted_n", "decode_tps",
                                                                         "prompt_tps", "ttft_s", "total_s", "draft_n",
                                                                         "draft_accepted", "error")}}
        row["score"] = LC.score(r.get("text"))["score"]
        rows.append(row)
    return rows


def one(prof, root, depth):
    run_dir = root / f"{time.strftime('%H%M%S')}_{prof.name}"
    srv = vlab.Server(prof, run_dir, max_hold_s=900)
    rec = srv.record
    try:
        srv.start()
        rec["work"] = run_set(srv, depth)
        rec["after"] = srv.memory()
        rec["classification"] = "COMPLETED_WITH_RESULT"
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        if rec.get("classification") == "STARTED":
            rec["classification"] = "FAILED"
    finally:
        srv.stop()
        vlab.save(run_dir, "pair", rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", type=int, default=65536)
    ap.add_argument("--vision", default="off")
    ap.add_argument("--depth", type=int, default=24000)
    a = ap.parse_args()
    root = vlab.EVIDENCE / "mtp_pair" / f"{time.strftime('%Y%m%d-%H%M%S')}_{a.ctx // 1024}k"
    on = vlab.Profile(f"mtp-on-{a.ctx // 1024}k", ctx=a.ctx, mtp=True, vision=a.vision)
    off = vlab.Profile(f"mtp-off-{a.ctx // 1024}k", ctx=a.ctx, mtp=False, vision=a.vision)
    recs = [one(p, root, a.depth) for p in (on, off, off, on)]
    summary = {}
    for r in recs:
        if r.get("classification") != "COMPLETED_WITH_RESULT":
            continue
        key = r["profile"]["name"]
        for w in r["work"]:
            summary.setdefault(key, {}).setdefault(w["work"], []).append(w)
    table = {}
    for key, works in summary.items():
        table[key] = {w: {"decode_tps": round(statistics.mean(x["decode_tps"] for x in rows if x.get("decode_tps")), 1),
                          "total_s": round(statistics.mean(x["total_s"] for x in rows if x.get("total_s")), 2),
                          "n": len(rows)} for w, rows in works.items()}
    out = {"classes": [r.get("classification") for r in recs],
           "requests": [(r["profile"]["name"], (r.get("buffers") or {}).get("device_total_mib")) for r in recs],
           "table": table}
    vlab.save(root, "summary", out)
    print(json.dumps(out, indent=1))
    print("EVIDENCE", root)


if __name__ == "__main__":
    main()
