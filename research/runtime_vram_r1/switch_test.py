"""Profile switch A -> B -> A with conversation (KV) preservation through llama-server's own slot save/restore.

b11425 has no endpoint that unloads only the vision projector or only the MTP draft (endpoints in
llama-server-impl.dll: /models, /models/load, /models/unload for router mode, /slots, /lora-adapters), so swapping
Vision for MTP is a process reload. This measures what that costs and whether the KV state survives:

  1. load A, build a long conversation prefix (~depth tokens), answer turn 1, POST /slots/0?action=save;
  2. stop A; measure the VRAM release lag; load B with the same --slot-save-path;
  3. POST /slots/0?action=restore, ask a follow-up on the same prefix: cache_n (reused tokens), TTFT, correctness;
     control: without restore the whole prefix is re-processed; turn 1's prompt_ms on A is that cost;
  4. switch back to A the same way.

    python -I switch_test.py --a ctx=65536,mtp=1,vision=off --b ctx=65536,mtp=0,vision=gpu --depth 20000
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
sys.path.insert(0, str(HERE.parents[1] / "model_lab"))
import vlab  # noqa: E402
import speed  # noqa: E402
import longctx_suite as LC  # noqa: E402
import run_probe as RP  # noqa: E402

SLOTS = Path(r"D:\uri-dev\uri-vram-r1-slots")


def parse(spec, name):
    kv = dict(x.split("=") for x in spec.split(","))
    return vlab.Profile(name, ctx=int(kv.get("ctx", 65536)), mtp=kv.get("mtp", "1") == "1",
                        vision=kv.get("vision", "off"), extra=("--slot-save-path", str(SLOTS)))


def slot(url, action, filename):
    t0 = time.monotonic()
    r = httpx.post(url + f"/slots/0?action={action}", json={"filename": filename}, timeout=300)
    return {"status": r.status_code, "s": round(time.monotonic() - t0, 2), "body": r.json() if r.content else None}


def turn(url, msgs, mx=200):
    r = speed.stream_chat(url, msgs, max_tokens=mx)
    return r, {k: r.get(k) for k in ("prompt_n", "cache_n", "prompt_ms", "ttft_s", "total_s", "decode_tps", "error")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--depth", type=int, default=20000)
    a = ap.parse_args()
    SLOTS.mkdir(parents=True, exist_ok=True)
    root = vlab.EVIDENCE / "switch" / time.strftime("%Y%m%d-%H%M%S")
    A, B = parse(a.a, "switch-A"), parse(a.b, "switch-B")
    out = {"A": A.argv(), "B": B.argv(), "steps": []}
    fname = "uri_switch_slot0.bin"
    msgs = None
    t_switch = None
    for i, prof in enumerate((A, B, A)):
        srv = vlab.Server(prof, root / f"{i}_{prof.name}", max_hold_s=900)
        step = {"profile": prof.name, "i": i}
        try:
            t_load0 = time.monotonic()
            srv.start()
            step["load_s"] = srv.record["load_seconds"]
            step["request_mib"] = srv.record["buffers"]["device_total_mib"]
            step["loaded"] = srv.record["loaded"]
            if t_switch is not None:
                step["switch_total_s"] = round(time.monotonic() - t_switch, 1)   # stop -> ready on the new profile
            if msgs is None:
                dossier = LC.build(a.depth, tokenize=srv.tokenize)
                msgs = LC.messages(dossier)
                r1, step["turn1"] = turn(srv.url, msgs, 500)
                step["turn1_score"] = LC.score(r1.get("text"))["score"]
                msgs = msgs + [{"role": "assistant", "content": r1.get("text") or ""}]
            else:
                step["restore"] = slot(srv.url, "restore", fname)
            q = msgs + [{"role": "user", "content": LC.FOLLOWUP}]
            r2, step["followup"] = turn(srv.url, q)
            step["followup_ok"] = LC.score_followup(r2.get("text"))["followup_needle"]
            if prof.vision != "off":
                step["vision"] = RP.run_vision(srv, reps=1)
            step["save"] = slot(srv.url, "save", fname)
            step["after"] = srv.memory()
            step["classification"] = "COMPLETED_WITH_RESULT"
        except Exception as exc:
            step["error"] = f"{type(exc).__name__}: {exc}"
            step["classification"] = "FAILED"
        finally:
            t_switch = time.monotonic()
            srv.stop()
            step["release"] = vlab.wait_vram_released(timeout=90, poll=1.0)
            vlab.save(srv.dir, "server", srv.record)
        out["steps"].append(step)
        if step["classification"] != "COMPLETED_WITH_RESULT":
            break
    vlab.save(root, "switch", out)
    print(json.dumps(out["steps"], indent=1, default=str)[:6000])
    print("EVIDENCE", root)


if __name__ == "__main__":
    main()
