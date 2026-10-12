"""Bridge behaviour against the real supervisor with SYNTHETIC tickets (no server): executor gates, outcome mapping,
retry/authority discipline, replay, misleading streams, injection attempts."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

from phase2b.conftest import CLAUDE, CODEX, fake_binding, fake_registry
from uri_core.client_runtime.process_tree import process_alive
from uri_supervisor_bridge.bridge import NOT_STARTED, SupervisorBridge


def work_for(authority, reasoning=CLAUDE, **kw):
    signed, request, now = authority.issue(**kw)
    return authority.verify(signed, request, reasoning, now=now), signed, request, now


def task_rows(bridge, tid):
    L = bridge.L
    return (L.task(tid), L.q("SELECT * FROM attempt WHERE task_id=? ORDER BY attempt_id", (tid,)),
            L.q("SELECT * FROM recovery_decision WHERE task_id=? ORDER BY decision_id", (tid,)))


def test_honest_run_is_verified_only_through_uri_postcondition(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    work, *_ = work_for(authority)
    outcome, evidence, failure = bridge.execute(work)
    assert (outcome, failure) == ("verified", None)
    ev = evidence[0]
    assert ev["check"] == "harness_output_check" and ev["matched"] is True and ev["argument_digest"] == work.ticket.argument_digest
    assert ev["verifier_id"] == work.ticket.verifier_id and ev["basis"] == "uri_supervisor_postcondition_verified"
    t, attempts, decisions = task_rows(bridge, work.task_id)
    assert t["state"] == "COMPLETE" and len(attempts) == 1 and decisions[-1]["outcome"] == "COMPLETE"
    # the completion record cites URI-verified postcondition evidence, never the executor's claim
    comp = bridge.L.q1("SELECT * FROM completion_record WHERE task_id=?", (work.task_id,))
    assert comp["kind"] == "verified"
    pcr = bridge.L.q1("SELECT e.source, e.kind FROM postcondition_result r JOIN evidence e ON e.evidence_id=r.evidence_id "
                      "WHERE r.task_id=? ORDER BY r.result_id DESC LIMIT 1", (work.task_id,))
    assert (pcr["source"], pcr["kind"]) == ("uri_verified", "postcondition_check")
    # evidence is public: no path keys, no absolute paths
    from uri_core.client_contracts import public_projection
    public_projection(evidence)
    # authorization scope derived from the ticket and bound to it
    auth = bridge.L.q1("SELECT * FROM authorization WHERE task_id=?", (work.task_id,))
    scope = json.loads(auth["scope_json"])
    assert scope["allowed_executors"] == ["claude_code"] and scope["ticket_digest"] == work.ticket_digest
    assert scope["approval_digest"] == work.ticket.approval_digest and auth["valid_until_us"] == work.deadline_us
    assert auth["issued_by"] == "uri_core.execution_ticket"


def test_replaying_the_same_ticket_never_creates_a_second_task_or_effect(bridge, authority, monkeypatch, tmp_path):
    counter = tmp_path / "counter.txt"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    monkeypatch.setenv("URI_FAKE_COUNTER", str(counter))
    work, *_ = work_for(authority)
    assert bridge.execute(work)[0] == "verified"
    again = bridge.execute(work)
    assert again == ("execution_uncertain", [], "DUPLICATE_OPERATION")
    assert counter.read_text().count("effect") == 1
    assert bridge.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (work.task_id,))[0] == 1


@pytest.mark.parametrize("scenario,expect,ledger_state", [
    ("false_claim", "failed", "FAILED"),                 # claim without effect: absence proven, retried once, budget out
    ("done_ok_exit3", "failed", "FAILED"),               # success-shaped claim, exit 3, nothing written
    ("success_shaped_string", "failed", "FAILED"),       # ok:"true" is not a success claim
    ("text_success_failed_command", "failed", "FAILED"), # free text "Success!" is never parsed for facts
    ("hang", "failed", "FAILED"),                        # inactivity kill, nothing written
])
def test_misleading_or_empty_streams_are_never_verified(bridge, authority, monkeypatch, scenario, expect, ledger_state):
    monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
    work, *_ = work_for(authority)
    outcome, evidence, failure = bridge.execute(work)
    assert outcome == expect and evidence == [] and failure and not failure.startswith(NOT_STARTED), (outcome, failure)
    t, attempts, decisions = task_rows(bridge, work.task_id)
    assert t["state"] == ledger_state and all(d["outcome"] != "COMPLETE" for d in decisions)
    assert len(attempts) == bridge.max_attempts            # retried under the SAME authorization, then budget exhausted
    auth_ids = {a["auth_id"] for a in bridge.L.q("SELECT auth_id FROM admission WHERE task_id=?", (work.task_id,))}
    assert len(auth_ids) == 1                              # retry obtained no new authority
    assert bridge.L.q1("SELECT COUNT(*) FROM completion_record WHERE task_id=?", (work.task_id,))[0] == 0


@pytest.mark.parametrize("scenario", ["empty_output", "wrong_file", "partial_then_die"])
def test_partial_or_wrong_effects_are_uncertain_not_retried(bridge, authority, monkeypatch, scenario):
    monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
    work, *_ = work_for(authority)
    outcome, evidence, failure = bridge.execute(work)
    assert outcome == "execution_uncertain" and failure.startswith("SUPERVISOR_NEEDS_USER"), (outcome, failure)
    t, attempts, _ = task_rows(bridge, work.task_id)
    assert t["state"] == "NEEDS_USER" and len(attempts) == 1          # workspace changed: never auto-retried


def test_quota_before_any_activity_is_a_clean_pause_but_after_activity_is_uncertain(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    work, *_ = work_for(authority)
    assert bridge.execute(work) == ("quota", [], "QUOTA")
    t, attempts, decisions = task_rows(bridge, work.task_id)
    assert decisions[-1]["reason_code"] == "PROVIDER_QUOTA_EXHAUSTED" and t["state"] == "FAILED"   # closed for this ticket
    assert bridge.L.q1("SELECT breaker_state FROM resource_pool WHERE name='quota_claude_code'")[0] == "open"
    assert bridge.L.q1("SELECT breaker_state FROM resource_pool WHERE name='quota_codex_cli'")[0] == "closed"
    for sc in ("quota_after_write", "quota_after_tool_no_effect"):
        monkeypatch.setenv("URI_FAKE_SCENARIO", sc)
        work2, *_ = work_for(authority, reasoning=CODEX)
        outcome, _, failure = bridge.execute(work2)
        assert outcome != "quota", (sc, outcome, failure)
        assert outcome in ("execution_uncertain", "failed")


def test_quota_on_one_provider_does_not_block_the_users_explicit_choice_of_another(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    work, *_ = work_for(authority)
    assert bridge.execute(work)[0] == "quota"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    work2, *_ = work_for(authority, reasoning=CODEX)
    assert bridge.execute(work2)[0] == "verified"
    # ...and the quota-hit provider is NOT silently retried: its breaker refuses admission
    work3, *_ = work_for(authority)
    outcome, _, failure = bridge.execute(work3)
    assert outcome == "failed" and failure.startswith(NOT_STARTED + "EXECUTOR_NOT_ADMITTED"), failure
    assert bridge.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (work3.task_id,))[0] == 0


def test_executor_selection_cannot_widen_to_an_unregistered_or_unqualified_executor(tmp_path, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    # registry says codex is usable, but the supervisor has no codex executor: refused before any task exists
    b = SupervisorBridge(tmp_path / "c1", registry=fake_registry("claude_code", "codex_cli"),
                         executors={"claude_code": fake_binding("claude_code")})
    try:
        work, *_ = work_for(authority, reasoning=CODEX)
        assert b.execute(work) == ("failed", [], NOT_STARTED + "EXECUTOR_NOT_REGISTERED")
        assert b.L.task(work.task_id) is None
        # supervisor has claude but the Phase 1 registry does not consider it usable: refused, no task
        b.registry.qualified.pop("claude_code")
        work, *_ = work_for(authority)
        outcome, _, failure = b.execute(work)
        assert outcome == "failed" and failure == NOT_STARTED + "HARNESS_HARNESS_NOT_USABLE" and b.L.task(work.task_id) is None
    finally:
        b.close()
    b = SupervisorBridge(tmp_path / "c2", registry=None, executors={"claude_code": fake_binding("claude_code")})
    try:
        work, *_ = work_for(authority)
        assert b.execute(work) == ("failed", [], NOT_STARTED + "NO_HARNESS_REGISTRY")
    finally:
        b.close()


def test_executor_binding_must_match_provider_id(tmp_path):
    from uri_supervisor_bridge.authority import BridgeRefused
    with pytest.raises(BridgeRefused, match="EXECUTOR_BINDING_ID_MISMATCH"):
        SupervisorBridge(tmp_path / "c", registry=None, executors={"codex_cli": fake_binding("claude_code")})


def test_admission_is_restricted_to_the_ticket_task_even_if_a_higher_priority_task_waits(bridge, authority, monkeypatch):
    """A queued foreign task (higher priority, valid authorization) must never be run by a ticket that is not its own."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    sup = bridge.sup
    sup.submit_task("foreign", "someone", {"x": 1}, authorization={"scope": {}}, priority=100,
                    effects=[{"op_class": "read", "operation": "r"}], postconditions=[{"kind": "terminal_success"}],
                    requirements={"capabilities": ["harness_task"]})
    work, *_ = work_for(authority)
    assert bridge.execute(work)[0] == "verified"
    assert bridge.L.task("foreign")["state"] == "QUEUED"
    assert bridge.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id='foreign'")[0] == 0


