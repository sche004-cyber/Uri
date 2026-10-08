"""Evidence-grounded narration. Policy: NO EVENT, NO CLAIM.

Every sentence is a template instantiated with fields that are RE-DERIVED from the ledger rows it
cites. A claim carries a level:
  executor_says  - from `executor_report` evidence (a claim by the executor)
  uri_observed   - from `uri_observed` evidence (URI looked, nothing more is asserted)
  uri_verified   - from `uri_verified` evidence / completion record (URI proved it)
  system         - a statement about URI's own recorded state (task row, recovery decision)
`verify_claim` mechanically re-checks any claim, including ones proposed by an LLM summariser: a
claim whose citations do not resolve, whose fields differ from the cited rows, whose text differs
from the template, or whose level is stronger than its evidence supports is dropped or downgraded.
Executor free text is never parsed for facts and can never override structured evidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .ledger import Ledger

LEVEL_RANK = {"executor_says": 0, "uri_observed": 1, "uri_verified": 2, "system": 3}
SRC_TO_LEVEL = {"executor_report": "executor_says", "uri_observed": "uri_observed", "uri_verified": "uri_verified", "user": "system"}


@dataclass
class Claim:
    template_id: str
    fields: dict
    text: str
    level: str
    citations: list = field(default_factory=list)   # [("evidence", 12), ("recovery_decision", 3), ...]


def _clip(s, n=160):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


TEMPLATES = {
    "tests_ran": "Ran tests: {passed}/{total} passed.",
    "files_changed": "Changed {n} files.",
    "executor_file_changes": "Executor reports {n} file change events.",
    "command_failed": "Executor reports command `{command}` exited with code {exit_code}.",
    "command_ok": "Executor reports command `{command}` exited with code 0.",
    "executor_claims_complete": "Executor reports completion; URI has not verified it.",
    "executor_claims_error": "Executor reports it ended with an error.",
    "executor_message": "Executor message (unverified): {text}",
    "postcondition_verified": "Verified by URI: {kind}.",
    "postcondition_failed": "URI checked {kind}: not satisfied.",
    "process_gone": "Executor process confirmed gone.",
    "state_queued": "Task is queued.",
    "state_running": "Task is running (attempt {attempt}).",
    "state_recovering": "Task is being reconciled after an interruption.",
    "state_complete": "Task complete: every required postcondition was verified by URI.",
    "state_retry_safe": "Attempt ended without proof of completion; URI proved a retry is safe ({reason}).",
    "state_uncertain": "Outcome uncertain: URI cannot prove whether the effect happened ({reason}).",
    "state_needs_user": "Waiting for user decision because the effect cannot be confirmed ({reason}).",
    "state_failed": "Task failed ({reason}).",
}


def render(template_id, fields):
    return TEMPLATES[template_id].format(**fields)


def _row(L: Ledger, table, rid):
    key = {"evidence": "evidence_id", "recovery_decision": "decision_id", "completion_record": "completion_id",
           "postcondition_result": "result_id", "event": "seq", "stream_event": "stream_event_id", "task": "task_id"}[table]
    return L.q1(f"SELECT * FROM {table} WHERE {key}=?", (rid,))


def _payload(r):
    return json.loads(r["payload"])


def derive(L: Ledger, task_id, template_id, citations):
    """Recompute (fields, level) for a template from ONLY its cited rows. None if cited rows do not support it."""
    rows = []
    for table, rid in citations:
        r = _row(L, table, rid)
        if r is None or ("task_id" in r.keys() and r["task_id"] != task_id):
            return None
        rows.append((table, r))
    ev = [r for t, r in rows if t == "evidence"]
    t = L.task(task_id)
    if template_id == "tests_ran":
        if len(ev) != 1 or ev[0]["kind"] != "postcondition_check":
            return None
        o = _payload(ev[0]).get("observation", {})
        if "passed" not in o or "total" not in o or _payload(ev[0]).get("status") != "PASS":
            return None
        return {"passed": o["passed"], "total": o["total"]}, SRC_TO_LEVEL[ev[0]["source"]]
    if template_id == "files_changed":
        if len(ev) != 1 or ev[0]["kind"] != "files_changed" or ev[0]["source"] == "executor_report":
            return None
        return {"n": _payload(ev[0])["n"]}, SRC_TO_LEVEL[ev[0]["source"]]
    if template_id == "executor_file_changes":
        if not ev or any(e["kind"] != "file_change" or e["source"] != "executor_report" for e in ev):
            return None
        return {"n": len(ev)}, "executor_says"
    if template_id in ("command_failed", "command_ok"):
        if len(ev) != 1 or ev[0]["kind"] != "tool_result" or ev[0]["source"] != "executor_report":
            return None
        p = _payload(ev[0])
        code = p.get("exit_code")
        if not isinstance(code, int) or isinstance(code, bool) or (code == 0) != (template_id == "command_ok"):
            return None
        return {"command": _clip(p.get("command", "?"), 120), "exit_code": code}, "executor_says"
    if template_id in ("executor_claims_complete", "executor_claims_error"):
        kind = "terminal_success_claim" if template_id == "executor_claims_complete" else "terminal_error_claim"
        if len(ev) != 1 or ev[0]["kind"] != kind or ev[0]["source"] != "executor_report":
            return None
        if template_id == "executor_claims_complete" and t["state"] == "COMPLETE":
            return None   # once verified, the unverified-claim sentence would mislead
        return {}, "executor_says"
    if template_id == "executor_message":
        if len(ev) != 1 or ev[0]["kind"] != "agent_message" or ev[0]["source"] != "executor_report":
            return None
        p = _payload(ev[0])
        return {"text": "«" + _clip(json.dumps(p.get("text"), ensure_ascii=False)[:400], 160) + "»"}, "executor_says"
    if template_id in ("postcondition_verified", "postcondition_failed"):
        if len(ev) != 1 or ev[0]["kind"] != "postcondition_check":
            return None
        p = _payload(ev[0])
        want = "PASS" if template_id == "postcondition_verified" else "FAIL"
        if p.get("status") != want:
            return None
        return {"kind": p["kind"]}, SRC_TO_LEVEL[ev[0]["source"]]
    if template_id == "process_gone":
        if len(ev) != 1 or ev[0]["kind"] != "process_identity" or _payload(ev[0]).get("state") not in ("DEAD_CONFIRMED", "NEVER_STARTED"):
            return None
        return {}, "uri_observed"
    if template_id.startswith("state_"):
        want = template_id[6:].upper()
        if t["state"] != want or not any(tb in ("event", "recovery_decision", "completion_record") for tb, _ in rows):
            return None
        if want == "COMPLETE":
            cr = [r for tb, r in rows if tb == "completion_record"]
            if not cr or cr[0]["completion_id"] != t["completion_ref"]:
                return None
            return {}, "uri_verified" if cr[0]["kind"] == "verified" else "system"
        f = {"reason": t["reason_code"]}
        if want == "RUNNING":
            f = {"attempt": t["attempt_count"]}
        elif want in ("QUEUED", "RECOVERING"):
            f = {}
        return f, "system"
    return None


def verify_claim(L: Ledger, task_id, claim: Claim):
    """-> ("ok", claim) | ("downgraded", claim) | ("dropped", reason). Pure re-derivation from the ledger."""
    if claim.template_id not in TEMPLATES:
        return "dropped", "UNKNOWN_TEMPLATE"
    if not claim.citations:
        return "dropped", "NO_EVENT_NO_CLAIM"
    for table, rid in claim.citations:
        try:
            if _row(L, table, rid) is None:
                return "dropped", f"CITATION_UNRESOLVED:{table}:{rid}"
        except KeyError:
            return "dropped", f"CITATION_BAD_TABLE:{table}"
    got = derive(L, task_id, claim.template_id, claim.citations)
    if got is None:
        return "dropped", "CITATION_DOES_NOT_SUPPORT_TEMPLATE"
    fields, max_level = got
    if fields != claim.fields:
        return "dropped", "FIELDS_DIFFER_FROM_EVIDENCE"
    if render(claim.template_id, fields) != claim.text:
        return "dropped", "TEXT_DIFFERS_FROM_TEMPLATE"
    if LEVEL_RANK.get(claim.level, 99) > LEVEL_RANK[max_level]:
        return "downgraded", Claim(claim.template_id, fields, claim.text, max_level, claim.citations)
    return "ok", claim


def _mk(tid, fields, level, cites):
    return Claim(tid, fields, render(tid, fields), level, cites)


def narrate(L: Ledger, task_id) -> list[Claim]:
    """Deterministic narration. Each emitted claim is verified before being returned."""
    t = L.task(task_id)
    out = []
    st = {"QUEUED": "state_queued", "RETRY_SAFE": "state_retry_safe", "RUNNING": "state_running", "RECOVERING": "state_recovering",
          "COMPLETE": "state_complete", "UNCERTAIN": "state_uncertain", "NEEDS_USER": "state_needs_user", "FAILED": "state_failed"}[t["state"]]
    cites = []
    if t["state"] == "COMPLETE":
        cites = [("completion_record", t["completion_ref"])]
    else:
        d = L.q1("SELECT decision_id FROM recovery_decision WHERE task_id=? ORDER BY decision_id DESC LIMIT 1", (task_id,))
        ev = L.q1("SELECT MAX(seq) FROM event WHERE task_id=? AND kind='task.state'", (task_id,))
        cites = [("event", ev[0])] if ev and ev[0] else []
        if d and t["state"] in ("RETRY_SAFE", "UNCERTAIN", "NEEDS_USER", "FAILED"):
            cites.append(("recovery_decision", d[0]))
    fields = {"reason": t["reason_code"]} if "reason" in TEMPLATES[st] else ({"attempt": t["attempt_count"]} if "attempt" in TEMPLATES[st] else {})
    out.append(_mk(st, fields, "uri_verified" if t["state"] == "COMPLETE" else "system", cites))
    for e in L.q("SELECT * FROM evidence WHERE task_id=? ORDER BY evidence_id", (task_id,)):
        p = json.loads(e["payload"])
        c = [("evidence", e["evidence_id"])]
        k = e["kind"]
        if k == "terminal_success_claim" and t["state"] != "COMPLETE":
            out.append(_mk("executor_claims_complete", {}, "executor_says", c))
        elif k == "terminal_error_claim":
            out.append(_mk("executor_claims_error", {}, "executor_says", c))
        elif k == "tool_result" and isinstance(p.get("exit_code"), int) and not isinstance(p.get("exit_code"), bool):
            f = {"command": _clip(p.get("command", "?"), 120), "exit_code": p["exit_code"]}
            out.append(_mk("command_ok" if p["exit_code"] == 0 else "command_failed", f, "executor_says", c))
        elif k == "agent_message":
            out.append(_mk("executor_message", {"text": "«" + _clip(json.dumps(p.get("text"), ensure_ascii=False)[:400], 160) + "»"},
                           "executor_says", c))
        elif k == "postcondition_check":
            o = p.get("observation", {})
            if p.get("status") == "PASS" and "passed" in o and "total" in o:
                out.append(_mk("tests_ran", {"passed": o["passed"], "total": o["total"]}, SRC_TO_LEVEL[e["source"]], c))
            elif p.get("status") == "PASS":
                out.append(_mk("postcondition_verified", {"kind": p["kind"]}, SRC_TO_LEVEL[e["source"]], c))
            elif p.get("status") == "FAIL":
                out.append(_mk("postcondition_failed", {"kind": p["kind"]}, SRC_TO_LEVEL[e["source"]], c))
        elif k == "files_changed" and e["source"] != "executor_report":
            out.append(_mk("files_changed", {"n": p["n"]}, SRC_TO_LEVEL[e["source"]], c))
        elif k == "process_identity" and p.get("state") in ("DEAD_CONFIRMED", "NEVER_STARTED"):
            out.append(_mk("process_gone", {}, "uri_observed", c))
    fc = [e for e in L.q("SELECT evidence_id FROM evidence WHERE task_id=? AND kind='file_change' AND source='executor_report'", (task_id,))]
    if fc:
        out.append(_mk("executor_file_changes", {"n": len(fc)}, "executor_says", [("evidence", e[0]) for e in fc]))
    verified = []
    for c in out:
        status, res = verify_claim(L, task_id, c)
        if status in ("ok", "downgraded"):
            verified.append(res if status == "downgraded" else c)
    return verified


def filter_proposed_claims(L: Ledger, task_id, proposed: list[Claim]):
    """For an LLM layer: it must emit Claim objects (template + fields + citations). -> (kept, [(claim, reason)])."""
    kept, dropped = [], []
    for c in proposed:
        status, res = verify_claim(L, task_id, c)
        if status == "dropped":
            dropped.append((c, res))
        else:
            kept.append(res)
    return kept, dropped


def format_claim(c: Claim) -> str:
    tag = {"executor_says": "[executor says]", "uri_observed": "[URI observed]", "uri_verified": "[URI verified]", "system": "[URI state]"}[c.level]
    return f"{tag} {c.text}"
