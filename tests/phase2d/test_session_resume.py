"""F-C1 (Phase 2D): a harness session/thread id is resumable execution metadata, never URI authority.

Decision implemented: URI persists the executor-reported session id ONLY on the attempt row of the task that
produced it (Phase 2A ledger). It is reused for exactly one purpose, a RESUME_SESSION retry of the SAME task under
the SAME authorization, SAME executor registration and SAME model, admitted through the normal admission path
(authorization validity re-checked). Anything else (other task, re-registered executor, revoked/expired authority,
settled task, supervisor restart) runs fresh or does not run at all. A failed resume (stale/invalid session) is an
ordinary terminal failure: governed retry path, never COMPLETE from a claim. SYNTHETIC executor (fake harness).
"""
import hashlib
import json
import sys
from dataclasses import replace

import pytest

from phase2b.conftest import CLAUDE, FAKE, fake_binding, fake_registry
from uri_supervisor.executors import GENERIC_NDJSON
from uri_supervisor.supervisor import Supervisor, sha
from uri_supervisor_bridge.bridge import SupervisorBridge

RESUME_OK = ("import sys,re,json\n"
             "t=sys.stdin.read(); m=re.search(r'named (\\S+) in the working directory', t)\n"
             "open(m.group(1),'w').write('resumed\\n')\n"
             "print(json.dumps({'type':'session','session_id':sys.argv[1]}))\n"
             "print(json.dumps({'type':'done','ok':True}))\n")
RESUME_STALE = ("import sys,json\n"
                "sys.stdin.read()\n"
                "print(json.dumps({'type':'done','ok':False,'message':'session '+sys.argv[1]+' not found'}))\n"
                "sys.exit(1)\n")


def spec_with(resume_script, executor_id="fake"):
    return replace(GENERIC_NDJSON, executor_id=executor_id, stdin="instructions",
                   resume_argv=("-X", "utf8", "-c", resume_script, "{session}"), resume_mode="replace")


class Env:
    def __init__(self, tmp_path, spec, max_attempts=3):
        self.tmp = tmp_path
        self.sup = Supervisor(tmp_path / "l" / "ledger.db")
        self.L = self.sup.ledger
        self.sup.registry.create_pool("slot", 1)
        self.spec = spec
        self.reg = self.sup.registry.register_executor(spec, capabilities=["run"], claims={"slot": 1}, version="v1")
        self.max_attempts = max_attempts

    def submit(self, tid, auth=None):
        ws = self.tmp / tid
        ws.mkdir()
        out = ws / "out.txt"
        self.sup.submit_task(tid, "tester", {"t": tid}, authorization=auth or {"scope": {"workspace": str(ws), "allowed_executors": ["fake"]}},
                             effects=[{"op_class": "local_write", "operation": "w", "target": str(ws), "paths": [str(ws)]}],
                             postconditions=[{"kind": "file_regular_nonempty", "spec": {"path": str(out)}}],
                             requirements={"capabilities": ["run"], "executors": ["fake"]}, max_attempts=self.max_attempts)
        return ws

    def run(self, admitted, ws, scenario, monkeypatch, inactivity_s=2):
        monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
        return self.sup.run_attempt(admitted, cwd=str(ws), instructions=b"write it\nWrite the result to a file named out.txt in the working directory.",
                                    resolved_executable=sys.executable, extra_argv=[FAKE], timeout_s=20, inactivity_s=inactivity_s)

    def attempts(self, tid):
        return [dict(r) for r in self.L.q("SELECT attempt_id,registration_id,session_id,resume_of,end_reason,argv_sha256 FROM attempt WHERE task_id=? ORDER BY attempt_id", (tid,))]

    def decisions(self, tid):
        return [(d["outcome"], d["action"]) for d in self.L.q("SELECT outcome,action FROM recovery_decision WHERE task_id=? ORDER BY decision_id", (tid,))]

    def close(self):
        self.sup.close()


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path, spec_with(RESUME_OK))
    yield e
    e.close()


def test_normal_continuation_resumes_same_task_same_registration(env, monkeypatch):
    ws = env.submit("t1")
    a1 = env.sup.admit_next()
    env.run(a1, ws, "hang", monkeypatch)
    assert env.decisions("t1") == [("RETRY_SAFE", "RESUME_SESSION")]
    a2 = env.sup.admit_next()
    env.run(a2, ws, "hang", monkeypatch)          # replaced argv: the resume script runs instead of the fake
    att = env.attempts("t1")
    assert att[1]["resume_of"] == 1 and att[1]["session_id"] == att[0]["session_id"] == "fake-1"
    assert env.L.task("t1")["state"] == "COMPLETE" and env.decisions("t1")[-1] == ("COMPLETE", "NONE")
    assert len({r[0] for r in env.L.q("SELECT auth_id FROM admission WHERE task_id='t1'")}) == 1