def test_settled_ticket_leaves_no_admittable_work(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "false_claim")
    work, *_ = work_for(authority)
    bridge.execute(work)
    # nothing for this task can be admitted again: authorization closed, state terminal
    assert bridge.sup.admit_next(only_task_id=work.task_id) is None
    auth = bridge.L.q1("SELECT * FROM authorization WHERE task_id=? AND superseded_at_us IS NULL", (work.task_id,))
    assert auth["issued_by"] == "uri_supervisor_bridge" and auth["valid_until_us"] <= bridge.L.now_us()
    assert bridge.L.task(work.task_id)["state"] in ("FAILED", "UNCERTAIN", "NEEDS_USER")


def test_user_retry_decision_on_uncertain_task_cannot_run_without_new_authority(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "partial_then_die")
    work, *_ = work_for(authority)
    assert bridge.execute(work)[0] == "execution_uncertain"
    assert bridge.L.task(work.task_id)["state"] == "NEEDS_USER"
    bridge.sup.record_user_decision(work.task_id, "retry", work.principal, "user says retry")   # Phase 2A decision API
    assert bridge.L.task(work.task_id)["state"] == "RETRY_SAFE"
    assert bridge.sup.admit_next(only_task_id=work.task_id) is None            # no valid authorization: nothing runs
    assert bridge.sup.admit_next() is None


