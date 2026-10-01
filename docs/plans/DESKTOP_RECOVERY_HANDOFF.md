# Desktop recovery + Edge-first: handoff to Codex (implementer)

Date: 2026-10-02. From: Claude (desktop-recovery thread). To: Codex CLI, the
implementer for the next batches in this worktree. Claude stops implementing
here after this note.

## Where things are

- Worktree: `C:\Users\cheta\Development\uri-m37-m39-integration`
- Branch: `experimental/desktop-recovery-repair` (also pushed to
  `https://github.com/sche004-cyber/Uri.git`, same branch name). Not merged
  anywhere.
- Accepted baseline kept intact: `985dc54` (M37 re-frozen 3fefb91 + M39 R0
  c716f80 lines are ancestors; dynamic planning e4dea8c is NOT on this branch).
- **Accepted candidate: `a9d562c`** - independent Codex audit (gpt-6-sol,
  read-only, fresh session) `VERDICT: ACCEPT`. Codex could not run pytest in
  its read-only sandbox; test results below are Claude's runs.
- Antigravity's uncommitted state at handover was preserved as
  `refs/backup/antigravity-wip-20261001` (and committed in 33527b9).
- Runtime files that are NOT committed and must stay that way:
  `uri_workspace/uri_server.pid`, `uri_workspace/uri_ui.pid`, logs, user dirs.
  Per-checkout secrets live outside the repo in
  `%LOCALAPPDATA%\URI\desktop_secrets_<hash>.json`.

## Audit trail (this branch)

| Candidate | Codex verdict | What followed |
|---|---|---|
| 3c8087b (Antigravity) | REJECT (`DESKTOP_RECOVERY_REAUDIT_VERDICT.md`) | /ask interception removed etc. |
| 7af87df | REPAIR_REQUIRED (2 HIGH, 2 MED, 1 LOW: stale-PID kill, fixed secret, mutex, PID ownership, wording) | 9f8cb3d |
| 9f8cb3d | REPAIR_REQUIRED (substring ownership, UI-start success on failure, secret regeneration/race, repo_root claim) | a52f5ad |
| dc5b337 | REPAIR_REQUIRED (unpinned Edge model, call undercount, uncapped conversational drafts, override label) | 030dec5 |
| 030dec5 | REPAIR_REQUIRED (zero-call label for unrecorded adapters, stream clock) | a9d562c |
| **a9d562c** | **ACCEPT** (2 LOW disclosed: failed-request caption shows the selected model; stream->ask fallback restarts the turn clock) | - |

## What is done (a9d562c)

1. Launcher lifecycle (`Launch URI.bat` -> `launch_desktop.ps1`,
   `Stop URI.bat` -> `stop_desktop.ps1`, `run_desktop_server.py`): named-mutex
   single instance (concurrent launches wait, then re-check), ownership by
   exact process command line, socket-owner PID file, attach only to this
   checkout's backend, PowerShell 5.1-safe ASCII. Desktop shortcut
   `C:\Users\cheta\OneDrive\Desktop\URI.lnk` -> `Launch URI.bat`.
2. Canonical `/ask` only: no middleware interception. `GET /desktop/status`
   (inventory, labels uri_v1 as *_NOT_WIRED) and a pass-through timing
   middleware (`uri_workspace/logs/desktop_request_timing.jsonl`).
3. Edge-first (User product decision 2026-10-01): purely social turns go to
   `qwen3:0.6b` via `uri_desktop_seams/harness_first` (outside frozen
   uri_core), hooked into `/ask` after approval resumption and lifecycle
   handling; S6 decides; only pinned qualified models; capability questions,
   work, references, negation, approvals, URLs, attachments escalate.
   Qualification: `experiments/desktop_edge_qual/` (pre-registered; r1 FAIL,
   repaired, r2 PASS; self-authored corpus - not an independent holdout).
4. Whole-turn telemetry: `serving_*` sum every model call this turn;
   `serving_calls`, `serving_call_count` (None = unknown), `turn_duration_seconds`,
   `harness_route`. Flutter caption: executing model, call count, model time,
   Send-to-reply time.
5. `response_validation`: pure conversation turns skip the capability-gap
   length cap (bounded at 1,000 chars) - chat no longer shows the rationale.
6. Frozen-scope allowlist (User authorization 2026-10-01 18:21/18:24 UTC):
   exactly six uri_core/uri_ui files, blob-pinned in
   `desktop_recovery_allowlist.py`; record and justification in
   `DESKTOP_RECOVERY_ALLOWLIST.md`. **Any further edit to those files needs a
   re-pin chain and, beyond this scope, new User authorization.**
7. M39 folder discovery recorded as a deferred INT task
   (`DESKTOP_FOLDER_DISCOVERY_INTEGRATION_TASK.md`).

## Evidence (Claude's runs, Windows 11)

- Guard + clone suites + seam/validation tests: 182 passed (a9d562c).
- `tests/` full: 1555 passed before the allowlist commit; the 6 clone-based
  failures then were the uncommitted-state artefact and pass after commit.
- Root affected tests: 193 passed, 2 failed (`test_server_ask_narrative`:
  pre-existing, also failing at 3c8087b).
- Flutter: 205/205; Windows release build of `uri_ui.exe` rebuilt.
- Live app (restarted via the shortcut path): social turns 0.04-0.15 s on
  qwen3:0.6b, 0 Main Brain calls; work/negation/approval/capability turns
  escalate with 2 qwen3.5:9b calls (about 10-40 s depending on GPU load).
  Attached workbook read through `read_attached_file` with a grounded
  summary. Records: `experiments/desktop_edge_qual/live_battery_*.json`.
- Not done by Claude: hands-on GUI interaction (no desktop automation in its
  session); the M39 live Claude Code smoke test (needs Chetan's terminal).

## Open items (for Codex / the User)

- Main Brain turns still make 2 sequential 9B calls over ~4-5k-token prompts
  (10-40 s). Not reduced in this batch.
- "what is 17 times 23?" makes 4 9B calls and ends "no capability".
- Office drafting: no invented costs/approvals in the regression, but
  justification sentences can still be invented ("aging units").
- qwen3:0.6b is qualified only for social replies; not for selection,
  extraction or labelling (harness-first track evidence: 0.30-0.50 precision).
- After a 9B call the 0.6B model can be evicted; next social turn ~2.8 s.
- Concurrent turns of the same user can be counted together in telemetry.
- Later batches named in the Codex brief (tool, memory, office wiring, file
  discovery) were not started here.
