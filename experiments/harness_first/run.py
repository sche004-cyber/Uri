"""Runs the harness-first pipeline over a corpus and records every stage.

Per case it records, once:
  harness          deterministic stages (always)
  edge.<arm>       the bounded Edge job for the residue, per Edge arm (only when the harness left an
                   admitted residue)
  main_prepared    the local Main Brain on the prepared residue (only when the harness left a residue)
  main_only        the local Main Brain on the raw turn with the full offered catalogue (baseline)
Configurations (harness only, harness+Edge, harness+Main, Main only, pairs) are composed afterwards by
score.py from these records. That is valid because each stage's input does not depend on which
configuration is being scored: Edge never sees Main output and Main never sees Edge output.

Usage:
  python run.py --corpus corpus/hf_dev.json --out runs/dev_r1.jsonl [--edge granite_json,needle] [--repeat 1]
           [--no-main] [--ids T001,RF01]
No metered API: Main Brain is local Ollama qwen3.5:9b. Gmail, Drive and every write are test doubles.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline as P  # noqa: E402

sys.path.insert(0, str(P.EPQ))
import harness as H  # noqa: E402
from catalogue import CONTROLS, public  # noqa: E402

H.VARIANT = "v3"   # EPQ-1 repair R-A (no <<< >>> fence), the variant EPQ-1 froze for its holdout

SMALL_TALK = {"name": "reply_small_talk",
              "description": "Use only when the message is a greeting, thanks, farewell or a question about URI itself, "
                             "and asks for no action.",
              "parameters": {"type": "object", "properties": {"intent": {"type": "string", "enum": ["greeting", "thanks", "farewell", "about_uri"]}},
                             "required": ["intent"]}}
INTENT_MAP = {"greeting": "greeting", "thanks": "thanks", "farewell": "farewell", "about_uri": "self"}


def select_spec(case, binding, feasible, *, for_edge: bool):
    c = {"kind": "select", "text": case["text"], "context": P.trusted_state(case, binding), "document": None,
         "offered": feasible}
    sp = H.spec(c, "P1")
    if for_edge:
        sp["tools"] = sp["tools"] + [SMALL_TALK]
    return c, sp


def call(adapter, sp, case_like):
    t = time.perf_counter()
    try:
        r = adapter.call(sp, case_like, "P1", None)
        r.pop("raw", None) if isinstance(r.get("raw"), dict) and len(json.dumps(r.get("raw"), default=str)) > 4000 else None
        r["stage_ms"] = (time.perf_counter() - t) * 1000
        return r
    except Exception as exc:  # transport failure is recorded, never repaired
        return {"calls": [], "error": f"{type(exc).__name__}: {exc}", "stage_ms": (time.perf_counter() - t) * 1000,
                "wall_ms": (time.perf_counter() - t) * 1000}


def decide_select(case, residue, r, *, role):
    """Validate a model's SELECT_ACTION output and run it through URI fill/gates/execute."""
    binding = residue["binding"]
    feasible = residue["feasible"]
    if r.get("error"):
        return {"status": "MODEL_ERROR", "error": r["error"]}
    calls = r.get("calls") or []
    st_calls = [c for c in calls if c.get("name") == "reply_small_talk"]
    if st_calls and len(calls) == 1:
        intent = (st_calls[0].get("arguments") or {}).get("intent")
        if intent in INTENT_MAP and not residue.get("reasons") and not binding.get("candidate_id"):
            return {"status": "REPLIED", "intent": INTENT_MAP[intent], "reply": P.deterministic_reply(INTENT_MAP[intent]),
                    "wording": "deterministic_template_after_edge_label"}
        return {"status": "REJECTED", "reason": "SMALL_TALK_INVALID"}
    if not calls and role == "main":
        text = ((r.get("raw") or {}).get("message") or {}).get("content") if isinstance(r.get("raw"), dict) else None
        return {"status": "REPLIED", "intent": None, "reply": (text or "")[:400], "wording": "main_brain"} if text else \
            {"status": "REJECTED", "reason": "REJECT_EMPTY"}
    action, state, control = P.validate_selection(calls, feasible)
    if state == "ABSTAIN":
        return {"status": "ABSTAIN", "control": control}
    if state != "ACCEPTED":
        return {"status": "REJECTED", "reason": state}
    impact = P.declared_impact(action)
    bind = P.BINDING_ARGS.get(action)
    b = P.Binding(**binding)
    model_args = next((c.get("arguments") or {} for c in calls if c.get("name") == action), {})
    binding_source = None
    if bind:
        if b.candidate_id and b.candidate_id.startswith(bind[1] + ":"):
            binding_source = f"RAR_S1_{b.state}"
            if b.state == "TENTATIVE" and impact != P.WrongBindingImpact.RECOVERABLE:
                return {"status": "CLARIFY", "by": "S1_consequential_tentative", "action": action,
                        "candidate": b.candidate_id}
        else:
            v = model_args.get(bind[0])
            titles = {c.id.split(":", 1)[1] for c in P.build_candidates(case["session"]) if c.id.startswith(bind[1] + ":")}
            if isinstance(v, str) and v in titles:
                if impact != P.WrongBindingImpact.RECOVERABLE:
                    return {"status": "CLARIFY", "by": "consequential_model_selected_candidate", "action": action}
                b = P.Binding("MODEL_SELECTED_GROUNDED", candidate_id=f"{bind[1]}:{v}")
                binding_source = "MODEL_SELECTED_AMONG_GROUNDED"
    args, why = P.fill_arguments(action, b, case["text"], case["session"], model_args)
    if args is None:
        return {"status": "REJECTED", "reason": why, "action": action}
    ex = P.execute(action, args, feasible, case["text"])
    ex["binding_source"] = binding_source
    ex["model_args_discarded"] = model_args
    return ex


