"""C5 Brain transport through the REAL paired composition.

The Brain is a configurable ModelProvider row chosen explicitly by the user. These tests use
a scripted provider and the real OpenAI-compatible provider against a local stub HTTP endpoint
(no network, no account, no paid inference). They prove the transport is wired, proposes only,
cannot widen what the user said, and never falls back to another reasoning source.
"""
import http.server
import json
import threading

import pytest

from test_c5_intent_discovery import Stack, confirm_and_approve, two_reports, uid
from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT
from uri_core.core.model_providers.base import ModelProviderConfig, ModelResponse, ProviderUnavailableError
from uri_core.core.model_providers.openai_compatible_provider import OpenAICompatibleProvider
from uri_core.core.paired_brain import BrainProposer, brain_composition

ROW = ("server_local_model", "example-local-provider", "example-model")
BRAIN = {"kind": ROW[0], "provider": ROW[1], "model": ROW[2]}
NOBRAIN = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}


def contract(**overrides):
    base = {"goal": "remember a fact", "mode": "single_action", "capability": "remember_fact",
            "actions": [{"name": "remember_fact", "inputs": {}}], "clarification": None,
            "unsupported_reason": None, "requires_approval": False, "confidence": 0.9, "reason": "explicit request"}
    return {**base, **overrides}


class ScriptedBrain:
    def __init__(self, *replies, error=None):
        self.replies, self.error, self.calls = list(replies), error, []

    def complete(self, *, system, user, temperature=0.0, max_tokens=None, tools=None):
        self.calls.append({"system": system, "user": json.loads(user), "temperature": temperature})
        if self.error:
            raise self.error
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return ModelResponse(content=reply if isinstance(reply, str) else json.dumps(reply), model=ROW[2],
                             provider=ROW[1])


@pytest.fixture
def s():
    stack = Stack(18247)
    yield stack
    stack.close()


def brain_stack(s, brain):
    s.start(**brain_composition({ROW: brain}))
    return s


def say(s, session, text, reasoning=BRAIN):
    return s.runner.begin(text, session, reasoning)


def test_selected_brain_proposes_and_the_confirmed_intent_executes_from_the_users_words(s):
    brain = ScriptedBrain(contract())
    brain_stack(s, brain)
    session = two_reports(s)
    first = say(s, session, "remember that the budget report is due on Friday")
    assert brain.calls and brain.calls[0]["system"] == DECISION_CONTRACT_SYSTEM_PROMPT
    assert brain.calls[0]["user"]["user_text"] == "remember that the budget report is due on Friday"
    assert first["code"] == "INTENT_CLARIFICATION"
    awaiting = say(s, session, "the Q4 one")
    nxt = s.runner.confirm(session, BRAIN, awaiting)
    final = s.runner.decide("Confirm", session, BRAIN, nxt, True)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Budget report Q4.docx is due on Friday"]


def test_brain_cannot_inject_arguments_the_user_never_gave(s):
    brain = ScriptedBrain(contract(actions=[{"name": "remember_fact",
                                             "inputs": {"request_text": "remember that the budget is cancelled"}}]))
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "remember that my favourite colour is teal")
    assert out["state"] == "approval_required"
    assert out["approval_request"]["arguments"]["inputs"] == {"request_text": "remember that my favourite colour is teal"}
    final = s.runner.decide("x", session, BRAIN, out, True)
    assert s.memory(session) == ["my favourite colour is teal"]


@pytest.mark.parametrize("brain,code", [
    (ScriptedBrain(error=ProviderUnavailableError("down")), "SELECTED_MODEL_UNAVAILABLE"),
    (ScriptedBrain("not json at all"), "BRAIN_OUTPUT_INVALID"),
    (ScriptedBrain(contract(capability="delete_everything")), "BRAIN_OUTPUT_INVALID"),
    (ScriptedBrain({"mode": "single_action"}), "BRAIN_OUTPUT_INVALID"),
])
def test_failed_or_invalid_brain_never_falls_back(s, brain, code):
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "remember that my favourite colour is teal")   # deterministic rules WOULD act on this
    assert out["state"] == "failed" and out["code"] == code
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)


