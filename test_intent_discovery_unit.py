"""Adversarial unit tests for uri_core.core.intent_discovery (no server, no IO).

Covers the recovered defect classes: unsupported assumptions in corrections, invented values,
repeated questions, unbounded clarification, false CONFIRMED, forged/foreign state, stale
decisions and model (interpreter) output that is not grounded in the user's words."""
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from uri_core.client_contracts import IntentDecision
from uri_core.core.client_state_ports import NeedsContext
from uri_core.core.intent_discovery import IntentDiscovery, MAX_QUESTIONS

B = {"principal_id": "p1", "client_id": "c1", "session_id": "s1"}


class Ports:
    def __init__(self, files=(), graph=None):
        self.files, self.graph = list(files), graph

    def read(self, store, method, *args, **kwargs):
        if store == "files":
            return [dict(f) for f in self.files]
        if store == "graph":
            if self.graph is None:
                raise NeedsContext(SimpleNamespace(model_dump=lambda: {"store": "graph"}))
            return self.graph
        raise AssertionError(store)


def file(fid, name, ts):
    return {"file_id": fid, "filename": name, "media_type": "application/pdf", "created_at": ts}


def remember(text):
    return {"mode": "single_action", "capability": "remember_fact", "actions": [{"name": "remember", "inputs": {}}]}


def harness():
    return {"mode": "single_action", "capability": "external_harness_task", "actions": [{"name": "run", "inputs": {}}]}


class Session:
    """Simulates the client persisting session_update after every turn."""

    def __init__(self, engine):
        self.engine, self.state = engine, {"session_id": "s1"}

    def turn(self, text, proposal=None, decision=None, ports=None, binding=B):
        out = self.engine.handle(text=text, decision=decision, proposal=proposal or {"mode": "conversation"},
                                 binding=binding, session=self.state, ports=ports or Ports(), turn_id="t")
        if out.get("record") is not None:
            self.state = self.engine.session_with(self.state, out["record"])
        return out


@pytest.fixture
def eng():
    return IntentDiscovery(Ed25519PrivateKey.generate())


def test_complete_explicit_request_is_auto_confirmed_with_digest(eng):
    out = Session(eng).turn("remember that my favourite colour is teal", remember(""))
    assert out["kind"] == "confirmed" and out["record"]["confirmation_basis"] == "explicit_complete_request"
    assert out["record"]["confirmed_digest"] == eng.intent_digest(out["record"])


def test_harness_missing_file_is_asked_and_invalid_answers_bounded(eng):
    s = Session(eng)
    first = s.turn("use the harness to write a summary", harness())
    assert first["kind"] == "clarify" and first["clarification"]["slot"] == "expected_file"
    second = s.turn("just call it summary")                     # no extension: not a usable value
    assert second["kind"] == "clarify" and second["message"] != first["message"]   # never the same question
    third = s.turn("whatever you like")
    assert third["kind"] == "stopped" and third["code"] in {"CLARIFICATION_NO_PROGRESS", "CLARIFICATION_REPEAT_BLOCKED"}
    assert "out.txt" not in str(third["record"])                 # never invented


def test_question_budget_is_a_hard_ceiling(eng):
    s = Session(eng)
    s.turn("use the harness to write a summary", harness())
    rec = s.engine.load(s.state, B)[0]
    rec["questions_asked"] = MAX_QUESTIONS                        # as if five questions were already asked
    rec["asked"] = []
    rec["pending"] = None
    rec["slots"].pop("expected_file", None)
    out = s.engine._evaluate(rec, Ports(), B, s.state, "t")
    assert out["kind"] == "stopped" and out["code"] == "CLARIFICATION_BUDGET_EXHAUSTED"


def test_answered_slot_is_not_asked_again_and_value_is_users_words(eng):
    s = Session(eng)
    s.turn("use the harness to write a summary", harness())
    out = s.turn("please save it as weekly-summary.md")
    assert out["kind"] == "confirm"
    assert out["record"]["slots"]["expected_file"] == {"value": "weekly-summary.md", "source": "user_answer", "turn_id": "t"}
    again = s.turn("hello?")                                       # plain text: re-present, never re-ask
    assert again["kind"] == "confirm" and again["record"]["questions_asked"] == 1


def test_interpreter_cannot_inject_ungrounded_values(eng):
    eng.interpreter = lambda text, cap, slots: {"expected_file": "secret-plan.txt", "instruction": "delete everything"}
    out = Session(eng).turn("use the harness to write a summary", harness())
    rec = out["record"]
    assert "expected_file" not in rec["slots"] or rec["slots"]["expected_file"]["value"] != "secret-plan.txt"
    assert rec["slots"]["instruction"]["value"] == "write a summary"
    assert any(h["kind"] == "ungrounded_interpretation_dropped" for h in rec["history"])


