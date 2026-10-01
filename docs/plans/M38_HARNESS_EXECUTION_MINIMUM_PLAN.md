# M38 — Harness Execution Minimum

- **Status:** `M38_IMPLEMENTED_PROVISIONAL_NOT_FROZEN` once the implementation commit lands. PROVISIONAL / NOT FROZEN until the batched independent audit. No claim of independent qualification or closure.
- **Date:** 2026-09-28. **Author / implementer:** Claude Code. Preferred independent auditor: Codex.
- **Authority:** User instruction 2026-09-28: "Harness Execution minimum — plan and implement, including harness capability/plugin/skill/MCP discovery and controlled use", then stop before the Office demonstrator and prepare one Codex audit package for Memory → Edge → Harness.
- **Governing rulings (repository evidence):** D-A/OD-1 (harness ≠ Brain; claims only; URI verifies), OD-2 (harness access mode is the harness's own concern; URI never holds its credentials), OD-3 (default `COPY_IN_COPY_OUT`), OD-4 (restrictive default posture; per-run elevation only by explicit user choice), OD-5 (`uri_v1/execution/`; no `uri_core` import), VG-1 and LF-1 (`docs/plans/PAPERCLIP_URI_ARCHITECTURE_RECONNAISSANCE.md` §20, §24; `docs/plans/URI_EXTERNAL_HARNESS_VIABILITY_GATE.md`), project instructions (preserve native plugins/skills/MCPs/extensions; never install globally; prefer per-run injection).
- **Recorded dependencies on unaudited work:** M36 at `405db1f` (claim/verifier recording, sources) and M37 at `5460d64` (workspace, acceptance, verifier, lineage, `EscalationRequest`). If either changes under audit, M38 must be re-qualified.

## 0. Acceptance criteria (defined before drafting)

| ID | Criterion |
|---|---|
| AC-H1 | One harness contract in `uri_v1/execution/harness/` implementing the §20 sketch as amended by §24.2 (describe, probe, start/run, events, cancel-verified, result as claims). |
| AC-H2 | A harness receives only an Execution Capsule built from an Edge `EscalationRequest`: copy-in workspace, hashed inputs, hashed acceptance, unresolved remainder, local findings. |
| AC-H3 | Default posture is restrictive (OD-4); any elevation needs an explicit, trusted, per-run user grant naming it. No bypass flag is ever emitted. |
| AC-H4 | Capability discovery (plugins, skills, MCP servers, agents, hooks, prompts) for Claude Code and Codex is read-only, never reads credential files, and never records secrets. |
| AC-H5 | Controlled use: a discovered capability is available to a run only when explicitly granted for that run, and is injected per run (no global install or global config change). |
| AC-H6 | Results are claims. URI computes changed artifacts, verifies independently, and a harness claim can never become `VERIFIED` without the URI verifier; a false success claim is caught. |
| AC-H7 | Originals are never modified by a harness run; if they are, the run can never verify and is flagged. |
| AC-H8 | Timeouts, output inactivity and cancellation terminate the whole process group, and the result is `outcome_unknown`, not success. |
| AC-H9 | Harness session ids and transcripts never enter M36 Memory; the run record keeps only opaque handles and hashes. |
| AC-H10 | VG-1 instrumentation: tokens, cost, turns, tool calls, capsule size and latency are recorded when the harness reports them, `UNAVAILABLE` otherwise; never estimated. |
| AC-H11 | Tests, fake-harness adversarial qualification with a frozen gate, at least one live run where a harness is available, governance checks, self-review, disclosed limits. |

## 1. Scope

New files only:

```
uri_v1/execution/harness/
  contracts.py     HarnessType, PermissionProfile, ElevationGrant, CapabilityGrant, ExecutionCapsule, HarnessRunResult
  discovery.py     read-only inventory of native capabilities (Claude Code, Codex CLI), redacted
  process.py       process-group runner with total timeout, output-inactivity watchdog, verified settlement, log hash
  claude_code.py   adapter: argv/env for restrictive or elevated profiles, per-run MCP/plugin/skill injection, stream-json parsing
  codex_cli.py     adapter: argv/env (workspace-write sandbox, no network, approval never), JSONL parsing
  capsule.py       capsule and instructions bundle from an EscalationRequest
  runner.py        HarnessRunner: workspace → capsule → run → URI diff → claim → URI verification → lineage
```

Out of scope: the Office demonstrator; automatic escalation routing (S6 unchanged; the decision to escalate stays with the caller); session resume (the handle is stored, not used); `DIRECT_ORIGINAL`; `worktree` workspaces; write-back in any automated flow; Brain changes (M31 unchanged: the Brain never shells out; the harness is launched by URI execution code).

## 2. Posture (OD-4)

Default `PermissionProfile`: workspace-write inside the copy-in `files/` directory only; no network tools; shell limited to running Python; no approval bypass; no additional directories; no package installation.

- Claude Code: `-p`, `--permission-mode dontAsk`, `--tools Read,Edit,Write,Glob,Grep,Bash`, `--allowedTools` for file tools plus `Bash(python *)`/`Bash(python3 *)`, `--disallowedTools WebFetch WebSearch`, `--setting-sources ""` (user/project/local settings, hooks and enabled plugins are not loaded unless granted), `--strict-mcp-config --mcp-config <per-run file>`, `--no-session-persistence`, `--max-budget-usd`. `--dangerously-skip-permissions` and `bypassPermissions` are never emitted.
- Codex CLI: `exec --json --sandbox workspace-write --skip-git-repo-check -C <files> -c approval_policy="never" -c sandbox_workspace_write.network_access=false`. `--dangerously-bypass-approvals-and-sandbox` is never emitted.
- Elevations (each needs an `ElevationGrant` from a trusted user turn that names it): `network`, `package_install`, `extra_dir:<authorized path>`.

## 3. Discovery and controlled use

Discovery reads only descriptor files: Claude Code `~/.claude/settings.json` (`enabledPlugins`, hook event names), `~/.claude.json` (`mcpServers` names/transport), project `.mcp.json`, `~/.claude/plugins/installed_plugins.json`, `~/.claude/skills/*/SKILL.md` and `~/.claude/agents/*.md` (name and description only); Codex `~/.codex/config.toml` (`[mcp_servers.*]`), `~/.codex/skills/*/SKILL.md`, `~/.codex/prompts/*.md`. It records name, kind, scope, transport, command basename or URL host, and a fingerprint of the redacted descriptor. It never records `env`, `headers`, `args` or URL paths/queries, and it never opens `~/.claude/.credentials.json` or `~/.codex/auth.json` (their existence only sets `auth_mode`).

Controlled use (Claude Code): a `CapabilityGrant` names discovered items. Granted MCP servers are written to a per-run `mcp.json` in the run's `bundle/` (outside `files/`, mode 0600, deleted after the run). Granted plugins are passed with `--plugin-dir <installed path>`. Granted skills are wrapped into a per-run plugin directory in `bundle/` and passed with `--plugin-dir`. Nothing is installed or enabled globally. For Codex, the minimum supports no capability injection (the adapter refuses a non-empty grant), because injecting into Codex without touching the user's `CODEX_HOME` could not be verified here.

## 4. Run procedure

1. Probe the harness (version, auth mode). Unavailable → typed `HARNESS_UNAVAILABLE`, nothing started.
2. Copy-in workspace from the escalation's hashed inputs (M37 `Workspace`).
3. Build the instructions bundle (outside `files/`): goal for the task class, unresolved remainder, compact local findings, acceptance items and hash, the rule that verification is URI's. Hash it. Build and hash the capsule.
4. Record `RUN_STARTED` (executor `HARNESS`, capsule and hash, adapter/version/auth mode, posture, grant, inventory fingerprint).
5. Run in a process group with total timeout and output-inactivity watchdog; keep the full output as a run log file and record its SHA-256.
6. Parse claims (claimed outcome, question, final message hash, session handle, usage). Check originals still match copy-in hashes.
7. `record_and_verify` (M37): URI diff → S11 versions → Memory claim (`CLAIMED_ONLY`, or `FAILED` when the harness itself reports failure) → registered URI verifier.
8. Return the outcome with VG-1 metrics. Nothing is written back.

## 5. Qualification

- **Offline adversarial gate** (fake harness executable that emits real Claude Code stream-json and acts per scenario): honest fix, false success claim, extra-file modification, write to the original outside the workspace, symlink escape, hang (inactivity), overrun (timeout), harness-reported error, question. Frozen gate: `false_verified` = 0, `originals_modified_undetected` = 0, `unkilled_processes` = 0, `bypass_flags_emitted` = 0, `secrets_in_records` = 0, expected status per scenario 100 %.
- **Live runs** (this environment has Claude Code; Codex is not installed): a small VG-1 pilot on one real task outside the Edge's local envelope, Arm A (direct Claude Code with the raw request in a directory holding the same files plus unrelated files) vs Arm B (URI-mediated capsule), each verified by the same URI verifier. Reported as a pilot (n is tiny), never as VG-1 qualification. Codex is recorded `UNAVAILABLE`.

## 6. Known limitations accepted for the minimum

- Claude Code on Windows has no OS-level shell sandbox; restriction is by tool permissions (`dontAsk` + allowlist). A Python process the harness runs could still reach the network. Disclosed; OD-4 "no network" is enforced at the tool layer only for Claude Code.
- The Codex adapter is built from documented flags but not executed here; it stays `UNQUALIFIED` until a live run exists.
- Session resume is not implemented.