def test_session_from_another_task_is_never_reused(env, monkeypatch):
    ws1 = env.submit("a")
    a1 = env.sup.admit_next()
    env.run(a1, ws1, "hang", monkeypatch)
    assert env.attempts("a")[0]["session_id"] == "fake-1"
    ws2 = env.submit("b")
    b1 = env.sup.admit_next(only_task_id="b")
    env.run(b1, ws2, "honest", monkeypatch)
    att = env.attempts("b")
    fresh = env.spec.build_argv(workspace=str(ws2), resolved_executable=sys.executable) + [FAKE]
    assert att[0]["resume_of"] is None and att[0]["argv_sha256"] == sha(fresh)
    assert env.L.task("b")["state"] == "COMPLETE"


def test_reregistered_executor_does_not_inherit_the_session(env, monkeypatch):
    ws = env.submit("t")
    a1 = env.sup.admit_next()
    env.run(a1, ws, "hang", monkeypatch)
    assert env.decisions("t") == [("RETRY_SAFE", "RESUME_SESSION")]
    env.sup.registry.register_executor(env.spec, capabilities=["run"], claims={"slot": 1}, version="v2")   # new registration
    a2 = env.sup.admit_next()
    assert a2.registration_id != a1.registration_id
    env.run(a2, ws, "honest", monkeypatch)
    att = env.attempts("t")
    assert att[1]["resume_of"] is None
    refused = env.L.q("SELECT payload FROM event WHERE kind='attempt.resume_refused' AND task_id='t'")
    assert refused and json.loads(refused[0][0])["why"] == "SESSION_NOT_REUSABLE"
    assert env.L.task("t")["state"] == "COMPLETE"


def test_stale_session_resume_failure_takes_the_governed_retry_path(tmp_path, monkeypatch):
    env = Env(tmp_path, spec_with(RESUME_STALE), max_attempts=3)
    try:
        ws = env.submit("t")
        a1 = env.sup.admit_next()
        env.run(a1, ws, "hang", monkeypatch)
        a2 = env.sup.admit_next()
        env.run(a2, ws, "hang", monkeypatch)              # resume attempt: executor reports the session is gone
        att = env.attempts("t")
        assert att[1]["resume_of"] == 1 and att[1]["end_reason"] == "exited_after_terminal_error_claim"
        assert env.decisions("t") == [("RETRY_SAFE", "RESUME_SESSION"), ("RETRY_SAFE", "RETRY_FRESH")]
        a3 = env.sup.admit_next()
        env.run(a3, ws, "honest", monkeypatch)            # fresh attempt, no session in argv
        att = env.attempts("t")
        assert att[2]["resume_of"] is None and env.L.task("t")["state"] == "COMPLETE"
        assert (ws / "out.txt").read_text().startswith("hello from fake")
    finally:
        env.close()


def test_stale_session_with_exhausted_budget_fails_closed(tmp_path, monkeypatch):
    env = Env(tmp_path, spec_with(RESUME_STALE), max_attempts=2)
    try:
        ws = env.submit("t")
        env.run(env.sup.admit_next(), ws, "hang", monkeypatch)
        env.run(env.sup.admit_next(), ws, "hang", monkeypatch)
        assert env.L.task("t")["state"] == "FAILED" and env.L.task("t")["reason_code"] == "RETRY_BUDGET_EXHAUSTED"
        assert env.sup.admit_next() is None
    finally:
        env.close()


def test_revoked_authority_blocks_the_resume(env, monkeypatch):
    ws = env.submit("t")
    env.run(env.sup.admit_next(), ws, "hang", monkeypatch)
    assert env.decisions("t") == [("RETRY_SAFE", "RESUME_SESSION")]
    env.sup.supersede_authorization("t", scope={}, valid_until_us=env.L.now_us(), issued_by="test_revocation")
    assert env.sup.admit_next(only_task_id="t") is None
    assert env.L.task("t")["state"] == "RETRY_SAFE" and len(env.attempts("t")) == 1