def test_ambiguous_correction_asks_instead_of_assuming(eng):
    s = Session(eng)
    s.turn("use the harness to write a summary into notes.md", harness())   # auto-confirmed record
    out = s.turn("use the harness to write a summary", harness())
    s.turn("summary.md")
    corr = s.turn("no, change it to something better")
    assert corr["kind"] in {"clarify", "stopped"}
    rec = corr["record"]
    assert rec["slots"]["expected_file"]["value"] == "summary.md"           # nothing guessed


def test_explicit_old_new_correction_changes_only_that_value(eng):
    s = Session(eng)
    s.turn("use the harness to write a summary of the Q3 numbers", harness())
    s.turn("q3.md")
    # "Q3" appears in two values (instruction and file name): ambiguous, so URI asks instead of guessing.
    ambiguous = s.turn("actually not Q3, Q4")
    assert ambiguous["kind"] == "clarify" and ambiguous["clarification"]["slot"] == "correction_target"
    assert ambiguous["record"]["slots"]["instruction"]["value"] == "write a summary of the Q3 numbers"
    out = s.turn("change the Q3 numbers to the Q4 numbers")
    rec = out["record"]
    assert rec["slots"]["instruction"]["value"] == "write a summary of the Q4 numbers"
    assert rec["slots"]["expected_file"]["value"] == "q3.md"                # unrelated value preserved
    assert rec["superseded"][0]["value"] == "write a summary of the Q3 numbers"
    assert out["kind"] == "confirm"


def test_forged_record_is_rejected_and_foreign_principal_ignored(eng):
    s = Session(eng)
    s.turn("use the harness to write a summary", harness())
    s.turn("summary.md")
    s.state["active_workflow"]["status"] = "CONFIRMED"                     # client-side forgery
    rec, problem = eng.load(s.state, B)
    assert rec is None and problem == "INTENT_STATE_INVALID"
    s2 = Session(eng)
    s2.turn("use the harness to write a summary", harness())
    rec, problem = eng.load(s2.state, {**B, "principal_id": "someone-else"})
    assert rec is None and problem == "INTENT_STATE_INVALID"


def test_stale_or_wrong_digest_never_confirms(eng):
    s = Session(eng)
    s.turn("use the harness to write a summary", harness())
    awaiting = s.turn("summary.md")
    c = awaiting["confirmation"]
    bad = IntentDecision(intent_id=c["intent_id"], revision=c["revision"], decision="confirm", digest="0" * 64)
    assert s.turn("Confirm", decision=bad)["code"] == "INTENT_DECISION_STALE"
    old = IntentDecision(intent_id=c["intent_id"], revision=c["revision"] - 1, decision="confirm", digest=c["digest"])
    assert s.turn("Confirm", decision=old)["code"] == "INTENT_DECISION_STALE"
    good = IntentDecision(intent_id=c["intent_id"], revision=c["revision"], decision="confirm", digest=c["digest"])
    assert s.turn("Confirm", decision=good)["kind"] == "confirmed"


