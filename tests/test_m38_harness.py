"""M38 Harness Execution minimum: posture, discovery, controlled use, claims vs URI verification."""
import ast
import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest

from tests.m37_edge_support import intake
from tests.m38_harness_support import ROOT, escalated, fake_adapter
from uri_v1.execution.harness.adapters import FORBIDDEN_FLAGS, ClaudeCodeAdapter, CodexCliAdapter
from uri_v1.execution.harness.capsule import build_capsule
from uri_v1.execution.harness.contracts import (CapabilityGrant, ElevationGrant, HarnessError, HarnessType, Limits,
                                                PermissionProfile)
from uri_v1.execution.harness.discovery import discover_claude_code, discover_codex
from uri_v1.execution.workspace import Workspace, WorkspaceInput
from uri_v1.memory.contracts import Authority, VerificationStatus


def _run(tmp_path, monkeypatch, scenario, *, limits=None, **env):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
    for k, v in env.items(): monkeypatch.setenv(k, v)
    out = runner.run(esc, fake_adapter(home), session_id="session", limits=limits or Limits(timeout_s=60, inactivity_s=30))
    return e, esc, out


def test_honest_fix_is_verified_by_uri_not_by_the_harness(tmp_path, monkeypatch):
    e, esc, out = _run(tmp_path, monkeypatch, "honest")
    assert out.verified and out.verification_status == "VERIFIED" and out.claimed_outcome == "completed_claimed"
    index = e.log.load()
    claim, verdict = index.records[out.claim_record_id], index.records[out.verifier_record_id]
    assert claim.authority is Authority.CLAIMED_OUTCOME and verdict.authority is Authority.VERIFIED_OUTCOME
    run = e.store.get(out.run_id)
    assert [c["relpath"] for c in run["result"]["uri_computed_diff"]["changes"]] == ["report.py"]
    assert out.metrics["input_tokens"] == 1200 and out.metrics["cost_usd"] == 0.0123 and out.metrics["tool_calls"] == 2
    assert (e.root / "report.py").read_text().count('"Amt"') == 1  # the original is untouched; no write-back


def test_false_success_claim_is_rejected(tmp_path, monkeypatch):
    e, esc, out = _run(tmp_path, monkeypatch, "false_claim")
    assert out.claimed_outcome == "completed_claimed" and out.verification_status == "FAILED" and not out.verified


def test_unrequested_modification_fails_only_changed(tmp_path, monkeypatch):
    e, esc, out = _run(tmp_path, monkeypatch, "extra_file")
    assert out.verification_status == "FAILED"
    items = e.store.get(out.run_id)["verifications"][-1]["items"]
    assert next(i for i in items if i["kind"] == "only_changed")["detail"] == ["sales.xlsx"]


def test_write_to_original_is_flagged_and_never_verifies(tmp_path, monkeypatch):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "write_original"); monkeypatch.setenv("URI_FAKE_ORIGINAL", str(e.root / "report.py"))
    out = runner.run(esc, fake_adapter(home), session_id="session", limits=Limits(timeout_s=60, inactivity_s=30))
    assert "ORIGINAL_MODIFIED_DURING_RUN" in out.safety_flags and not out.verified
    assert out.verification_status == "CLAIMED_ONLY" and out.reason == "VERIFIER_SOURCE_NOT_CURRENT"


def test_symlink_escape_is_a_containment_violation(tmp_path, monkeypatch):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "symlink_escape"); monkeypatch.setenv("URI_FAKE_ORIGINAL", str(e.root / "report.py"))
    out = runner.run(esc, fake_adapter(home), session_id="session", limits=Limits(timeout_s=60, inactivity_s=30))
    assert "CONTAINMENT_VIOLATION" in out.safety_flags and out.verification_status == "FAILED"


def test_silent_hang_is_killed_for_inactivity_and_is_not_success(tmp_path, monkeypatch):
    e, esc, out = _run(tmp_path, monkeypatch, "hang_silent", limits=Limits(timeout_s=30, inactivity_s=2))
    assert out.claimed_outcome == "outcome_unknown" and out.metrics["inactivity_killed"] and not out.verified


