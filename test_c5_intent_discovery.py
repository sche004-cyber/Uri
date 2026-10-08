"""C5 Intent Discovery through the REAL paired loop: real server app (TestClient), real client
persistence (DPAPI credentials, consented commits), deterministic no-Brain proposer, salvaged
RAR/S1 reference binding, ARN cold-start retrieval, and server restarts. Synthetic data only."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from uri_core.app.paired_server import create_app
from uri_core.client_contracts import ReadQuery
from uri_core.client_runtime.manifest import ClientManifest, provision_client
from uri_core.client_runtime.persistence import ClientPersistence
from uri_core.client_runtime.turn_runner import TurnRunner, TurnError
from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, dpapi, provision

ROOT = Path(__file__).resolve().parent
NOBRAIN = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}


def uid():
    return str(uuid.uuid4())


class Stack:
    """A paired server that can be restarted (new process state) over the same durable roots."""

    def __init__(self, port):
        base = ROOT / "work/c1" / ("c5i_test_" + uuid.uuid4().hex)
        self.server_manifest = provision(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core")
        self.runtime = RuntimeIdentity(RuntimeManifest(self.server_manifest))
        self.cm = ClientManifest(provision_client(self.server_manifest, base / "client", uid(), ["remember_fact"]))
        self.cred = json.loads(dpapi((Path(self.cm.data["client_root"]) / "secure/uri-credentials.dpapi").read_bytes(), True))
        self.persistence = ClientPersistence(self.cm)
        self.calls = []
        self.start()

    def start(self, **composition):
        if getattr(self, "http", None):
            self.http.__exit__(None, None, None)
        policy = ReasoningSelectionPolicy({("server_local_model", "uri-deterministic", None)})
        self.app = create_app(self.runtime, composition={"policy": policy, **composition})
        self.http = TestClient(self.app).__enter__()
        session = self.http.post("/client/v1/session", json={"server_id": self.cred["server_id"], "client_id": self.cred["client_id"]},
            headers={"Authorization": "Bearer " + self.cred["principal_token"], "X-URI-Pairing": self.cred["pairing_token"]}).json()
        headers = {"Authorization": "Bearer " + session["token"], "X-URI-Client": self.cred["client_id"]}

        def call(method, path, body):
            self.calls.append((method, path))
            r = self.http.request(method, path, json=body, headers=headers)
            return r.status_code, r.json()
        self.runner = TurnRunner(self.cm, self.persistence, call, self.cm.data["server_public_key"], self.runtime.generation)
        return self

    @property
    def coordinator(self):
        return self.app.state.client_service.coordinator

    def close(self):
        self.http.__exit__(None, None, None)

    def read(self, session, store, method, *args):
        return self.persistence.snapshot(session, [ReadQuery(store=store, method=method, args=list(args))]).reads[0].result

    def memory(self, session):
        return [m["fact"]["value"] for m in self.read(session, "memory", "list_all")]

    def session_state(self, session):
        return self.read(session, "sessions", "get_session", session)

    def add_file(self, session, name):
        data = ("synthetic content of " + name).encode()
        self.runner._commit_consented(session, [("files", "list_for_session", [session], "save", {
            "filename": name, "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "session_id": session, "content": {"encoding": "base64", "data": base64.b64encode(data).decode(),
                                              "sha256": hashlib.sha256(data).hexdigest()}})])


@pytest.fixture
def s():
    stack = Stack(18241)
    yield stack
    stack.close()


def two_reports(s):
    session = uid()
    s.add_file(session, "Budget report Q3.docx")
    s.add_file(session, "Budget report Q4.docx")
    return session


def say(s, session, text):
    return s.runner.begin(text, session, NOBRAIN)


def confirm_and_approve(s, session, turn, approve=True):
    nxt = s.runner.confirm(session, NOBRAIN, turn)
    assert nxt["state"] == "approval_required", nxt
    return nxt, s.runner.decide("Confirm", session, NOBRAIN, nxt, approve)


# ---- scenarios 1-9, 16: ambiguity -> clarification -> answer -> confirm -> execute -> verify -> persist
def test_ambiguous_reference_is_clarified_confirmed_and_executed_exactly(s):
    session = two_reports(s)
    first = say(s, session, "remember that the budget report is due on Friday")
    assert first["code"] == "INTENT_CLARIFICATION" and first["state"] == "reply"
    clar = first["clarification"]
    assert clar["kind"] == "reference" and {o["label"] for o in clar["options"]} == {"Budget report Q3.docx", "Budget report Q4.docx"}
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)   # nothing executed
    pending = s.session_state(session)
    assert pending["active_workflow"]["status"] == "CLARIFYING" and pending["active_workflow_status"] == "waiting_for_input"

    answered = say(s, session, "the Q4 one")
    assert answered["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert answered["confirmation"]["arguments"] == {"request_text": "remember that Budget report Q4.docx is due on Friday"}
    assert answered["intent"]["references"]["statement"]["title"] == "Budget report Q4.docx"
    assert s.memory(session) == []

    approval, final = confirm_and_approve(s, session, answered)
    assert approval["approval_request"]["intent_digest"] == answered["confirmation"]["digest"]
    assert approval["approval_request"]["arguments"]["inputs"] == answered["confirmation"]["arguments"]
    assert approval["approval_request"]["replanned"] is False
    assert final["code"] == "SETTLED_VERIFIED"
    assert s.memory(session) == ["Budget report Q4.docx is due on Friday"]          # independent read-back
    after = s.session_state(session)
    assert after["active_workflow"] is None                                         # intent completed
    recent = after["current_facts"]["reference.recent_subject"]["data"]
    assert recent["value"] == "Budget report Q4.docx" and recent["status"] == "CONFIRMED"
    assert len(s.read(session, "history", "get_session", session)) == 3             # every turn persisted


# ---- scenarios 10, 11: same-session follow-up reuses the resolved referent; nothing re-asked
def test_followup_reuses_session_referent_without_asking(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    confirm_and_approve(s, session, say(s, session, "the Q4 one"))
    follow = say(s, session, "remember that it was approved by Priya")
    assert follow["code"] == "INTENT_CONFIRMATION_REQUIRED"                          # bound, not asked
    assert follow["intent"]["questions_asked"] == 0
    assert follow["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.docx was approved by Priya"
    _, final = confirm_and_approve(s, session, follow)
    assert final["code"] == "SETTLED_VERIFIED"
    assert "Budget report Q4.docx was approved by Priya" in s.memory(session)


# ---- scenarios 12, 13, 14 + false-CONFIRMED prevention
def test_correction_replaces_only_the_named_value_and_invalidates_old_confirmation(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    corrected = say(s, session, "actually it is due on Monday, not Friday")
    assert corrected["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert corrected["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.docx is due on Monday"
    assert corrected["intent"]["superseded"][0]["value"].endswith("Friday")
    assert corrected["confirmation"]["digest"] != awaiting["confirmation"]["digest"]
    # The obsolete confirmation can never authorize the corrected (or the old) request.
    stale = s.runner.confirm(session, NOBRAIN, awaiting)
    assert stale["code"] == "INTENT_DECISION_STALE" and stale["state"] == "reply"
    _, final = confirm_and_approve(s, session, corrected)
    assert final["code"] == "SETTLED_VERIFIED"
    assert s.memory(session) == ["Budget report Q4.docx is due on Monday"]              # obsolete value never stored


def test_correcting_a_confirmed_value_requires_reconfirmation(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    _, declined = confirm_and_approve(s, session, awaiting, approve=False)            # confirmed, approval declined
    assert declined["code"] == "APPROVAL_DENIED" and s.memory(session) == []
    assert s.session_state(session)["active_workflow"]["status"] == "CONFIRMED"
    corrected = say(s, session, "no, the Q3 one")
    assert corrected["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert corrected["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q3.docx is due on Friday"
    assert corrected["intent"]["status"] == "AWAITING_CONFIRMATION"
    _, final = confirm_and_approve(s, session, corrected)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Budget report Q3.docx is due on Friday"]


def test_text_never_confirms(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    say(s, session, "the Q4 one")
    again = say(s, session, "yes go ahead")
    assert again["code"] == "INTENT_CONFIRMATION_REQUIRED" and again["state"] == "reply"
    assert not any(p.endswith("/approval") for _, p in s.calls) and s.memory(session) == []


# ---- scenario 15: restart preserves answered information
def test_restart_preserves_pending_question_and_answers(s):
    session = two_reports(s)
    first = say(s, session, "remember that the budget report is due on Friday")
    s.start()                                                                         # server restart: binding rounds lost
    answered = say(s, session, "the Q4 one")
    assert answered["code"] == "INTENT_CONFIRMATION_REQUIRED"
    assert answered["intent"]["questions_asked"] == 1                                 # not asked again
    assert answered["confirmation"]["arguments"]["request_text"].endswith("Q4.docx is due on Friday")
    s.start()                                                                         # restart before confirming
    _, final = confirm_and_approve(s, session, answered)
    assert final["code"] == "SETTLED_VERIFIED"
    assert first["clarification"]["intent_id"] == answered["confirmation"]["intent_id"]


def test_tampered_client_record_cannot_forge_confirmation(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    state = s.session_state(session)
    state["active_workflow"]["slots"]["statement"]["value"] = "the budget report is cancelled"
    s.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session", {"session_id": session}, state)])
    out = s.runner.confirm(session, NOBRAIN, awaiting)
    assert out["code"] in {"INTENT_STATE_INVALID", "INTENT_DECISION_STALE"} and s.memory(session) == []


# ---- scenario 17 (+ ARN cold start): missing information is asked for, never invented
def test_unresolvable_reference_triggers_arn_widening_then_asks(s):
    session = uid()
    out = say(s, session, "remember that the travel form is due on Friday")
    assert any(p.endswith("/continue") for _, p in s.calls)                          # server-requested graph read
    assert out["code"] == "INTENT_CLARIFICATION" and out["clarification"]["kind"] == "reference_free"
    assert "couldn't find" in out["message"] and s.memory(session) == []
    arn = s.session_state(session)["active_workflow"]["arn"]
    assert [c[0] for c in arn["checked"]] == ["session_context", "graph"]             # widened once, recorded
    answered = say(s, session, "the HR travel form")
    assert answered["confirmation"]["arguments"]["request_text"] == "remember that the HR travel form is due on Friday"
    assert answered["intent"]["references"]["statement"]["state"] == "USER_SUPPLIED"


def test_pronoun_without_any_session_referent_is_asked_not_guessed(s):
    session = uid()
    out = say(s, session, "remember that it is due on Friday")
    assert out["code"] == "INTENT_CLARIFICATION" and out["clarification"]["kind"] == "reference_free"
    assert not any(p.endswith("/continue") for _, p in s.calls)                      # no meaningless graph search for "it"


def test_harness_request_without_output_file_is_asked_not_invented():
    from uri_core.core.paired_coordinator import deterministic_proposer
    from types import SimpleNamespace
    directory = SimpleNamespace(describe=lambda cap: {"actions": {"run": {}}} if cap == "external_harness_task" else None)
    proposal = deterministic_proposer({"directory": directory}, SimpleNamespace(text="use the harness to write a summary"), None)
    assert proposal["actions"][0]["inputs"] == {"instruction": "write a summary"}    # no "out.txt"
    named = deterministic_proposer({"directory": directory}, SimpleNamespace(text="use the harness to write a summary into notes.md"), None)
    assert named["actions"][0]["inputs"]["expected_file"] == "notes.md"
    claude = deterministic_proposer({"directory": directory}, SimpleNamespace(text="use claude to write a summary"), None)
    assert claude["mode"] == "conversation"                                          # provider names are not Core vocabulary


# ---- scenario 18: conflicting downstream proposal rejected and replanned from the confirmed intent
def test_conflicting_downstream_proposal_is_rejected_and_replanned(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    seen = []

    def drifting_planner(prepared, request, selection, intent):
        seen.append(intent["digest"])
        return {"goal": "x", "mode": "single_action", "capability": "remember_fact", "clarification": None,
                "unsupported_reason": None, "requires_approval": False, "confidence": 0.9, "reason": "drift",
                "actions": [{"name": "remember", "inputs": {"request_text": "remember that Budget report Q3.docx is due on Thursday"}}]}
    s.coordinator.planner = drifting_planner
    approval = s.runner.confirm(session, NOBRAIN, awaiting)
    req = approval["approval_request"]
    assert seen and req["replanned"] is True and "input_changed:request_text" in req["rejected_proposal"]["conflicts"]
    assert req["arguments"]["inputs"]["request_text"] == "remember that Budget report Q4.docx is due on Friday"
    final = s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Budget report Q4.docx is due on Friday"]


# ---- scenario 19: unauthorized request is blocked before any clarification
def test_ungranted_capability_is_refused_without_interviewing_the_user(s):
    session = two_reports(s)
    s.app.state.client_service.pairings.revoke(s.cm.data["client_id"])
    with pytest.raises(TurnError):
        say(s, session, "remember that the budget report is due on Friday")
    assert s.memory(session) == []


# ---- scenario 20: unavailable executor preserves the confirmed intent for a later explicit retry
def test_executor_failure_preserves_confirmed_intent(s, monkeypatch):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    monkeypatch.setattr(TurnRunner, "_run_local", lambda self, *a, **k: ("failed", [], "NOT_STARTED:NO_LOCAL_EXECUTOR"))
    _, failed = confirm_and_approve(s, session, awaiting)
    assert failed["code"] == "SETTLED_FAILED" and s.memory(session) == []
    record = s.session_state(session)["active_workflow"]
    assert record["status"] == "CONFIRMED" and record["slots"]["statement"]["value"] == "the budget report is due on Friday"
    monkeypatch.undo()
    reminder = say(s, session, "what about that request?")
    assert reminder["code"] == "INTENT_CONFIRMED_NOT_EXECUTED"
    retry = s.runner.confirm(session, NOBRAIN, reminder)
    final = s.runner.decide("Confirm", session, NOBRAIN, retry, True)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["Budget report Q4.docx is due on Friday"]


# ---- scenario 21: uncertain execution is never blindly repeated
def test_uncertain_execution_is_not_repeated_by_reconfirming(s, monkeypatch):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    approval = s.runner.confirm(session, NOBRAIN, awaiting)

    def crash(self, *a, **k):
        raise RuntimeError("executor crashed after claim")
    monkeypatch.setattr(TurnRunner, "_run_local", crash)
    with pytest.raises(RuntimeError):
        s.runner.decide("Confirm", session, NOBRAIN, approval, True)
    monkeypatch.undo()
    s.start()                                                                         # restart reconciles the claimed ticket
    before = len(s.calls)
    again = s.runner.confirm(session, NOBRAIN, awaiting)
    assert again["state"] == "reply" and again["code"] in {"INTENT_EXECUTION_UNCERTAIN", "INTENT_DECISION_STALE",
                                                            "INTENT_CONFIRMED_NOT_EXECUTED"}
    assert again["code"] == "INTENT_EXECUTION_UNCERTAIN"
    assert not any(p.endswith(("/approval", "/claim")) for _, p in s.calls[before:])  # nothing re-dispatched
    assert s.memory(session) == []


# ---- clarification safeguards
def test_no_progress_answers_stop_without_guessing(s):
    session = uid()
    s.add_file(session, "Budget report Q3.docx")
    s.add_file(session, "Budget report Q4.docx")
    s.add_file(session, "Budget report Q2.docx")
    say(s, session, "remember that the budget report is due on Friday")
    a = say(s, session, "hmm not sure")
    b = say(s, session, "whatever")
    c = say(s, session, "still not sure")
    codes = [x["code"] for x in (a, b, c)]
    assert "CLARIFICATION_NO_PROGRESS" in codes or "CLARIFICATION_REPEAT_BLOCKED" in codes
    assert s.memory(session) == [] and not any(p.endswith("/approval") for _, p in s.calls)
    texts = [x["message"] for x in (a, b, c) if x["code"] == "INTENT_CLARIFICATION"]
    assert len(texts) == len(set(texts))                                              # no question reissued


def test_new_request_while_pending_supersedes_old_intent(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    fresh = say(s, session, "remember that my favourite colour is teal")
    # The pending reference question was answered with a new explicit request: old intent abandoned,
    # the new complete request is auto-confirmed and goes straight to approval.
    assert fresh["state"] == "approval_required" and fresh["approval_request"]["intent_digest"]
    final = s.runner.decide("x", session, NOBRAIN, fresh, True)
    assert final["code"] == "SETTLED_VERIFIED" and s.memory(session) == ["my favourite colour is teal"]


def test_replayed_older_signed_record_cannot_resurrect_superseded_meaning(s):
    """Regression: a validly signed OLDER revision (client rollback) must not reinstate 'Friday'."""
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    awaiting = say(s, session, "the Q4 one")
    old_state = s.session_state(session)                               # signed revision with Friday
    say(s, session, "actually it is due on Monday, not Friday")         # newer revision exists server-side
    s.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session",
                                          {"session_id": session}, old_state)])
    out = s.runner.confirm(session, NOBRAIN, awaiting)
    assert out["code"] == "INTENT_STATE_STALE" and out["state"] == "reply"
    assert s.session_state(session)["active_workflow"] is None and s.memory(session) == []
