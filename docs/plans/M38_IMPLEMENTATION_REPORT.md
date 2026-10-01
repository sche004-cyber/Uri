# M38 Harness Execution Minimum — implementation report

State: `M38_IMPLEMENTED_PROVISIONAL_NOT_FROZEN`. Implemented and self-qualified by Claude Code on 2026-09-28. Not independently audited, not frozen, not integrated. The Office demonstrator was not started (batch stop point).

## Authority and recorded dependencies

- User instruction 2026-09-28: plan and implement the Harness Execution minimum, including capability/plugin/skill/MCP discovery and controlled use; stop before the Office demonstrator.
- Depends on unaudited **M36** at `405db1f` (recorder, verifier bootstrap, sources, `TrustedInput`, `negated`) and unaudited **M37** at `5460d64` (workspace, acceptance, verifier, lineage, `EscalationRequest`). No M36, M37-core-contract, frozen M33.3, S6, M31 or `uri_core` change. M38 touched two M37 files additively: `record_and_verify` gained an optional `uri_observations` argument, and the M37 verifier now returns `FAILED` when URI recorded safety flags for the run. Both are listed in the batch package.

## What was built (`uri_v1/execution/harness/`)

| File | Summary |
|---|---|
| `contracts.py` | `HarnessType`; restrictive `PermissionProfile` with per-run `ElevationGrant` (trusted, explicit, named, non-negated, run-scoped); `CapabilityGrant` (default none; trusted, named items only); `Limits`; hashed `ExecutionCapsule`; claims-only `HarnessRunResult` with `UNAVAILABLE` for unreported usage. |
| `discovery.py` | Read-only inventory for Claude Code (plugins, hooks, MCP servers user/project, skills, agents) and Codex (MCP servers, skills, prompts). Redacted by construction: name, kind, scope, transport, command basename or URL host. Credential files are only tested for existence. |
| `process.py` | Process-group supervision: total timeout, output-inactivity watchdog, cancel, verified settlement, hashed log; nesting-guard and URI-secret env vars stripped. |
| `adapters.py` | Claude Code adapter (`-p`, `stream-json`, `--setting-sources ""`, `dontAsk` + allowlist, no web tools, Python-only shell, `--strict-mcp-config` with a per-run 0600 `mcp.json`, granted plugins via `--plugin-dir`, granted skills wrapped in a per-run plugin, `--max-budget-usd`). Codex adapter (`exec --json --sandbox workspace-write`, `approval_policy="never"`, network off). A forbidden-flag check runs on every invocation. |
| `capsule.py` | Capsule and instructions bundle from an Edge escalation, outside `files/`, hashed; names and structure only. |
| `runner.py` | Probe → copy-in → capsule → supervised run → claims → originals check → URI diff → Memory claim → URI verifier → lineage. |

## Acceptance criteria disposition (plan §0)

| ID | Result | Evidence |
|---|---|---|
| AC-H1 | Met | `adapters.py` (describe/probe/invocation/parse), `process.py` (cancel with verified settlement), `runner.py`. |
| AC-H2 | Met | `test_capsule_carries_hashes_not_contents`; tampered instructions refused. |
| AC-H3 | Met | `test_restrictive_default_argv_and_no_bypass_flags`, `test_elevation_requires_explicit_trusted_named_grant`; gate `bypass_flags_emitted` = 0. |
| AC-H4 | Met | `test_discovery_is_complete_and_redacted` (seeded `sk-live` secrets in env, args, headers, URL query, TOML and credential files; none appear). |
| AC-H5 | Met | `test_controlled_use_injects_only_granted_capabilities_per_run` (empty `mcp.json` by default, only the granted server, skill copied into a per-run plugin under `bundle/`, no global change, forged grant refused, Codex refuses injection). |
| AC-H6 | Met | Fake-harness gate: false claim → `FAILED`; unrequested change → `FAILED`; reported error with a real fix → `VERIFIED`. |
| AC-H7 | Met | `write_original` → flag and `CLAIMED_ONLY` (M36 refuses to verify against a changed source); symlink escape → `FAILED`. |
| AC-H8 | Met | Silent hang, chatty overrun and a spawned grandchild are all killed; outcome `outcome_unknown`; gate `unkilled_processes` = 0. |
| AC-H9 | Met | `test_session_ids_and_transcripts_never_enter_memory`; gate `session_ids_in_memory` = 0. |
| AC-H10 | Met | Usage parsed only from harness output; `UNAVAILABLE` otherwise (Codex cost). |
| AC-H11 | Met, with limits | Below. |

