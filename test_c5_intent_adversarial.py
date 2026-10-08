"""Second review: Intent Discovery attacked through the REAL composition.

Real paired app, real client persistence (DPAPI, consented commits), the real GraphStore
and FileStore behind the client ports, and real app restarts. Each test names the attack.
"""
import time

import pytest

from test_c5_intent_discovery import NOBRAIN, Stack, confirm_and_approve, say, two_reports, uid
from uri_core.client_runtime.turn_runner import TurnRunner


@pytest.fixture
def s():
    stack = Stack(18245)
    yield stack
    stack.close()


def dispatched(s, before):
    return [p for _, p in s.calls[before:] if p.endswith(("/approval", "/claim"))]


def files(s, session):
    return {f["filename"]: f for f in s.read(session, "files", "list_for_session", session)}


def add_graph(s, session, *names):
    for name in names:
        s.runner._commit_consented(session, [("graph", "list_nodes", [], "upsert_node",
                                              {"entity_type": "document", "canonical_name": name})])


# ---- negation ---------------------------------------------------------------------------------
def test_negation_survives_binding_confirmation_and_execution(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is not due on Friday")
    awaiting = say(s, session, "the Q4 one")
    assert awaiting["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.docx is not due on Friday"
    _, final = confirm_and_approve(s, session, awaiting)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Budget report Q4.docx is not due on Friday"]


def test_bare_negation_while_confirming_asks_instead_of_guessing(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    out = say(s, session, "it is not due on Friday")
    assert out["state"] == "reply" and out["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert out["message"].startswith("I did not change anything")             # not mistaken for an applied change
    assert out["confirmation"]["digest"] == awaiting["confirmation"]["digest"]  # and nothing was changed
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)


# ---- correction -------------------------------------------------------------------------------
def test_ambiguous_correction_asks_which_detail_and_changes_nothing(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    out = say(s, session, "actually change it")
    assert out["code"] == "INTENT_CLARIFICATION" and "Which detail should change" in out["message"]
    record = s.session_state(session)["active_workflow"]
    assert record["slots"]["statement"]["value"].endswith("due on Friday") and s.memory(session) == []
    assert s.runner.confirm(session, NOBRAIN, awaiting)["code"] == "INTENT_DECISION_STALE"


def test_reference_rebinding_replaces_only_the_referent(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    rebound = say(s, session, "no, the Q3 one")
    assert rebound["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q3.docx is due on Friday"
    assert rebound["confirmation"]["digest"] != awaiting["confirmation"]["digest"]
    assert s.runner.confirm(session, NOBRAIN, awaiting)["code"] == "INTENT_DECISION_STALE"
    _, final = confirm_and_approve(s, session, rebound)
    assert s.memory(session) == ["Budget report Q3.docx is due on Friday"]


# ---- stale references -------------------------------------------------------------------------
def test_confirming_after_the_bound_file_was_removed_is_stale_and_reasked(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    q4 = files(s, session)["Budget report Q4.docx"]
    s.runner._commit_consented(session, [("files", "list_for_session", [session], "delete", {"file_id": q4["file_id"]})])
    before = len(s.calls)
    out = s.runner.confirm(session, NOBRAIN, awaiting)
    assert out["state"] == "reply" and not dispatched(s, before)
    assert out["code"] in {"INTENT_CONFIRMATION_REQUIRED", "INTENT_CLARIFICATION"}
    assert "Q4" not in str(out.get("confirmation") or "")
    record = s.session_state(session)["active_workflow"]
    assert any(h["kind"] == "reference_stale" for h in record["history"]) and s.memory(session) == []


# ---- "I don't know", repeated clarification, budget -------------------------------------------
def test_i_dont_know_never_becomes_a_referent_and_stops_without_guessing(s):
    session = uid()
    first = say(s, session, "remember that it is due on Friday")
    assert first["code"] == "INTENT_CLARIFICATION"
    answers = [say(s, session, t) for t in ("I don't know", "not sure", "no idea")]
    assert any(a["code"] in {"CLARIFICATION_NO_PROGRESS", "CLARIFICATION_REPEAT_BLOCKED"} for a in answers)
    questions = [a["message"] for a in [first, *answers] if a["code"] == "INTENT_CLARIFICATION"]
    assert len(questions) == len(set(questions))                          # never the same question twice
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)
    record = s.session_state(session)["active_workflow"]
    assert record is None or not any(str(r.get("title") or "").lower().startswith(("i don", "not sure", "no idea"))
                                     for r in record["references"].values())


def test_question_budget_never_exceeds_five_in_the_real_loop(s):
    session = uid()
    for i in range(6):
        s.add_file(session, f"Budget report {i}.docx")
    say(s, session, "remember that the budget report is due on Friday")
    asked = []
    for text in ("hmm", "the one from last week", "the newer one", "the important one", "the right one", "that one",
                 "the other one"):
        out = say(s, session, text)
        asked.append(out)
        if out["code"] != "INTENT_CLARIFICATION":
            break
    record = s.session_state(session)["active_workflow"] or {}
    assert record.get("questions_asked", 0) <= 5
    assert asked[-1]["code"] != "INTENT_CLARIFICATION"                    # it stops, it does not loop
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)


# ---- confirmation replay / stale digest / proposal mutation ------------------------------------
def test_confirmation_replay_after_execution_never_runs_twice(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    confirm_and_approve(s, session, awaiting)
    before = len(s.calls)
    replay = s.runner.confirm(session, NOBRAIN, awaiting)
    assert replay["state"] == "reply" and not dispatched(s, before)
    assert s.memory(session) == ["Budget report Q4.docx is due on Friday"]


def test_approval_cannot_be_moved_to_a_different_turn_or_mutated(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    first = s.runner.confirm(session, NOBRAIN, say(s, session, "the Q4 one"))
    assert first["state"] == "approval_required"
    req = first["approval_request"]
    assert req["intent_digest"] and req["arguments"]["inputs"]["request_text"].endswith("Q4.docx is due on Friday")
    forged = dict(first, approval_request=dict(req, approval_digest="0" * 64))
    with pytest.raises(Exception):
        s.runner.decide("Confirm", session, NOBRAIN, forged, True)
    assert s.memory(session) == []


# ---- graph widening ----------------------------------------------------------------------------
def test_graph_widening_with_several_plausible_candidates_asks_and_binds_the_choice(s):
    session = uid()
    add_graph(s, session, "Expense form 2025", "Expense form 2026")
    out = say(s, session, "remember that the expense form is due on Friday")
    assert out["code"] == "INTENT_CLARIFICATION" and out["clarification"]["kind"] == "reference"
    labels = {o["label"] for o in out["clarification"]["options"]}
    assert labels == {"Expense form 2025", "Expense form 2026"}           # asked, not guessed
    chosen = next(o for o in out["clarification"]["options"] if o["label"] == "Expense form 2025")
    bound = s.runner.select(session, NOBRAIN, out, chosen["candidate_id"])
    assert bound["confirmation"]["arguments"]["request_text"] == "remember that Expense form 2025 is due on Friday"
    record = s.session_state(session)["active_workflow"]
    assert [c[0] for c in record["arn"]["checked"]] == ["session_context", "graph"]   # widened exactly once
    _, final = confirm_and_approve(s, session, bound)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Expense form 2025 is due on Friday"]


def test_graph_widening_with_one_candidate_still_requires_confirmation(s):
    session = uid()
    add_graph(s, session, "Travel plan 2026")
    out = say(s, session, "remember that the travel plan is approved")
    assert out["state"] == "reply" and out["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert out["confirmation"]["arguments"]["request_text"] == "remember that Travel plan 2026 is approved"
    assert s.memory(session) == []


def test_graph_nodes_sharing_a_word_but_implausible_ask_freely_not_an_empty_choice(s):
    """Fifth review: graph widening on 'report' returned unrelated nodes, RAR found none plausible, and the
    FREE_INPUT_ONLY contract was rendered as "Which one do you mean by 'the Q4 report'? ." with NO options;
    any answer then hit CLARIFICATION_REPEAT_BLOCKED. Nothing was ever guessed, but the user could not answer."""
    session = uid()
    add_graph(s, session, "Sales report 2019", "HR report archive")
    out = say(s, session, "remember that the Q4 report is final")
    assert out["code"] == "INTENT_CLARIFICATION" and out["clarification"]["kind"] == "reference_free"
    assert out["clarification"]["options"] == [] and "couldn't find" in out["message"]
    answered = say(s, session, "the Q4 sales report")
    assert answered["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert answered["confirmation"]["arguments"]["request_text"] == "remember that the Q4 sales report is final"
    assert answered["intent"]["references"]["statement"]["state"] == "USER_SUPPLIED"   # the user's words, not a graph node
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)


def test_selecting_an_option_that_was_never_displayed_is_refused(s):
    session = uid()
    add_graph(s, session, "Expense form 2025", "Expense form 2026")
    out = say(s, session, "remember that the expense form is due on Friday")
    before = len(s.calls)
    forged = s.runner.select(session, NOBRAIN, out, "graph:not-a-displayed-option")
    assert forged["state"] == "reply" and forged["code"] != "INTENT_CONFIRMATION_REQUIRED" and not dispatched(s, before)


# ---- cancellation and crashes ------------------------------------------------------------------
def test_cancelling_during_clarification_drops_the_request(s):
    session = two_reports(s)
    first = say(s, session, "remember that the budget report is due on Friday")
    out = s.runner.abandon(session, NOBRAIN, first)
    assert out["code"] == "INTENT_ABANDONED"
    before = len(s.calls)
    again = s.runner.select(session, NOBRAIN, first, first["clarification"]["options"][0]["candidate_id"])
    assert again["state"] == "reply" and not dispatched(s, before) and s.memory(session) == []


def test_crash_before_confirmation_then_restart_confirms_exactly_once(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    s.start()                                                         # crash/restart before confirming
    _, final = confirm_and_approve(s, session, awaiting)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Budget report Q4.docx is due on Friday"]


def test_crash_after_confirmation_before_approval_needs_a_fresh_approval(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    s.start()                                                         # pending approval lost with the process
    with pytest.raises(Exception):
        s.runner.decide("Confirm", session, NOBRAIN, approval, True)   # old approval cannot be used
    assert s.memory(session) == []
    fresh = s.runner.confirm(session, NOBRAIN, awaiting)
    assert fresh["state"] == "approval_required"
    final = s.runner.decide("Confirm", session, NOBRAIN, fresh, True)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Budget report Q4.docx is due on Friday"]


def test_crash_around_execution_handoff_never_repeats(s, monkeypatch):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    real = TurnRunner._run_local

    def run_then_crash(self, *a, **k):
        real(self, *a, **k)                                            # the effect happens...
        raise RuntimeError("crash before settle")                      # ...then the client dies
    monkeypatch.setattr(TurnRunner, "_run_local", run_then_crash)
    with pytest.raises(RuntimeError):
        s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    assert s.memory(session) == ["Budget report Q4.docx is due on Friday"]
    before = len(s.calls)
    with pytest.raises(Exception, match="TURN_CAPACITY"):     # session still held by the in-flight attempt
        s.runner.confirm(session, NOBRAIN, awaiting)
    assert not dispatched(s, before)
    s.start()
    before = len(s.calls)
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["code"] == "INTENT_EXECUTION_UNCERTAIN" and not dispatched(s, before)
    s.app.state.client_service.clock = lambda: time.time() + 3 * 3600
    assert s.runner.confirm(session, NOBRAIN, awaiting)["code"] == "INTENT_EXECUTION_UNCERTAIN"
    assert s.memory(session) == ["Budget report Q4.docx is due on Friday"]       # exactly one effect


def test_a_new_request_after_a_stopped_one_gets_its_own_question_allowance(s):
    """Salvaged from the superseded experimental intent controller ('new cycle has its own allowance')."""
    session = uid()
    for i in range(3):
        s.add_file(session, f"Budget report Q{i + 1}.docx")
    say(s, session, "remember that the budget report is due on Friday")
    for text in ("hmm", "whatever", "still not sure", "no idea"):
        last = say(s, session, text)
        if last["code"] != "INTENT_CLARIFICATION":
            break
    assert last["code"] in {"CLARIFICATION_NO_PROGRESS", "CLARIFICATION_REPEAT_BLOCKED", "CLARIFICATION_BUDGET_EXHAUSTED"}
    fresh = say(s, session, "remember that the budget report is due on Monday")
    assert fresh["code"] == "INTENT_CLARIFICATION" and fresh["intent"]["questions_asked"] == 1
    assert fresh["clarification"]["intent_id"] != (last.get("intent") or {}).get("intent_id")


def test_abandoned_intent_replayed_from_older_client_state_is_stale(s):
    """Fourth review: abandoning did not advance the revision, so a client replaying its pre-abandon
    session state could re-present the abandoned request for confirmation and reach approval."""
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    pre_abandon = s.session_state(session)
    assert s.runner.abandon(session, NOBRAIN, awaiting)["code"] == "INTENT_ABANDONED"
    s.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session",
                                          {"session_id": session}, pre_abandon)])
    before = len(s.calls)
    out = s.runner.confirm(session, NOBRAIN, awaiting)
    assert out["code"] == "INTENT_STATE_STALE" and not dispatched(s, before) and s.memory(session) == []
    assert s.session_state(session)["active_workflow"] is None
