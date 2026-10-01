"""Deterministic RAR (uri_v1/turn/rar_deterministic.py, read-only import) on the reference workflows. No model call."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
from uri_v1.turn.rar_contracts import RARCandidate, RARQuery
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended

def run(expr, cands):
    q = RARQuery(reference_expression=expr, candidates=tuple(RARCandidate(**c) for c in cands))
    t = resolve_rar_deterministic_extended(q)
    r = t.resolution
    return {"expr": expr, "outcome": getattr(r.outcome, "value", str(r.outcome)), "selected": r.candidate_id, "ambiguous": list(r.ambiguous_candidate_ids),
            "rule": getattr(t.rule_used, "value", str(t.rule_used)), "failure": getattr(t.failure_class, "value", t.failure_class),
            "latency_ms": round(t.latency_ms, 3)}

doc = lambda i, title, rank, att=True: {"id": i, "title": title, "candidate_type": "document", "recency_rank": rank, "is_attachment": att}
probes = [
    ("W5 follow-up: one resolved attachment", "it", [doc("a1", "field_visit_report.docx", 0)]),
    ("W3 ambiguous: two attachments", "the attachment", [doc("a1", "claim_form_a.pdf", 0), doc("a2", "claim_form_b.pdf", 1)]),
    ("named reference", "the field visit report", [doc("a1", "field_visit_report.docx", 0), doc("a2", "budget_q3.xlsx", 1)]),
    ("latest of versions", "the latest plan", [doc("a1", "plan_v1.docx", 2), doc("a2", "plan_v2.docx", 1), doc("a3", "plan_v3.docx", 0)]),
    ("no candidates", "it", []),
]
out = [dict(case=n, **run(e, c)) for n, e, c in probes]
for o in out: print(o)
(HERE / "runs" / "rar_probe.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
