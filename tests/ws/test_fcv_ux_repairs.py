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
    assert text == "If you ask, I reply with a hidden routing signal and the controller asks you."
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


@pytest.mark.parametrize("text,claim", [
    ("Use any information you asked URI to remember (if it has been saved).", False),
    ("These are the facts I have saved for you.", True),          # R4-01: no memory exemption any more
    ("I have saved the file to your desktop.", True),
    ("Done. I sent the email.", True),
    ("I have sent the email.", True),
    ("Once it has been saved you will see it.", False),
])
def test_action_claim_detection_ignores_only_governing_conditionals(text, claim):
    assert A.claims_action(text) is claim


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


# ---- review round 2 ----------------------------------------------------------------------------------------------

FACTS = {"status": "available", "facts": ["the science lab is closed on Friday"]}


@pytest.mark.parametrize("text", [
    "Once again, I have deleted the files.",
    "After checking your inbox, I have sent the email to Sam.",
    "When you asked, I have deleted the old files.",
    "I have remembered your locker number is 42.",
    "I have saved this new information to your memory.",
    "If you want, I have saved it already.",
])
def test_real_action_claims_are_still_flagged(text):
    """R2-01: the round-1 exemptions must not hide genuine 'I did it' claims (canonical flags every one)."""
    assert A.claims_action(text) is True


def test_a_fabricated_memory_save_gets_the_correction(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "Done! I have saved this new information to your memory.")], "finish": "stop"})
    b, frames, _ = make(fake, tmp_path, FakeCore(), memory=lambda: ["the science lab is closed on Friday"])
    turn(b, "What day is it?")
    done = frames.data("answer.done")[-1]
    assert "UNVERIFIED_ACTION_CLAIM" in done["flags"]


# ---- review round 3 ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Once again the files have been deleted.",
    "Once more the email has been sent to Sam.",
    "The new details I have saved: your locker is 42.",
    "Good news: the information I have stored now includes your locker number 42.",
])
def test_round3_claims_canonical_flags_stay_flagged(text):
    """R3-01: no exemption may pass a sentence canonical flags."""
    assert A.claims_action(text) is True


# ---- review round 4 ----------------------------------------------------------------------------------------------

R4_CLAIMS = [
    "The new facts I have saved: your locker is 42.",
    "The facts I have saved now include your locker number 42.",
    "Facts I have stored today: your locker is 42.",
    "The facts I have saved for you: the bus leaves at 7 am.",
    "Once upon request the files have been deleted.",
]


@pytest.mark.parametrize("text", R4_CLAIMS)
def test_round4_every_sentence_canonical_flags_is_flagged(text):
    """R4-01: the memory-reference exemption is gone, so the candidate flags exactly what canonical flags here."""
    assert A._CLAIM.search(text)            # canonical's rule (unchanged pattern) flags each one
    assert A.claims_action(text) is True


@pytest.mark.parametrize("text", [
    "You asked URI to remember: the bus leaves at 7 am.",
    "You asked URI to remember two things: the bus leaves at 7 am and the lab is closed on Friday.",
    "URI has nothing saved about your locker.",
    "Your saved notes disagree: “the bus leaves at 7 am” and “the bus leaves at 8 am”.",
    "Use any information you asked URI to remember (if it has been saved).",
])
def test_round4_recall_phrasing_the_memory_instruction_asks_for_is_not_a_claim(text):
    assert A.claims_action(text) is False


def test_memory_instruction_names_the_recall_phrasing():
    system = A.build_messages("q", memory=FACTS)[0]["content"]
    assert "You asked URI to remember: ...\"" in system
    assert "never write that you saved, stored or remembered them" in system


@pytest.mark.parametrize("reply", ["The facts I have saved for you: the science lab is closed on Friday.",
                                   "The new facts I have saved: your locker is 42."])
def test_a_recall_answer_with_a_save_claim_gets_the_correction(fake, tmp_path, reply):
    fake.scripts.append({"chunks": [("answer", reply)], "finish": "stop"})
    b, frames, _ = make(fake, tmp_path, FakeCore(), memory=lambda: ["the science lab is closed on Friday"])
    turn(b, "What did I ask you to remember?")
    done = frames.data("answer.done")[-1]
    assert "UNVERIFIED_ACTION_CLAIM" in done["flags"]
    assert shown(frames).endswith(A.CLAIM_CORRECTION)


def test_a_plain_recall_answer_is_shown_unchanged(fake, tmp_path):
    reply = "You asked URI to remember: the science lab is closed on Friday."
    fake.scripts.append({"chunks": [("answer", reply)], "finish": "stop"})
    b, frames, _ = make(fake, tmp_path, FakeCore(), memory=lambda: ["the science lab is closed on Friday"])
    turn(b, "When is the science lab closed?")
    assert shown(frames) == reply
    assert "UNVERIFIED_ACTION_CLAIM" not in frames.data("answer.done")[-1]["flags"]


def save_claim(fake):
    fake.scripts.append({"chunks": [("answer", "Done! I have saved that to your memory.")], "finish": "stop"})


def test_action_states_only_a_verified_completion_reports_success(fake, tmp_path):
    """R4-01 / owner task: completed, proposed, failed and declined actions. Success is reported only from Core's
    verified settlement plus the store read-back; an answer-channel save claim is always corrected."""
    # proposed: Core asks for approval; nothing is reported as saved.
    core = approval_core()
    b, frames, _ = make(fake, tmp_path, core, memory=lambda: [])
    r = turn(b, "remember that the science lab is closed on Friday")
    assert frames.data("core.outcome") == []
    assert frames.data("turn.finished") == [] or frames.data("turn.finished")[-1]["status"] != "ok"
    # declined: the user says No; still nothing reported as saved.
    b.handle("oi_decide", {"command": "oi_decide", "turn_id": r["turn_id"], "approve": False,
                           "approval_digest": DIGEST})
    b.wait(10)
    assert frames.data("core.outcome") == []
    # failed or uncertain settlement: no success summary.
    request = {"approval_request": {"capability_id": "remember_fact"}}
    for env in ({"code": "SETTLED_FAILED", "state": "failed"},
                {"code": "SETTLED_EXECUTION_UNCERTAIN", "state": "execution_uncertain"}):
        assert completion_outcome(request, env, [], ["x"]) is None
    # completed: only the verified settlement names the fact, read from the store.
    out = completion_outcome(request, {"code": "SETTLED_VERIFIED", "state": "reply"}, [], ["x"])
    assert out["saved"] == ["x"] and out["read_back"] is True
    # an answer-channel claim with no executed action is corrected in every case.
    save_claim(fake)
    b2, frames2, _ = make(fake, tmp_path, FakeCore(), memory=lambda: ["x"])
    turn(b2, "Did it work?")
    assert "UNVERIFIED_ACTION_CLAIM" in frames2.data("answer.done")[-1]["flags"]