def decide_extract(case, r):
    if r.get("error"):
        return {"status": "MODEL_ERROR", "error": r["error"]}
    calls = r.get("calls") or []
    if len(calls) != 1:
        return {"status": "REJECTED", "reason": "REJECT_CALL_COUNT"}
    vals = calls[0].get("arguments") or {}
    if case["kind"] == "extract":
        ok, bad = P.validate_extract(vals, case)
        return {"status": "EXTRACTED", "values": vals} if ok else {"status": "REJECTED", "reason": "N5_VERBATIM", "fields": bad, "values": vals}
    return {"status": "LABELLED", "value": vals.get("value")} if P.validate_label(vals, case) else \
        {"status": "REJECTED", "reason": "ENUM", "value": vals.get("value")}


def main_only_spec(case):
    if case["kind"] in ("extract", "label"):
        return case, H.spec(case, None)
    ctx = P.trusted_state(case, None)
    c = {"kind": "select", "text": case["text"], "context": ctx, "document": case.get("document"),
         "offered": case.get("offered") or []}
    return c, H.spec(c, "P1")


def run_case(case, edges, adapters, brain, with_main):
    rec = {"type": "case", "id": case["id"], "family": case["family"], "kind": case["kind"], "expected": case["expected"]}
    hr = P.run_harness(case)
    rec["harness"] = {"decided": hr.decided, "outcome": hr.outcome, "residue": hr.residue, "stages": hr.stages,
                      "harness_ms": hr.harness_ms}
    if not hr.decided:
        res = hr.residue
        rec["edge"] = {}
        if res["admitted"]:
            for arm in edges:
                if res["job"] == "SELECT_ACTION":
                    c, sp = select_spec(case, res["binding"], res["feasible"], for_edge=True)
                    r = call(adapters[arm], sp, c)
                    d = decide_select(case, res, r, role="edge")
                else:
                    sp = H.spec(case, None)
                    r = call(adapters[arm], sp, case)
                    d = decide_extract(case, r)
                rec["edge"][arm] = {"calls": r.get("calls"), "suppressed": r.get("suppressed"), "wall_ms": r.get("wall_ms"),
                                    "stage_ms": r.get("stage_ms"), "prompt_chars": len(sp["system"]) + len(sp["user"])
                                    + len(json.dumps(sp["tools"])), "decision": d, "error": r.get("error"),
                                    "ollama": r.get("ollama"), "infer_ms": r.get("infer_ms")}
        if with_main:
            if res["job"] == "SELECT_ACTION":
                c, sp = select_spec(case, res["binding"], res["feasible"], for_edge=False)
                if case.get("document"):
                    c["document"] = case["document"]
                    sp = H.spec(c, "P1")
                r = call(brain, sp, c)
                d = decide_select(case, res, r, role="main")
            else:
                sp = H.spec(case, None)
                r = call(brain, sp, case)
                d = decide_extract(case, r)
            rec["main_prepared"] = {"calls": r.get("calls"), "wall_ms": r.get("wall_ms"), "stage_ms": r.get("stage_ms"),
                                    "prompt_chars": len(sp["system"]) + len(sp["user"]) + len(json.dumps(sp["tools"])),
                                    "decision": d, "error": r.get("error"), "ollama": r.get("ollama")}
    if with_main:
        c, sp = main_only_spec(case)
        r = call(brain, sp, c)
        if case["kind"] in ("extract", "label"):
            d = decide_extract(case, r)
        else:
            fake_res = {"binding": P.Binding("NONE").__dict__, "feasible": c["offered"], "reasons": ["main_only"]}
            d = decide_select(case, fake_res, r, role="main")
        rec["main_only"] = {"calls": r.get("calls"), "wall_ms": r.get("wall_ms"), "stage_ms": r.get("stage_ms"),
                            "prompt_chars": len(sp["system"]) + len(sp["user"]) + len(json.dumps(sp["tools"])),
                            "decision": d, "error": r.get("error"), "ollama": r.get("ollama")}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(HERE / "corpus" / "hf_dev.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--edge", default="granite_json,needle")
    ap.add_argument("--no-main", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()
    cases = json.loads(Path(a.corpus).read_text(encoding="utf-8"))
    if a.ids:
        keep = set(a.ids.split(","))
        cases = [c for c in cases if c["id"] in keep]
    edges = [e for e in a.edge.split(",") if e]
    adapters = {}
    for e in edges:
        adapters[e] = H.NeedleAdapter() if e == "needle" else H.OllamaAdapter(H.GRANITE, "json") if e == "granite_json" \
            else H.OllamaAdapter(H.GRANITE, "native")
    brain = H.OllamaAdapter(H.BRAIN, "native", think=False, num_ctx=None)
    out = Path(a.out)
    out.parent.mkdir(exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            o = json.loads(line)
            if o.get("type") == "case":
                done.add((o["id"], o.get("rep", 0)))
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "batch_start", "t": time.time(), "edges": edges, "main": not a.no_main,
                             "variant": H.VARIANT, "load": H.load_snapshot()}, default=str) + "\n")
        for rep in range(a.repeat):
            for i, c in enumerate(cases):
                if (c["id"], rep) in done:
                    continue
                try:
                    rec = run_case(c, edges, adapters, brain, not a.no_main)
                except Exception:
                    rec = {"type": "case", "id": c["id"], "crash": traceback.format_exc()}
                rec["rep"] = rep
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                fh.flush()
                if i % 25 == 0:
                    fh.write(json.dumps({"type": "load", "i": i, "rep": rep, "load": H.load_snapshot()}, default=str) + "\n")
                    print(rep, i, c["id"], flush=True)
        fh.write(json.dumps({"type": "batch_end", "t": time.time(), "load": H.load_snapshot()}, default=str) + "\n")
    for ad in adapters.values():
        if hasattr(ad, "close"):
            ad.close()


if __name__ == "__main__":
    main()