def test_chatty_overrun_is_killed_by_total_timeout(tmp_path, monkeypatch):
    e, esc, out = _run(tmp_path, monkeypatch, "hang_chatty", limits=Limits(timeout_s=2, inactivity_s=2))
    assert out.claimed_outcome == "outcome_unknown" and out.metrics["timed_out"] and not out.verified


def test_whole_process_group_is_terminated(tmp_path, monkeypatch):
    pid_file = tmp_path / "child.pid"
    e, esc, out = _run(tmp_path, monkeypatch, "hang_with_child", limits=Limits(timeout_s=30, inactivity_s=2),
                       URI_FAKE_CHILD_PID=str(pid_file))
    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
            with open(f"/proc/{pid}/stat") as f:
                if f.read().split()[2] == "Z": break
        except (ProcessLookupError, FileNotFoundError): break
        time.sleep(0.1)
    else:
        pytest.fail("grandchild survived process-group termination")


# ---- M38 repair regressions (2026-09-28, from the internal audit's adversarial probes) ----

def test_same_group_orphan_is_killed_and_never_touches_the_original(tmp_path, monkeypatch):
    """H-2: a background child in the harness's own process group, stdio closed, used to
    survive a clean exit and overwrite the original a moment later. `supervise()` now
    sweeps the whole process group after every exit, not only on timeout/inactivity/cancel."""
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "orphan_same_group"); monkeypatch.setenv("URI_FAKE_ORIGINAL", str(e.root / "report.py"))
    out = runner.run(esc, fake_adapter(home), session_id="session", limits=Limits(timeout_s=60, inactivity_s=30))
    assert out.verified and out.verification_status == "VERIFIED" and out.safety_flags == ()
    before = (e.root / "report.py").read_text()
    time.sleep(2.5)
    assert (e.root / "report.py").read_text() == before  # the orphan never got to run


def test_originals_are_rechecked_after_verification_not_only_before(tmp_path, monkeypatch):
    """H-2/M-1: code that only fires under URI's verifier (scrubbed HOME) used to overwrite
    the original after the pre-verification check already passed, and nothing looked again."""
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "verifier_time_bomb"); monkeypatch.setenv("URI_FAKE_ORIGINAL", str(e.root / "report.py"))
    out = runner.run(esc, fake_adapter(home), session_id="session", limits=Limits(timeout_s=60, inactivity_s=30))
    assert not out.verified and "ORIGINAL_MODIFIED_DURING_VERIFICATION" in out.safety_flags


def test_oversized_prompt_does_not_block_the_watchdog(tmp_path):
    """M-5: stdin used to be written synchronously before the timeout loop started, so a
    harness that never reads stdin could hang `supervise()` past its own timeout."""
    from uri_v1.execution.harness.process import supervise
    log = tmp_path / "log"
    started = time.monotonic()
    r = supervise([sys.executable, "-c", "import time; time.sleep(3600)"], cwd=tmp_path, env=dict(os.environ),
                 stdin_bytes=b"x" * (1 << 20), timeout_s=2, inactivity_s=1, log_path=log)
    assert time.monotonic() - started < 8 and (r.timed_out or r.inactivity_killed)


