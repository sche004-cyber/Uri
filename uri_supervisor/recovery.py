"""Deterministic reconciliation / restart recovery.

Evidence order (brief section 7): 1 fence the old attempt; 2 inspect process identity; 3 executor
terminal evidence; 4 resumable session evidence; 5 artifacts; 6 declared postconditions; 7 decide;
8 record decision + supporting evidence durably, atomically with the state change.

One decision per (task, attempt) (UNIQUE): running recovery twice returns the same authoritative
outcome. Every attempt ending, clean or not, goes through here so there is exactly one decision
procedure: executor claims are evidence, never completion.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import crashpoints, winproc
from .executors import ExecutorSpec, valid_session_id
from .ledger import LedgerError, LedgerRefused, jdump
from .postconditions import EvalContext, evaluate_postconditions, fingerprint_paths
from .stream import PARSER_ID, interpret_line


@dataclass
class Decision:
    outcome: str                 # COMPLETE | RETRY_SAFE | UNCERTAIN | FAILED | NEEDS_USER
    action: str                  # NONE | RETRY_FRESH | RETRY_SAME_KEY | RESUME_SESSION | ESCALATE
    reason: str
    detail: str = ""
    intent_id: int | None = None
    quota: bool = False
    steps: dict = field(default_factory=dict)


def _ev(sup, task_id, attempt_id, source, kind, subject, payload, recorded_by="recovery"):
    with sup.ledger.tx() as db:
        now = sup.ledger.now_us()
        cur = db.execute("INSERT INTO evidence(task_id,attempt_id,source,kind,subject,payload,occurred_at_us,recorded_at_us,recorded_by) "
                         "VALUES (?,?,?,?,?,?,?,?,?)", (task_id, attempt_id, source, kind, subject, jdump(payload), now, now, recorded_by))
        sup.ledger.emit("evidence." + kind, task_id, attempt_id, ("evidence", cur.lastrowid))
        return cur.lastrowid


# ---- step 1 ------------------------------------------------------------------------------------

def _fence(sup, task_id, attempt_id, reason):
    L = sup.ledger
    with L.tx() as db:
        t = L.task(task_id)
        a = L.attempt(attempt_id)
        if a["status"] != "FENCED":
            db.execute("UPDATE attempt SET status='FENCED', fenced_at_us=? WHERE attempt_id=?", (L.now_us(), attempt_id))
        if t["state"] == "RUNNING":
            L.transition(task_id, "RECOVERING", reason, attempt_id=attempt_id, set_fence=None)
        L.emit("attempt.fenced", task_id, attempt_id, ("attempt", attempt_id), {"reason": reason})


# ---- step 2 ------------------------------------------------------------------------------------

def _inspect_process(sup, a):
    """-> (proc_state, observation). proc_state: DEAD_CONFIRMED | NEVER_STARTED | NOT_CONFIRMED_DEAD."""
    obs = {"pid": a["pid"], "create_time": a["pid_create_time"], "job": a["job_name"], "attempt_status_at_recovery": a["status"]}
    if a["pid"] is None:
        # Identity is made durable BEFORE the executor is resumed (winproc.spawn_contained), so no recorded pid
        # means the executor never executed an instruction.
        exists, active = (winproc.job_state(a["job_name"]) if a["job_name"] else (False, 0)) if winproc.IS_WINDOWS else (False, 0)
        obs.update(job_exists=exists, active=active)
        if exists and active:
            ok = winproc.terminate_named_job(a["job_name"])
            obs["terminated"] = ok
            return ("DEAD_CONFIRMED" if ok else "NOT_CONFIRMED_DEAD"), obs
        return "NEVER_STARTED", obs
    if not winproc.IS_WINDOWS:
        obs["note"] = "non-windows: identity unverifiable"
        return "NOT_CONFIRMED_DEAD", obs
    exists, active = winproc.job_state(a["job_name"]) if a["job_name"] else (False, 0)
    ident = winproc.identity_state(a["pid"], a["pid_create_time"])
    obs.update(job_exists=exists, active=active, identity=ident)
    if exists and active:
        ok = winproc.terminate_named_job(a["job_name"])
        obs["terminated"] = ok
        return ("DEAD_CONFIRMED" if ok else "NOT_CONFIRMED_DEAD"), obs
    if ident == "ALIVE_MATCH":
        # Matching creation time proves it is OUR process even though it is outside any live job.
        ok = winproc.terminate_identity(a["pid"], a["pid_create_time"])
        obs["terminated"] = ok
        return ("DEAD_CONFIRMED" if ok else "NOT_CONFIRMED_DEAD"), obs
    if ident in ("DEAD", "PID_REUSED"):
        return "DEAD_CONFIRMED", obs          # PID_REUSED: the original is gone; the new owner is never touched
    return "NOT_CONFIRMED_DEAD", obs          # UNKNOWN


# ---- step 3/4 ----------------------------------------------------------------------------------

def _terminal_and_session(sup, task_id, attempt_id, spec: ExecutorSpec):
    """Re-derive terminal claims from RAW persisted lines (never from live memory). Truncated tails never count."""
    L = sup.ledger
    claims, tail_incomplete, session = [], False, None
    for se in L.q("SELECT * FROM stream_event WHERE attempt_id=? AND stream='stdout' ORDER BY line_no", (attempt_id,)):
        it = interpret_line(bytes(se["raw"]), spec.rules, bool(se["complete"]))
        if not se["complete"] and se["raw"].strip():
            tail_incomplete = True
        for label, ext in it.semantics:
            if label in ("terminal_success_claim", "terminal_error_claim"):
                claims.append({"label": label, "stream_event_id": se["stream_event_id"], "extracted": ext})
            elif label == "session" and valid_session_id(ext.get("session_id")) and session is None:
                session = ext["session_id"]
        interp = L.q1("SELECT 1 FROM stream_interpretation WHERE stream_event_id=?", (se["stream_event_id"],))
        if interp is None:   # raw persisted but never interpreted (e.g. parser upgrade): interpret now, recorded by recovery
            with L.tx() as db:
                db.execute("INSERT INTO stream_interpretation(stream_event_id,parser_id,parse_status,event_type,semantics,extracted) "
                           "VALUES (?,?,?,?,?,?)", (se["stream_event_id"], PARSER_ID, it.parse_status, it.event_type,
                                                    jdump([s[0] for s in it.semantics]), jdump([s[1] for s in it.semantics])))
    return claims, tail_incomplete, session


# ---- effect classification ---------------------------------------------------------------------

def _classify_effects(sup, task_id, attempt_id, ctx_recorded_by="recovery"):
    """Return list of per-intent verdicts: dict(intent_id, op_class, safe(bool), action, reason, needs_user, applied(bool))."""
    L = sup.ledger
    verdicts = []
    for it in L.q("SELECT * FROM effect_intent WHERE task_id=? AND attempt_id=? ORDER BY intent_id", (task_id, attempt_id)):
        cls, ctx = it["op_class"], json.loads(it["pre_state_json"] or "{}")
        v = {"intent_id": it["intent_id"], "op_class": cls, "safe": False, "action": "ESCALATE", "reason": "", "needs_user": False,
             "applied": False}
        if cls == "read":
            v.update(safe=True, action="RETRY_FRESH", reason="READ_ONLY")
        elif cls == "idem_write":
            v.update(safe=True, action="RETRY_SAME_KEY", reason="IDEMPOTENT_KEY_PRESENT")
        elif cls == "local_write":
            before = ctx.get("fingerprints")
            if not before:
                v.update(reason="LOCAL_WRITE_NO_PRESTATE", needs_user=True)
            else:
                now_fp = fingerprint_paths(before.keys())
                if now_fp == before:
                    v.update(safe=True, action="RETRY_FRESH", reason="LOCAL_WRITE_ABSENCE_PROVEN")
                    _ev(sup, task_id, attempt_id, "uri_verified", "effect_absent", f"intent:{it['intent_id']}",
                        {"fingerprints_equal_to_pre_attempt": True, "paths": sorted(before)})
                else:
                    changed = sorted(k for k in before if now_fp.get(k) != before[k])
                    v.update(reason="LOCAL_WRITE_STATE_CHANGED_UNPROVEN", needs_user=True, applied=True, detail=changed)
        else:  # external
            rec_name, lookup = ctx.get("reconciler"), ctx.get("lookup")
            verdict = None
            if rec_name and rec_name in sup.reconcilers:
                try:
                    verdict, detail = sup.reconcilers[rec_name](lookup, ctx)
                except Exception as e:
                    verdict, detail = "UNKNOWN", type(e).__name__
                src = "uri_verified" if verdict in ("FOUND", "NOT_FOUND") else "uri_observed"
                eid = _ev(sup, task_id, attempt_id, src, "external_reconcile", f"intent:{it['intent_id']}",
                          {"reconciler": rec_name, "verdict": verdict, "detail": detail})
                with L.tx() as db:
                    db.execute("INSERT INTO effect_observation(intent_id,task_id,attempt_id,status,basis,evidence_id,observed_at_us,"
                               "recorded_at_us,recorded_by) VALUES (?,?,?,?,?,?,?,?,?)",
                               (it["intent_id"], task_id, attempt_id,
                                {"FOUND": "APPLIED", "NOT_FOUND": "ABSENT"}.get(verdict, "UNKNOWN"), f"reconciler:{rec_name}",
                                eid, L.now_us(), L.now_us(), "recovery"))
            if verdict == "FOUND":
                v.update(applied=True, reason="EXTERNAL_EFFECT_APPLIED", needs_user=False)
                # Applied but NOT proven complete by postconditions => never repeat it.
                v.update(safe=False, action="ESCALATE", reason="EXTERNAL_EFFECT_APPLIED_UNVERIFIED_COMPLETION")
            elif it["idempotency_key"]:
                v.update(safe=True, action="RETRY_SAME_KEY", reason="EXTERNAL_KEYED_RETRY" if verdict != "NOT_FOUND" else "EXTERNAL_ABSENT_KEYED_RETRY")
            elif verdict == "NOT_FOUND":
                # absence observed but no idempotency mechanism: eventual consistency could still surface the effect
                v.update(reason="EXTERNAL_ABSENT_NO_IDEMPOTENCY_KEY", needs_user=True)
            else:
                v.update(reason="EXTERNAL_EFFECT_UNCONFIRMED", needs_user=(verdict is None))
        verdicts.append(v)
    return verdicts


# ---- decision ----------------------------------------------------------------------------------

def decide(sup, task, attempt, proc_state, claims, tail_incomplete, session, spec, pcs, verdicts, quota) -> Decision:
    steps = {"process": proc_state, "terminal_claims": [c["label"] for c in claims], "tail_incomplete": tail_incomplete,
             "session": session, "postconditions": [{"id": p["postcondition_id"], "kind": p["kind"], "status": p["status"],
                                                      "required": p["required"]} for p in pcs],
             "effects": [{k: v[k] for k in ("intent_id", "op_class", "safe", "reason")} for v in verdicts]}
    required = [p for p in pcs if p["required"]]
    if proc_state == "NOT_CONFIRMED_DEAD":
        return Decision("UNCERTAIN", "ESCALATE", "PROCESS_NOT_CONFIRMED_DEAD",
                        "executor process could not be proven gone; effects cannot be bounded", steps=steps)
    if required and all(p["status"] == "PASS" for p in required):
        why = "POSTCONDITIONS_VERIFIED"
        if any(c["label"] == "terminal_error_claim" for c in claims):
            why = "POSTCONDITIONS_VERIFIED_DESPITE_EXECUTOR_ERROR_CLAIM"
        elif not claims:
            why = "POSTCONDITIONS_VERIFIED_WITHOUT_TERMINAL_EVENT"
        return Decision("COMPLETE", "NONE", why, steps=steps)
    unsafe = [v for v in verdicts if not v["safe"]]
    if proc_state == "NEVER_STARTED":
        # Identity is durable before the executor is resumed, so no recorded identity means it never ran an
        # instruction: no effect can have occurred, whatever intents were (or were not yet) declared.
        unsafe = []
    elif not verdicts:
        unsafe = [{"intent_id": None, "needs_user": True, "reason": "NO_EFFECT_INTENT_RECORDED", "op_class": None}]
    if unsafe:
        worst = unsafe[0]
        needs_user = any(v["needs_user"] for v in unsafe)
        claim_note = ""
        if any(c["label"] == "terminal_success_claim" for c in claims):
            claim_note = " executor reported completion, but URI has not verified it;"
        return Decision("NEEDS_USER" if needs_user else "UNCERTAIN", "ESCALATE", worst["reason"],
                        f"{claim_note} effects of attempt cannot be proven absent or complete".strip(), worst["intent_id"], steps=steps)
    # every effect is provably safe to repeat
    budget_left = task["attempt_count"] < task["max_attempts"] or quota
    keyed = any(v["action"] == "RETRY_SAME_KEY" for v in verdicts)
    resumable = bool(session and spec.resume_argv and not claims)
    action = "RETRY_SAME_KEY" if keyed else ("RESUME_SESSION" if resumable else "RETRY_FRESH")
    if quota:
        return Decision("RETRY_SAFE", action, "PROVIDER_QUOTA_EXHAUSTED", quota=True, steps=steps)
    if not budget_left:
        return Decision("FAILED", "NONE", "RETRY_BUDGET_EXHAUSTED", steps=steps)
    if any(c["label"] == "terminal_success_claim" for c in claims):
        reason = "EXECUTOR_CLAIMED_SUCCESS_NOT_VERIFIED_RETRY_SAFE"
    elif claims:
        reason = "EXECUTOR_REPORTED_ERROR_RETRY_SAFE"
    else:
        reason = "EXECUTOR_INTERRUPTED_NO_TERMINAL_EVENT_RETRY_SAFE"
    return Decision("RETRY_SAFE", action, reason, steps=steps)


# ---- driver ------------------------------------------------------------------------------------

def reconcile(sup, task_id, attempt_id, mode="attempt_end", forced_reason=None):
    """Run (or re-run) reconciliation for one attempt. Idempotent. -> recovery_decision row or None."""
    L = sup.ledger
    existing = L.q1("SELECT * FROM recovery_decision WHERE task_id=? AND attempt_id=?", (task_id, attempt_id))
    if existing:
        return existing
    task = L.task(task_id)
    if task["state"] not in ("RUNNING", "RECOVERING"):
        return None
    a = L.attempt(attempt_id)
    if a is None or a["task_id"] != task_id:
        raise LedgerError("UNKNOWN_ATTEMPT", str(attempt_id))
    # 1 fence
    _fence(sup, task_id, attempt_id, "RECOVERING_AFTER_RESTART" if mode == "restart" else "RECONCILING_ATTEMPT_END")
    crashpoints.hit("recovery_after_fence")
    a = L.attempt(attempt_id)
    reg = L.q1("SELECT spec_json FROM executor_registration WHERE registration_id=?", (a["registration_id"],))
    spec = ExecutorSpec.from_json(json.loads(reg[0]))
    # 2 process
    proc_state, pobs = _inspect_process(sup, a)
    _ev(sup, task_id, attempt_id, "uri_observed", "process_identity", f"attempt:{attempt_id}", {"state": proc_state, **pobs})
    crashpoints.hit("recovery_after_process_inspection")
    # 3,4 terminal + session evidence from raw lines
    claims, tail_incomplete, session = _terminal_and_session(sup, task_id, attempt_id, spec)
    if tail_incomplete:
        _ev(sup, task_id, attempt_id, "uri_observed", "truncated_tail_ignored", f"attempt:{attempt_id}",
            {"note": "unterminated final line preserved raw, not interpreted"})
    for c in claims:  # executor terminal claims as executor_report evidence if the live path never recorded them
        have = L.q1("SELECT 1 FROM evidence WHERE stream_event_id=? AND kind=?", (c["stream_event_id"], c["label"]))
        if have is None:
            with L.tx() as db:
                now = L.now_us()
                cur = db.execute("INSERT INTO evidence(task_id,attempt_id,source,kind,subject,payload,stream_event_id,occurred_at_us,"
                                 "recorded_at_us,recorded_by) VALUES (?,?,'executor_report',?,?,?,?,?,?,'recovery')",
                                 (task_id, attempt_id, c["label"], f"attempt:{attempt_id}", jdump(c["extracted"]),
                                  c["stream_event_id"], now, now))
                L.emit("evidence." + c["label"], task_id, attempt_id, ("evidence", cur.lastrowid))
    if session and not a["session_id"]:
        with L.tx() as db:
            db.execute("UPDATE attempt SET session_id=? WHERE attempt_id=?", (session, attempt_id))
    # quota detection from persisted text (stdout error claims + stderr), never from memory
    text = " ".join(json.dumps(c["extracted"]) for c in claims if c["label"] == "terminal_error_claim")
    text += " " + " ".join(bytes(r["raw"]).decode("utf-8", "replace") for r in
                           L.q("SELECT raw FROM stream_event WHERE attempt_id=? AND stream='stderr' ORDER BY line_no DESC LIMIT 200",
                               (attempt_id,)))
    text += " " + " ".join(json.dumps(json.loads(e["payload"])) for e in L.q(
        "SELECT payload FROM evidence WHERE attempt_id=? AND kind IN ('error_event','warning')", (attempt_id,)))
    quota = spec.quota_hit(text) and not any(c["label"] == "terminal_success_claim" for c in claims)
    reset_us = spec.provider_reset_wall_us(text) if quota else None
    crashpoints.hit("recovery_before_postconditions")
    # 6 postconditions (fresh observation) — only meaningful once the process can no longer change the world
    if proc_state != "NOT_CONFIRMED_DEAD":
        pcs = evaluate_postconditions(L, task_id, EvalContext(sup.reconcilers, attempt_id, "recovery"))
    else:
        pcs = []
    verdicts = _classify_effects(sup, task_id, attempt_id) if proc_state != "NOT_CONFIRMED_DEAD" else []
    crashpoints.hit("recovery_before_decision")
    d = decide(sup, L.task(task_id), a, proc_state, claims, tail_incomplete, session, spec, pcs, verdicts, quota)
    if forced_reason:
        d.steps["forced"] = forced_reason
    return _commit(sup, task_id, attempt_id, d, proc_state, spec, reset_us, pcs)


def _commit(sup, task_id, attempt_id, d: Decision, proc_state, spec, reset_us, pcs):
    L = sup.ledger
    quota_pools = json.loads(L.q1("SELECT quota_pools_json FROM executor_registration WHERE registration_id="
                                  "(SELECT registration_id FROM attempt WHERE attempt_id=?)", (attempt_id,))[0])
    try:
        with L.tx() as db:
            now = L.now_us()
            cur = db.execute("INSERT INTO recovery_decision(task_id,attempt_id,epoch,outcome,action,reason_code,evidence_json,"
                             "decided_at_us,recorded_at_us) VALUES (?,?,?,?,?,?,?,?,?)",
                             (task_id, attempt_id, sup.epoch, d.outcome, d.action, d.reason, jdump(d.steps), now, now))
            did = cur.lastrowid
            kw = {}
            completion = None
            if d.outcome == "COMPLETE":
                completion = db.execute("INSERT INTO completion_record(task_id,attempt_id,kind,basis_json,recorded_at_us) "
                                        "VALUES (?,?,'verified',?,?)", (task_id, attempt_id, jdump(d.steps), now)).lastrowid
            if d.outcome in ("UNCERTAIN", "NEEDS_USER"):
                db.execute("INSERT INTO uncertainty(task_id,attempt_id,intent_id,reason_code,detail,opened_at_us) VALUES (?,?,?,?,?,?)",
                           (task_id, attempt_id, d.intent_id, d.reason, d.detail, now))
            if d.quota:
                kw["max_attempts"] = L.task(task_id)["max_attempts"] + 1   # quota attempts do not consume the retry budget
            L.transition(task_id, d.outcome, d.reason, d.detail, attempt_id=attempt_id, completion_ref=completion,
                         set_fence=None, extra=kw or None)
            if proc_state in ("DEAD_CONFIRMED", "NEVER_STARTED"):
                db.execute("UPDATE claim SET state='released', ended_at_us=?, end_reason=? WHERE attempt_id=? AND state='held'",
                           (now, "RECOVERY_" + d.outcome, attempt_id))
                L.emit("claims.release", task_id, attempt_id, payload={"reason": "RECOVERY_" + d.outcome})
            L.emit("recovery.decision", task_id, attempt_id, ("recovery_decision", did),
                   {"outcome": d.outcome, "action": d.action, "reason": d.reason})
            # breaker feedback commits ATOMICALLY with the decision (re-entrant tx): a crash can never leave a
            # quota-exhausted provider looking healthy.
            if d.quota and quota_pools:
                sup.admitter.breaker_quota_hit(quota_pools, reset_us)
            else:
                sup.admitter.probe_done(attempt_id, provider_answered=bool(d.steps.get("terminal_claims")))
    except LedgerRefused as e:
        if "UNIQUE" in str(e.detail or e):   # a concurrent/second run already decided
            return L.q1("SELECT * FROM recovery_decision WHERE task_id=? AND attempt_id=?", (task_id, attempt_id))
        raise
    crashpoints.hit("recovery_after_decision")
    return L.q1("SELECT * FROM recovery_decision WHERE task_id=? AND attempt_id=?", (task_id, attempt_id))
