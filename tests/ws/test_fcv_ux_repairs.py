"""FCV-20261014 UX repairs in the integrated worker: no routing marker in shown text (FCV-06), memory wording
(FCV-08) and a completion message that says what was actually saved (UX-D)."""
import pytest

from uri_operational_intelligence import answer as A
from uri_operational_intelligence.worker_bridge import completion_outcome
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ws_worker_bridge import DIGEST, SID, approval_core, fake, make  # noqa: F401  (fixture)


def turn(bridge, text):
    r = bridge.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": text, "depth": "auto"})
    bridge.wait(10)
    return r


def shown(frames):
    return "".join(d["text"] for d in frames.data("answer.delta"))


@pytest.mark.parametrize("chunks", [
    [("answer", "If you ask, I reply with `<<ACTION>>` and the controller asks you.")],
    [("answer", "If you ask, I reply with `<<AC"), ("answer", "TION>>` and the controller asks you.")],
    [("answer", "If you ask, I reply with <"), ("answer", "<ACTION"), ("answer", ">> and the controller asks you.")],
])
def test_marker_mentioned_mid_answer_is_never_shown(fake, tmp_path, chunks):
    fake.scripts.append({"chunks": chunks, "finish": "stop"})
    b, frames, _ = make(fake, tmp_path, FakeCore())
    turn(b, "How do you handle actions?")
    text = shown(frames)
    assert "<<" not in text and "ACTION>>" not in text and "`" not in text
    assert text == "If you ask, I reply with an action request and the controller asks you."
    assert frames.data("answer.done")[-1]["status"] == "COMPLETE"


def test_a_reply_that_is_the_marker_still_reroutes_to_core(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "<<ACTION>>")], "finish": "stop"})
    core = FakeCore([{"turn_id": "c1", "state": "reply", "code": "CONVERSATION", "message": "Core handled it."}])
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Please tidy my desktop")
    assert "<<ACTION>>" not in shown(frames)
    assert any(c[0] == "begin" for c in core.calls)


def test_plain_streaming_is_unchanged_without_a_marker(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "Hel"), ("answer", "lo")], "finish": "stop", "delay": 0.05})
    b, frames, _ = make(fake, tmp_path, FakeCore())
    turn(b, "What is VRAM?")
    assert [d["text"] for d in frames.data("answer.delta")] == ["Hel", "lo"]


def test_memory_instruction_forbids_internal_names():
    system = A.build_messages("q", memory={"status": "available", "facts": []})[0]["content"]
    assert "never mention MEMORY_EVIDENCE" in system and "asked URI to remember" in system
    assert "conversation context, never describe it as remembered or saved" in system   # live FCV-R discovery


def test_verified_memory_save_names_the_fact_read_from_the_store(fake, tmp_path):
    core = approval_core()
    # The client store gains the fact only once Core has settled the approved request.
    store = lambda: ["the bus leaves at 7"] + (["the science lab is closed on Friday"]
                                               if ("decide", True) in core.calls else [])
    b, frames, _ = make(fake, tmp_path, core, memory=store)
    r = turn(b, "remember that the science lab is closed on Friday")
    b.handle("oi_decide", {"command": "oi_decide", "turn_id": r["turn_id"], "approve": True, "approval_digest": DIGEST})
    b.wait(10)
    out = frames.data("core.outcome")
    assert len(out) == 1 and out[0]["saved"] == ["the science lab is closed on Friday"]
    assert "“the science lab is closed on Friday”" in out[0]["summary"]
    assert "independently verified" not in out[0]["summary"]
    types = [e["type"] for e in frames.events if e["turn_id"] == r["turn_id"]]
    last = lambda t: len(types) - 1 - types[::-1].index(t)
    assert last("core.result") < last("core.outcome") < last("turn.finished")


def test_denial_or_unverified_settlement_gets_no_success_summary(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, approval_core(), memory=lambda: [])
    r = turn(b, "remember that x")
    b.handle("oi_decide", {"command": "oi_decide", "turn_id": r["turn_id"], "approve": False, "approval_digest": DIGEST})
    b.wait(10)
    assert frames.data("core.outcome") == []
    request = {"approval_request": {"capability_id": "remember_fact"}}
    for env in ({"code": "SETTLED_FAILED", "state": "failed"}, {"code": "SETTLED_EXECUTION_UNCERTAIN",
                                                                 "state": "execution_uncertain"},
                {"code": "SETTLED_VERIFIED", "state": "executing"}):
        assert completion_outcome(request, env, [], ["x"]) is None
    other = {"approval_request": {"capability_id": "external_harness_task"}}
    assert completion_outcome(other, {"code": "SETTLED_VERIFIED", "state": "reply"}, [], []) is None


