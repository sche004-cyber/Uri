"""Checkpoint/prompt-cache diagnostics: run a few consecutive canonical proposer prompts with verbose server
logging and extract the checkpoint create/restore and prompt-cache load/save lines, so the reuse mechanism
behind the measured cache_n values is documented from the server's own trace, not inferred.

  python model_lab/uri_engine/diag_ckpt.py [--extra "..."]
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from lab import decision  # noqa: E402
from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402
from scripts.m30_4_decision_quality_analysis import real_directory, turn_state_for  # noqa: E402
from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT, build_decision_request, preselect_candidate_ids  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine"
FAST = {"enable_thinking": False}
PAT = re.compile(r"checkpoint|prompt cache|cache_n|n_past|reuse|restored|forcing full|lcp|f_keep|cached n_tokens|erasing|superseding", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", default="-b 2048 -ub 1024 --cache-ram 1024")
    ap.add_argument("--port", type=int, default=18499)
    a = ap.parse_args()
    log_dir = EVID / "diag_logs"
    cfg = ServerConfig(name="diag", model=CFG["model"]["path"], ctx=32768, ngl=999, port=a.port, load_mode="none",
                       mmproj=CFG["model"]["mmproj"], extra=tuple(a.extra.split() + ["-v"]))
    srv = Server(cfg, log_dir).start()
    directory = real_directory()
    cases = decision.cases()
    # three consecutive turns that share the same preselected set, then one that does not, then an interpreter call
    ids = ["clarify_1", "clarify_2", "continue_1", "conv_1"]
    picked = [c for c in cases if c["id"] in ids]
    rows = []
    try:
        chat(srv.url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs=FAST)
        for c in picked:
            st = turn_state_for(c["text"], directory, active_pointer=c.get("active_pointer"),
                                recent_conversation=c.get("recent_conversation"), attempt_history=c.get("attempt_history"))
            pre = preselect_candidate_ids(st, directory) or [s["capability_id"] for s in directory.summaries()]
            req = build_decision_request(st, preselected_ids=pre, capability_directory=directory)
            r = chat(srv.url, [{"role": "system", "content": DECISION_CONTRACT_SYSTEM_PROMPT},
                               {"role": "user", "content": json.dumps(req, sort_keys=True, separators=(",", ":"), ensure_ascii=True)}],
                     max_tokens=120, template_kwargs=FAST)
            t = r.get("timings") or {}
            rows.append({"id": c["id"], "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"), "prompt_ms": t.get("prompt_ms")})
            print(rows[-1])
    finally:
        srv.stop()
    log = (log_dir / "server_diag.log").read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [l for l in log if PAT.search(l) and "print_timing" not in l]
    out = {"extra": a.extra, "rows": rows, "trace": hits[-400:]}
    (EVID / "diag_ckpt.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for l in hits[-120:]:
        print(l[:220])


if __name__ == "__main__":
    main()