def test_discovery_target_never_carries_a_single_string_commands_arguments(tmp_path):
    """M-2: `_target()` used to basename the *whole* command string, so a single-string
    MCP command such as `npx -y pkg --api-key sk-live-...` leaked the secret argument."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude.json").write_text(json.dumps({"mcpServers": {
        "acme": {"command": "npx -y @acme/mcp-server --api-key sk-live-LEAK1"}}}))
    inv = discover_claude_code(tmp_path)
    assert inv.find("MCP_SERVER", "acme").target == "npx" and "sk-live" not in json.dumps(inv.to_dict())


def test_harness_env_is_an_allowlist_not_a_denylist(monkeypatch):
    """M-3: `harness_env()` used to forward the whole environment minus a short denylist,
    so URI's own provider keys and the user's unrelated secrets reached the harness."""
    from uri_v1.execution.harness.process import harness_env
    for k in ("OPENAI_API_KEY", "TAVILY_API_KEY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "sk-live-" + k)
    env = harness_env()
    assert not any(k in env for k in ("OPENAI_API_KEY", "TAVILY_API_KEY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY"))
    assert "PATH" in env
    env = harness_env(("ANTHROPIC_API_KEY",))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-adapter-owns-this-one")
    assert harness_env(("ANTHROPIC_API_KEY",))["ANTHROPIC_API_KEY"] == "sk-ant-adapter-owns-this-one"


def test_elevated_posture_needs_a_grant_it_cannot_be_built_without(tmp_path, monkeypatch):
    """H-3/P3: `PermissionProfile(network=True, ...)` used to be buildable directly, with
    no `ElevationGrant` at all, making the restrictive default posture opt-out by construction."""
    with pytest.raises(HarnessError): PermissionProfile(network=True)
    with pytest.raises(HarnessError): PermissionProfile(package_install=True)
    with pytest.raises(HarnessError): PermissionProfile(extra_dirs=("/tmp",))


def test_elevation_grant_is_bound_to_the_run_it_was_issued_for(tmp_path, monkeypatch):
    """H-3/P3b: an `ElevationGrant`'s `run_scope` used to never be compared with the actual
    run: `HarnessRunner.run()` generated its own run id after the posture was already built,
    so a grant issued for one run could be reused on any other. `run()` now requires the
    caller to name the run up front and checks every grant against it."""
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    from uri_v1.execution.workspace import new_run_id
    run_a, run_b = new_run_id(), new_run_id()
    g = ElevationGrant.from_user(intake("yes, allow network access for this run"), "network", run_a)
    p = PermissionProfile().elevate(g, run_a)
    limits = Limits(timeout_s=30, inactivity_s=15)
    with pytest.raises(HarnessError): runner.run(esc, fake_adapter(home), session_id="s", posture=p, limits=limits)
    with pytest.raises(HarnessError):
        runner.run(esc, fake_adapter(home), session_id="s", posture=p, run_id=run_b, limits=limits)
    out = runner.run(esc, fake_adapter(home), session_id="s", posture=p, run_id=run_a, limits=limits)
    assert out.verified


def test_extra_dir_grant_needs_the_whole_directory_name_not_an_incidental_letter(tmp_path):
    """M-4/P4: `extra_dir:/home/someone/e` used to be granted by any "allow" sentence that
    happened to contain the letter `e`, because the basename was matched as a substring."""
    with pytest.raises(HarnessError):
        ElevationGrant.from_user(intake("yes allow the repair"), "extra_dir:/home/someone/e", "run-1")
    g = ElevationGrant.from_user(intake("yes, allow access to /home/someone/e for this run"), "extra_dir:/home/someone/e", "run-1")
    assert g.elevation.startswith("extra_dir:") and g.elevation.endswith("/e")
    with pytest.raises(HarnessError):  # root and home are never an allowed extra_dir
        ElevationGrant.from_user(intake("yes, allow access to / for this run"), "extra_dir:/", "run-1")


def test_capability_grant_needs_the_whole_name_not_a_substring(tmp_path):
    """M-4/P4b: a granted capability name used to be matched as a bare substring, so "the
    digital report fix" satisfied a grant for an MCP server named "git"."""
    with pytest.raises(HarnessError): CapabilityGrant.from_user(intake("allow the digital report fix"), [("MCP_SERVER", "git")])
    g = CapabilityGrant.from_user(intake("allow the git server"), [("MCP_SERVER", "git")])
    assert g.items == (("MCP_SERVER", "git"),)