def test_unreadable_store_never_invents_the_saved_text():
    request = {"approval_request": {"capability_id": "remember_fact"}}
    out = completion_outcome(request, {"code": "SETTLED_VERIFIED", "state": "reply"}, None, None)
    assert out["saved"] == [] and "“" not in out["summary"]


def confirmation_core():
    return FakeCore([{"turn_id": "c1", "state": "reply", "code": "INTENT_CONFIRMATION_REQUIRED", "message": "Confirm?",
                      "confirmation": {"intent_id": "i1", "revision": 2, "digest": "d" * 64,
                                       "arguments": {"request_text": "remember that the staff meeting is on Tuesday"}}}])


def test_no_on_a_confirmation_reaches_core_as_its_structured_abandon(fake, tmp_path):
    """FCVR-01 (live): "No" only dropped the card in the worker; Core kept the intent open and answered every later
    action request in the session with it. The decision now reaches Core (frozen TurnRunner.abandon)."""
    core = confirmation_core()
    b, frames, _ = make(fake, tmp_path, core)
    r = turn(b, "remember that the staff meeting is on Tuesday")
    assert frames.data("core.result")[-1]["needs"] == "confirmation"
    out = b.handle("oi_abandon", {"command": "oi_abandon", "turn_id": r["turn_id"]})
    b.wait(10)
    assert out == {"turn_id": r["turn_id"], "accepted": True}      # the outcome comes from Core (R1-07)
    assert ("abandon", "c1") in core.calls
    assert frames.data("core.result")[-1]["code"] == "INTENT_ABANDONED"
    assert frames.data("turn.finished")[-1]["status"] != "ok"          # an abandon is never reported as success
    with pytest.raises(Exception):
        b.handle("oi_confirm", {"command": "oi_confirm", "turn_id": r["turn_id"]})   # the card is gone


def test_no_on_an_approval_still_releases_it_as_a_denial(fake, tmp_path):
    core = approval_core()
    b, _, _ = make(fake, tmp_path, core)
    r = turn(b, "remember that x")
    assert b.handle("oi_abandon", {"command": "oi_abandon", "turn_id": r["turn_id"]}) == {"abandoned": True}
    assert ("decide", False) in core.calls and not any(c[0] == "abandon" for c in core.calls)


# ---- review round 1 ----------------------------------------------------------------------------------------------

def test_discovery_names_only_configured_actions_and_marks_others_unavailable():
    """R1-02: live discovery listed sending messages and opening apps as approval-gated actions."""
    system = A.build_messages("What can you do?", capability_ids={"remember_fact"})[0]["content"]
    assert "saving a fact you ask URI to remember" in system
    assert "never describe it as available with permission" in system
    assert "development tool" not in system                   # not configured here, so not offered


@pytest.mark.parametrize("text,memory,claim", [
    ("Use any information you asked URI to remember (if it has been saved).", None, False),
    ("These are the facts I have saved for you.", {"status": "available", "facts": ["x"]}, False),
    ("These are the facts I have saved for you.", {"status": "available", "facts": []}, True),
    ("I have saved the file to your desktop.", {"status": "available", "facts": ["x"]}, True),
    ("Done. I sent the email.", None, True),
    ("I have sent the email.", None, True),
    ("Once it has been saved you will see it.", None, False),
])
def test_action_claim_detection_ignores_conditionals_and_recorded_facts(text, memory, claim):
    assert A.claims_action(text, memory) is claim


@pytest.mark.parametrize("reply", ["`<<ACTION>>`", " `<<ACTION>>` ", "<<ACTION>>"])
def test_a_reply_that_is_only_the_backticked_marker_reroutes(fake, tmp_path, reply):
    """R1-05."""
    fake.scripts.append({"chunks": [("answer", reply)], "finish": "stop"})
    core = FakeCore([{"turn_id": "c1", "state": "reply", "code": "CONVERSATION", "message": "Core handled it."}])
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Please tidy my desktop")
    assert any(c[0] == "begin" for c in core.calls)
    assert "action request" not in shown(frames)


def test_unreadable_store_is_said_plainly():
    """R1-06: no claim that 'no new entry appeared' when the store could not be read."""
    request = {"approval_request": {"capability_id": "remember_fact"}}
    out = completion_outcome(request, {"code": "SETTLED_VERIFIED", "state": "reply"}, None, ["x"])
    assert "could not list the store" in out["summary"] and "No new entry" not in out["summary"]
