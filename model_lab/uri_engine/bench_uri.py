"""URI-workload latency profile for one llama-server configuration (research only, no Core changes).

Measures what URI actually pays for: repeated decision turns whose system prefix is stable while the
user JSON changes, alternating seams (proposer / interpreter / answer), long-context ingestion with
follow-ups, decode speed, trivial turns and one vision call. Every call records llama-server's own
timings (prompt_n, cache_n, prompt_ms, predicted_ms) so prefix reuse is measured, not assumed.

  python model_lab/uri_engine/bench_uri.py --name base --extra "-b 2048 -ub 1024 --cache-ram 1024"

Evidence: model_lab/evidence/uri_engine/runs/<name>_<stamp>.json (+ .calls.jsonl, server log).
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
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import httpx  # noqa: E402

from lab import cases as CS  # noqa: E402
from lab import decision, longctx, vision  # noqa: E402
from lab import prompts as P  # noqa: E402
from lab.client import chat, extract_json  # noqa: E402
from lab.paired import INTERPRETER_SYSTEM  # noqa: E402
from lab.runtime import Server, ServerConfig, file_sha256  # noqa: E402
from scripts.m30_4_decision_quality_analysis import real_directory, turn_state_for  # noqa: E402
from uri_core.core.decision_engine import (  # noqa: E402
    DECISION_CONTRACT_SYSTEM_PROMPT, build_decision_request, preselect_candidate_ids)

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
MODEL = CFG["model"]["path"]
MMPROJ = CFG["model"]["mmproj"]
FAST = {"enable_thinking": False}
EVID = LAB / "evidence" / "uri_engine"

STABLE_FIRST = ("capability_summaries", "capability_action_affordances", "capability_index_hint",
                "session_facts", "attempt_history", "recent_conversation", "active_pointer",
                "current_turn_attachments", "user_text")


def serialize_request(req, mode):
    """Core builds the request dict; the integration adapter chooses the JSON serialization.
    lab: model_lab's json.dumps (user_text first). canonical: production paired_brain.canonical()
    (sorted keys, compact, ascii). stable: slowly-changing keys first, user_text last."""
    if mode == "lab":
        return json.dumps(req, ensure_ascii=False)
    if mode == "canonical":
        return json.dumps(req, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    ordered = {k: req[k] for k in STABLE_FIRST if k in req}
    ordered.update({k: v for k, v in req.items() if k not in ordered})
    return json.dumps(ordered, ensure_ascii=False)


def tokenize(url, text):
    r = httpx.post(url + "/tokenize", json={"content": text, "add_special": False}, timeout=60)
    return len(r.json().get("tokens", []))


def rec(rows, role, phase, r, **extra):
    t = r.get("timings") or {}
    row = {"phase": phase, "role": role, "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"),
           "prompt_ms": t.get("prompt_ms"), "prompt_tps": t.get("prompt_per_second"),
           "predicted_n": t.get("predicted_n"), "predicted_ms": t.get("predicted_ms"),
           "gen_tps": t.get("predicted_per_second"), "ttft_s": r.get("ttft_s"), "total_s": r.get("total_s"),
           "finish": r.get("finish_reason"), "error": r.get("error"), **extra}
    rows.append(row)
    return row


def proposer(url, state, directory, grammar, reorder, rows, phase, cid):
    pre = preselect_candidate_ids(state, directory) or [s["capability_id"] for s in directory.summaries()]
    req = build_decision_request(state, preselected_ids=pre, capability_directory=directory)
    schema = decision.decision_schema([s["capability_id"] for s in req["capability_summaries"]]) if grammar else None
    r = chat(url, [{"role": "system", "content": DECISION_CONTRACT_SYSTEM_PROMPT},
                   {"role": "user", "content": serialize_request(req, reorder)}],
             max_tokens=500, template_kwargs=FAST, json_schema=schema)
    obj, _ = extract_json(r.text)
    return rec(rows, "proposer", phase, r, id=cid, mode=(obj or {}).get("mode") if isinstance(obj, dict) else None,
               capability=(obj or {}).get("capability") if isinstance(obj, dict) else None)


def interpreter(url, text, capability, slots, grammar, rows, phase, cid):
    schema = {"type": "object", "properties": {s: {"anyOf": [{"type": "string"}, {"type": "null"}]} for s in slots},
              "required": list(slots), "additionalProperties": False} if grammar else None
    r = chat(url, [{"role": "system", "content": INTERPRETER_SYSTEM},
                   {"role": "user", "content": json.dumps({"message": text, "capability": capability, "slots": list(slots)})}],
             max_tokens=200, template_kwargs=FAST, json_schema=schema)
    return rec(rows, "interpreter", phase, r, id=cid)


def answer(url, case, rows, phase):
    r = chat(url, case["messages"], max_tokens=case["max_tokens"], template_kwargs=FAST)
    return rec(rows, "answer", phase, r, id=case["id"], score=case["score"](r).get("score"))


def p50(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 3) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--extra", default="-b 2048 -ub 1024 --cache-ram 1024")
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--port", type=int, default=18495)
    ap.add_argument("--no-mmproj", action="store_true")
    ap.add_argument("--no-grammar", action="store_true")
    ap.add_argument("--serial", default="canonical", choices=["lab", "canonical", "stable"], help="proposer request JSON serialization")
    ap.add_argument("--turns", type=int, default=12)
    ap.add_argument("--long", default="4000,16000,32000")
    ap.add_argument("--skip", default="", help="comma list of phases to skip: session,repeat,long,decode,trivial,vision")
    ap.add_argument("--binary", default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--load-mode", default="none")
    a = ap.parse_args()
    skip = set(filter(None, a.skip.split(",")))
    grammar = not a.no_grammar
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = EVID / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"{a.name}_{stamp}"

    cfg = ServerConfig(name=a.name, model=a.model, ctx=a.ctx, ngl=999, port=a.port, load_mode=a.load_mode,
                       mmproj=None if a.no_mmproj else MMPROJ, extra=tuple(a.extra.split()),
                       **({"binary": a.binary} if a.binary else {}))
    srv = Server(cfg, out_dir / "logs").start()
    url = srv.url
    rows = []
    summary = {"name": a.name, "stamp": stamp, "argv": cfg.argv(), "model_sha256": file_sha256(a.model),
               "grammar": grammar, "serial": a.serial, "load_seconds": srv.load_seconds, "props": srv.props()}
    try:
        chat(url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs=FAST)
        directory = real_directory()
        dcases = decision.cases()[: a.turns]

        # token budget of one decision request, by section
        st0 = turn_state_for(dcases[0]["text"], directory)
        pre0 = preselect_candidate_ids(st0, directory) or [s["capability_id"] for s in directory.summaries()]
        req0 = build_decision_request(st0, preselected_ids=pre0, capability_directory=directory)
        summary["tokens"] = {"decision_system": tokenize(url, DECISION_CONTRACT_SYSTEM_PROMPT),
                             "decision_request": tokenize(url, serialize_request(req0, a.serial)),
                             "request_sections": {k: tokenize(url, json.dumps(v, ensure_ascii=False)) for k, v in req0.items()},
                             "interpreter_system": tokenize(url, INTERPRETER_SYSTEM),
                             "language_layer_system": tokenize(url, P.LANGUAGE_LAYER_SYSTEM)}

        states = [turn_state_for(c["text"], directory, active_pointer=c.get("active_pointer"),
                                 recent_conversation=c.get("recent_conversation"),
                                 attempt_history=c.get("attempt_history")) for c in dcases]
        ccases = [CS.build_c(c) for c in CS.C_CASES]

        if "session" not in skip:
            # realistic alternation: proposer -> interpreter -> (every 3rd turn) answer
            for i, (c, st) in enumerate(zip(dcases, states)):
                row = proposer(url, st, directory, grammar, a.serial, rows, "session", c["id"])
                if row.get("capability"):
                    interpreter(url, c["text"], row["capability"], ["statement"], grammar, rows, "session", c["id"])
                if i % 3 == 2:
                    answer(url, ccases[(i // 3) % len(ccases)], rows, "session")

        if "repeat" not in skip:
            # second pass over the same turns: does the stable prefix survive the other seams?
            for c, st in zip(dcases, states):
                proposer(url, st, directory, grammar, a.serial, rows, "repeat", c["id"])
            # byte-identical repeat of the last turn
            proposer(url, states[-1], directory, grammar, a.serial, rows, "identical", dcases[-1]["id"])

        if "long" not in skip:
            for size in [int(x) for x in a.long.split(",") if x]:
                dossier, task = longctx.build_package(size)
                sysm = {"role": "system", "content": "You are URI's local assistant. Follow the user's standing instructions."}
                head = "SESSION DOSSIER\n\n" + dossier + "\n\n---\n"
                r = chat(url, [sysm, {"role": "user", "content": head + task}], max_tokens=300, template_kwargs=FAST)
                rec(rows, "long_fresh", "long", r, id=f"l_{size//1000}k", score=longctx.score(r).get("score"))
                r = chat(url, [sysm, {"role": "user", "content": head + "Reply with JSON {\"convocation_date\": \"YYYY-MM-DD\"} only."}],
                         max_tokens=60, template_kwargs=FAST)
                rec(rows, "long_followup", "long", r, id=f"l_{size//1000}k")
                r = chat(url, [sysm, {"role": "user", "content": head + task}], max_tokens=300, template_kwargs=FAST)
                rec(rows, "long_identical", "long", r, id=f"l_{size//1000}k")
                # multi-turn continuation: assistant reply appended, new user turn
                r2 = chat(url, [sysm, {"role": "user", "content": head + task}, {"role": "assistant", "content": r.text},
                                {"role": "user", "content": "Which block did the medical case request? One word."}],
                          max_tokens=20, template_kwargs=FAST)
                rec(rows, "long_continue", "long", r2, id=f"l_{size//1000}k")

        if "decode" not in skip:
            o = CS.build_o(CS.O_CASES[0])
            r = chat(url, o["messages"], max_tokens=400, template_kwargs=FAST)
            rec(rows, "decode", "decode", r, id=o["id"])
            r = chat(url, [{"role": "system", "content": P.FAST_SYSTEM},
                           {"role": "user", "content": "Write a 350-word formal circular announcing a library hours extension."}],
                     max_tokens=500, template_kwargs=FAST)
            rec(rows, "decode", "decode", r, id="circular_350w")

        if "trivial" not in skip:
            for f in CS.F_CASES[:6]:
                c = CS.build_f(f)
                r = chat(url, c["messages"], max_tokens=c["max_tokens"], template_kwargs=FAST)
                rec(rows, "trivial", "trivial", r, id=c["id"], score=c["score"](r).get("score"))

        if "vision" not in skip and not a.no_mmproj:
            im = vision.img_ui()
            r = chat(url, [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + vision._b64(im)}},
                {"type": "text", "text": "What error is shown and which toggles are on? Answer in one sentence."}]}],
                max_tokens=120, template_kwargs=FAST)
            rec(rows, "vision", "vision", r, id="ui_error")
            r = chat(url, [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + vision._b64(im)}},
                {"type": "text", "text": "Which toggles are off? Answer in one sentence."}]}],
                max_tokens=120, template_kwargs=FAST)
            rec(rows, "vision_followup", "vision", r, id="ui_error")

        summary["resources"] = srv.resource_snapshot()
    finally:
        srv.stop()

    def agg(pred):
        rs = [r for r in rows if pred(r)]
        return {"n": len(rs), "prompt_n_p50": p50([r["prompt_n"] for r in rs]), "cache_n_p50": p50([r["cache_n"] for r in rs]),
                "prompt_ms_p50": p50([r["prompt_ms"] for r in rs]), "ttft_p50": p50([r["ttft_s"] for r in rs]),
                "total_p50": p50([r["total_s"] for r in rs]), "gen_tps_p50": p50([r["gen_tps"] for r in rs]),
                "errors": sum(1 for r in rs if r["error"])}

    summary["agg"] = {
        "session_proposer": agg(lambda r: r["phase"] == "session" and r["role"] == "proposer"),
        "session_interpreter": agg(lambda r: r["phase"] == "session" and r["role"] == "interpreter"),
        "session_answer": agg(lambda r: r["phase"] == "session" and r["role"] == "answer"),
        "repeat_proposer": agg(lambda r: r["phase"] == "repeat"),
        "identical": agg(lambda r: r["phase"] == "identical"),
        "decode": agg(lambda r: r["phase"] == "decode"),
        "trivial": agg(lambda r: r["phase"] == "trivial"),
        "vision": agg(lambda r: r["phase"] == "vision"),
    }
    summary["long"] = [{k: r[k] for k in ("role", "id", "prompt_n", "cache_n", "prompt_ms", "prompt_tps", "ttft_s", "total_s", "score", "error") if k in r}
                       for r in rows if r["phase"] == "long"]
    (base.with_suffix(".calls.jsonl")).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("name", "load_seconds", "tokens", "agg", "long", "resources")}, indent=1))


if __name__ == "__main__":
    main()