def test_default_posture_has_no_shell_and_scopes_file_tools_to_the_workspace(tmp_path, monkeypatch):
    """H-1: bare `Read`/`Edit`/`Write`/`Glob`/`Grep` allow rules were not path-scoped at all,
    and `Bash(python *)` gave the harness arbitrary code execution by default. Chetan's
    decision (2026-09-28): no shell in the default posture; URI's own verifier runs any
    script. File tools are scoped to the workspace's `files/` directory."""
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    ws = Workspace.create(user_id=e.user, scratch_root=e.scratch, sources=e.sources,
                          inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in esc.inputs])
    cap = build_capsule(esc, ws, harness_type=HarnessType.CLAUDE_CODE)
    argv, _, _ = fake_adapter(home).invocation(cap, ws.bundle)
    disallowed = argv[argv.index("--disallowedTools"):]
    assert "Bash" in disallowed and not any(a.startswith("Bash(python") for a in argv)
    scope = str(ws.files.resolve())
    for tool in ("Read", "Edit", "Write", "Glob", "Grep"):
        assert f"{tool}({scope}/**)" in argv and tool in disallowed  # scoped allow + bare deny elsewhere


def test_reported_error_is_recorded_as_failed_claim_but_uri_still_checks(tmp_path, monkeypatch):
    e, esc, out = _run(tmp_path, monkeypatch, "honest_but_reports_error")
    assert out.claimed_outcome == "failed" and out.verification_status == "VERIFIED"
    claim = e.log.load().records[out.claim_record_id]
    assert claim.payload["verification_status"] == VerificationStatus.FAILED


def test_session_ids_and_transcripts_never_enter_memory(tmp_path, monkeypatch):
    e, esc, out = _run(tmp_path, monkeypatch, "honest")
    raw = b"".join(p.read_bytes() for p in e.log.path.rglob("*") if p.is_file())
    assert b"fake-session-0001" not in raw and b"Fixed the column name" not in raw
    run = e.store.get(out.run_id)
    assert run["result"]["executor_claim"]["session_ref"]["opaque"] == "fake-session-0001"  # run record only


def test_restrictive_default_argv_and_no_bypass_flags(tmp_path, monkeypatch):
    argv_out = tmp_path / "argv.json"
    e, esc, out = _run(tmp_path, monkeypatch, "honest", URI_FAKE_ARGV_OUT=str(argv_out))
    argv = json.loads(argv_out.read_text())
    assert not FORBIDDEN_FLAGS.intersection(argv)
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk" and argv[argv.index("--setting-sources") + 1] == ""
    disallowed = argv[argv.index("--disallowedTools"):]
    assert "--strict-mcp-config" in argv and "WebFetch" in disallowed and "Bash" in disallowed  # no shell by default
    assert "Bash(python *)" not in argv and "Bash(pip *)" not in argv and "--add-dir" not in argv
    assert any(a.startswith("Read(") and a.endswith("/**)") for a in argv)  # file tools are path-scoped to the workspace
    mcp = Path(argv[argv.index("--mcp-config") + 1])
    assert not mcp.exists()  # per-run config removed after the run


def test_elevation_requires_explicit_trusted_named_grant(tmp_path, monkeypatch):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    with pytest.raises(HarnessError): ElevationGrant.from_user(intake("go ahead"), "network", "run-1")
    with pytest.raises(HarnessError): ElevationGrant.from_user(intake("don't allow network"), "network", "run-1")
    with pytest.raises(HarnessError): ElevationGrant.from_user(object(), "network", "run-1")
    g = ElevationGrant.from_user(intake("yes, allow network access for this run"), "network", "run-1")
    with pytest.raises(HarnessError): PermissionProfile().elevate(g, "run-2")
    p = PermissionProfile().elevate(g, "run-1")
    ws = Workspace.create(user_id=e.user, scratch_root=e.scratch, sources=e.sources,
                          inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in esc.inputs])
    cap = build_capsule(esc, ws, harness_type=HarnessType.CLAUDE_CODE, posture=p)
    argv, _, _ = fake_adapter(home).invocation(cap, ws.bundle)
    disallowed = argv[argv.index("--disallowedTools"):]  # file tools stay path-scoped and denied bare (H-1) even when elevated
    assert "WebFetch" in argv and "WebFetch" not in disallowed and "WebSearch" not in disallowed
    cx, _, _ = CodexCliAdapter(("python3",), home=home).invocation(cap, ws.bundle)
    assert "sandbox_workspace_write.network_access=true" in cx


