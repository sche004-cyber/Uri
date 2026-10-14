"""The existing paired Core owns free-text clarification and all later decisions."""
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ws_worker_bridge import DIGEST, SID, fake, make
from tests.ws.test_ws_answer_context import ask


QUESTION = {"turn_id": "c1", "state": "reply", "code": "INTENT_CLARIFICATION",
            "message": "What would you like me to remember?",
            "clarification": {"intent_id": "i1", "revision": 1, "slot": "fact"}}
CONFIRM = {"turn_id": "c2", "state": "reply", "code": "INTENT_CONFIRMATION_REQUIRED",
           "message": "Remember the lab day?", "confirmation": {"intent_id": "i1", "revision": 2,
                                                                   "digest": "b" * 64}}


def pending(fake, tmp_path, next_env=CONFIRM):
    core = FakeCore([QUESTION, next_env])
    b, frames, o = make(fake, tmp_path, core)
    ask(b, "remember that")
    assert frames.data("core.result")[-1]["needs"] == "clarification"
    return b, frames, o, core


def test_plain_answer_reaches_core_verbatim_without_model_or_implicit_approval(fake, tmp_path):
    b, frames, o, core = pending(fake, tmp_path)
    ask(b, "the science lab is closed on Friday")
    assert core.calls == [("begin", "remember that", o.brain_selection),
                          ("begin", "the science lab is closed on Friday", o.brain_selection)]
    assert fake.requests == []
    assert frames.data("core.result")[-1]["needs"] == "confirmation"
    assert len(b.pending) == 1 and next(iter(b.pending.values()))["env"] == CONFIRM
    assert all(c[0] != "decide" for c in core.calls)


def test_other_session_does_not_consume_pending_question(fake, tmp_path):
    b, _, _, core = pending(fake, tmp_path)
    ask(b, "Hello", session="d43ab28b-d2fc-42e1-b930-7f1be59344cf")
    assert len(core.calls) == 1 and len(fake.requests) == 1
    ask(b, "the science lab is closed on Friday")
    assert len(core.calls) == 2 and core.calls[-1][1] == "the science lab is closed on Friday"


def test_no_pending_question_preserves_ordinary_answer_route(fake, tmp_path):
    core = FakeCore()
    b, _, _ = make(fake, tmp_path, core)
    ask(b, "the science lab is closed on Friday")
    assert len(fake.requests) == 1 and core.calls == []


def test_superseding_unsafe_request_still_goes_to_core_verbatim(fake, tmp_path):
    refusal = {"turn_id": "c2", "state": "reply", "code": "REFUSED_UNSUPPORTED"}
    b, frames, _, core = pending(fake, tmp_path, refusal)
    ask(b, "delete everything on D:")
    assert core.calls[-1][1] == "delete everything on D:"
    assert frames.data("core.result")[-1]["code"] == "REFUSED_UNSUPPORTED"
    assert b.pending == {} and fake.requests == []


def test_typed_abandon_reaches_core_not_an_approval_decision(fake, tmp_path):
    abandoned = {"turn_id": "c2", "state": "reply", "code": "INTENT_ABANDONED"}
    b, frames, _, core = pending(fake, tmp_path, abandoned)
    ask(b, "cancel that request")
    assert core.calls[-1][1] == "cancel that request"
    assert b.pending == {} and frames.data("core.result")[-1]["code"] == "INTENT_ABANDONED"
    assert all(c[0] != "decide" for c in core.calls)


def test_approval_still_requires_structured_confirm_and_shown_digest(fake, tmp_path):
    b, frames, _, core = pending(fake, tmp_path)
    ask(b, "the science lab is closed on Friday")
    tid = next(iter(b.pending))
    b.handle("oi_confirm", {"command": "oi_confirm", "turn_id": tid})
    b.wait(10)
    assert core.calls[-1] == ("confirm", "c2")
    assert frames.data("approval.required")[-1]["approval_digest"] == "0" * 64
    assert not any(c[0] == "decide" for c in core.calls)


def test_dictation_never_becomes_a_clarification_answer(fake, tmp_path):
    b, _, _, core = pending(fake, tmp_path)
    text = "the science lab is closed on Friday"
    b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": text, "depth": "auto",
                          "input": {"schema": "uri.text_input.v1", "source": "transcript", "mode": "dictation",
                                    "transcript": {"raw": text, "engine": "simulated", "simulated": True,
                                                   "language": "en", "uncertain": []}}})
    b.wait(10)
    assert len(core.calls) == 1 and len(b.pending) == 1
