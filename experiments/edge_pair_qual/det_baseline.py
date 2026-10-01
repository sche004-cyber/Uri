"""Deterministic baseline (no model). Writes run records in the harness format, arm "deterministic".

Two layers:
1. The frozen M36 gate ``uri_v1.memory.contracts.negated`` (accepted URI code, imported read-only).
   A negated request is never acted on.
2. Experimental keyword and pattern rules for select cases. These rules are NOT a URI
   component; they stand in for "tasks that need no model" (one unambiguous keyword family plus a
   pattern-matched argument). The same author wrote the battery, so the rules may fit it better
   than they would fit real traffic. Route, extract and label cases get no deterministic answer
   (outcome "not handled", which in the combined configurations means the case goes to a model).

Usage: python det_baseline.py --split dev --out runs/det_dev.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
from uri_v1.memory.contracts import negated  # noqa: E402  (frozen M36, read-only)

FILE = r"[\w\-À-ɏऀ-ॿ一-鿿().' ]+?\.(?:pdf|docx?|xlsx?|pptx?|csv|txt|jpg)"
RULES = [
    ("system_performance", r"\b(cpu|processor|ram|memory usage|disk usage|disk|performance)\b", {}),
    ("fetch_url", r"https?://\S+", {"url": r"(https?://[^\s,]+[^\s,.])"}),
    ("extract_student_records", r"\b(roll|record|transcript|grades?)\b", {"roll_number": r"\b(\d{2}[A-Za-z]{2,4}\d{2,6})\b"}),
    ("fetch_drive_spreadsheet", r"\bspreadsheet\b|\bsheet id\b", {"spreadsheet_id": r"\b(1[\w\-]{9,})\b", "range": r"((?:'[^']+'|\w+)?!?[A-Z]+\d+:[A-Z]+\d+)"}),
    ("convert_document", r"\bconvert\b", {"attachment_name": "(" + FILE + ")"}),
    ("read_attached_file", r"\battach(ed|ment)\b", {"attachment_name": "(" + FILE + ")"}),
    ("gmail_find_draft", r"\bdrafts?\b.*\b(gmail|search|look)\b|\b(search|look)\b.*\bdrafts\b", {}),
    ("gmail_search", r"\b(gmail|inbox|mailbox|emails?|mails?)\b", {}),
    ("drive_search", r"\bdrive\b", {}),
    ("web_search", r"\b(web|internet|online)\b", {}),
    ("remember_fact", r"\b(remember that|remember my|save this|please remember)\b", {}),
    ("recall_memory", r"\bwhat do you remember\b|\bdo you know\b", {}),
    ("drive_upload", r"\bupload\b", {"file_name": "(" + FILE + ")"}),
]


def decide(case):
    t = case["text"]
    if case["kind"] != "select":
        return {"handled": False}
    if negated(t):
        return {"handled": True, "calls": [], "abstain": "DECLINE", "reason": "m36_negated"}
    hits = [(n, a) for n, pat, a in RULES if re.search(pat, t, re.I) and n in case["offered"]]
    if len(hits) != 1:
        return {"handled": False, "reason": f"{len(hits)}_rules_matched"}
    name, argpats = hits[0]
    args = {}
    for k, p in argpats.items():
        m = re.search(p, t)
        if not m:
            return {"handled": True, "calls": [], "abstain": "CLARIFY", "reason": f"no_{k}"}
        args[k] = m.group(1).strip()
    if argpats == {} and name not in ("system_performance",):
        # free-text argument tools: the rule cannot fill a query deterministically
        return {"handled": False, "reason": "free_text_argument"}
    return {"handled": True, "calls": [{"name": name, "arguments": args}], "reason": "rule"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cases = [c for c in json.loads((HERE / "battery" / "cases.json").read_text(encoding="utf-8")) if c["split"] == a.split]
    with open(a.out, "w", encoding="utf-8") as fh:
        for c in cases:
            t0 = time.perf_counter()
            d = decide(c)
            ms = (time.perf_counter() - t0) * 1000
            fh.write(json.dumps({"type": "call", "arm": "deterministic", "cond": None, "case": c["id"], "rep": 1,
                                 "split": a.split, "calls": d.get("calls", []), "suppressed": [], "handled": d["handled"],
                                 "reason": d.get("reason"), "det_abstain": d.get("abstain"), "wall_ms": ms, "error": None},
                                ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