def test_unconfigured_brain_selection_is_refused_and_no_model_is_built_in(s):
    brain_stack(s, ScriptedBrain(contract()))
    session = uid()
    other = {"kind": "server_local_model", "provider": "example-local-provider", "model": "another-model"}
    out = say(s, session, "remember that my favourite colour is teal", other)
    assert out["state"] == "failed" and out["code"] == "SELECTED_MODEL_UNAVAILABLE"
    cloud = {"kind": "client_cloud_model", "provider": "example-local-provider", "model": "example-model"}
    assert say(s, session, "remember that my favourite colour is teal", cloud)["code"] == "CLIENT_PROVIDER_UNAVAILABLE"
    with pytest.raises(ValueError, match="BRAIN_ROW_INVALID"):
        BrainProposer({("client_external_harness", "claude_code", None): ScriptedBrain(contract())})
    from uri_core.app.paired_server import default_composition
    assert "proposer" not in default_composition()                      # no Brain unless composed explicitly


def test_deterministic_row_still_works_beside_a_configured_brain(s):
    brain = ScriptedBrain(contract())
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "remember that my favourite colour is teal", NOBRAIN)
    assert out["state"] == "approval_required" and brain.calls == []


class _Stub(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Stub.seen.append({"path": self.path, "body": body, "auth": self.headers.get("Authorization")})
        reply = json.dumps({"choices": [{"message": {"content": json.dumps(contract())}}],
                            "model": body["model"]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *a):
        pass


def test_real_openai_compatible_transport_against_a_local_stub(s):
    server = http.server.HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        provider = OpenAICompatibleProvider(ModelProviderConfig(base_url=f"http://127.0.0.1:{server.server_port}/v1",
                                                                model=ROW[2], timeout_seconds=10))
        brain_stack(s, provider)
        session = uid()
        out = say(s, session, "remember that my favourite colour is teal")
        assert out["state"] == "approval_required", out
        sent = _Stub.seen[-1]
        assert sent["path"] == "/v1/chat/completions" and sent["body"]["model"] == ROW[2] and sent["auth"] is None
        assert sent["body"]["messages"][0]["content"] == DECISION_CONTRACT_SYSTEM_PROMPT
        final = s.runner.decide("x", session, BRAIN, out, True)
        assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["my favourite colour is teal"]
    finally:
        server.shutdown()


@pytest.mark.parametrize("mode", ["multi_action", "single_action"])
def test_brain_cannot_reach_approval_without_a_confirmed_intent(s, mode):
    """Defect found in review: a multi_action proposal skipped intent discovery and put
    proposer-invented arguments ("the budget is cancelled") in front of the user for approval."""
    brain = ScriptedBrain(contract(mode=mode, actions=[{"name": "remember_fact",
                                                        "inputs": {"request_text": "remember that the budget is cancelled"}}]))
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "hello there")
    assert out["state"] == "reply" and out["code"] != "APPROVAL_REQUIRED"
    assert not any(p.endswith("/approval") for _, p in s.calls) and s.memory(session) == []


def test_brain_labelling_an_answer_as_a_new_request_does_not_discard_the_open_intent(s):
    """Defect found in review: 'the Q4 one' classified by the Brain as a new remember request replaced
    the pending clarification. Superseding needs the user's own words to form a new request."""
    brain_stack(s, ScriptedBrain(contract()))
    session = two_reports(s)
    first = say(s, session, "remember that the budget report is due on Friday")
    answered = say(s, session, "the Q4 one")
    assert answered["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert answered["confirmation"]["intent_id"] == first["clarification"]["intent_id"]
    assert answered["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.docx is due on Friday"


# ---- third review: interpreter and planner seams, bound to the same explicitly selected row ----------
from uri_core.core.paired_brain import INTERPRETER_PROMPT


class RoleBrain:
    """Scripted ModelProvider that answers by seam (proposer/planner share the decision prompt)."""
    def __init__(self, propose, interpret=None, plan=None, fail=()):
        # Default planner reply: a contract with no inputs, i.e. it does not restate the values (recompiled).
        self.answers = {"propose": propose, "interpret": interpret or {},
                        "plan": plan if plan is not None else contract(actions=[{"name": "remember_fact", "inputs": {}}])}
        self.fail, self.calls = set(fail), []

    def complete(self, *, system, user, temperature=0.0, max_tokens=None, tools=None):
        body = json.loads(user)
        role = "interpret" if system == INTERPRETER_PROMPT else ("plan" if "confirmed_intent" in body else "propose")
        self.calls.append(role)
        if role in self.fail:
            raise ProviderUnavailableError("down")
        answer = self.answers[role]
        return ModelResponse(content=json.dumps(answer(body) if callable(answer) else answer), model=ROW[2],
                             provider=ROW[1])


def test_interpreted_slot_needs_explicit_confirmation_even_when_verbatim(s):
    """Before: interpreter values were stored as source 'user_request', so a model's reading of WHICH words
    fill a slot could auto-confirm and go straight to approval."""
    brain = RoleBrain(contract(actions=[{"name": "remember_fact", "inputs": {}}]),
                      interpret={"statement": "the boiler service is booked for June"})
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "note for later: the boiler service is booked for June")
    assert brain.calls[:2] == ["propose", "interpret"]
    assert out["code"] == "INTENT_CONFIRMATION_REQUIRED" and out["state"] == "reply", out
    assert out["intent"]["sources"] == {"statement": "interpreted_from_request"}
    assert not any(p.endswith("/approval") for _, p in s.calls)
    nxt = s.runner.confirm(session, BRAIN, out)
    assert nxt["approval_request"]["arguments"]["inputs"] == {
        "request_text": "remember that the boiler service is booked for June"}
    assert s.runner.decide("Confirm", session, BRAIN, nxt, True)["code"] == "SETTLED_VERIFIED"
    assert s.memory(session) == ["the boiler service is booked for June"]


def test_interpreter_failure_is_reported_and_never_replaced(s):
    brain = RoleBrain(contract(actions=[{"name": "remember_fact", "inputs": {}}]), fail={"interpret"})
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "note for later: the boiler service is booked for June")
    assert out["state"] == "failed" and out["code"] == "SELECTED_MODEL_UNAVAILABLE", out
    assert brain.calls == ["propose", "interpret"]
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)