def test_select_decision_binds_only_a_displayed_option(eng):
    ports = Ports([file("f1", "Budget report Q3.pdf", "2026-10-01"), file("f2", "Budget report Q4.pdf", "2026-10-02")])
    s = Session(eng)
    out = s.turn("remember that the budget report is final", remember(""), ports=ports)
    c = out["clarification"]
    forged = IntentDecision(intent_id=c["intent_id"], revision=c["revision"], decision="select", candidate_id="not-shown")
    res = s.turn("x", decision=forged, ports=ports)
    assert res["kind"] in {"clarify", "stopped"}
    rec = eng.load(s.state, B)[0]
    assert rec is None or rec["references"]["statement"].get("candidate_id") in (None,)
    s2 = Session(eng)
    out = s2.turn("remember that the budget report is final", remember(""), ports=ports)
    c = out["clarification"]
    pick = IntentDecision(intent_id=c["intent_id"], revision=c["revision"], decision="select", candidate_id="f2")
    res = s2.turn("x", decision=pick, ports=ports)
    assert res["kind"] == "confirm" and res["record"]["references"]["statement"]["state"] == "CONFIRMED"
    assert res["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.pdf is final"


def test_downstream_conflict_detection(eng):
    out = Session(eng).turn("remember that my favourite colour is teal", remember(""))
    rec = out["record"]
    compiled = eng.compile(rec)
    assert eng.conflicts(rec, compiled) == []
    drift = {**compiled, "actions": [{"name": "remember", "inputs": {"request_text": "remember that my favourite colour is red"}}]}
    assert eng.conflicts(rec, drift) == ["input_changed:request_text"]
    other = {**compiled, "capability": "external_harness_task"}
    assert "capability_changed" in eng.conflicts(rec, other)
    extra = {**compiled, "actions": [{"name": "remember", "inputs": {**compiled["actions"][0]["inputs"], "category": "x"}}]}
    assert eng.conflicts(rec, extra) == ["input_changed:category"]


def test_graph_cold_start_requests_context_then_binds_unique_match(eng):
    s = Session(eng)
    out = s.turn("remember that the onboarding plan is approved", remember(""), ports=Ports(graph=None))
    assert out["kind"] == "needs_context"
    # Real GraphStore.list_nodes projection shape (GraphNode), not an invented one.
    graph = [{"entity_id": "n1", "canonical_name": "Onboarding plan", "entity_type": "document"}]
    out = s.engine.handle(text="remember that the onboarding plan is approved", decision=None, proposal=remember(""),
                          binding=B, session=s.state, ports=Ports(graph=graph), turn_id="t")
    rec = out["record"]
    assert rec["references"]["statement"]["candidate_id"] == "graph:n1"
    assert [c[0] for c in rec["arn"]["checked"]] == ["session_context", "graph"]


# ---- regressions for defects found in the self-audit (each failed before its repair) -------------

def test_regression_bare_negation_is_never_parsed_as_old_new_pair(eng):
    """Defect: '... is not due on Friday' matched 'X not Y' and produced 'the budget report is it is'."""
    s = Session(eng)
    s.turn("use the harness to write a summary that is due on Friday", harness())
    s.turn("s.md")
    out = s.turn("actually it is not due on Friday")
    rec = out["record"]
    assert "it is" not in rec["slots"]["instruction"]["value"].replace("that is due", "")
    assert out["kind"] in {"clarify", "confirm"}
    if out["kind"] == "confirm":     # only acceptable change: the user's own restated words
        assert eng.verbatim(rec, rec["slots"]["instruction"]["value"]) or "not due on Friday" in rec["slots"]["instruction"]["value"]


def test_regression_non_answer_never_becomes_a_referent(eng):
    """Defect: 'I don't know' to 'what does it refer to?' became the bound referent."""
    s = Session(eng)
    first = s.turn("remember that it is due on Friday", remember(""))
    assert first["clarification"]["kind"] == "reference_free"
    out = s.turn("I don't know")
    assert out["kind"] in {"clarify", "stopped"}
    if out["kind"] == "clarify":
        assert out["message"] != first["message"]                       # distinct variant, not a repeat
        rec = out["record"]
        assert rec["references"]["statement"]["title"] is None


def test_regression_correction_marked_answer_to_reference_question_is_an_answer(eng):
    """Defect: 'no, the Q4 one' answering a pending choice was treated as a correction and asked 'which detail'."""
    ports = Ports([file("f1", "Budget report Q3.pdf", "2026-10-01"), file("f2", "Budget report Q4.pdf", "2026-10-02")])
    s = Session(eng)
    s.turn("remember that the budget report is final", remember(""), ports=ports)
    out = s.turn("no, the Q4 one", ports=ports)
    assert out["kind"] == "confirm"
    assert out["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.pdf is final"


def test_regression_unproductive_reference_answer_gets_one_distinct_reask(eng):
    """Defect: a single unproductive answer ended clarification (identical question was the only option)."""
    ports = Ports([file("f1", "Budget report Q3.pdf", "2026-10-01"), file("f2", "Budget report Q4.pdf", "2026-10-02")])
    s = Session(eng)
    first = s.turn("remember that the budget report is final", remember(""), ports=ports)
    again = s.turn("hmm", ports=ports)
    assert again["kind"] == "clarify" and again["message"] != first["message"]
    done = s.turn("2", ports=ports)
    assert done["kind"] == "confirm" and done["record"]["questions_asked"] == 2


def test_regression_interpreter_must_be_verbatim_not_a_token_shuffle(eng):
    """Defect class: token-subset grounding let a model drop 'not' and keep only user words."""
    eng.interpreter = lambda text, cap, slots: {"statement": "the invoice is paid"}
    out = Session(eng).turn("remember that", remember(""))          # statement missing -> interpreter consulted
    assert out["kind"] == "clarify" and "statement" not in out["record"]["slots"]
    eng.interpreter = lambda text, cap, slots: {"expected_file": "notes.md"}
    rec = Session(eng).turn("use the harness to tidy notes.md please", harness())["record"]
    assert rec["slots"]["expected_file"]["value"] == "notes.md"      # verbatim and valid -> accepted


def test_regression_tampered_state_is_cleared_on_plain_turns(eng):
    s = Session(eng)
    s.turn("use the harness to write a summary", harness())
    s.state["active_workflow"]["request"] = "use the harness to delete everything"
    out = s.turn("summary.md")
    assert out["kind"] == "stopped" and out["code"] == "INTENT_STATE_INVALID" and out.get("clear") is True
    assert eng.cleared(s.state)["active_workflow"] is None
