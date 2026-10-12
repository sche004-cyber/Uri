"""Fifth (closure) review: gate probes and independent F1/F3 attacks through the REAL paired composition.

Real paired app (TestClient), real client persistence (DPAPI, consented commits), real GraphStore / FileStore /
MemoryStore behind the client ports, real fake-harness subprocesses, real app restarts. Every probe records what
Core actually guarantees; assertions marked DOCUMENTED pin observed behaviour so the report is evidence.
Evidence files are written under work/c1/review5/closure_evidence/.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from test_c5_intent_adversarial import add_graph, dispatched
from test_c5_intent_discovery import NOBRAIN, Stack, confirm_and_approve, say, two_reports, uid
from test_c5_loop import harness_stack, CLAUDE, CODEX, FAKE   # noqa: F401  (fixture reused)
from uri_core.client_contracts import ReadQuery
from uri_core.client_runtime import harness as hx
from uri_core.client_runtime.persistence import ClientPersistence
from uri_core.client_runtime.turn_runner import TurnError, TurnRunner
from uri_core.core.paired_coordinator import deterministic_proposer
from uri_harness_adapters import parse_codex, parse_claude

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "work/c1/review5/closure_evidence"
OUT.mkdir(parents=True, exist_ok=True)


def record(name, payload):
    (OUT / (name + ".json")).write_text(json.dumps(payload, indent=2, default=str))


@pytest.fixture
def s():
    stack = Stack(18251)
    yield stack
    stack.close()



# ===== from test_review5_closure.py =====
def capturing(captured):
    def proposer(prepared, request, selection):
        captured.append(json.loads(json.dumps(prepared["request"], default=str)))
        return deterministic_proposer(prepared, request, selection)
    return proposer


def memory_rows(s):
    fresh = ClientPersistence(s.cm)      # independent instance: disk, not the writer's cache
    return fresh.snapshot(uid(), [ReadQuery(store="memory", method="list_all")]).reads[0].result


# =====================================================================================================
# GATE 1 - MEMORY
# =====================================================================================================
def test_g1_memory_learn_persist_restart_new_session_correct_duplicate_provenance_delete(s):
    a = uid()
    final = s.runner.run("remember that my favourite colour is teal", a, NOBRAIN, lambda req: True)
    assert final["code"] == "SETTLED_VERIFIED"
    rows = memory_rows(s)
    assert [r["fact"]["value"] for r in rows] == ["my favourite colour is teal"]
    entry = rows[0]
    # provenance available on the entry itself
    assert entry["consent"] == "user_provided" and entry["fact"]["source"] == "user_explicit" and entry["fact"]["status"] == "CONFIRMED"
    # DOCUMENTED: no turn/intent/session linkage on the memory entry
    assert not ({"turn_id", "intent_id", "session_id"} & set(entry)) and entry["fact"]["notes"] is None and entry["fact"]["evidence_ids"] == []

    # server restart + brand-new session: the fact is still there (principal-scoped store)
    s.start()
    b = uid()
    assert [r["fact"]["value"] for r in memory_rows(s)] == ["my favourite colour is teal"]
    # a pronoun in the NEW session does not bind to anything from the old session
    out = say(s, b, "remember that it is my favourite")
    assert out["code"] == "INTENT_CLARIFICATION" and out["clarification"]["kind"] == "reference_free"
    s.runner.abandon(b, NOBRAIN, out)

    # "correction" after execution: a new explicit statement is a NEW entry; the old one is untouched
    final = s.runner.run("remember that my favourite colour is green", b, NOBRAIN, lambda req: True)
    assert final["code"] == "SETTLED_VERIFIED"
    rows = memory_rows(s)
    values = [r["fact"]["value"] for r in rows]
    assert values == ["my favourite colour is teal", "my favourite colour is green"]
    assert all(r["fact"]["status"] == "CONFIRMED" for r in rows)          # DOCUMENTED: no supersession marker

    # duplicate: the same statement again is a new intent -> executes again -> a third entry
    final = s.runner.run("remember that my favourite colour is teal", b, NOBRAIN, lambda req: True)
    assert final["code"] == "SETTLED_VERIFIED"
    values = [r["fact"]["value"] for r in memory_rows(s)]
    assert values.count("my favourite colour is teal") == 2                  # DOCUMENTED: duplicates allowed

    # forgetting: only a client-local consented mutation (C3 port); no Core intent path exists for it
    target = next(r for r in memory_rows(s) if r["fact"]["value"] == "my favourite colour is green")["memory_id"]
    s.runner._commit_consented(b, [("memory", "list_all", [], "delete", {"memory_id": target})])
    assert "my favourite colour is green" not in [r["fact"]["value"] for r in memory_rows(s)]
    record("g1_memory", {"entry_example": entry, "after": memory_rows(s)})


def test_g1_session_fact_supersession_and_followup_binding_after_restart(s):
    captured = []
    s.start(proposer=capturing(captured))
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    confirm_and_approve(s, session, say(s, session, "the Q4 one"))
    say(s, session, "remember that the budget report was reviewed")
    confirm_and_approve(s, session, say(s, session, "the Q3 one"))
    state = s.session_state(session)
    assert state["current_facts"]["reference.recent_subject"]["data"]["value"] == "Budget report Q3.docx"
    hist = state["fact_history"]["reference.recent_subject"]
    assert [h["data"]["value"] for h in hist] == ["Budget report Q4.docx"] and hist[0]["data"]["status"] == "SUPERSEDED"
    s.start(proposer=capturing(captured))                                   # restart: binding must come from persisted facts
    follow = say(s, session, "remember that it is final")
    assert follow["code"] == "INTENT_CONFIRMATION_REQUIRED" and follow["intent"]["questions_asked"] == 0
    assert follow["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q3.docx is final"   # current, not superseded
    # What the proposer (a future Brain) was shown for that turn:
    req = captured[-1]
    record("g1_session_facts_projection", req)
    facts = {f["name"]: f for f in req["session_facts"]}
    # DOCUMENTED: Turn State projects fact_history (superseded values, labelled) - the current value is absent
    assert facts["reference.recent_subject"]["status"] == "SUPERSEDED" and facts["reference.recent_subject"]["value"] == "Budget report Q4.docx"
    assert "Budget report Q3.docx" not in json.dumps(req["session_facts"])


# =====================================================================================================
# GATE 2 - CONTEXT
# =====================================================================================================
def test_g2_decision_request_is_bounded_and_grounded(s):
    captured = []
    s.start(proposer=capturing(captured))
    session = uid()
    s.runner.run("remember that my favourite colour is teal", session, NOBRAIN, lambda req: True)
    for i in range(10):
        say(s, session, f"hello {i}")
    req = captured[-1]
    record("g2_decision_request", req)
    assert set(req) <= {"user_text", "recent_conversation", "active_pointer", "capability_summaries", "session_facts",
                        "attempt_history", "capability_index_hint", "current_turn_attachments", "capability_action_affordances"}
    assert len(req["recent_conversation"]) <= 6
    # DOCUMENTED: durable memory entries are never projected into the decision request in the paired loop
    assert "teal" not in json.dumps({k: v for k, v in req.items() if k != "recent_conversation"})
    assert len(json.dumps(req)) < 20000


def test_g2_unrelated_graph_nodes_and_conflicting_candidates(s):
    session = uid()
    add_graph(s, session, "Sales report 2019", "HR report archive", "Expense form 2025")
    out = say(s, session, "remember that the Q4 report is final")
    record("g2_graph_widening_unrelated", out)
    # Never guessed: either asks a free question or lists graph options; nothing executed
    assert out["code"] == "INTENT_CLARIFICATION" and not any(p.endswith("/approval") for _, p in s.calls)
    labels = [o["label"] for o in (out["clarification"].get("options") or [])]
    record("g2_graph_widening_unrelated_options", labels)
    assert out["clarification"]["kind"] == "reference_free" and labels == []     # repaired: free question, no empty choice
    s.runner.abandon(session, NOBRAIN, out)
    # session file and graph node with the same title: session-first wins without widening
    s.add_file(session, "Expense form 2025.docx")
    out = say(s, session, "remember that the expense form is approved")
    record("g2_session_vs_graph_same_title", out)
    assert out["state"] in {"approval_required", "reply"}
    args = (out.get("approval_request") or {}).get("arguments", {}).get("inputs", {}).get("request_text") or \
           (out.get("confirmation") or {}).get("arguments", {}).get("request_text")
    assert args == "remember that Expense form 2025.docx is approved", out
    rec = s.session_state(session)["active_workflow"] or {}
    assert not rec.get("arn")                      # no widening happened


def test_g2_session_transcript_ceiling_fails_closed_then_session_unusable(s):
    session = uid()
    failed_at = None
    for i in range(60):
        try:
            say(s, session, "x" * 7990 + f" {i:02d}")
        except Exception as exc:        # pydantic CONTEXT_LIMIT on the client snapshot
            failed_at = (i, type(exc).__name__, "CONTEXT_LIMIT" in str(exc))
            break
    record("g2_transcript_ceiling", {"failed_at": failed_at})
    assert failed_at is not None and failed_at[2]            # DOCUMENTED: deterministic ceiling, fails closed
    with pytest.raises(Exception):
        say(s, session, "hello")                             # DOCUMENTED: the session cannot continue afterwards
    assert say(s, uid(), "hello")["code"] == "CONVERSATION"  # a new session still works


# =====================================================================================================
# GATE 3 - AUTHORITY: interpreted values stay distinguishable and never auto-confirm
# =====================================================================================================
def labelling_proposer(prepared, request, selection):
    if request.text.startswith("note for you"):
        name = sorted(prepared["directory"].describe("remember_fact")["actions"])[0]
        return {"goal": request.text, "mode": "single_action", "capability": "remember_fact", "clarification": None,
                "unsupported_reason": None, "requires_approval": False, "confidence": 1.0, "reason": "labelled",
                "actions": [{"name": name, "inputs": {"request_text": request.text}}]}
    return deterministic_proposer(prepared, request, selection)


def test_g3_interpreted_slot_is_labelled_requires_confirmation_and_compiles_verbatim(s):
    seen = []
    def interpreter(text, capability, slots, selection):
        seen.append((text, capability, tuple(slots)))
        return {"statement": "my office is room 12"}
    s.start(proposer=labelling_proposer, interpreter=interpreter)
    session = uid()
    out = say(s, session, "note for you: my office is room 12")
    assert seen and out["code"] == "INTENT_CONFIRMATION_REQUIRED"           # never the auto-confirm path
    assert out["intent"]["sources"] == {"statement": "interpreted_from_request"}
    assert out["confirmation"]["arguments"]["request_text"] == "remember that my office is room 12"
    # a model that paraphrases is dropped, and the user is asked instead
    s.runner.abandon(session, NOBRAIN, out)
    seen.clear()
    s.start(proposer=labelling_proposer, interpreter=lambda t, c, sl, sel: {"statement": "office = room twelve"})
    out2 = say(s, session, "note for you: my office is room 12")
    assert out2["code"] == "INTENT_CLARIFICATION" and out2["clarification"]["slot"] == "statement"
    rec = s.session_state(session)["active_workflow"]
    assert any(h["kind"] == "ungrounded_interpretation_dropped" for h in rec["history"])
    s.runner.abandon(session, NOBRAIN, out2)
    # confirm the labelled one end to end
    s.start(proposer=labelling_proposer, interpreter=interpreter)
    out = say(s, session, "note for you: my office is room 12")
    assert out["code"] == "INTENT_CONFIRMATION_REQUIRED", out
    nxt = s.runner.confirm(session, NOBRAIN, out)
    assert nxt["state"] == "approval_required", (nxt["code"], nxt.get("message"))
    final = s.runner.decide("Confirm", session, NOBRAIN, nxt, True)
    approval = nxt
    assert approval["approval_request"]["intent_digest"] == out["confirmation"]["digest"]
    assert final["code"] == "SETTLED_VERIFIED" and "my office is room 12" in s.memory(session)
    record("g3_interpreted_slot", {"turn": out, "approval": approval["approval_request"], "final": final})


# =====================================================================================================
# GATE 4 - RECOVERY / INTEGRITY
# =====================================================================================================
def test_g4_corrupted_server_ledger_fails_closed(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    path = s.app.state.client_service.path
    good = path.read_text()
    path.write_text("{not json")
    with pytest.raises(Exception, match="CONTROL_STORE_UNAVAILABLE"):
        say(s, session, "the Q4 one")
    path.write_text(good)
    out = say(s, session, "the Q4 one")                     # restored ledger: the pending question continues
    assert out["code"] == "INTENT_CONFIRMATION_REQUIRED" and s.memory(session) == []


def test_g4_corrupted_execution_control_ledger_between_approval_and_claim(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    control = s.coordinator.control.path
    original = s.runner._post
    def corrupt_then_post(path, body):
        if path.endswith("/claim"):
            control.write_text("garbage")
        return original(path, body)
    s.runner._post = corrupt_then_post
    with pytest.raises(Exception, match="EXECUTION_CONTROL_UNAVAILABLE"):
        s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    s.runner._post = original
    assert s.memory(session) == []
    # the client journal recorded its intent before the online claim; recovery keeps it uncertain
    rows = s.runner.journal.recover()
    assert [r["state"] for r in rows] == ["execution_uncertain"]
    # the server side: ledger unreadable -> every later claim/settle on it is refused; a new turn in the
    # same session is blocked while the in-flight turn holds the session (fail closed, not silent retry)
    with pytest.raises(Exception):
        s.runner.confirm(session, NOBRAIN, awaiting)


def test_g4_cancel_after_server_restart_keeps_claimed_turn_uncertain(s, monkeypatch):
    from uri_core.client_runtime.turn_runner import TurnRunner
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    monkeypatch.setattr(TurnRunner, "_run_local", lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    s.start()
    turn_id = approval["turn_id"]
    status = s.runner.call("GET", f"/client/v1/turns/{turn_id}/status", None)[1] if hasattr(s.runner, "call") else None
    st, data = s.http.get(f"/client/v1/turns/{turn_id}/status", headers=_headers(s)).status_code, s.http.get(
        f"/client/v1/turns/{turn_id}/status", headers=_headers(s)).json()
    assert data["state"] == "executing" and data["context_available"] is False
    cancelled = s.runner._post(f"/client/v1/turns/{turn_id}/cancel", s.runner._control(session, data))
    assert cancelled["state"] == "execution_uncertain" and cancelled["code"] == "EXECUTION_UNCERTAIN_NOT_CANCELLED"
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["code"] == "INTENT_EXECUTION_UNCERTAIN" and s.memory(session) == []


def _headers(s):
    # the TestClient session token lives inside Stack.start's closure; re-acquire a session for raw GETs
    session = s.http.post("/client/v1/session", json={"server_id": s.cred["server_id"], "client_id": s.cred["client_id"]},
                          headers={"Authorization": "Bearer " + s.cred["principal_token"], "X-URI-Pairing": s.cred["pairing_token"]}).json()
    return {"Authorization": "Bearer " + session["token"], "X-URI-Client": s.cred["client_id"]}


# =====================================================================================================
# GATE 5 - OBSERVABILITY / PROVENANCE
# =====================================================================================================
def test_g5_reconstruct_request_intent_context_confirmation_approval_execution_outcome(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    say(s, session, "the Q4 one")
    corrected = say(s, session, "actually it is due on Monday, not Friday")
    approval, final = confirm_and_approve(s, session, corrected)
    assert final["code"] == "SETTLED_VERIFIED"
    history = s.read(session, "history", "get_session", session)
    state = s.session_state(session)
    turns = s.app.state.client_service._load()["turns"]
    control = s.coordinator.control._load()["operations"]
    db = sqlite3.connect(Path(s.cm.data["client_root"]) / "control/execution-journal.sqlite3")
    journal = [dict(zip(("id", "ticket_digest", "state", "receipt_digest", "binding_digest"), r))
               for r in db.execute("SELECT * FROM operations")]
    memory = memory_rows(s)
    dump = {"history": history, "session_state": state, "server_turns": turns, "control": control,
            "journal": journal, "memory": memory, "approval_request": approval["approval_request"], "final": final}
    record("g5_reconstruction", dump)
    blob = json.dumps(dump)
    # (a) user request words: durable (client history)
    assert any(t["user_text"] == "remember that the budget report is due on Friday" for t in history)
    assert any(t["user_text"] == "actually it is due on Monday, not Friday" for t in history)
    # (b) the confirmation that was shown: durable only as rendered reply text in history
    assert any("Please confirm before I continue: request_text = remember that Budget report Q4.docx is due on Monday" in t["response_text"] for t in history)
    # (c) outcome: durable in history, server ledger, control ledger, journal, memory
    exec_turn = next(t for t in turns.values() if t.get("execution_outcome"))
    assert exec_turn["execution_outcome"] == "verified" and exec_turn["intent_id"]
    assert [o["state"] for o in control.values()] == ["verified"] and [j["state"] for j in journal] == ["verified"]
    assert [m["fact"]["value"] for m in memory] == ["Budget report Q4.docx is due on Monday"]
    # (d) after completion the signed intent record is cleared from the session (by design); the lineage now
    #     lives in the client-private provenance attachment of each transcript turn (fifth-review repair).
    assert state["active_workflow"] is None
    prov = {t["user_text"]: (t.get("attachments") or [None])[0] for t in history}
    corr = prov["actually it is due on Monday, not Friday"]
    assert corr["kind"] == "uri.turn.provenance.v1" and corr["intent"]["sources"] == {"statement": "user_correction"}
    assert corr["intent"]["superseded"][0]["value"].endswith("Friday") and corr["intent"]["references"]["statement"]["title"] == "Budget report Q4.docx"
    assert corr["intent"]["references"]["statement"]["rule"] and corr["confirmation"]["digest"] == corrected["confirmation"]["digest"]
    done = prov["Confirm"]
    assert done["approval"]["argument_digest"] == approval["approval_request"]["argument_digest"]
    assert done["approval"]["intent_digest"] == corrected["confirmation"]["digest"]
    assert done["approval"]["arguments"]["inputs"] == {"request_text": "remember that Budget report Q4.docx is due on Monday"}
    assert done["execution"]["state"] == "verified" and done["intent"]["intent_id"] == exec_turn["intent_id"]
    assert next(t for t in history if t["user_text"] == "Confirm")["capability"] == "remember_fact"
    # the link from the client record to the server ledger and the control ledger: intent_id and operation_id
    assert exec_turn["operation_id"] in control and exec_turn["intent_id"] == done["intent"]["intent_id"]
    assert state["current_facts"]["reference.recent_subject"]["data"]["evidence_ids"]   # the bound file id survives as a session fact


# ===== from test_review5_f1_f3.py =====
# ---- F1 ---------------------------------------------------------------------------------------------
def _proc(tmp_path, lines, exit_code=1, contained=True):
    log = tmp_path / "h.log"
    log.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return hx.ProcessResult(exit_code, False, False, False, contained, 1.0, str(log), "0" * 64, 1, "")


def test_f1_codex_shaped_tool_activity_before_quota_counts_as_tool_activity(tmp_path):
    proc = _proc(tmp_path, [{"type": "thread.started"},
                            {"type": "item.completed", "item": {"type": "command_execution", "command": "echo hi"}},
                            {"type": "turn.failed", "error": {"message": "usage limit reached"}}])
    c = parse_codex(proc)
    assert c["claimed_outcome"] == "quota_exhausted" and c["usage"]["tool_calls"] == 1


def test_f1_claude_shaped_unparseable_stream_has_unavailable_tool_count(tmp_path):
    # a quota error with NO parsable assistant events at all: tool activity is unknown, not zero
    proc = _proc(tmp_path, [{"type": "result", "subtype": "error_during_execution", "is_error": True,
                             "result": "rate limit"}])
    c = parse_claude(proc)
    assert c["claimed_outcome"] == "quota_exhausted" and c["usage"]["tool_calls"] == 0   # DOCUMENTED: counts only visible tool_use


@pytest.mark.parametrize("claim_patch,expected", [
    ({"usage": {"tool_calls": hx.UNAVAILABLE}}, "SETTLED_EXECUTION_UNCERTAIN"),     # unknown count fails closed
    ({"usage": {"tool_calls": 0}, "contained": False}, "SETTLED_EXECUTION_UNCERTAIN"),  # not contained -> uncertain
    ({"usage": {"tool_calls": 0}}, "WAITING_FOR_MODEL"),                                 # genuine first-call quota
])
def test_f1_runner_quota_classification_through_real_server(harness_stack, monkeypatch, claim_patch, expected):
    runner, persistence, app, call, cm = harness_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    real_parse = runner.harness.parse
    real_supervise = hx.supervise
    def parse(provider, proc):
        c = real_parse(provider, proc)
        c["usage"] = {**c["usage"], **claim_patch.get("usage", {})}
        return c
    def supervise(*a, **k):
        p = real_supervise(*a, **k)
        if "contained" in claim_patch:
            p = hx.ProcessResult(p.exit_code, p.timed_out, p.inactivity_killed, p.cancelled, claim_patch["contained"],
                                 p.duration_ms, p.log_path, p.log_sha256, p.log_bytes, p.stderr_tail)
        return p
    monkeypatch.setattr(runner.harness, "parse", parse)
    monkeypatch.setattr(hx, "supervise", supervise)
    final = runner.run("use the harness to write a greeting into out.txt", uid(), CLAUDE, lambda req: True)
    assert final["code"] == expected, final


def test_f1_stale_quota_checkpoint_rerun_after_uncertain_continuation(harness_stack, monkeypatch):
    """Composition attack: T1 pauses cleanly (no tool activity), the user continues on provider B, that
    attempt hits quota AFTER tool activity (uncertain). Can the user re-run the same task again from the
    T1 checkpoint while the B attempt is uncertain?"""
    runner, persistence, app, call, cm = harness_stack
    session = uid()
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    paused = runner.run("use the harness to write a greeting into out.txt", session, CODEX, lambda req: True)   # codex-shaped fake: first-call quota
    assert paused["code"] == "WAITING_FOR_MODEL"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota_after_tool")
    second = runner.continue_waiting(session, paused["turn_id"], CLAUDE, lambda req: True)
    assert second["code"] == "SETTLED_EXECUTION_UNCERTAIN"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    approvals = []
    try:
        third = runner.continue_waiting(session, paused["turn_id"], CLAUDE, lambda req: approvals.append(1) or True)
    except TurnError as exc:
        third = {"code": "REFUSED:" + exc.code}
    results = list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))
    record("f1_stale_checkpoint", {"third": third, "approvals": approvals, "results": len(results)})
    # expected invariant: the T1 checkpoint is one explicit continuation, not a standing retry button
    assert third["code"] != "SETTLED_VERIFIED", third


# ---- F3 ---------------------------------------------------------------------------------------------
def test_f3_abandon_then_restart_then_replay_of_every_older_path_is_stale(s):
    session = two_reports(s)
    first = say(s, session, "remember that the budget report is due on Friday")      # CLARIFYING
    pre_answer = s.session_state(session)
    awaiting = say(s, session, "the Q4 one")                                          # AWAITING_CONFIRMATION
    pre_abandon = s.session_state(session)
    assert s.runner.abandon(session, NOBRAIN, awaiting)["code"] == "INTENT_ABANDONED"
    assert s.session_state(session)["active_workflow"] is None
    s.start()                                                                          # real app restart
    for name, state, action in (
            ("confirm-old", pre_abandon, lambda: s.runner.confirm(session, NOBRAIN, awaiting)),
            ("text-answer-old", pre_abandon, lambda: say(s, session, "yes go ahead")),
            ("select-older", pre_answer, lambda: s.runner.select(session, NOBRAIN, first, first["clarification"]["options"][0]["candidate_id"])),
            ("text-answer-older", pre_answer, lambda: say(s, session, "the Q4 one"))):
        s.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session", {"session_id": session}, state)])
        before = len(s.calls)
        out = action()
        assert out["code"] == "INTENT_STATE_STALE", (name, out)
        assert not dispatched(s, before) and s.session_state(session)["active_workflow"] is None and s.memory(session) == []


def test_f3_stopped_intent_replayed_from_older_state_is_stale(s):
    session = uid()
    for i in range(3):
        s.add_file(session, f"Budget report Q{i + 1}.docx")
    first = say(s, session, "remember that the budget report is due on Friday")
    pre_stop = s.session_state(session)
    last = None
    for text in ("hmm", "whatever", "still not sure", "no idea"):
        last = say(s, session, text)
        if last["code"] != "INTENT_CLARIFICATION":
            break
    assert last["code"] in {"CLARIFICATION_NO_PROGRESS", "CLARIFICATION_REPEAT_BLOCKED", "CLARIFICATION_BUDGET_EXHAUSTED"}
    s.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session", {"session_id": session}, pre_stop)])
    s.start()
    before = len(s.calls)
    out = s.runner.select(session, NOBRAIN, first, first["clarification"]["options"][0]["candidate_id"])
    assert out["code"] == "INTENT_STATE_STALE" and not dispatched(s, before) and s.memory(session) == []


def test_f3_abandon_decision_with_stale_revision_changes_nothing(s):
    session = two_reports(s)
    first = say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    out = s.runner.abandon(session, NOBRAIN, first)          # revision 1 decision against revision 2 record
    assert out["code"] == "INTENT_DECISION_STALE"
    rec = s.session_state(session)["active_workflow"]
    assert rec["status"] == "AWAITING_CONFIRMATION" and rec["revision"] == awaiting["confirmation"]["revision"]
    _, final = confirm_and_approve(s, session, awaiting)   # the live record is intact
    assert final["code"] == "SETTLED_VERIFIED"


# ===== from test_review5_longtext.py =====
@pytest.mark.parametrize("length", [300, 470])
def test_long_statement_with_binding_and_correction_persists(s, length):
    session = two_reports(s)
    body = ("the budget report is " + "very " * (length // 5))[:length]
    say(s, session, "remember that " + body + " due on Friday")
    awaiting = say(s, session, "the Q4 one")
    assert awaiting["code"] == "INTENT_CONFIRMATION_REQUIRED"
    corrected = say(s, session, "actually it is due on Monday, not Friday")
    assert corrected["code"] == "INTENT_CONFIRMATION_REQUIRED"
    _, final = confirm_and_approve(s, session, corrected)
    assert final["code"] == "SETTLED_VERIFIED"
    history = s.read(session, "history", "get_session", session)
    prov = [(t.get("attachments") or [None])[0] for t in history]
    assert all(p is None or len(str(p)) < 6000 for p in prov)
    assert prov[-1]["approval"]["argument_digest"] and prov[-1]["intent"]["intent_id"]


def test_statement_over_memory_limit_settles_uncertain_documented(s):
    """DOCUMENTED (pre-existing, identical on the incoming checkpoint): MemoryStore refuses content > 500 chars
    inside the consented commit (rolled back by the C3 journal), the client reports 'failed' after dispatch, and
    the server settles it execution_uncertain. Honest fail-closed, but the intent is then set aside forever."""
    session = uid()
    body = "my favourite colour is " + "very " * 120
    final = s.runner.run("remember that " + body + " long", session, NOBRAIN, lambda req: True)
    assert final["code"] == "SETTLED_EXECUTION_UNCERTAIN" and s.memory(session) == []