def test_planner_is_called_with_the_confirmed_intent_and_cannot_change_it(s):
    seen = []

    def plan(body):
        seen.append(body["confirmed_intent"])
        return contract(actions=[{"name": "remember_fact", "inputs": {"request_text": "remember that it is cancelled"}}])
    brain = RoleBrain(contract(actions=[{"name": "remember_fact", "inputs": {}}]), plan=plan)
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "remember that my favourite colour is teal")
    assert brain.calls == ["propose", "plan"] and seen[0]["values"] == {"statement": "my favourite colour is teal"}
    request = out["approval_request"]
    assert request["replanned"] is True and request["arguments"]["inputs"] == {
        "request_text": "remember that my favourite colour is teal"}
    assert s.runner.decide("x", session, BRAIN, out, True)["code"] == "SETTLED_VERIFIED"
    assert s.memory(session) == ["my favourite colour is teal"]


def test_planner_failure_keeps_the_confirmed_intent_and_runs_once_on_explicit_retry(s):
    brain = RoleBrain(contract(actions=[{"name": "remember_fact", "inputs": {}}]), fail={"plan"})
    brain_stack(s, brain)
    session = uid()
    out = say(s, session, "remember that my favourite colour is teal")
    assert out["state"] == "failed" and out["code"] == "SELECTED_MODEL_UNAVAILABLE", out
    assert s.session_state(session)["active_workflow"]["status"] == "CONFIRMED"
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)
    brain.fail.clear()
    reminder = say(s, session, "is that done?")
    assert reminder["code"] == "INTENT_CONFIRMED_NOT_EXECUTED"
    nxt = s.runner.confirm(session, BRAIN, reminder)
    assert s.runner.decide("x", session, BRAIN, nxt, True)["code"] == "SETTLED_VERIFIED"
    assert s.memory(session) == ["my favourite colour is teal"]


def test_deterministic_row_never_reaches_any_brain_seam(s):
    brain = RoleBrain(contract())
    brain_stack(s, brain)
    out = say(s, uid(), "remember that my favourite colour is teal", NOBRAIN)
    assert out["state"] == "approval_required" and brain.calls == []
