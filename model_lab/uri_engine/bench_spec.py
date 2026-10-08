"""Speculative-decoding experiment (prompt lookup / n-gram / MTP) on URI-style generation tasks.

Runs the same greedy tasks against one server configuration and records tokens/s, acceptance
(timings.draft_n / draft_n_accepted when the server reports them) and the exact output text, so a
run with speculation can be diffed against the plain-decoding run: with greedy sampling, accepted
drafts must not change a single token.

  python model_lab/uri_engine/bench_spec.py --name spec_off --extra "-b 2048 -ub 1024 --cache-ram 1024"
  python model_lab/uri_engine/bench_spec.py --name ngram_mod --extra "... --spec-type ngram-mod ..."
  python model_lab/uri_engine/bench_spec.py --compare spec_off ngram_mod

Tasks: office drafting, rewriting text given in context, a code patch, document extraction to JSON,
a decision contract (grammar), a conversational answer, and a long dossier answer.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from lab import cases as CS  # noqa: E402
from lab import decision, longctx  # noqa: E402
from lab import prompts as P  # noqa: E402
from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402
from scripts.m30_4_decision_quality_analysis import real_directory, turn_state_for  # noqa: E402
from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT, build_decision_request, preselect_candidate_ids  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
FAST = {"enable_thinking": False}
EVID = LAB / "evidence" / "uri_engine" / "spec"

NOTE = """Office of the Dean (Academics)
Circular No. ACAD/2026/117                                             4 October 2026
Subject: Revision of the mid-semester examination timetable
All Heads of Departments are informed that the mid-semester examinations scheduled from 13 October 2026
will now commence on 16 October 2026 owing to the state holiday on 14 October. The revised timetable is
attached. Departments shall display it on their notice boards and inform students through the portal
by 7 October 2026. Invigilation duty rosters already circulated remain valid with dates shifted by
three days. Queries may be addressed to the Examination Section (ext. 2210).
Sd/- Dean (Academics)"""

CODE = '''def allocate_rooms(students, rooms):
    """Assign students to rooms in order; returns dict room -> list of roll numbers."""
    out = {}
    i = 0
    for room in rooms:
        out[room["id"]] = []
        for _ in range(room["capacity"]):
            if i >= len(students):
                break
            out[room["id"]].append(students[i]["roll"])
            i += 1
    if i < len(students):
        raise ValueError("not enough capacity")
    return out


def summarize(allocation):
    lines = []
    for room, rolls in allocation.items():
        lines.append(f"{room}: {len(rolls)} students")
    return "\\n".join(lines)
'''

DOC = """ADMISSION RECORD
Name: Tenzin Lhamu Bhutia   Roll No: B250412CS   Programme: B.Tech Computer Science
Date of Birth: 14/03/2007   Category: ST   Hostel: Kanchenjunga Block, Room 214
Guardian: Mr. Sonam Bhutia (Father), +91 98xxxxxx12, Gangtok, Sikkim
Fee paid: Rs 42,000 on 11/07/2026 (Receipt 7781). Scholarship: State merit (pending verification).
Remarks: Medical certificate submitted on 02/09/2026 for hostel change request."""


def tasks():
    directory = real_directory()
    st = turn_state_for("Draft an office order appointing Dr. Rao as warden from 1 November.", directory)
    pre = preselect_candidate_ids(st, directory) or [s["capability_id"] for s in directory.summaries()]
    req = build_decision_request(st, preselected_ids=pre, capability_directory=directory)
    schema = decision.decision_schema([s["capability_id"] for s in req["capability_summaries"]])
    dossier, task = longctx.build_package(4000)
    o = CS.build_o(CS.O_CASES[0])
    return [
        {"id": "office_draft", "max_tokens": 400, "messages": o["messages"]},
        {"id": "rewrite_circular", "max_tokens": 450, "messages": [
            {"role": "system", "content": P.DRAFT_SYSTEM},
            {"role": "user", "content": "Rewrite the following circular so that the new commencement date is 19 October 2026 and the "
                                        "portal deadline is 9 October 2026. Keep every other sentence exactly as it is.\n\n" + NOTE}]},
        {"id": "code_patch", "max_tokens": 500, "messages": [
            {"role": "system", "content": P.FAST_SYSTEM},
            {"role": "user", "content": "Return the complete modified file. Change allocate_rooms so that it skips students whose "
                                        "'roll' is None instead of assigning them, and keep everything else identical.\n\n```python\n" + CODE + "```"}]},
        {"id": "extract_record", "max_tokens": 300, "messages": [
            {"role": "system", "content": P.EXTRACTION_SYSTEM},
            {"role": "user", "content": "Fields: name, roll_number, programme, date_of_birth, hostel_block, room, guardian_name, fee_paid_inr, "
                                        "fee_date, receipt_no, scholarship_status.\n\n" + DOC}]},
        {"id": "decision_contract", "max_tokens": 500, "json_schema": schema, "messages": [
            {"role": "system", "content": DECISION_CONTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(req, sort_keys=True, separators=(",", ":"), ensure_ascii=True)}]},
        {"id": "conversational", "max_tokens": 250, "messages": [
            {"role": "system", "content": P.FAST_SYSTEM},
            {"role": "user", "content": "In four or five sentences, how should a department convener prepare for an academic audit visit?"}]},
        {"id": "dossier_answer", "max_tokens": 300, "messages": [
            {"role": "system", "content": "You are URI's local assistant. Follow the user's standing instructions."},
            {"role": "user", "content": "SESSION DOSSIER\n\n" + dossier + "\n\n---\n" + task}]},
        {"id": "quote_back", "max_tokens": 350, "messages": [
            {"role": "system", "content": P.FAST_SYSTEM},
            {"role": "user", "content": "Repeat the circular below verbatim, then add one sentence saying it was acknowledged.\n\n" + NOTE}]},
    ]


def run(a):
    cfg = ServerConfig(name=a.name, model=CFG["model"]["path"], ctx=a.ctx, ngl=999, port=a.port, load_mode="none",
                       mmproj=None if a.no_mmproj else CFG["model"]["mmproj"], extra=tuple(a.extra.split()),
                       **({"binary": a.binary} if a.binary else {}))
    EVID.mkdir(parents=True, exist_ok=True)
    srv = Server(cfg, EVID / "logs").start()
    rows = []
    try:
        chat(srv.url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs=FAST)
        for rep in range(a.repeats):
            for t in tasks():
                r = chat(srv.url, t["messages"], max_tokens=t["max_tokens"], template_kwargs=FAST, json_schema=t.get("json_schema"))
                tm = r.get("timings") or {}
                rows.append({"id": t["id"], "rep": rep, "text": r.text, "finish": r.get("finish_reason"), "error": r.get("error"),
                             "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"), "prompt_ms": tm.get("prompt_ms"),
                             "predicted_n": tm.get("predicted_n"), "predicted_ms": tm.get("predicted_ms"),
                             "gen_tps": tm.get("predicted_per_second"), "draft_n": tm.get("draft_n"),
                             "draft_n_accepted": tm.get("draft_n_accepted"), "ttft_s": r.get("ttft_s"), "total_s": r.get("total_s")})
        res = srv.resource_snapshot()
    finally:
        srv.stop()
    out = {"name": a.name, "argv": cfg.argv(), "load_seconds": srv.load_seconds, "resources": res, "rows": rows}
    (EVID / f"{a.name}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        print(f'{r["id"]:18s} rep{r["rep"]} gen={r["predicted_n"]} tps={r["gen_tps"] and round(r["gen_tps"],1)} '
              f'draft={r["draft_n"]}/{r["draft_n_accepted"]} total={r["total_s"]} fin={r["finish"]} err={r["error"]}')


def compare(names):
    runs = {n: json.loads((EVID / f"{n}.json").read_text(encoding="utf-8")) for n in names}
    base = runs[names[0]]
    by_id = {}
    for r in base["rows"]:
        by_id.setdefault(r["id"], []).append(r)
    report = {"baseline": names[0], "variants": {}}
    for n in names[1:]:
        v = runs[n]
        rows = {}
        for r in v["rows"]:
            b = by_id[r["id"]][r["rep"]] if r["rep"] < len(by_id[r["id"]]) else by_id[r["id"]][0]
            rows[f'{r["id"]}#{r["rep"]}'] = {
                "identical_text": r["text"] == b["text"], "gen_tps_base": b["gen_tps"], "gen_tps": r["gen_tps"],
                "speedup": round(r["gen_tps"] / b["gen_tps"], 3) if r["gen_tps"] and b["gen_tps"] else None,
                "draft_n": r["draft_n"], "draft_n_accepted": r["draft_n_accepted"],
                "accept_rate": round(r["draft_n_accepted"] / r["draft_n"], 3) if r.get("draft_n") else None,
                "total_base": b["total_s"], "total": r["total_s"]}
        sp = [x["speedup"] for x in rows.values() if x["speedup"]]
        report["variants"][n] = {"rows": rows, "median_speedup": round(statistics.median(sp), 3) if sp else None,
                                 "all_identical": all(x["identical_text"] for x in rows.values()),
                                 "resources": v["resources"], "load_seconds": v["load_seconds"]}
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (EVID / f"compare_{'_'.join(names)}_{stamp}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for n, v in report["variants"].items():
        print(f"== {n}: median speedup {v['median_speedup']}, all identical {v['all_identical']}")
        for k, x in v["rows"].items():
            print(f"  {k:24s} same={x['identical_text']} tps {x['gen_tps_base']}->{x['gen_tps']} x{x['speedup']} acc={x['accept_rate']} ({x['draft_n_accepted']}/{x['draft_n']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--extra", default="-b 2048 -ub 1024 --cache-ram 1024")
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--port", type=int, default=18496)
    ap.add_argument("--no-mmproj", action="store_true")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--compare", nargs="+")
    ap.add_argument("--binary", default=None, help="alternative llama-server.exe (self-built)")
    a = ap.parse_args()
    if a.compare:
        compare(a.compare)
    else:
        run(a)


if __name__ == "__main__":
    main()
