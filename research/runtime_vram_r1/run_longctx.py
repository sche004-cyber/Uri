"""(Adapted from research/qwen38 @9689a666 to vlab profiles.) Context-capacity run: for each (ctx, kv type) load a profile, fill ~(ctx - reserve) tokens, score retrieval and
reasoning, then a same-prefix follow-up (cache reuse), and record memory/residency at every step.

    python -I run_longctx.py --model q38-iq4xs --sizes 8192:q8_0,32768:q8_0,65536:q4_0 [--mtp] [--think]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vlab as lab  # noqa: E402
import longctx_suite as LC  # noqa: E402
import speed  # noqa: E402

RESERVE = 1500   # answer + template + follow-up headroom


def run_one(model, ctx, kv, mtp, think, label, vision="off", run_root=None):
    prof = lab.Profile(f"{label}-{model}-{ctx // 1024}k-{kv}", ctx=ctx, ctk=kv, mtp=mtp, vision=vision)
    run_dir = run_root / prof.name
    srv = lab.Server(prof, run_dir, max_hold_s=900)
    rec = srv.record
    try:
        srv.start()
        target = ctx - RESERVE - (1200 if think else 0)
        dossier = LC.build(target, tokenize=srv.tokenize)
        msgs = LC.messages(dossier)
        rec["prompt_tokens_measured"] = srv.tokenize(msgs[1]["content"])
        r1 = speed.stream_chat(srv.url, msgs, max_tokens=500 + (1500 if think else 0), thinking=think)
        rec["mem_after_turn1"] = srv.memory()
        rec["turn1"] = {k: v for k, v in r1.items() if k != "reasoning"}
        rec["turn1"]["reasoning_chars"] = len(r1.get("reasoning") or "")
        rec["turn1_score"] = LC.score(r1.get("text"))
        msgs2 = msgs + [{"role": "assistant", "content": r1.get("text") or ""}, {"role": "user", "content": LC.FOLLOWUP}]
        r2 = speed.stream_chat(srv.url, msgs2, max_tokens=200, thinking=False)
        rec["turn2"] = {k: v for k, v in r2.items() if k != "reasoning"}
        rec["turn2_score"] = LC.score_followup(r2.get("text"))
        rec["mem_after_turn2"] = srv.memory()
        # decode speed at depth vs short-prompt decode on the same loaded server
        rec["short_after"] = {k: v for k, v in speed.stream_chat(srv.url, [{"role": "user", "content": speed.FIXED_PROMPT}],
                                                                  max_tokens=300).items() if k not in ("text", "reasoning")}
        rec["classification"] = "COMPLETED_WITH_RESULT"
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["classification"] = "FAILED"
    finally:
        srv.stop()
        lab.save(run_dir, "longctx", rec)
    t1, t2 = rec.get("turn1", {}), rec.get("turn2", {})
    brief = {"profile": prof.name, "class": rec.get("classification"), "error": rec.get("error"), "load_s": rec.get("load_seconds"),
             "request_mib": (rec.get("buffers") or {}).get("device_total_mib"),
             "loaded_gpu": rec.get("loaded", {}).get("server"), "after_gpu": rec.get("mem_after_turn2", {}).get("server"),
             "prompt_tokens": t1.get("prompt_n"), "prefill_tps": t1.get("prompt_tps"), "ttft_s": t1.get("ttft_s"),
             "decode_tps_at_depth": t1.get("decode_tps"), "turn1_total_s": t1.get("total_s"), "finish": t1.get("finish_reason"),
             "score": rec.get("turn1_score"), "turn2_cache_n": t2.get("cache_n"), "turn2_prompt_n": t2.get("prompt_n"),
             "turn2_ttft_s": t2.get("ttft_s"), "turn2": rec.get("turn2_score"),
             "short_decode_after": rec.get("short_after", {}).get("decode_tps"),
             "draft": (t1.get("draft_n"), t1.get("draft_accepted"))}
    print(json.dumps(brief, default=str), flush=True)
    return brief


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--sizes", required=True)
    ap.add_argument("--mtp", action="store_true")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--vision", default="off")
    ap.add_argument("--label", default="lc")
    a = ap.parse_args()
    root = lab.EVIDENCE / "longctx" / time.strftime("%Y%m%d-%H%M%S")
    out = []
    for spec in a.sizes.split(","):
        ctx, kv = spec.split(":")
        out.append(run_one(a.model, int(ctx), kv, a.mtp, a.think, a.label, a.vision, root))
    lab.save(root, "summary", out)
    print("EVIDENCE", root)


if __name__ == "__main__":
    main()
