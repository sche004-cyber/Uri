"""Phase 2C: `resume_mode="replace"` lets the supervisor resume executors whose resume grammar is a different
subcommand (Codex: `codex exec resume <id> ...`). Real Codex resume evidence: evidence/phase2c/codex_resume1.json
(REAL executor, interruption induced by a harness-injected supervisor timeout). Here: argv construction, injection
refusal, JSON round trip, and the full supervisor resume path with a SYNTHETIC executor whose resume argv is replaced.
"""
import json
import sys
from dataclasses import replace

import pytest

from phase2b.conftest import CLAUDE, FAKE, fake_registry
from uri_supervisor.executors import CLAUDE_CODE, CODEX_CLI, GENERIC_NDJSON, ExecutorSpec, ExecutorSpecError
from uri_supervisor_bridge.bridge import ExecutorBinding, SupervisorBridge

SESSION = "01a11496-16c0-7221-9feb-371efbcdf0a1"


def test_codex_first_attempt_argv_is_unchanged_by_the_resume_template():
    argv = CODEX_CLI.build_argv(workspace="W", model="gpt-6-sol", resolved_executable="codex.exe")
    assert argv == ["codex.exe", "exec", "--json", "--sandbox", "workspace-write", "--skip-git-repo-check", "-C", "W",
                    "-c", 'approval_policy="never"', "-m", "gpt-6-sol", "-"]


def test_codex_resume_argv_uses_the_resume_subcommand_with_sandbox_and_stdin_preserved():
    argv = CODEX_CLI.build_argv(workspace="W", model="gpt-6-sol", session=SESSION, resolved_executable="codex.exe")
    assert argv[:4] == ["codex.exe", "exec", "resume", SESSION]
    assert "--json" in argv and 'sandbox_mode="workspace-write"' in argv and 'approval_policy="never"' in argv
    assert argv[-1] == "-" and argv[argv.index("-m") + 1] == "gpt-6-sol"
    assert "--sandbox" not in argv and "-C" not in argv          # `exec resume` has neither flag; cwd + config carry them


def test_claude_resume_still_appends():
    argv = CLAUDE_CODE.build_argv(workspace="W", session="abc", resolved_executable="claude.exe")
    assert argv[-2:] == ["--resume", "abc"] and argv[1] == "-p"


@pytest.mark.parametrize("bad", ["--yolo", "x --dangerously-bypass-approvals-and-sandbox", "a b", "-m evil", "../x", " "])
def test_replace_mode_refuses_session_ids_that_do_not_look_like_ids(bad):
    with pytest.raises(ExecutorSpecError, match="BAD_SESSION_ID"):
        CODEX_CLI.build_argv(workspace="W", session=bad, resolved_executable="codex.exe")


def test_unknown_resume_mode_fails_closed():
    spec = replace(GENERIC_NDJSON, resume_argv=("x",), resume_mode="splice")
    with pytest.raises(ExecutorSpecError, match="BAD_RESUME_MODE"):
        spec.build_argv(session="abc", resolved_executable="x")


def test_resume_mode_round_trips_and_defaults_to_append():
    assert ExecutorSpec.from_json(CODEX_CLI.to_json()) == CODEX_CLI
    assert ExecutorSpec.from_json(CODEX_CLI.to_json()).spec_sha256() == CODEX_CLI.spec_sha256()
    legacy = dict(GENERIC_NDJSON.to_json())
    legacy.pop("resume_mode")
    assert ExecutorSpec.from_json(legacy).resume_mode == "append"


RESUMED_EXECUTOR = (
    "import sys,re,json\n"
    "t=sys.stdin.read(); m=re.search(r'named (\\S+) in the working directory', t)\n"
    "open(m.group(1),'w').write('resumed\\n')\n"
    "print(json.dumps({'type':'session','session_id':sys.argv[1]}))\n"
    "print(json.dumps({'type':'message','text':'RESUMED '+sys.argv[1]}))\n"
    "print(json.dumps({'type':'done','ok':True}))\n")