def _fake_home(home: Path, project: Path):
    (home / ".claude" / "skills" / "xlsx-helper").mkdir(parents=True)
    (home / ".claude" / "skills" / "xlsx-helper" / "SKILL.md").write_text("---\nname: xlsx-helper\ndescription: d\n---\nbody")
    plugin = home / "plugins" / "fmt"; (plugin / ".claude-plugin").mkdir(parents=True)
    (home / ".claude" / "plugins").mkdir(parents=True)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": {"fmt@market": [{"installPath": str(plugin)}]}}))
    (home / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {"fmt@market": True}, "hooks": {"PreToolUse": []},
                                                                "env": {"SECRET_TOKEN": "sk-live-SETTINGS"}}))
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {
        "sheets": {"command": "/opt/bin/sheets-mcp", "args": ["--token", "sk-live-ARGS"], "env": {"API_KEY": "sk-live-ENV"}},
        "remote": {"type": "http", "url": "https://mcp.example.com/v1?key=sk-live-URL", "headers": {"Authorization": "Bearer sk-live-HDR"}}}}))
    (home / ".claude" / ".credentials.json").write_text('{"token": "sk-live-CREDS"}')
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"proj": {"command": "node", "args": ["srv.js"]}}}))
    (home / ".codex" / "skills" / "c-skill").mkdir(parents=True)
    (home / ".codex" / "skills" / "c-skill" / "SKILL.md").write_text("---\nname: c-skill\n---\n")
    (home / ".codex" / "config.toml").write_text('[mcp_servers.docs]\ncommand = "npx"\nargs = ["-y", "docs", "--key", "sk-live-TOML"]\nenv = { K = "sk-live-TOMLENV" }\n')
    (home / ".codex" / "auth.json").write_text('{"k": "sk-live-CODEXAUTH"}')


def test_discovery_is_complete_and_redacted(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False); monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    home, project = tmp_path / "home", tmp_path / "proj"; home.mkdir(); project.mkdir(); _fake_home(home, project)
    inv = discover_claude_code(home, project)
    kinds = {(i.kind, i.name) for i in inv.items}
    assert {("SKILL", "xlsx-helper"), ("PLUGIN", "fmt@market"), ("HOOK", "PreToolUse"), ("MCP_SERVER", "sheets"),
            ("MCP_SERVER", "remote"), ("MCP_SERVER", "proj")} <= kinds
    assert inv.find("MCP_SERVER", "remote").target == "mcp.example.com" and inv.find("MCP_SERVER", "sheets").target == "sheets-mcp"
    assert inv.auth_mode == "subscription"
    codex = discover_codex(home)
    assert {("MCP_SERVER", "docs"), ("SKILL", "c-skill")} <= {(i.kind, i.name) for i in codex.items} and codex.auth_mode == "login"
    blob = json.dumps(inv.to_dict()) + json.dumps(codex.to_dict())
    assert "sk-live" not in blob


def test_controlled_use_injects_only_granted_capabilities_per_run(tmp_path, monkeypatch):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    project = tmp_path / "proj"; project.mkdir(); _fake_home(home, project)
    adapter = fake_adapter(home, project=project)
    ws = Workspace.create(user_id=e.user, scratch_root=e.scratch, sources=e.sources,
                          inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in esc.inputs])
    none = build_capsule(esc, ws, harness_type=HarnessType.CLAUDE_CODE)
    argv, _, _ = adapter.invocation(none, ws.bundle)
    assert json.loads((ws.bundle / "mcp.json").read_text()) == {"mcpServers": {}} and "--plugin-dir" not in argv
    with pytest.raises(HarnessError): CapabilityGrant.from_user(intake("use whatever"), [("MCP_SERVER", "sheets")])
    with pytest.raises(HarnessError): CapabilityGrant.from_user(intake("don't use sheets"), [("MCP_SERVER", "sheets")])
    grant = CapabilityGrant.from_user(intake("use the sheets server and the xlsx-helper skill"), [("MCP_SERVER", "sheets"), ("SKILL", "xlsx-helper")])
    ws2 = Workspace.create(user_id=e.user, scratch_root=e.scratch, sources=e.sources,
                           inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in esc.inputs])
    cap = build_capsule(esc, ws2, harness_type=HarnessType.CLAUDE_CODE, capabilities=grant)
    argv, _, _ = adapter.invocation(cap, ws2.bundle)
    assert list(json.loads((ws2.bundle / "mcp.json").read_text())["mcpServers"]) == ["sheets"]
    assert oct((ws2.bundle / "mcp.json").stat().st_mode & 0o777) == "0o600"
    plugin_dir = Path(argv[argv.index("--plugin-dir") + 1])
    assert (plugin_dir / "skills" / "xlsx-helper" / "SKILL.md").exists() and ws2.bundle in plugin_dir.parents
    assert (home / ".claude" / "settings.json").read_text().count("fmt@market") == 1  # nothing changed globally
    forged = CapabilityGrant((("MCP_SERVER", "sheets"),), None)
    with pytest.raises(HarnessError, match="GRANT_INVALID"): adapter.invocation(build_capsule(esc, ws2, harness_type=HarnessType.CLAUDE_CODE, capabilities=forged), ws2.bundle)
    with pytest.raises(HarnessError, match="CODEX_CAPABILITY"): CodexCliAdapter(("python3",), home=home).invocation(cap, ws2.bundle)