def test_expired_authority_window_blocks_the_resume(tmp_path, monkeypatch):
    env = Env(tmp_path, spec_with(RESUME_OK))
    try:
        ws = env.tmp / "t"
        ws.mkdir()
        now = env.L.now_us()
        env.sup.submit_task("t", "tester", {"t": 1}, authorization={"scope": {"workspace": str(ws), "allowed_executors": ["fake"]},
                                                                      "valid_from_us": now, "valid_until_us": now + 3_000_000},
                            effects=[{"op_class": "local_write", "operation": "w", "target": str(ws), "paths": [str(ws)]}],
                            postconditions=[{"kind": "file_regular_nonempty", "spec": {"path": str(ws / "out.txt")}}],
                            requirements={"capabilities": ["run"], "executors": ["fake"]}, max_attempts=3)
        env.run(env.sup.admit_next(), ws, "hang", monkeypatch, inactivity_s=4)       # runs past the 3 s window
        assert env.decisions("t") == [("RETRY_SAFE", "RESUME_SESSION")]
        assert env.sup.admit_next(only_task_id="t") is None                            # window closed: no resume
    finally:
        env.close()


def test_completed_task_is_never_readmitted_or_resumed(env, monkeypatch):
    ws = env.submit("t")
    env.run(env.sup.admit_next(), ws, "honest", monkeypatch)
    assert env.L.task("t")["state"] == "COMPLETE"
    assert env.sup.admit_next(only_task_id="t") is None and len(env.attempts("t")) == 1


def test_bridge_resume_keeps_one_authorization_and_the_bound_model(tmp_path, authority, monkeypatch):
    """Through the bridge: attempt 2 (resume) is admitted against the same auth row and the SAME model the ticket's
    bound selection named (the model travels with the work, never with the session)."""
    spec = spec_with(RESUME_OK, executor_id="claude_code")
    binding = fake_binding("claude_code")
    binding = replace(binding, spec=spec)
    b = SupervisorBridge(tmp_path / "client", registry=fake_registry("claude_code"), executors={"claude_code": binding},
                         timeout_s=20, inactivity_s=3)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
        signed, request, now = authority.issue()
        work = authority.verify(signed, request, {**CLAUDE, "model": "m-1"}, now=now)
        assert b.execute(work)[0] == "verified"
        tid = work.task_id
        att = [dict(r) for r in b.L.q("SELECT attempt_id,resume_of,session_id FROM attempt WHERE task_id=? ORDER BY attempt_id", (tid,))]
        assert [a["resume_of"] for a in att] == [None, 1] and att[1]["session_id"] == "fake-1"
        assert len({r[0] for r in b.L.q("SELECT auth_id FROM admission WHERE task_id=?", (tid,))}) == 1
        req = json.loads(b.L.task(tid)["request_json"])
        assert req["model"] == "m-1"
    finally:
        b.close()


def test_supervisor_restart_never_resumes_a_leftover_session(tmp_path, monkeypatch):
    """A RETRY_SAFE/RESUME_SESSION leftover survives the supervisor restart as data only; the bridge revokes the
    authority and fails the task (Phase 2B rule), so the recorded session is never used after a restart."""
    env = Env(tmp_path, spec_with(RESUME_OK, executor_id="claude_code"))
    env.close()
    binding = replace(fake_binding("claude_code"), spec=spec_with(RESUME_OK, executor_id="claude_code"))
    from phase2b.conftest import SyntheticAuthority
    auth = SyntheticAuthority()
    client = tmp_path / "client"
    b = SupervisorBridge(client, registry=fake_registry("claude_code"), executors={"claude_code": binding}, timeout_s=20, inactivity_s=2)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
    signed, request, now = auth.issue()
    work = auth.verify(signed, request, CLAUDE, now=now)
    # stop the bridge after the first attempt by making the second admission impossible: close mid-loop
    real = b.sup.run_attempt
    state = {}

    def once(admitted, **kw):
        r = real(admitted, **kw)
        state["after_first"] = b.L.task(work.task_id)["state"]
        raise RuntimeError("simulated worker death after attempt 1")
    b.sup.run_attempt = once
    with pytest.raises(RuntimeError):
        b.execute(work)
    assert state["after_first"] == "RETRY_SAFE"
    b.close()
    b2 = SupervisorBridge(client, registry=fake_registry("claude_code"), executors={"claude_code": binding}, timeout_s=20, inactivity_s=2)
    try:
        assert b2.L.task(work.task_id)["state"] == "FAILED" and b2.L.task(work.task_id)["reason_code"] == "AUTHORITY_REVOKED_RESTART"
        assert b2.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (work.task_id,))[0] == 1
        assert b2.execute(work) == ("execution_uncertain", [], "DUPLICATE_OPERATION")
    finally:
        b2.close()
