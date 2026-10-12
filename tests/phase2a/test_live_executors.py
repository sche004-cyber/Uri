"""LIVE executor smoke through the real supervisor (opt-in: URI_PHASE2A_LIVE=1).

Runs the real installed Codex CLI / Claude Code through admission -> intent -> contained spawn -> raw stream ->
reconcile, on a read-only task in a temp directory. It never logs in, never passes credentials, and uses no tools.
On this machine both CLIs fail fast (Codex: configured model rejected for the ChatGPT account; Claude: OAuth session
expired), which is itself the important case: a failure stream must never become COMPLETE.
If a CLI is authenticated elsewhere and replies, a clean success (terminal claim + exit 0) is the only way to COMPLETE.
"""
import json
import os
import shutil
from dataclasses import replace

import pytest

from phase2a.conftest import Env
from uri_supervisor.executors import CLAUDE_CODE, CODEX_CLI

pytestmark = pytest.mark.skipif(os.environ.get("URI_PHASE2A_LIVE") != "1", reason="live executors are opt-in (URI_PHASE2A_LIVE=1)")

PROMPT = b"Reply with exactly the word OK and nothing else.\n"


def codex_spec():
    toks = list(CODEX_CLI.argv)
    toks.insert(toks.index("--json") + 1, "--ephemeral")
    return replace(CODEX_CLI, argv=tuple(toks))


def claude_spec():
    toks = list(CLAUDE_CODE.argv)
    toks[toks.index("--tools") + 1] = ""                                  # no tools at all
    return replace(CLAUDE_CODE, argv=tuple(toks) + ("--max-budget-usd", "0.5"))


@pytest.mark.parametrize("name,spec,exe", [("codex_cli", codex_spec(), "codex"), ("claude_code", claude_spec(), "claude")])
def test_live_executor_failure_stream_never_becomes_complete(tmp_path, name, spec, exe):
    if shutil.which(exe) is None:
        pytest.skip(f"{exe} not installed")
    e = Env(tmp_path)
    e.setup_pools(slot=1)
    e.sup.registry.register_executor(spec, capabilities=["run"], claims={"slot": 1}, version=spec.probe_version())
    e.task("live")
    adm = e.sup.admit_next()
    work = tmp_path / "w"; work.mkdir()
    r = e.sup.run_attempt(adm, cwd=str(work), instructions=PROMPT, timeout_s=120, inactivity_s=90)
    L = e.L
    lines = L.q1("SELECT COUNT(*) FROM stream_event WHERE attempt_id=? AND stream='stdout'", (adm.attempt_id,))[0]
    claims = [x["kind"] for x in L.q("SELECT kind FROM evidence WHERE attempt_id=? AND kind LIKE 'terminal_%'", (adm.attempt_id,))]
    state = e.state("live")
    version = L.q1("SELECT executor_version FROM attempt")[0]
    print("LIVE", name, json.dumps({"state": state, "exit": r.exit_code, "end_reason": r.end_reason, "stdout_lines": lines,
                                     "claims": claims, "reason": L.task("live")["reason_code"], "version": version}))
    assert lines >= 1, "raw stream must be persisted"
    if state == "COMPLETE":
        assert claims == ["terminal_success_claim"] and r.exit_code == 0
    else:
        assert state in ("RETRY_SAFE", "FAILED"), state                  # read-only task: failure is safely retryable, never COMPLETE
    e.close()