## Validation (Linux container, Python 3.11.15)

- M38 tests: `tests/test_m38_harness.py` **18 passed**; `tests/test_m38_harness_qualification.py` **6 passed**.
- Offline gate: `python scripts/m38_harness_qualification.py` → **PASSED**, 10 scenarios × 2 runs, all eight thresholds met. Results: `docs/plans/M38_QUALIFICATION_RESULTS.json`.
- Live pilot with the real Claude Code CLI 2.1.283: `python scripts/m38_live_pilot.py 2` → `docs/plans/M38_LIVE_PILOT_RESULTS.json`. Codex: `UNAVAILABLE` (not installed).

### Live pilot (indicative only; n = 2 per arm; not a VG-1 qualification)

Task: make `report.py` work with `sales.xlsx`; the script's `"Amt"` column has no unique local remap, so the Edge escalates. Both arms judged by the same URI verifier.

| Arm | Verified | Input-side tokens (input + cache read + cache write) | Output tokens | Reported cost (USD) | Turns / tool calls | Wall time | Files the harness saw |
|---|---|---|---|---|---|---|---|
| A direct | 2/2 | 85,808 · 85,834 | 1,426 · 1,326 | 0.222 · 0.090 | 5/4 · 5/4 | 19.7 s · 17.4 s | 6 (incl. a decoy `sales_2024.xlsx` with an `Amt` column) |
| B URI-mediated | 2/2 | 43,657 · 42,750 | 1,239 · 1,228 | 0.093 · 0.069 | 5/4 · 5/4 | 17.5 s · 17.7 s | 2 |

Observations, not conclusions: equal verified success; Arm B used about half the input-side tokens and about half the mean reported cost; turns and tool calls were identical; the cost gap is partly prompt-cache timing (cache writes differ run to run). Claude Code's own system prompt dominates token usage, so the absolute saving on a small task is modest. A VG-1 qualification needs a predeclared benchmark with more tasks, repeated runs, Codex, and frozen thresholds.

## Known issues and limitations (disclosed)

1. **Claude Code has no OS sandbox here.** "No network" is enforced at the tool layer only (no web tools; shell limited to `python`), so a Python process the harness runs could still open sockets. OD-4 is therefore met for Codex's sandbox and only partly for Claude Code.
2. **Codex adapter never executed.** Flags come from documentation; it stays UNQUALIFIED until a live run on the user's machine.
3. **Windows untested.** Process groups use `CREATE_NEW_PROCESS_GROUP` + `taskkill /T` on Windows; only the Linux path is exercised. The grandchild-kill test reads `/proc` and is Linux-only.
4. **Fake-harness gate proves plumbing, not competence.** It shows URI catches false claims and unsafe behavior; the live pilot is the only evidence of a real harness completing the task.
5. **Same-author gate and scenarios**, written by the implementer.
6. Session resume is stored, not implemented. Hooks and agents are discovered but cannot be granted in the minimum.
7. `mcp.json` for a granted MCP server copies that server's configuration (which may include its env values) into the run's private bundle for the duration of the run, then deletes it. URI records never contain it.

## Not done (out of scope)

Office demonstrator, automatic escalation routing, write-back in any flow, session resume, `DIRECT_ORIGINAL`, worktrees, production wiring, freeze.