def test_supervisor_resumes_with_replaced_argv_after_an_interrupted_attempt(tmp_path, authority, monkeypatch):
    """Attempt 1 (fake, `hang`) is killed by inactivity with a recorded session and no terminal event: absence proven,
    RESUME_SESSION. Attempt 2's argv is the replace template (the fake script becomes a trailing argument of the
    `-c` executor), carries the session id, and completes. Same authorization row for both attempts."""
    spec = replace(GENERIC_NDJSON, executor_id="claude_code", stdin="instructions",
                   resume_argv=("-X", "utf8", "-c", RESUMED_EXECUTOR, "{session}"), resume_mode="replace")
    binding = ExecutorBinding(spec=spec, resolved_executable=sys.executable, extra_argv=(FAKE,), version="fake")
    bridge = SupervisorBridge(tmp_path / "client", registry=fake_registry("claude_code"), executors={"claude_code": binding},
                              timeout_s=20, inactivity_s=3)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "hang")
        signed, request, now = authority.issue()
        work = authority.verify(signed, request, CLAUDE, now=now)
        outcome, evidence, failure = bridge.execute(work)
        assert (outcome, failure) == ("verified", None), (outcome, failure)
        L = bridge.L
        attempts = L.q("SELECT attempt_id,session_id,resume_of,end_reason,exit_code FROM attempt WHERE task_id=? ORDER BY attempt_id", (work.task_id,))
        assert len(attempts) == 2
        assert attempts[0]["end_reason"] == "inactivity_killed" and attempts[0]["session_id"] == "fake-1"
        assert attempts[1]["resume_of"] == 1 and attempts[1]["session_id"] == "fake-1"
        decisions = L.q("SELECT outcome,action,reason_code FROM recovery_decision WHERE task_id=? ORDER BY decision_id", (work.task_id,))
        assert [(d["outcome"], d["action"]) for d in decisions] == [("RETRY_SAFE", "RESUME_SESSION"), ("COMPLETE", "NONE")]
        assert len({r[0] for r in L.q("SELECT auth_id FROM admission WHERE task_id=?", (work.task_id,))}) == 1
        msgs = [json.loads(e["payload"]) for e in L.q("SELECT payload FROM evidence WHERE task_id=? AND kind='agent_message' AND attempt_id=2", (work.task_id,))]
        assert msgs and msgs[0]["text"] == "RESUMED fake-1"            # the replaced argv carried the recorded session
        assert evidence[0]["supervisor_attempt"] == 2 and L.task(work.task_id)["state"] == "COMPLETE"
    finally:
        bridge.close()


def test_resume_is_never_chosen_when_the_executor_reported_a_terminal_claim(tmp_path, authority, monkeypatch):
    """A terminal error claim (real model-rejected case) is not an interruption: RETRY_FRESH, not RESUME_SESSION."""
    spec = replace(GENERIC_NDJSON, executor_id="claude_code", stdin="instructions",
                   resume_argv=("-X", "utf8", "-c", RESUMED_EXECUTOR, "{session}"), resume_mode="replace")
    binding = ExecutorBinding(spec=spec, resolved_executable=sys.executable, extra_argv=(FAKE,), version="fake")
    bridge = SupervisorBridge(tmp_path / "client", registry=fake_registry("claude_code"), executors={"claude_code": binding},
                              timeout_s=15, inactivity_s=4)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "quota_after_tool_no_effect")      # done ok:false after a read-only tool
        signed, request, now = authority.issue()
        work = authority.verify(signed, request, CLAUDE, now=now)
        bridge.execute(work)
        actions = [d["action"] for d in bridge.L.q("SELECT action FROM recovery_decision WHERE task_id=? ORDER BY decision_id", (work.task_id,))]
        assert "RESUME_SESSION" not in actions
    finally:
        bridge.close()