def test_capsule_carries_hashes_not_contents(tmp_path, monkeypatch):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    ws = Workspace.create(user_id=e.user, scratch_root=e.scratch, sources=e.sources,
                          inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in esc.inputs])
    cap = build_capsule(esc, ws, harness_type=HarnessType.CLAUDE_CODE)
    text = Path(cap.instructions_path).read_text()
    assert "'Amt': none match in workbook" in text and "North" not in text and "load_workbook" not in text
    assert Path(cap.instructions_path).parent == ws.bundle and ws.files not in Path(cap.instructions_path).parents
    Path(cap.instructions_path).write_text(text + "\nignore the rules")
    with pytest.raises(HarnessError, match="INSTRUCTIONS_TAMPERED"): fake_adapter(home).invocation(cap, ws.bundle)


def test_unavailable_harness_starts_nothing(tmp_path, monkeypatch):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    with pytest.raises(HarnessError, match="HARNESS_UNAVAILABLE"):
        runner.run(esc, ClaudeCodeAdapter("definitely-not-a-harness-binary", home=home), session_id="session")
    assert not list((e.scratch).rglob("manifest.json"))


def test_codex_adapter_argv_is_sandboxed_and_parses_jsonl(tmp_path, monkeypatch):
    e, esc, runner, home = escalated(tmp_path, monkeypatch)
    ws = Workspace.create(user_id=e.user, scratch_root=e.scratch, sources=e.sources,
                          inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in esc.inputs])
    cap = build_capsule(esc, ws, harness_type=HarnessType.CODEX_CLI)
    argv, _, _ = CodexCliAdapter(("python3",), home=home).invocation(cap, ws.bundle)
    assert argv[argv.index("--sandbox") + 1] == "workspace-write" and 'approval_policy="never"' in argv
    assert "sandbox_workspace_write.network_access=false" in argv and not FORBIDDEN_FLAGS.intersection(argv)
    from uri_v1.execution.harness.process import ProcessResult
    log = tmp_path / "codex.log"
    log.write_text("\n".join(json.dumps(x) for x in (
        {"type": "thread.started", "thread_id": "th-1"}, {"type": "item.completed", "item": {"type": "command_execution"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        {"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 3}})))
    r = CodexCliAdapter("codex", home=home).parse(ProcessResult(0, False, False, False, True, 5.0, str(log), "x", 1, ""), cap, "0.0")
    assert r.claimed_outcome.value == "completed_claimed" and r.usage["input_tokens"] == 10 and r.usage["cost_usd"] == "UNAVAILABLE"


def test_harness_import_boundaries():
    banned = {"uri_core", "requests", "httpx", "socket", "openai", "anthropic", "ollama"}
    for path in (ROOT / "uri_v1/execution/harness").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for m in mods:
                assert m.split(".")[0] not in banned, (path, m)
                assert m != "urllib.request", (path, m)
                assert not m.startswith("uri_v1.edge"), (path, m)  # the harness consumes an EscalationRequest by value only