def test_executor_supplied_session_id_cannot_inject_argv(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "evil_session")
    work, *_ = work_for(authority)
    bridge.execute(work)
    rows = bridge.L.q("SELECT session_id, argv_sha256 FROM attempt WHERE task_id=?", (work.task_id,))
    assert rows and all(r["session_id"] is None for r in rows)
    assert bridge.L.q1("SELECT COUNT(*) FROM recovery_decision WHERE task_id=? AND action='RESUME_SESSION'", (work.task_id,))[0] == 0


def test_grandchild_is_killed_with_the_attempt(bridge, authority, monkeypatch, tmp_path):
    pidfile = tmp_path / "gc.pid"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "grandchild")
    monkeypatch.setenv("URI_FAKE_PIDFILE", str(pidfile))
    work, *_ = work_for(authority)
    outcome, _, failure = bridge.execute(work)
    assert outcome == "failed"
    assert pidfile.exists() and not process_alive(int(pidfile.read_text()))


def test_effect_outside_the_declared_workspace_is_not_detected_by_absence_proof(bridge, authority, monkeypatch, tmp_path):
    """Documented limitation (Phase 2A K): absence proofs cover declared paths only. This test pins the honest
    behaviour: the task still VERIFIES on its declared postcondition; the escape is invisible to the ledger.
    Containment of writes outside the workspace is the executor sandbox's job, not the bridge's claim."""
    escape = tmp_path / "escaped.txt"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "escape_write")
    monkeypatch.setenv("URI_FAKE_ESCAPE_TARGET", str(escape))
    work, *_ = work_for(authority)
    assert bridge.execute(work)[0] == "verified"
    assert escape.exists()      # the fake executor had no sandbox; a real one is bounded only by its own flags


def test_instruction_text_never_enters_argv_or_the_ledger_request(bridge, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    marker = "ZZ-SECRET-INSTRUCTION-MARKER-" + os.urandom(4).hex()
    work, *_ = work_for(authority, instruction="write a greeting " + marker)
    assert bridge.execute(work)[0] == "verified"
    t = bridge.L.task(work.task_id)
    assert marker not in t["request_json"] and marker not in t["requirements_json"]
    # argv is only recorded as a hash; the executor got the instruction on stdin (it parsed the file name from it)
    assert (bridge.root / "workspace" / "results").rglob("out.txt")


def test_deadline_passed_before_admission_runs_nothing(bridge, authority):
    signed, request, now = authority.issue(deadline_s=61)
    work = authority.verify(signed, request, CLAUDE, now=now)
    real = bridge.clock
    bridge.clock = lambda: now + 100            # the ticket's deadline has passed by the time the bridge runs
    try:
        outcome, _, failure = bridge.execute(work)
    finally:
        bridge.clock = real
    assert outcome == "failed" and failure.startswith(NOT_STARTED + "EXECUTOR_NOT_ADMITTED"), failure
    assert bridge.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (work.task_id,))[0] == 0
    assert bridge.L.task(work.task_id)["state"] == "FAILED"


def test_supervisor_runs_only_the_binary_phase1_qualified(tmp_path, authority, monkeypatch):
    """The Phase 1 registry qualifies ONE executable per provider. A supervisor binding pointing at a different binary
    would run unqualified code under a qualified name: refused before any task exists."""
    import shutil
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    other = shutil.copyfile(sys.executable, tmp_path / "other-python.exe")
    from dataclasses import replace as dc_replace
    b = SupervisorBridge(tmp_path / "c", registry=fake_registry("claude_code"),
                         executors={"claude_code": dc_replace(fake_binding("claude_code"), resolved_executable=str(other))})
    try:
        work, *_ = work_for(authority)
        outcome, _, failure = b.execute(work)
        assert outcome == "failed" and failure == NOT_STARTED + "EXECUTOR_BINARY_MISMATCH", (outcome, failure)
        assert b.L.task(work.task_id) is None
    finally:
        b.close()


def test_binding_without_explicit_executable_uses_the_qualified_one(tmp_path, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    from dataclasses import replace as dc_replace
    b = SupervisorBridge(tmp_path / "c", registry=fake_registry("claude_code"),
                         executors={"claude_code": dc_replace(fake_binding("claude_code"), resolved_executable=None)})
    try:
        work, *_ = work_for(authority)
        assert b.execute(work)[0] == "verified"
    finally:
        b.close()
