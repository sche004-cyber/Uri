"""Repeated-URI-context prefill benchmark: how much new computation does the runtime pay when only a small
part of a large, logically stable context changed? (research only, no Core changes)

Context layout (all sizes): [stable URI/system contract] [capability definitions] [permission state]
                            [session state] [retrieved evidence] [current user turn]
  layout "single": system = contract+capabilities+permission; user = session+evidence+turn (URI's one-JSON-request shape)
  layout "split" : same, but the current turn is its own user message after an "Acknowledged." assistant turn
                   (gives the stock server a user-message boundary = context checkpoint right before the turn)
  layout "multi" : split + the evidence delivered as 4 acknowledged user messages (a checkpoint before each part,
                   so a changed block at 75% of the evidence only invalidates the last part)

Scenarios, run as one sequence per (size, rep) against a single resident server (state carries over, as in URI):
  A_fresh               completely new prompt
  B_repeat              exact repeat
  C_new_turn            same stable prefix, different short user turn
  A_reprime             the A prompt again (re-establish the A state before the next scenario)
  D_evidence_changed    one evidence block at ~75% of the evidence replaced
  A_reprime2
  E_permission_changed  permission-state version bump early in the prompt (must invalidate everything after it)
  A_after_E             the A prompt again (does the prompt cache still hold it after D and E states?)
rep 1 uses a different evidence seed, i.e. a second fresh sequence.

Per call: llama-server timings (prompt_n = tokens actually recomputed, cache_n = tokens reused, prompt_ms), client
TTFT/total, the output text, and the logical change: tokens after the first differing token versus the A prompt
(LCP over the tokenized rendered prompt). excess_recompute = prompt_n - logical_new_tokens is the number the
research question is about. Correctness: outputs are compared across configs by the --compare mode; the
config run with --cache-ram 0 --ctx-checkpoints 0 (full recompute every time) is the control.

  python model_lab/uri_engine/bench_context_reuse.py --name ctx_prod --extra "-b 2048 -ub 1024 --cache-ram 1024"
  python model_lab/uri_engine/bench_context_reuse.py --compare ctx_control ctx_prod ctx_ckpt1024 ...
Evidence: model_lab/evidence/uri_engine/context_reuse/<name>_<stamp>.json (+ logs/, prompts_<layout>.json)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import re
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

from lab import longctx  # noqa: E402
from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig, file_sha256, gpu_dedicated_mib  # noqa: E402
from scripts.m30_4_decision_quality_analysis import real_directory, turn_state_for  # noqa: E402
from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT, build_decision_request, preselect_candidate_ids  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine" / "context_reuse"
FAST = {"enable_thinking": False}
SIZES = [4000, 16000, 30000]
MULTI_PARTS = 4
FINAL_TASK_PARTS = 3
SEQUENCE = [("A_fresh", "A"), ("B_repeat", "A"), ("C_new_turn", "C"), ("A_reprime", "A"), ("D_evidence_changed", "D"),
            ("A_reprime2", "A"), ("E_permission_changed", "E"), ("A_after_E", "A"),
            ("S_session_changed", "S"), ("A_after_S", "A")]

PERM = {"version": 7, "granted_scopes": ["gmail.read", "gmail.draft", "files.read", "calendar.read", "memory.read", "memory.write"],
        "approval_required": ["gmail.send", "files.delete", "calendar.write"], "denied": ["payments", "system.settings"],
        "updated": "2026-10-06T09:00:00+05:30"}
PERM_E = dict(PERM, version=8, granted_scopes=PERM["granted_scopes"] + ["gmail.send"],
              approval_required=["files.delete", "calendar.write"], updated="2026-10-06T09:41:00+05:30")
SESSION = {"session_facts": [{"fact": "office extension is 4412", "turn": -40}, {"fact": "preferred signature: Dean (Academics)", "turn": -31},
                             {"fact": "hostel allocation file is HOSTEL_2026.xlsx", "turn": -12}],
           "attempt_history": [], "active_pointer": None,
           "recent_conversation": [{"user": "Find the circular about library hours.", "uri": "Found one Registrar circular on library hours; want a summary?"},
                                   {"user": "Later. Keep it handy.", "uri": "Noted."}]}
SESSION_S = dict(SESSION, session_facts=SESSION["session_facts"] + [{"fact": "the warden vacancy is in Hostel C", "turn": -2}],
                 recent_conversation=SESSION["recent_conversation"] + [{"user": "Which hostel is it?", "uri": "Hostel C, per the notice."}])
TURN_A = ('Reply ONLY with JSON {"convocation_date": "YYYY-MM-DD", "evidence_blocks": <integer count of evidence blocks>, '
          '"note": "<one short sentence>"}.')
TURN_C = ('Reply ONLY with JSON {"convocation_date": "YYYY-MM-DD", "granted_scope_count": <integer>, '
          '"note": "<one short sentence>"}.')
ANCHOR = ("[Email] From: registrar.office@college.example | Subject: Convocation\nThe annual convocation is scheduled for "
          "21 December 2026 in the main auditorium. Please update all communication.")
STANDING = "[Standing instruction from the user, recorded 2 September 2026] Never include any student roll number in anything you write for me."


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def stable_sections():
    directory = real_directory()
    st = turn_state_for("Draft an office order appointing Dr. Rao as warden from 1 November.", directory)
    pre = preselect_candidate_ids(st, directory) or [s["capability_id"] for s in directory.summaries()]
    req = build_decision_request(st, preselected_ids=pre, capability_directory=directory)
    caps = {k: req[k] for k in ("capability_summaries", "capability_action_affordances", "capability_index_hint") if k in req}
    s1 = "[STABLE URI SYSTEM CONTRACT]\n" + DECISION_CONTRACT_SYSTEM_PROMPT
    s2 = "[CAPABILITY DEFINITIONS]\n" + json.dumps(caps, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return s1, s2


def evidence_blocks(n, seed, replace_at=None):
    rng = random.Random(seed)
    blocks = [longctx._filler(rng, i + 1) for i in range(n)]
    if replace_at is not None:
        alt = random.Random(seed + 7919)
        blocks[replace_at] = longctx._filler(alt, 9000 + replace_at)
    blocks.insert(max(1, int(0.9 * len(blocks))), ANCHOR)
    blocks.insert(max(0, int(0.1 * len(blocks))), STANDING)
    return blocks


def messages(layout, s1, s2, perm, session, blocks, turn):
    system = s1 + "\n\n" + s2 + "\n\n[PERMISSION STATE]\n" + json.dumps(perm, sort_keys=True)
    body = "[SESSION STATE]\n" + json.dumps(session, sort_keys=True) + "\n\n[RETRIEVED EVIDENCE]\n" + "\n\n".join(blocks)
    if layout == "split":
        return [{"role": "system", "content": system}, {"role": "user", "content": body},
                {"role": "assistant", "content": "Acknowledged."}, {"role": "user", "content": "[CURRENT USER TURN]\n" + turn}]
    if layout == "final":
        # URI Resident Intelligence Runtime v1 context layout (see model_lab/uri_engine/CONTEXT_ARCHITECTURE_V1.md):
        #   system  : [URI_SYSTEM] [CAPABILITY_SCHEMA] [PERMISSION_STATE]      stable / session-stable / security-sensitive
        #   user 1  : [SESSION_STATE] [MEMORY_EVIDENCE]   + "Acknowledged."    session-stable
        #   user 2.n: [TASK_EVIDENCE part k/n]            + "Acknowledged."    changes per task; each part is a boundary
        #   user    : [CURRENT_TURN]                                           changes every turn
        n = max(1, len(blocks))
        n_mem = max(1, n // 5)
        mem, task = blocks[:n_mem], blocks[n_mem:]
        parts = [task[i * len(task) // FINAL_TASK_PARTS:(i + 1) * len(task) // FINAL_TASK_PARTS] for i in range(FINAL_TASK_PARTS)]
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": "[SESSION_STATE]\n" + json.dumps(session, sort_keys=True) + "\n\n[MEMORY_EVIDENCE]\n" + "\n\n".join(mem)},
                {"role": "assistant", "content": "Acknowledged."}]
        for i, part in enumerate(parts):
            msgs.append({"role": "user", "content": f"[TASK_EVIDENCE part {i + 1}/{FINAL_TASK_PARTS}]\n" + "\n\n".join(part)})
            msgs.append({"role": "assistant", "content": "Acknowledged."})
        msgs.append({"role": "user", "content": "[CURRENT_TURN]\n" + turn})
        return msgs
    if layout == "multi":
        # evidence delivered in MULTI_PARTS user messages, each acknowledged: the stock server creates a context
        # checkpoint at every user-message start, so a change inside part k only invalidates parts k..n
        n = max(1, len(blocks))
        parts = [blocks[i * n // MULTI_PARTS:(i + 1) * n // MULTI_PARTS] for i in range(MULTI_PARTS)]
        msgs = [{"role": "system", "content": system}]
        for i, part in enumerate(parts):
            head = ("[SESSION STATE]\n" + json.dumps(session, sort_keys=True) + "\n\n") if i == 0 else ""
            msgs.append({"role": "user", "content": head + f"[RETRIEVED EVIDENCE part {i + 1}/{MULTI_PARTS}]\n" + "\n\n".join(part)})
            msgs.append({"role": "assistant", "content": "Acknowledged."})
        msgs.append({"role": "user", "content": "[CURRENT USER TURN]\n" + turn})
        return msgs
    return [{"role": "system", "content": system}, {"role": "user", "content": body + "\n\n[CURRENT USER TURN]\n" + turn}]


def render_tokens(url, msgs):
    r = httpx.post(url + "/apply-template", json={"messages": msgs, "chat_template_kwargs": FAST}, timeout=120).json()
    prompt = r["prompt"]
    t = httpx.post(url + "/tokenize", json={"content": prompt, "add_special": False}, timeout=120).json()
    return prompt, t["tokens"]


def lcp(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def build_prompts(url, layout, sizes, reps):
    """Deterministic prompts, sized by the server's tokenizer, saved so every config sees byte-identical input."""
    f = EVID / f"prompts_{layout}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    s1, s2 = stable_sections()
    out = {"layout": layout, "sizes": {}}
    for size in sizes:
        for rep in range(reps):
            seed = 101 + rep
            # size the evidence: tokens of the fixed parts + per-block average, then correct once
            base_msgs = messages(layout, s1, s2, PERM, SESSION, [], TURN_A)
            _, base_tok = render_tokens(url, base_msgs)
            sample = evidence_blocks(60, seed)
            _, samp_tok = render_tokens(url, messages(layout, s1, s2, PERM, SESSION, sample, TURN_A))
            per_block = (len(samp_tok) - len(base_tok)) / len(sample)
            n = max(4, int((size - len(base_tok)) / per_block))
            _, tok = render_tokens(url, messages(layout, s1, s2, PERM, SESSION, evidence_blocks(n, seed), TURN_A))
            n = max(4, int(n * (size - len(base_tok)) / max(1, len(tok) - len(base_tok))))
            blocks_a = evidence_blocks(n, seed)
            replace_at = int(0.75 * n)
            blocks_d = evidence_blocks(n, seed, replace_at=replace_at)
            variants = {"A": messages(layout, s1, s2, PERM, SESSION, blocks_a, TURN_A),
                        "C": messages(layout, s1, s2, PERM, SESSION, blocks_a, TURN_C),
                        "D": messages(layout, s1, s2, PERM, SESSION, blocks_d, TURN_A),
                        "E": messages(layout, s1, s2, PERM_E, SESSION, blocks_a, TURN_A),
                        "S": messages(layout, s1, s2, PERM, SESSION_S, blocks_a, TURN_A)}
            toks = {k: render_tokens(url, v)[1] for k, v in variants.items()}
            meta = {k: {"n_tokens": len(toks[k]), "lcp_vs_A": lcp(toks["A"], toks[k]), "logical_new_tokens": len(toks[k]) - lcp(toks["A"], toks[k])}
                    for k in variants}
            out["sizes"][f"{size}:{rep}"] = {"size": size, "rep": rep, "seed": seed, "n_evidence_blocks": n + 2, "replace_at": replace_at,
                                             "messages": variants, "meta": meta}
            print(f"prompts size={size} rep={rep}: " + ", ".join(f"{k} n={m['n_tokens']} new={m['logical_new_tokens']}" for k, m in meta.items()), flush=True)
    f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def run(a):
    EVID.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    cfg = ServerConfig(name=a.name, model=CFG["model"]["path"], ctx=a.ctx, ngl=999, port=a.port, load_mode="none",
                       mmproj=None if a.no_mmproj else CFG["model"]["mmproj"], extra=tuple(a.extra.split()),
                       **({"binary": a.binary} if a.binary else {}))
    srv = Server(cfg, EVID / "logs").start()
    url = srv.url
    rows = []
    summary = {"name": a.name, "stamp": stamp, "layout": a.layout, "argv": cfg.argv(), "model_sha256": file_sha256(CFG["model"]["path"]),
               "binary_sha256": file_sha256(cfg.binary), "load_seconds": srv.load_seconds, "props": srv.props(), "sizes": a.sizes}
    try:
        chat(url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs=FAST)
        prompts = build_prompts(url, a.layout, a.sizes, a.reps)
        summary["prompt_meta"] = {k: v["meta"] for k, v in prompts["sizes"].items()}
        for size in a.sizes:
            for rep in range(a.reps):
                p = prompts["sizes"][f"{size}:{rep}"]
                for scen, key in SEQUENCE:
                    if key not in p["messages"]:   # prompts_<layout>.json built before this variant existed (kept byte-identical)
                        continue
                    msgs = p["messages"][key]
                    r = chat(url, msgs, max_tokens=a.max_tokens, template_kwargs=FAST)
                    t = r.get("timings") or {}
                    m = p["meta"][key]
                    row = {"size": size, "rep": rep, "scenario": scen, "variant": key, "n_tokens": m["n_tokens"],
                           "logical_new_tokens": m["logical_new_tokens"], "lcp_vs_A": m["lcp_vs_A"],
                           "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"), "prompt_ms": t.get("prompt_ms"),
                           "prompt_tps": t.get("prompt_per_second"), "predicted_n": t.get("predicted_n"), "predicted_ms": t.get("predicted_ms"),
                           "ttft_s": r.get("ttft_s"), "total_s": r.get("total_s"), "finish": r.get("finish_reason"), "error": r.get("error"),
                           "text": r.text, "sha": sha(r.text)}
                    if t.get("prompt_n") is not None:
                        row["excess_recompute"] = t["prompt_n"] - m["logical_new_tokens"]
                        row["reuse_ratio"] = round((t.get("cache_n") or 0) / max(1, m["n_tokens"]), 4)
                    if rep == 0 and size == a.sizes[-1]:
                        row["vram_mib_after"] = gpu_dedicated_mib()
                    rows.append(row)
                    print(f"{size:>6} r{rep} {scen:22s} n={m['n_tokens']:>6} new={m['logical_new_tokens']:>6} prompt_n={row['prompt_n']} "
                          f"cache_n={row['cache_n']} prompt_ms={row['prompt_ms']} ttft={row['ttft_s']} total={row['total_s']} "
                          f"excess={row.get('excess_recompute')} {row['sha']} err={row['error']}", flush=True)
        summary["resources"] = srv.resource_snapshot()
    finally:
        srv.stop()
    summary["rows"] = rows
    agg = {}
    for scen, _ in SEQUENCE:
        for size in a.sizes:
            rs = [r for r in rows if r["scenario"] == scen and r["size"] == size and r["prompt_n"] is not None]
            if rs:
                agg[f"{size}:{scen}"] = {"n": len(rs), "prompt_n": statistics.median(r["prompt_n"] for r in rs),
                                         "logical_new": statistics.median(r["logical_new_tokens"] for r in rs),
                                         "excess": statistics.median(r["excess_recompute"] for r in rs),
                                         "prompt_ms": round(statistics.median(r["prompt_ms"] for r in rs), 1),
                                         "ttft_s": statistics.median(r["ttft_s"] for r in rs if r["ttft_s"] is not None) if any(r["ttft_s"] is not None for r in rs) else None,
                                         "total_s": statistics.median(r["total_s"] for r in rs)}
    summary["agg"] = agg
    out = EVID / f"{a.name}_{stamp}.json"
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"name": a.name, "load_seconds": srv.load_seconds, "resources": summary["resources"], "agg": agg}, indent=1))


