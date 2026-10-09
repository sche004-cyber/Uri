# URI Scheduler — security and cancellation, verified against the final code (2026-10-09)

The owner conditionally accepted two limitations: F2 (Claude Code permissions are not an operating-system sandbox) and
R7-1 (the inherited supervisor's narrow cancel/start window). This record checks both against the code as it is now
(`uri_scheduler/harness.py`, `uri_supervisor/executors.py`, `uri_supervisor/supervisor.py` at `b809c6d`) and decides
whether a minimal improvement is justified. **Neither limitation is resolved; both remain recorded limitations.**

## 1. Acceptance criteria

| id | criterion | result |
|---|---|---|
| S-AC1 | Every boundary claim is traced to a line of code, not to an earlier report | met (§2) |
| S-AC2 | The cancel window is measured on the real accepted supervisor, with a positive control | met (§3) |
| S-AC3 | A code change is made only if the evidence shows a gap it closes without touching accepted modules | met: no change justified for F2 or R7-1; the logon-task script was improved (§4) |
| S-AC4 | Residual risks are stated with their effect | met (§5) |

## 2. F2: what bounds the Claude executor (code, not claims)

| boundary | where | effect |
|---|---|---|
| Tool set fixed to `Read,Edit,Write,Glob,Grep` | `executors.py` `CLAUDE_CODE` argv `--tools Read,Edit,Write,Glob,Grep` | no Bash, no WebFetch/WebSearch, no Task/agents: no shell, no network tool |
| No MCP servers | `--strict-mcp-config` with no `--mcp-config` | no external tool server can be loaded |
| No user or project settings, hooks or permission rules | `--setting-sources ""` | the owner's `~/.claude` rules or a repository's `.claude/` cannot widen anything |
| Unapproved actions denied, not asked | `--permission-mode dontAsk` | anything not pre-approved is refused |
| Writes only inside the attempt workspace | `--allowedTools Edit(./**)` (cwd = workspace); `run_attempt` refuses a cwd outside the authorised workspace (`CWD_OUTSIDE_WORKSPACE`) | edits are pre-approved only under the workspace |
| Bypass flags refused in the final argv | `check_final_argv` (`--dangerously-skip-permissions`, `bypassPermissions`, `--yolo`, ...) | a configuration change cannot add them |
| Environment allow-list | `ExecutorSpec.build_env`: `PATH, HOME, USERPROFILE, TEMP, ...` + `CLAUDE_CODE_OAUTH_TOKEN`; `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` never forwarded | checked live: this session has `ANTHROPIC_BASE_URL` set; it is **not** forwarded, so a stray variable cannot redirect or re-bill the executor |
| Separate login | `USERPROFILE`/`HOME` = scheduler client home | the owner's own Claude login is never used |
| Process containment | `winproc.spawn_contained`: suspended start, Job Object, kill-on-close | the executor and its children die with the attempt |
| No publication | no endpoint or tool can send, post or upload; `published: False` | — |

What is **not** enforced by the operating system: reads. Under `dontAsk`, Claude Code refuses reads outside its
working directory by its own rules; nothing at the OS level stops the `claude.exe` process from reading files the
Windows user can read. Because the executor has no network tool, no shell and no MCP server, a read cannot leave the
machine through a tool; it could only appear in the model's output in the workspace, which the owner reviews. That is
the accepted F2 limitation. An OS sandbox (AppContainer or a separate low-privilege account) is a major containment
redesign and is not justified by any observed failure; it stays an owner decision.

## 3. R7-1: the cancel/start window, measured

The window: the owner's cancel arrives after the harness's last post-admission check and before the supervisor spawns
the executor. `request_cancel` refuses then (the attempt is not active yet), so the harness pre-arms the supervisor's
kill set; the supervisor starts the process suspended, records its identity, resumes it, and checks the kill set on
its first supervision poll.

Probe: `docs/scheduler/evidence/cancel_window/cancel_window_probe.py` wraps the real `Supervisor.run_attempt` so the
cancel arrives exactly in that window, and runs executors that try to write a marker file the moment they start, before
reading their input.

| executor | cancelled runs | effects before kill | end reason | spawn → end (median / max) | control runs (not cancelled) | control effects |
|---|---|---|---|---|---|---|
| Python process | 30 | **0** | `cancelled_killed` (30/30) | 1.4 ms / 2.1 ms | 3 | 3 |
| `cmd.exe` batch file | 30 | **0** | `cancelled_killed` (30/30) | 1.5 ms / 3.6 ms | 3 | 3 |

Files: `cancel_window_summary.json`, `cancel_window_runs.json`. The controls prove the executors do write when not
cancelled, so the zero is meaningful.

Interpretation: the kill lands within a few milliseconds of the executor's start. Claude Code needs a Node start-up and
a model round trip before its first tool call, i.e. far longer than this. The window is therefore real but very small;
it is **not** a guarantee (a sufficiently fast native process could act first, and the probe cannot exclude a slow
poll under heavy load). A guarantee needs the accepted supervisor to check the kill set before resuming the suspended
process: that is a change to an accepted module and stays an owner decision. **No change made.**

## 4. Improvement made: logon-task procedure (`scripts/scheduler_task_ctl.ps1`)

Found by reading the script against the brief:

| gap | fix |
|---|---|
| The logon trigger had no user, so it fired at **any** user's logon (URIServer pattern) | trigger bound to the current user (`-User DOMAIN\user`) |
| `install -Apply` had no preconditions; the default Python (`.venv`) does not exist in the worktree | refuses unless Python exists and imports `uri_scheduler`, state parent and client home exist, the task is absent, **and** `-LiveValidation` names a live-test `result.json` with `simulated: false` and `verdict: PASS` |
| Rollback only unregistered; a running service kept running | rollback stops the task, stops the recorded service process only if its command line is this scheduler for this state dir, unregisters, and verifies removal; state is kept |
| No way to check the definition without registering | `-Action verify` builds it in memory |

Tests (`tests/scheduler/test_task_ctl.py`, 5 passed) run only dry runs and assert that the Windows task inventory is
identical before and after each test. `URIScheduler` is **not registered** (checked after the run).

## 5. Residual risks

| id | risk | likelihood | effect | owner visibility |
|---|---|---|---|---|
| F2 | executor reads outside the workspace bypassing Claude Code rules | low (no tool can send data out) | data could appear in a generated artifact | every artifact waits for owner review |
| R7-1 | an executor acts in the first milliseconds after a cancel | very low for Claude Code (measured window ≤ 3.6 ms) | an effect inside the attempt workspace only | reconciliation records it; the occurrence ends CANCELLED |
| L-UNCERTAIN | an uncertain outcome | — | never auto-retried | `NEEDS_ATTENTION` in the UI |