def latest(name):
    # exact name + run stamp only: "ctx_prod_*" must not match "ctx_prod_split_*"
    fs = sorted(f for f in EVID.glob(f"{name}_*.json") if re.fullmatch(rf"{re.escape(name)}_\d{{8}}-\d{{6}}", f.stem))
    return json.loads(fs[-1].read_text(encoding="utf-8")) if fs else None


def compare(names):
    runs = {n: latest(n) for n in names}
    missing = [n for n, v in runs.items() if not v]
    if missing:
        print("missing runs:", missing)
    names = [n for n in names if runs[n]]
    ctrl = runs[names[0]]
    ctrl_text = {(r["size"], r["rep"], r["variant"]): r["sha"] for r in ctrl["rows"]}
    report = {"control": names[0], "configs": {}}
    for n in names:
        v = runs[n]
        same = sum(1 for r in v["rows"] if ctrl_text.get((r["size"], r["rep"], r["variant"])) == r["sha"])
        report["configs"][n] = {"layout": v.get("layout"), "argv_extra": v["argv"][-12:], "agg": v["agg"], "resources": v.get("resources"),
                                "outputs_identical_to_control": f"{same}/{len(v['rows'])}", "load_seconds": v.get("load_seconds")}
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (EVID / f"compare_{stamp}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    keys = sorted({k for n in names for k in runs[n]["agg"]}, key=lambda k: (int(k.split(":")[0]), [s for s, _ in SEQUENCE].index(k.split(":")[1])))
    print("size:scenario".ljust(30) + "".join(n[:22].ljust(24) for n in names))
    print("".ljust(30) + "".join("prompt_n/excess ms".ljust(24) for _ in names))
    for k in keys:
        line = k.ljust(30)
        for n in names:
            x = runs[n]["agg"].get(k)
            line += (f"{int(x['prompt_n'])}/{int(x['excess'])} {x['prompt_ms']:.0f}ms".ljust(24) if x else "-".ljust(24))
        print(line)
    for n in names:
        c = report["configs"][n]
        r = c["resources"] or {}
        print(f"{n}: identical_to_control={c['outputs_identical_to_control']} peak_vram={r.get('peak_vram_dedicated_mib')} "
              f"peak_rss={r.get('peak_server_rss_mib')} min_free_ram={r.get('min_system_available_ram_mib')} load={c['load_seconds']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--extra", default="-b 2048 -ub 1024 --cache-ram 1024")
    ap.add_argument("--binary", default=None)
    ap.add_argument("--layout", default="single", choices=["single", "split", "multi", "final"])
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--port", type=int, default=18498)
    ap.add_argument("--no-mmproj", action="store_true")
    ap.add_argument("--sizes", default=",".join(map(str, SIZES)))
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=48)
    ap.add_argument("--compare", nargs="+")
    a = ap.parse_args()
    a.sizes = [int(x) for x in a.sizes.split(",") if x]
    if a.compare:
        compare(a.compare)
    else:
        run(a)


if __name__ == "__main__":
    main()
